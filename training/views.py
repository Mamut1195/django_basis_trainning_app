import hashlib
import json
import uuid
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from basis.bootstrap.accounts import identity, recover_password
from basis.bootstrap.athletes import save_observation, save_preferences, save_profile, save_rm
from basis.bootstrap.billing import webhooks
from basis.bootstrap.planning import (
    reschedule,
    save_cycle,
    save_goal,
    save_manual_plan,
    save_scheduled,
)
from basis.bootstrap.progress import save_stage, save_trip
from basis.bootstrap.training import edit_revision
from basis.modules.accounts.public import (
    AccountUnavailable,
    ConsumeAttempt,
    InvalidVerification,
    RegisterAccount,
    VerifyAccount,
)
from basis.modules.billing.adapters.web import InvalidWebhook, decode_event, encode_result
from basis.modules.training.adapters.wire import encode_session
from basis.modules.training.public import ExecutionConflict
from daily_trainning_app.models import User as Athlete
from daily_trainning_app.models import UserExerciseRM, WorkoutData

from . import billing as polar
from .access import can_write
from .forms import (
    AthleteForm,
    BlockForm,
    CycleForm,
    GoalForm,
    IntervalForm,
    MeasurementForm,
    MetricsForm,
    PlanForm,
    PlannedSessionForm,
    PreferencesForm,
    ProposalReviewForm,
    RMForm,
    SessionForm,
    SignupForm,
    SportProfileForm,
    StrengthSetForm,
    TrekStageForm,
    TrekTripForm,
    WellnessForm,
)
from .models import (
    AIJob,
    AthleteSettings,
    BillingAccount,
    Block,
    Cycle,
    Goal,
    Interval,
    Measurement,
    PlannedSession,
    PlanProposal,
    Session,
    SportProfile,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
    UsagePeriod,
    Wellness,
)
from .services import (
    Conflict,
    progress_report,
    revise_plan,
    session_snapshot,
    start_session,
    sync_session,
    trip_summary,
)


def write_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_write(request.user):
            return render(
                request,
                "training/notice.html",
                {
                    "title": "Tu historial sigue disponible",
                    "text": "Verifica tu correo y activa la prueba o suscripción para registrar entrenamiento.",
                    "billing_link": True,
                },
                status=403,
            )
        return view(request, *args, **kwargs)

    return wrapped


def rate_allowed(request, action, maximum=10, minutes=15):
    return identity().allow_attempt(
        ConsumeAttempt(action, request.META.get("REMOTE_ADDR", "unknown"), maximum, minutes)
    )


class BasisLoginView(LoginView):
    template_name = "registration/login.html"

    def post(self, request, *args, **kwargs):
        if not rate_allowed(request, "login"):
            return render(
                request,
                "training/notice.html",
                {
                    "title": "Inténtalo más tarde",
                    "text": "Se alcanzó el límite de intentos de acceso.",
                },
                status=429,
            )
        return super().post(request, *args, **kwargs)


class BasisPasswordResetView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.html"

    def form_valid(self, form):
        recover_password(form, self.request)
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        if not rate_allowed(request, "password-reset", maximum=5):
            return HttpResponse("Inténtalo más tarde.", status=429)
        return super().post(request, *args, **kwargs)


def signup(request):
    if request.method == "POST" and not rate_allowed(request, "signup", maximum=5):
        return HttpResponse("Inténtalo más tarde.", status=429)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save(commit=False)
        identity().register(
            RegisterAccount(
                email=form.cleaned_data["email"],
                name=form.cleaned_data["name"],
                encoded_password=account.password,
            )
        )
        return render(
            request,
            "training/notice.html",
            {
                "title": "Revisa tu correo",
                "text": "Te enviamos un enlace para verificar tu cuenta. Caduca en 24 horas.",
            },
        )
    return render(
        request,
        "training/form.html",
        {
            "title": "Empieza con BASIS",
            "subtitle": "Tu entrenamiento, tus datos y una dirección clara.",
            "form": form,
            "submit": "Crear cuenta",
        },
    )


