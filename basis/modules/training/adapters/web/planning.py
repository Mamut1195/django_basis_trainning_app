"""HTTP presentation for training planning."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner, write_required
from basis.bootstrap.manual_training import manual_training
from basis.modules.training.adapters.planning_actions import (
    reschedule,
    save_cycle,
    save_goal,
    save_manual_plan,
    save_scheduled,
)
from basis.shared.identifiers import AccountId, PlannedSessionId

from ...domain.manual import EmptyPrescription
from ..actions import revise_plan, start_session
from ..models import (
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)
from .forms import (
    CycleForm,
    GoalForm,
    PlanForm,
    PlannedSessionForm,
    RescheduleForm,
)


@login_required
def today(request: HttpRequest) -> HttpResponse:
    day = timezone.localdate()
    return render(
        request,
        "training/execution/today.html",
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
        "training/planning/index.html",
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
    return render(request, "shared/form.html", {"title": "Nuevo plan", "form": form})


@login_required
def plan_detail(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    return render(
        request,
        "training/planning/detail.html",
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
        "shared/form.html",
        {"title": "Añadir ciclo", "subtitle": "Macrociclo → mesociclo → microciclo", "form": form},
    )


@write_required
def scheduled_new(request: HttpRequest) -> HttpResponse:
    form = PlannedSessionForm(request.POST or None, owner=owner(request))
    if request.method == "POST" and form.is_valid():
        return redirect(
            "scheduled-detail", pk=save_scheduled(owner(request).pk, form.save(commit=False))
        )
    return render(request, "shared/form.html", {"title": "Programar sesión", "form": form})


@login_required
def scheduled_detail(request: HttpRequest, pk: int) -> HttpResponse:
    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
    return render(
        request,
        "training/planning/scheduled.html",
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
        manual_training().start_preflight(
            AccountId(owner(request).pk), PlannedSessionId(planned.pk)
        )
    except EmptyPrescription:
        messages.error(request, "Añade al menos un bloque antes de comenzar.")
        return redirect("scheduled-detail", pk=pk)
    return redirect("session-detail", pk=start_session(owner(request), planned).pk)


@write_required
def scheduled_reschedule(request: HttpRequest, pk: int) -> HttpResponse:
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
    return render(request, "shared/form.html", {"title": "Reprogramar sesión", "form": form})


@write_required
def goal_new(request: HttpRequest) -> HttpResponse:
    form = GoalForm(request.POST or None, instance=Goal(owner=owner(request)))
    if request.method == "POST" and form.is_valid():
        save_goal(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "shared/form.html", {"title": "Nuevo objetivo", "form": form})
