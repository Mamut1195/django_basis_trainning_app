from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from basis.bootstrap import presentation
from basis.bootstrap.manual_training import manual_training
from basis.bootstrap.planning import (
    reschedule,
    save_cycle,
    save_goal,
    save_manual_plan,
    save_scheduled,
)
from basis.bootstrap.progress import save_stage, save_trip
from basis.bootstrap.web_framework import Conflict, owner, public_id, sync_session, write_required
from basis.shared.identifiers import AccountId, PlannedSessionId, SessionId

from ..domain.manual import EmptyPrescription, SessionParent
from . import manual_actions as mutations
from .actions import progress_report, revise_plan, session_snapshot, start_session, trip_summary
from .forms import (
    BlockForm,
    CycleForm,
    GoalForm,
    IntervalForm,
    MetricsForm,
    PlanForm,
    PlannedSessionForm,
    SessionForm,
    StrengthSetForm,
    TrekStageForm,
    TrekTripForm,
)
from .models import (
    Block,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekTrip,
)


@login_required
def today(request: HttpRequest) -> HttpResponse:
    day = timezone.localdate()
    return render(
        request,
        "training/today.html",
        {
            "today": day,
            "scheduled": PlannedSession.objects.filter(
                owner=owner(request), date=day, plan__next_version__isnull=True
            ).select_related("plan"),
            "recent": Session.objects.filter(owner=owner(request))[:5],
            "wellness": presentation.wellness_today(owner(request).pk, day),
            "goals": Goal.objects.filter(owner=owner(request))[:3],
        },
    )


@login_required
def plan_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "training/plans.html",
        {
            "plans": TrainingPlan.objects.filter(owner=owner(request), next_version__isnull=True)
            .select_related("goal")
            .order_by("-created_at"),
            "goals": Goal.objects.filter(owner=owner(request)),
        },
    )


@write_required
def plan_new(request: HttpRequest) -> HttpResponse:
    form = PlanForm(request.POST or None, owner=owner(request))
    if request.method == "POST" and form.is_valid():
        return redirect(
            "plan-detail", pk=save_manual_plan(owner(request).pk, form.save(commit=False))
        )
    return render(request, "training/form.html", {"title": "Nuevo plan", "form": form})