def verify_email(request, token):
    try:
        identity().verify(VerifyAccount(token, confirm=request.method == "POST"))
        if request.method == "POST":
            messages.success(request, "Correo verificado. Ya puedes iniciar sesión.")
            return redirect("login")
        return render(
            request,
            "training/confirm.html",
            {
                "title": "Verifica tu correo",
                "text": "Confirma que quieres activar tu cuenta de BASIS.",
                "submit": "Verificar correo",
            },
        )
    except AccountUnavailable as error:
        raise Http404 from error
    except InvalidVerification:
        return render(
            request,
            "training/notice.html",
            {
                "title": "Enlace caducado o inválido",
                "text": "Solicita un nuevo correo de verificación.",
            },
            status=400,
        )


def resend_verification(request):
    from django import forms

    class EmailForm(forms.Form):
        email = forms.EmailField(label="Correo electrónico")

    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not rate_allowed(request, "resend-verification", maximum=5):
            return HttpResponse("Inténtalo más tarde.", status=429)
        identity().resend(form.cleaned_data["email"])
        return render(
            request,
            "training/notice.html",
            {
                "title": "Revisa tu correo",
                "text": "Si existe una cuenta pendiente, recibirás un enlace de verificación.",
            },
        )
    return render(request, "training/form.html", {"title": "Verificar mi correo", "form": form})


@login_required
def today(request):
    day = timezone.localdate()
    return render(
        request,
        "training/today.html",
        {
            "today": day,
            "scheduled": PlannedSession.objects.filter(
                owner=request.user, date=day, plan__next_version__isnull=True
            ).select_related("plan"),
            "recent": Session.objects.filter(owner=request.user)[:5],
            "wellness": Wellness.objects.filter(owner=request.user, date=day).first(),
            "goals": Goal.objects.filter(owner=request.user)[:3],
        },
    )


@login_required
def plan_list(request):
    return render(
        request,
        "training/plans.html",
        {
            "plans": TrainingPlan.objects.filter(owner=request.user, next_version__isnull=True)
            .select_related("goal")
            .order_by("-created_at"),
            "goals": Goal.objects.filter(owner=request.user),
        },
    )


@write_required
def plan_new(request):
    form = PlanForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        return redirect("plan-detail", pk=save_manual_plan(request.user.pk, form.save(commit=False)))
    return render(request, "training/form.html", {"title": "Nuevo plan", "form": form})


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=request.user)
    return render(
        request,
        "training/plan_detail.html",
        {
            "plan": plan,
            "cycles": plan.cycles.order_by("start_date", "kind"),
            "scheduled": plan.sessions.order_by("date"),
            "editable": not TrainingPlan.objects.filter(previous=plan).exists(),
        },
    )


@write_required
@require_POST
def plan_revise(request, pk):
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=request.user)
    new = revise_plan(request.user, plan)
    return redirect("plan-detail", pk=new.pk)


@write_required
def cycle_new(request, pk):
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=request.user, next_version__isnull=True)
    form = CycleForm(request.POST or None, plan=plan)
    if request.method == "POST" and form.is_valid():
        save_cycle(request.user.pk, form.save(commit=False))
        return redirect("plan-detail", pk=pk)
    return render(
        request,
        "training/form.html",
        {"title": "Añadir ciclo", "subtitle": "Macrociclo → mesociclo → microciclo", "form": form},
    )


@write_required
def scheduled_new(request):
    form = PlannedSessionForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        return redirect("scheduled-detail", pk=save_scheduled(request.user.pk, form.save(commit=False)))
    return render(request, "training/form.html", {"title": "Programar sesión", "form": form})


@login_required
def scheduled_detail(request, pk):
    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=request.user)
    return render(
        request,
        "training/scheduled.html",
        {
            "scheduled": scheduled,
            "blocks": scheduled.blocks.prefetch_related("sets__exercise", "intervals"),
        },
    )


