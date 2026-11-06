"""HTTP presentation for training planning."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner, write_required
from basis.bootstrap.manual_training import manual_training
from basis.bootstrap.planning import planning
from basis.bootstrap.training_dates import owner_date
from basis.modules.training.adapters.calendar import calendar_status, effective_sessions
from basis.modules.training.adapters.locking import intent_executions
from basis.modules.training.adapters.planning import scheduled_definition
from basis.modules.training.adapters.planning_actions import (
    reschedule,
    save_cycle,
    save_goal,
    save_manual_plan,
    save_scheduled,
)
from basis.modules.training.public import (
    ChangeScheduledSession,
    InvalidPlanning,
    PlanningConflict,
    RestorePlan,
    ScheduleStatus,
)
from basis.shared.identifiers import AccountId, PlanId, PlannedSessionId, Revision

from ...domain.manual import EmptyPrescription
from ..actions import revise_plan, start_session
from ..models import (
    Block,
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)
from .forms import (
    CycleForm,
    GoalForm,
    PlanChangeForm,
    PlanForm,
    PlannedSessionForm,
    RescheduleForm,
    ScheduledChangeForm,
)


@dataclass(frozen=True)
class TodayEntry:
    item: PlannedSession
    state: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class PlanDayEntry:
    title: str
    state: str
    url: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class PlanDay:
    date: date
    today: bool
    entries: tuple[PlanDayEntry, ...]


@login_required
def today(request: HttpRequest) -> HttpResponse:
    account = AccountId(owner(request).pk)
    day = owner_date(account, timezone.now())
    rows = effective_sessions(account, owner_date)
    week_start = day - timedelta(days=day.weekday())
    week_end = week_start + timedelta(days=6)
    week_rows = [
        (row, calendar_status(row, day)) for row in rows if week_start <= row.date <= week_end
    ]
    planned_blocks: dict[int, list[Block]] = defaultdict(list)
    planned_ids = [row.pk for row, _ in week_rows]
    if planned_ids:
        for block in (
            Block.objects.filter(planned_id__in=planned_ids)
            .prefetch_related("sets__exercise")
            .order_by("order", "pk")
        ):
            if block.planned_id is not None:
                planned_blocks[block.planned_id].append(block)
    today_sessions = [
        TodayEntry(row, state, tuple(planned_blocks.get(row.pk, ())))
        for row, state in week_rows
        if row.date == day
    ]
    week_sessions = (
        Session.objects.filter(owner=owner(request), date__range=(week_start, week_end))
        .prefetch_related("blocks")
        .order_by("date", "created_at")
    )
    week_days = []
    for offset in range(7):
        current = week_start + timedelta(days=offset)
        items = [
            {
                "kind": "plan",
                "title": row.title,
                "state": state,
                "url": reverse("scheduled-detail", args=[row.pk]),
                "sports": [block.sport for block in planned_blocks.get(row.pk, ())],
            }
            for row, state in week_rows
            if row.date == current
        ]
        items.extend(
            {
                "kind": "done",
                "title": session.title,
                "state": session.get_status_display(),
                "url": reverse("session-detail", args=[session.pk]),
                "sports": [block.sport for block in session.blocks.all()],
            }
            for session in week_sessions
            if session.date == current
        )
        week_days.append(
            {
                "date": current,
                "today": current == day,
                "items": items,
                "extra": max(0, len(items) - 2),
            }
        )
    active_session = (
        Session.objects.filter(owner=owner(request), status="in_progress")
        .prefetch_related("blocks__sets__exercise")
        .first()
    )
    today_others = [
        entry
        for entry in today_sessions
        if not (active_session and entry.item.pk == active_session.planned_id)
    ]
    return render(
        request,
        "training/execution/today.html",
        {
            "today": day,
            "today_sessions": today_sessions,
            "today_others": today_others,
            "week_days": week_days,
            "active_session": active_session,
            "recent": (
                Session.objects.filter(owner=owner(request))
                .prefetch_related("blocks")
                .order_by("-date", "-created_at")[:5]
            ),
            "wellness": presentation.wellness_today(owner(request).pk, day),
            "goals": Goal.objects.filter(owner=owner(request))[:3],
        },
    )


@login_required
def plan_list(request: HttpRequest) -> HttpResponse:
    account = AccountId(owner(request).pk)
    day = owner_date(account, timezone.now())
    plans = list(
        TrainingPlan.objects.filter(owner=owner(request), next_version__isnull=True)
        .select_related("goal")
        .order_by("-created_at")
    )
    plan = plans[0] if plans else None
    context: dict[str, object] = {
        "plans": plans,
        "plan": plan,
        "goals": Goal.objects.filter(owner=owner(request)),
    }
    if plan is not None:
        week_start = day - timedelta(days=day.weekday())
        week_end = week_start + timedelta(days=6)
        rows = [
            row
            for row in effective_sessions(account, owner_date)
            if row.plan_id == plan.pk and week_start <= row.date <= week_end
        ]
        planned_blocks: dict[int, list[Block]] = defaultdict(list)
        planned_ids = [row.pk for row in rows]
        if planned_ids:
            for block in (
                Block.objects.filter(planned_id__in=planned_ids)
                .prefetch_related("sets__exercise")
                .order_by("order", "pk")
            ):
                if block.planned_id is not None:
                    planned_blocks[block.planned_id].append(block)
        manual_sessions = (
            Session.objects.filter(
                owner=owner(request),
                planned__isnull=True,
                date__range=(week_start, week_end),
            )
            .prefetch_related("blocks__sets__exercise")
            .order_by("date", "created_at")
        )
        week_days: list[PlanDay] = []
        for offset in range(7):
            current = week_start + timedelta(days=offset)
            entries: list[PlanDayEntry] = [
                PlanDayEntry(
                    row.title,
                    calendar_status(row, day),
                    reverse("scheduled-detail", args=[row.pk]),
                    tuple(planned_blocks.get(row.pk, ())),
                )
                for row in rows
                if row.date == current
            ]
            entries.extend(
                PlanDayEntry(
                    session.title,
                    session.get_status_display(),
                    reverse("session-detail", args=[session.pk]),
                    tuple(session.blocks.all()),
                )
                for session in manual_sessions
                if session.date == current
            )
            week_days.append(PlanDay(current, current == day, tuple(entries)))
        context.update(
            {
                "week_start": week_start,
                "week_end": week_end,
                "week_days": week_days,
            }
        )
    return render(request, "training/planning/overview.html", context)


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
    day = owner_date(AccountId(owner(request).pk), timezone.now())
    editable = not TrainingPlan.objects.filter(previous=plan).exists()
    rows = (
        [
            s
            for s in effective_sessions(AccountId(owner(request).pk), owner_date)
            if s.plan.lineage == plan.lineage
        ]
        if editable
        else list(plan.sessions.all())
    )
    comparison = None
    compare = request.GET.get("compare")
    if compare and compare.isdecimal():
        comparison = get_object_or_404(
            TrainingPlan, pk=int(compare), owner=owner(request), lineage=plan.lineage
        )
    return render(
        request,
        "training/planning/detail.html",
        {
            "plan": plan,
            "cycles": plan.cycles.order_by("start_date", "kind"),
            "scheduled": [(row, calendar_status(row, day)) for row in rows],
            "editable": editable,
            "versions": TrainingPlan.objects.filter(
                owner=owner(request), lineage=plan.lineage
            ).order_by("version"),
            "comparison": comparison,
            "comparison_sessions": comparison.sessions.order_by("date") if comparison else (),
        },
    )


@write_required
def plan_revise(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    form = PlanChangeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new = revise_plan(owner(request), plan, form.cleaned_data["reason"])
        return redirect("plan-detail", pk=new.pk)
    return render(request, "shared/form.html", {"title": "Nueva versión del plan", "form": form})


@write_required
def plan_restore(request: HttpRequest, pk: int, target: int) -> HttpResponse:
    head = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    selected = get_object_or_404(
        TrainingPlan, pk=target, owner=owner(request), lineage=head.lineage
    )
    form = PlanChangeForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            result = planning().restore(
                RestorePlan(
                    AccountId(owner(request).pk),
                    PlanId(pk),
                    PlanId(target),
                    form.cleaned_data["reason"],
                )
            )
            return redirect("plan-detail", pk=result.id)
        except InvalidPlanning as error:
            form.add_error(None, str(error))
            status = 409 if isinstance(error, PlanningConflict) else 200
    return render(
        request,
        "shared/form.html",
        {
            "title": "Restaurar como nueva versión",
            "subtitle": f"Intención de v{selected.version}; los resultados históricos se conservan.",
            "form": form,
        },
        status=status,
    )


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
        {
            "title": "Añadir ciclo",
            "subtitle": "Macrociclo → mesociclo → microciclo",
            "form": form,
        },
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
            "state": calendar_status(
                scheduled, owner_date(AccountId(owner(request).pk), timezone.now())
            ),
            "editable": not TrainingPlan.objects.filter(previous_id=scheduled.plan_id).exists()
            and not intent_executions(scheduled).exists()
            and scheduled.status == "scheduled",
            "executions": intent_executions(scheduled),
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
        request.POST or None,
        plan=scheduled.plan,
        initial={
            "date": scheduled.date,
            "revision": scheduled.revision,
            "cycle": scheduled.cycle_id,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            new_id = reschedule(
                owner(request).pk,
                scheduled.pk,
                form.cleaned_data["date"],
                form.cleaned_data["revision"],
                form.cleaned_data["reason"],
                form.cleaned_data["cycle"].pk if form.cleaned_data["cycle"] else None,
            )
            return redirect("scheduled-detail", pk=new_id)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "shared/form.html", {"title": "Reprogramar sesión", "form": form})


@write_required
def scheduled_change(request: HttpRequest, pk: int) -> HttpResponse:
    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
    form = ScheduledChangeForm(
        request.POST or None, owner=owner(request).pk, initial={"revision": scheduled.revision}
    )
    valid = request.method == "POST" and form.is_valid()
    status = 400 if request.method == "POST" and not valid else 200
    if valid:
        action = form.cleaned_data["action"]
        source = form.cleaned_data["replacement"] if action == "replace" else None
        replacement = (
            replace(
                scheduled_definition(source), cycle_key=str(scheduled.cycle_id), date=scheduled.date
            )
            if source
            else None
        )
        try:
            result = planning().change_session(
                ChangeScheduledSession(
                    AccountId(owner(request).pk),
                    PlannedSessionId(pk),
                    Revision(form.cleaned_data["revision"]),
                    form.cleaned_data["reason"],
                    ScheduleStatus.SCHEDULED if action == "replace" else ScheduleStatus(action),
                    replacement,
                )
            )
            return redirect("scheduled-detail", pk=result.id)
        except InvalidPlanning as error:
            form.add_error(None, str(error))
            status = 409 if isinstance(error, PlanningConflict) else 400
    return render(
        request,
        "shared/form.html",
        {"title": "Cambiar sesión mediante versión", "form": form},
        status=status,
    )


@write_required
def goal_new(request: HttpRequest) -> HttpResponse:
    form = GoalForm(request.POST or None, instance=Goal(owner=owner(request)))
    if request.method == "POST" and form.is_valid():
        save_goal(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "shared/form.html", {"title": "Nuevo objetivo", "form": form})