@login_required
def plan_detail(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
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
def plan_revise(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    new = revise_plan(owner(request), plan)
    return redirect("plan-detail", pk=new.pk)


@write_required
def cycle_new(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request), next_version__isnull=True)
    form = CycleForm(request.POST or None, plan=plan)
    if request.method == "POST" and form.is_valid():
        save_cycle(owner(request).pk, form.save(commit=False))
        return redirect("plan-detail", pk=pk)
    return render(
        request,
        "training/form.html",
        {"title": "Añadir ciclo", "subtitle": "Macrociclo → mesociclo → microciclo", "form": form},
    )


@write_required
def scheduled_new(request: HttpRequest) -> HttpResponse:
    form = PlannedSessionForm(request.POST or None, owner=owner(request))
    if request.method == "POST" and form.is_valid():
        return redirect(
            "scheduled-detail", pk=save_scheduled(owner(request).pk, form.save(commit=False))
        )
    return render(request, "training/form.html", {"title": "Programar sesión", "form": form})


@login_required
def scheduled_detail(request: HttpRequest, pk: int) -> HttpResponse:
    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
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
def scheduled_start(request: HttpRequest, pk: int) -> HttpResponse:
    planned = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
    try:
        manual_training().start_preflight(AccountId(owner(request).pk), PlannedSessionId(planned.pk))
    except EmptyPrescription:
        messages.error(request, "Añade al menos un bloque antes de comenzar.")
        return redirect("scheduled-detail", pk=pk)
    return redirect("session-detail", pk=start_session(owner(request), planned).pk)


@write_required
def scheduled_reschedule(request: HttpRequest, pk: int) -> HttpResponse:
    from django import forms

    class RescheduleForm(forms.Form):
        date = forms.DateField(
            label="Nueva fecha", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
        )
        revision = forms.IntegerField(widget=forms.HiddenInput)

    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
    form = RescheduleForm(
        request.POST or None, initial={"date": scheduled.date, "revision": scheduled.revision}
    )
    if request.method == "POST" and form.is_valid():
        try:
            reschedule(
                owner(request).pk,
                scheduled.pk,
                form.cleaned_data["date"],
                form.cleaned_data["revision"],
            )
            return redirect("scheduled-detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "training/form.html", {"title": "Reprogramar sesión", "form": form})


@write_required
def session_new(request: HttpRequest) -> HttpResponse:
    form = SessionForm(request.POST or None)
    block_form = BlockForm(request.POST or None, prefix="block")
    if request.method == "POST" and form.is_valid() and block_form.is_valid():
        session_id = mutations.create_session(
            owner(request).pk, form.save(commit=False),
            block_form.cleaned_data["sport"], block_form.cleaned_data["title"],
        )
        return redirect("session-detail", pk=session_id)
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
def session_detail(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    session = get_object_or_404(
        Session.objects.prefetch_related("blocks__sets__exercise", "blocks__intervals"),
        pk=pk,
        owner=owner(request),
    )
    return render(
        request,
        "training/session.html",
        {"session": session, "snapshot": session_snapshot(session), "blocks": session.blocks.all()},
    )


@write_required
def session_edit(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    mutations.inspect_metadata(owner(request).pk, SessionParent(SessionId(pk)))
    session = get_object_or_404(Session, pk=pk, owner=owner(request))
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        snapshot = session_snapshot(session)
        snapshot.update(
            {k: str(v) if v is not None else None for k, v in form.cleaned_data.items()}
        )
        snapshot["duration_seconds"] = form.cleaned_data["duration_seconds"]
        snapshot["revision"] = int(request.POST.get("revision", 0))
        try:
            sync_session(owner(request), uuid.uuid4(), snapshot)
            return redirect("session-detail", pk=pk)
        except Conflict:
            form.add_error(None, "La sesión cambió. Recarga para revisar la versión actual.")
    return render(
        request,
        "training/form.html",
        {"title": "Editar sesión", "form": form, "revision": session.revision},
    )


def get_parent(
    request: HttpRequest, kind: str, pk: int | str | uuid.UUID | None
) -> Session | PlannedSession:
    ref = mutations.parse_parent(kind, pk)
    mutations.inspect_parent(owner(request).pk, ref)
    if isinstance(ref, SessionParent):
        return get_object_or_404(Session, pk=ref.id, owner=owner(request))
    return get_object_or_404(PlannedSession, pk=ref.id, owner=owner(request))


def block_redirect(block: Block) -> HttpResponse:
    return redirect(
        "session-detail" if block.session_id else "scheduled-detail",
        pk=block.session_id or block.planned_id,
    )


@write_required
def set_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        StrengthSet.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=owner(request)) | Q(block__planned__owner=owner(request)),
        pk=pk,
    )
    block = row.block
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, instance=row, block=block)
    for key in mutations.edit_form_policy(owner(request).pk, parent).strength_read_only:
        if key in form.fields:
            form.fields[key].disabled = True
    if request.method == "POST" and form.is_valid():
        mutations.save_strength(owner(request).pk, form.save(commit=False),
                                request.POST.get("revision"), creating=False)
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {"title": "Registrar resultado de serie", "form": form, "revision": parent.revision},
    )


@write_required
def interval_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        Interval.objects.select_related("block__session", "block__planned__plan"),
        Q(block__session__owner=owner(request)) | Q(block__planned__owner=owner(request)),
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
    for key in mutations.edit_form_policy(owner(request).pk, parent).interval_read_only:
        form.fields[key].disabled = True
    if request.method == "POST" and form.is_valid() and metrics.is_valid():
        row = form.save(commit=False)
        setattr(row, attr, metrics.cleaned_data)
        mutations.save_interval(owner(request).pk, row, request.POST.get("revision"), creating=False)
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
def block_new(request: HttpRequest, kind: str, pk: int | str | uuid.UUID | None) -> HttpResponse:
    parent = get_parent(request, kind, pk)
    form = BlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        block_id = mutations.add_block(owner(request).pk, parent, request.POST.get("revision"),
                                       form.cleaned_data["sport"], form.cleaned_data["title"])
        return block_redirect(get_object_or_404(Block, pk=block_id))
    return render(
        request,
        "training/form.html",
        {"title": "Añadir bloque", "form": form, "revision": parent.revision},
    )