@write_required
@require_POST
def scheduled_start(request, pk):
    planned = get_object_or_404(PlannedSession, pk=pk, owner=request.user)
    if not planned.blocks.exists():
        messages.error(request, "Añade al menos un bloque antes de comenzar.")
        return redirect("scheduled-detail", pk=pk)
    return redirect("session-detail", pk=start_session(request.user, planned).pk)


@write_required
def scheduled_reschedule(request, pk):
    from django import forms

    class RescheduleForm(forms.Form):
        date = forms.DateField(
            label="Nueva fecha", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
        )
        revision = forms.IntegerField(widget=forms.HiddenInput)

    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=request.user)
    form = RescheduleForm(
        request.POST or None, initial={"date": scheduled.date, "revision": scheduled.revision}
    )
    if request.method == "POST" and form.is_valid():
        try:
            reschedule(request.user.pk, scheduled.pk, form.cleaned_data["date"], form.cleaned_data["revision"])
            return redirect("scheduled-detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "training/form.html", {"title": "Reprogramar sesión", "form": form})


@write_required
def session_new(request):
    form = SessionForm(request.POST or None)
    block_form = BlockForm(request.POST or None, prefix="block")
    if request.method == "POST" and form.is_valid() and block_form.is_valid():
        with transaction.atomic():
            session = form.save(commit=False)
            session.owner = request.user
            session.save()
            Block.objects.create(session=session, **block_form.cleaned_data)
        return redirect("session-detail", pk=session.pk)
    return render(
        request,
        "training/form.html",
        {
            "title": "Registrar entrenamiento",
            "subtitle": "Puedes dejar los datos que no conozcas sin registrar.",
            "form": form,
            "extra_forms": [block_form],
        },
    )


@login_required
def session_detail(request, pk):
    session = get_object_or_404(
        Session.objects.prefetch_related("blocks__sets__exercise", "blocks__intervals"),
        pk=pk,
        owner=request.user,
    )
    return render(
        request,
        "training/session.html",
        {"session": session, "snapshot": session_snapshot(session), "blocks": session.blocks.all()},
    )


@write_required
def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk, owner=request.user, status="in_progress")
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        snapshot = session_snapshot(session)
        snapshot.update(
            {k: str(v) if v is not None else None for k, v in form.cleaned_data.items()}
        )
        snapshot["duration_seconds"] = form.cleaned_data["duration_seconds"]
        snapshot["revision"] = int(request.POST.get("revision", 0))
        try:
            sync_session(request.user, uuid.uuid4(), snapshot)
            return redirect("session-detail", pk=pk)
        except Conflict:
            form.add_error(None, "La sesión cambió. Recarga para revisar la versión actual.")
    return render(
        request,
        "training/form.html",
        {"title": "Editar sesión", "form": form, "revision": session.revision},
    )


def get_parent(request, kind, pk):
    from django.http import Http404

    if kind not in ("session", "planned"):
        raise Http404
    model = Session if kind == "session" else PlannedSession
    try:
        parent = get_object_or_404(model, pk=pk, owner=request.user)
    except (ValueError, ValidationError):
        raise Http404 from None
    if isinstance(parent, Session) and parent.status == "completed":
        raise ValidationError("Esta ejecución está completada y se conserva como historial.")
    if isinstance(parent, PlannedSession) and (
        parent.executions.exists() or TrainingPlan.objects.filter(previous=parent.plan).exists()
    ):
        raise ValidationError("Crea otra versión del plan para cambiar la prescripción.")
    return parent


def block_redirect(block):
    return redirect(
        "session-detail" if block.session_id else "scheduled-detail",
        pk=block.session_id or block.planned_id,
    )


def touch_parent(parent, expected):
    model = type(parent)
    current = model.objects.select_for_update().get(pk=parent.pk)
    try:
        expected = int(expected)
    except (TypeError, ValueError):
        raise ValidationError("Recarga la página antes de guardar.") from None
    if isinstance(current, Session):
        try:
            current.revision = edit_revision(current, expected)
        except ExecutionConflict as exc:
            if exc.current.revision == expected:
                raise ValidationError("La sesión ya se completó.") from None
            raise Conflict(encode_session(exc.current)) from None
    else:
        if current.revision != expected:
            raise Conflict(None)
        current.revision += 1
    current.save()


@write_required
def set_edit(request, pk):
    row = get_object_or_404(
        StrengthSet.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=request.user) | Q(block__planned__owner=request.user),
        pk=pk,
    )
    block = row.block
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, instance=row, block=block)
    if block.session_id and block.session.planned_id:
        for key, field in form.fields.items():
            if key.startswith("target_") or key in ("exercise", "rest_seconds", "rm_reference"):
                field.disabled = True
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            form.save()
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {"title": "Registrar resultado de serie", "form": form, "revision": parent.revision},
    )


@write_required
def interval_edit(request, pk):
    row = get_object_or_404(
        Interval.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=request.user) | Q(block__planned__owner=request.user),
        pk=pk,
    )
    block = row.block
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = IntervalForm(request.POST or None, instance=row, block=block)
    attr = "actual" if block.session_id else "target"
    metrics = MetricsForm(
        request.POST or None, sport=block.sport, initial=getattr(row, attr), prefix="metrics"
    )
    if block.session_id and block.session.planned_id:
        for key in ("repetitions", "rest_seconds", "target_rpe"):
            form.fields[key].disabled = True
    if request.method == "POST" and form.is_valid() and metrics.is_valid():
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            row = form.save(commit=False)
            setattr(row, attr, metrics.cleaned_data)
            row.save()
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {
            "title": "Registrar intervalo",
            "form": form,
            "extra_forms": [metrics],
            "revision": parent.revision,
        },
    )


@write_required
def block_new(request, kind, pk):
    parent = get_parent(request, kind, pk)
    form = BlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            relation = {"session": parent} if kind == "session" else {"planned": parent}
            block = Block.objects.create(
                **relation, order=parent.blocks.count() + 1, **form.cleaned_data
            )
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {"title": "Añadir bloque", "form": form, "revision": parent.revision},
    )


def owned_block(request, pk):
    return get_object_or_404(
        Block.objects.select_related("session", "planned__plan"),
        Q(session__owner=request.user) | Q(planned__owner=request.user),
        pk=pk,
    )


@write_required
def block_metrics(request, pk):
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    attr = "actual" if block.session_id else "target"
    form = MetricsForm(request.POST or None, sport=block.sport, initial=getattr(block, attr))
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            setattr(block, attr, form.cleaned_data)
            block.save()
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {
            "title": block.title,
            "subtitle": "Resultado real" if block.session_id else "Prescripción",
            "revision": parent.revision,
            "form": form,
        },
    )


@write_required
def set_new(request, pk):
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, block=block)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            row = form.save(commit=False)
            row.order = block.sets.count() + 1
            row.save()
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {"title": "Añadir serie", "form": form, "revision": parent.revision},
    )


@write_required
def interval_new(request, pk):
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = IntervalForm(request.POST or None, block=block)
    target = MetricsForm(request.POST or None, sport=block.sport, prefix="target")
    actual = (
        MetricsForm(request.POST or None, sport=block.sport, prefix="actual")
        if block.session_id
        else None
    )
    if (
        request.method == "POST"
        and form.is_valid()
        and target.is_valid()
        and (not actual or actual.is_valid())
    ):
        with transaction.atomic():
            touch_parent(parent, request.POST.get("revision"))
            row = form.save(commit=False)
            row.order = block.intervals.count() + 1
            row.target = target.cleaned_data
            row.actual = actual.cleaned_data if actual else {}
            row.save()
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {
            "title": "Añadir intervalo",
            "revision": parent.revision,
            "form": form,
            "extra_forms": [target, actual] if actual else [target],
        },
    )