def owned_block(request: HttpRequest, pk: int) -> Block:
    return get_object_or_404(
        Block.objects.select_related("session", "planned__plan"),
        Q(session__owner=owner(request)) | Q(planned__owner=owner(request)),
        pk=pk,
    )


@write_required
def block_metrics(request: HttpRequest, pk: int) -> HttpResponse:
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    attr = "actual" if block.session_id else "target"
    form = MetricsForm(request.POST or None, sport=block.sport, initial=getattr(block, attr))
    if request.method == "POST" and form.is_valid():
        mutations.save_metrics(owner(request).pk, block, request.POST.get("revision"), form.cleaned_data)
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
def set_new(request: HttpRequest, pk: int) -> HttpResponse:
    block = owned_block(request, pk)
    parent = get_parent(
        request, "session" if block.session_id else "planned", block.session_id or block.planned_id
    )
    form = StrengthSetForm(request.POST or None, block=block)
    if request.method == "POST" and form.is_valid():
        mutations.save_strength(owner(request).pk, form.save(commit=False),
                                request.POST.get("revision"), creating=True)
        return block_redirect(block)
    return render(
        request,
        "training/form.html",
        {"title": "Añadir serie", "form": form, "revision": parent.revision},
    )


@write_required
def interval_new(request: HttpRequest, pk: int) -> HttpResponse:
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
        row = form.save(commit=False)
        row.target = target.cleaned_data
        row.actual = actual.cleaned_data if actual else {}
        mutations.save_interval(owner(request).pk, row, request.POST.get("revision"), creating=True)
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
def progress(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "training/progress.html",
        {
            "report": progress_report(owner(request)),
            **presentation.progress_history(owner(request).pk),
            "trips": TrekTrip.objects.filter(owner=owner(request)),
        },
    )


@login_required
def trip_detail(request: HttpRequest, pk: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
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
def stage_new(request: HttpRequest, pk: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
    form = TrekStageForm(request.POST or None, trip=trip)
    if request.method == "POST" and form.is_valid():
        save_stage(owner(request).pk, form.save(commit=False))
        return redirect("trip-detail", pk=pk)
    return render(
        request, "training/form.html", {"title": "Añadir etapa de trekking", "form": form}
    )


@login_required
@require_GET
def snapshot_api(request: HttpRequest, pk: uuid.UUID) -> HttpResponse:
    session = get_object_or_404(
        Session.objects.prefetch_related("blocks__sets", "blocks__intervals"),
        pk=pk,
        owner=owner(request),
    )
    return JsonResponse({"account": str(public_id(request)), "session": session_snapshot(session)})


@write_required
def owned_new(request: HttpRequest, resource: str) -> HttpResponse:
    mapping = {
        "goal": (Goal, GoalForm, "Nuevo objetivo"),
        "trip": (TrekTrip, TrekTripForm, "Nuevo trekking"),
    }
    if resource not in mapping:
        return HttpResponse(status=404)
    model, cls, title = mapping[resource]
    instance = model(owner=owner(request))
    form = cls(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        instance = form.save(commit=False)
        if resource == "goal":
            instance.pk = save_goal(owner(request).pk, instance)
        else:
            instance.pk = save_trip(owner(request).pk, instance)
        return (
            redirect("trip-detail", pk=instance.pk)
            if resource == "trip"
            else redirect("profile" if resource in ("goal", "sport") else "progress")
        )
    return render(request, "training/form.html", {"title": title, "form": form})