@login_required
def progress(request):
    return render(
        request,
        "training/progress.html",
        {
            "report": progress_report(request.user),
            "legacy_records": WorkoutData.objects.filter(user__account=request.user)
            .select_related("exercise")
            .order_by("-fecha")[:50],
            "wellness_records": Wellness.objects.filter(owner=request.user).order_by("-date")[:14],
            "measurements": Measurement.objects.filter(owner=request.user).order_by("-date")[:14],
            "trips": TrekTrip.objects.filter(owner=request.user),
        },
    )


@login_required
def profile(request):
    preferences, _ = AthleteSettings.objects.get_or_create(owner=request.user)
    return render(
        request,
        "training/profile.html",
        {
            "preferences": preferences,
            "sports": SportProfile.objects.filter(owner=request.user),
            "goals": Goal.objects.filter(owner=request.user),
        },
    )


@write_required
def profile_edit(request):
    form = AthleteForm(request.POST or None, instance=request.user.athlete)
    if request.method == "POST" and form.is_valid():
        save_profile(request.user.pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "training/form.html", {"title": "Tu perfil", "form": form})


@write_required
def preferences_edit(request):
    preferences, _ = AthleteSettings.objects.get_or_create(owner=request.user)
    form = PreferencesForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        save_preferences(request.user.pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "training/form.html", {"title": "Disponibilidad y equipo", "form": form})


@write_required
def owned_new(request, resource):
    mapping = {
        "goal": (Goal, GoalForm, "Nuevo objetivo"),
        "sport": (SportProfile, SportProfileForm, "Experiencia y umbral"),
        "wellness": (Wellness, WellnessForm, "Cómo te sientes"),
        "measurement": (Measurement, MeasurementForm, "Registrar peso"),
        "trip": (TrekTrip, TrekTripForm, "Nuevo trekking"),
    }
    if resource not in mapping:
        return HttpResponse(status=404)
    model, cls, title = mapping[resource]
    instance = model(owner=request.user)
    if resource == "wellness":
        instance = (
            Wellness.objects.filter(owner=request.user, date=timezone.localdate()).first()
            or instance
        )
    form = cls(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        if resource in ("sport", "wellness", "measurement"):
            instance = form.save(commit=False)
            save_observation(request.user.pk, instance)
        elif resource == "goal":
            instance = form.save(commit=False)
            instance.pk = save_goal(request.user.pk, instance)
        else:
            instance = form.save(commit=False)
            instance.pk = save_trip(request.user.pk, instance)
        return (
            redirect("trip-detail", pk=instance.pk)
            if resource == "trip"
            else redirect("profile" if resource in ("goal", "sport") else "progress")
        )
    return render(request, "training/form.html", {"title": title, "form": form})


@login_required
def trip_detail(request, pk):
    trip = get_object_or_404(TrekTrip, pk=pk, owner=request.user)
    return render(
        request,
        "training/trip.html",
        {
            "trip": trip,
            "summary": trip_summary(trip),
            "stages": trip.stages.select_related("session"),
        },
    )


@write_required
def stage_new(request, pk):
    trip = get_object_or_404(TrekTrip, pk=pk, owner=request.user)
    form = TrekStageForm(request.POST or None, trip=trip)
    if request.method == "POST" and form.is_valid():
        save_stage(request.user.pk, form.save(commit=False))
        return redirect("trip-detail", pk=pk)
    return render(
        request, "training/form.html", {"title": "Añadir etapa de trekking", "form": form}
    )


@write_required
def rm_new(request):
    form = RMForm(request.POST or None, instance=UserExerciseRM(user=request.user.athlete))
    if request.method == "POST" and form.is_valid():
        save_rm(request.user.pk, form.save(commit=False))
        return redirect("profile")
    return render(
        request,
        "training/form.html",
        {
            "title": "Registrar 1RM medido",
            "subtitle": "Registra una medición real con su fecha. No es una estimación de la app.",
            "form": form,
        },
    )


@login_required
def billing_page(request):
    account, _ = BillingAccount.objects.get_or_create(owner=request.user)
    return render(
        request,
        "training/billing.html",
        {
            "billing": account,
            "usage": UsagePeriod.objects.filter(owner=request.user).order_by("-pk").first(),
            "payments_configured": bool(settings.POLAR_ACCESS_TOKEN and settings.POLAR_PRODUCT_ID),
        },
    )


@login_required
@require_POST
def billing_action(request, action):
    try:
        if action == "checkout":
            return redirect(polar.checkout(request.user))
        if action == "portal":
            return redirect(polar.portal(request.user))
        if action == "refresh":
            polar.reconcile(request.user)
        else:
            return HttpResponse(status=404)
    except (polar.ProviderUnavailable, ValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("billing")


@csrf_exempt
@require_POST
def polar_webhook(request):
    if not settings.POLAR_WEBHOOK_SECRET:
        return JsonResponse({"detail": "Webhook no configurado"}, status=503)
    try:
        event = decode_event(settings.POLAR_WEBHOOK_SECRET, request.body, request.headers)
    except InvalidWebhook:
        return JsonResponse({"detail": "Firma o evento inv\u00e1lido"}, status=400)
    result = webhooks(polar.polar_request).process(event)
    status, payload = encode_result(result)
    return JsonResponse(payload, status=status)



@login_required
def coach(request):
    return render(
        request,
        "training/coach.html",
        {
            "jobs": AIJob.objects.filter(owner=request.user).order_by("-created_at")[:20],
            "plans": TrainingPlan.objects.filter(owner=request.user, next_version__isnull=True),
            "ai_enabled": settings.AI_ENABLED and bool(settings.DEEPSEEK_API_KEY),
            "request_key": uuid.uuid4(),
        },
    )


@login_required
@require_POST
def coach_ask(request):
    from .ai import enqueue

    try:
        job = enqueue(
            request.user,
            request.POST.get("kind"),
            request.POST.get("prompt", ""),
            request.POST.get("request_key"),
            request.POST.get("base_plan") or None,
        )
        return redirect("job-detail", pk=job.pk)
    except (ValidationError, polar.ProviderUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect("coach")


@login_required
def job_detail(request, pk):
    job = get_object_or_404(AIJob, pk=pk, owner=request.user)
    template = (
        "training/job_fragment.html" if request.headers.get("HX-Request") else "training/job.html"
    )
    display_answer = job.answer if job.kind == "short" else ""
    if job.kind == "plan" and job.answer:
        try:
            content = json.loads(job.answer)
            display_answer = content.get("question", "") if isinstance(content, dict) else ""
        except ValueError:
            pass
    return render(
        request,
        template,
        {
            "job": job,
            "display_answer": display_answer,
            "proposal": PlanProposal.objects.filter(job=job, owner=request.user).first(),
        },
    )


@write_required
def proposal_review(request, pk):
    from .proposals import edit_and_accept_proposal, reject_proposal

    proposal = get_object_or_404(PlanProposal, pk=pk, owner=request.user)
    form = ProposalReviewForm(request.POST or None, content=proposal.content, owner=request.user)
    if request.method == "POST":
        if request.POST.get("decision") == "reject":
            reject_proposal(request.user, proposal.pk)
            return redirect("coach")
        if form.is_valid():
            try:
                plan = edit_and_accept_proposal(request.user, proposal.pk, form.to_content())
                return redirect("plan-detail", pk=plan.pk)
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, "training/proposal.html", {"proposal": proposal, "form": form})


@login_required
@require_GET
def snapshot_api(request, pk):
    session = get_object_or_404(
        Session.objects.prefetch_related("blocks__sets", "blocks__intervals"),
        pk=pk,
        owner=request.user,
    )
    return JsonResponse(
        {"account": str(request.user.athlete.public_id), "session": session_snapshot(session)}
    )


@login_required
@require_POST
def sync_api(request):
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict) or not isinstance(body.get("session"), dict):
            raise ValidationError("Formato inválido.")
        if body.get("account") != str(request.user.athlete.public_id):
            return JsonResponse({"detail": "La cola pertenece a otra cuenta."}, status=403)
        result = sync_session(request.user, body.get("mutation_id"), body["session"])
        return JsonResponse({"session": result})
    except Conflict as exc:
        return JsonResponse(
            {"detail": "Hay otra versión. Revisa ambas antes de resolver.", "current": exc.current},
            status=409,
        )
    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        return JsonResponse({"detail": getattr(exc, "messages", ["Datos inválidos"])}, status=400)
    except Exception as exc:
        from rest_framework.exceptions import PermissionDenied

        if isinstance(exc, PermissionDenied):
            return JsonResponse({"detail": str(exc.detail)}, status=403)
        raise


@login_required
def export_data(request):
    from django.core.serializers import serialize

    models = [
        AthleteSettings,
        AIJob,
        PlanProposal,
        Goal,
        TrainingPlan,
        Cycle,
        PlannedSession,
        Session,
        Block,
        StrengthSet,
        Interval,
        Wellness,
        Measurement,
        SportProfile,
        TrekTrip,
        TrekStage,
        WorkoutData,
        UserExerciseRM,
    ]
    result = {"schema": "basis-export-v1", "exported_at": timezone.now().isoformat()}
    result["athlete"] = json.loads(serialize("json", Athlete.objects.filter(account=request.user)))
    for model in models:
        if model in (WorkoutData, UserExerciseRM):
            queryset = model.objects.filter(user__account=request.user)
        elif model is Cycle:
            queryset = model.objects.filter(plan__owner=request.user)
        elif model is Block:
            queryset = model.objects.filter(
                Q(session__owner=request.user) | Q(planned__owner=request.user)
            )
        elif model in (StrengthSet, Interval):
            queryset = model.objects.filter(
                Q(block__session__owner=request.user) | Q(block__planned__owner=request.user)
            )
        elif model is TrekStage:
            queryset = model.objects.filter(trip__owner=request.user)
        else:
            queryset = model.objects.filter(owner=request.user)
        result[model._meta.model_name] = json.loads(serialize("json", queryset))
    response = JsonResponse(result)
    response["Content-Disposition"] = 'attachment; filename="basis-entrenamiento.json"'
    return response


def offline(request):
    from dataclasses import asdict

    from .domain import VARIABLES

    schema = {
        sport: {key: asdict(spec) for key, spec in metrics.items()}
        for sport, metrics in VARIABLES.items()
    }
    return render(request, "training/offline.html", {"offline_schema": schema})


@login_required
def csrf_api(request):
    return JsonResponse(
        {"account": str(request.user.athlete.public_id), "token": get_token(request)}
    )


def manifest(request):
    from .brand import IDENTITY

    return JsonResponse(
        {
            "id": "/",
            "name": "BASIS Training",
            "short_name": "BASIS",
            "lang": "es",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": IDENTITY["colors"]["background"],
            "theme_color": IDENTITY["colors"]["primary"],
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {
                    "src": "/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request):
    files = [
        *sorted((settings.BASE_DIR / "assets").rglob("*")),
        settings.BASE_DIR / "templates/base.html",
        settings.BASE_DIR / "templates/cotton/brand.html",
        settings.BASE_DIR / "templates/training/offline.html",
        settings.BASE_DIR / "templates/service-worker.js",
        settings.BASE_DIR / "requirements.txt",
    ]
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.read_bytes())
    response = render(
        request,
        "service-worker.js",
        {"shell_version": digest.hexdigest()[:16]},
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def health(request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
