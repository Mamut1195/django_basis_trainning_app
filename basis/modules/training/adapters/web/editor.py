"""Accessible planning UI; private reads and commands through application ports."""

from dataclasses import replace
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from basis.adapters.web.framework import owner, write_required
from basis.bootstrap.plan_editor import plan_editor
from basis.bootstrap.planning import planning
from basis.bootstrap.training_dates import owner_date
from basis.modules.training.adapters.editor_read import (
    cycle_tree,
    differences,
    impact,
    plan_rows,
    week_days,
)
from basis.modules.training.adapters.models import Cycle, PlannedSession, TrainingPlan
from basis.modules.training.adapters.planning import cycle_definition, scheduled_definition
from basis.modules.training.adapters.planning_actions import save_cycle, save_scheduled
from basis.modules.training.application.plan_editor import CopyTemplate, EditPlan
from basis.modules.training.domain.planning import InvalidPlanning, PlanningConflict
from basis.modules.training.public import ChangeScheduledSession, RescheduleSession, ScheduleStatus
from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId, PlannedSessionId, Revision

from .editor_forms import (
    CycleEditForm,
    PlanEditForm,
    ScheduledEditForm,
    ScopedSessionForm,
    TemplateForm,
)
from .forms import CycleForm, RescheduleForm, ScheduledChangeForm


def local_today(request: HttpRequest) -> date:
    return owner_date(AccountId(owner(request).pk), timezone.now())


@login_required
def calendar(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    today = local_today(request)
    try:
        selected = date.fromisoformat(request.GET.get("week", today.isoformat()))
        start = selected - timedelta(days=selected.weekday())
        previous, following = start - timedelta(days=7), start + timedelta(days=7)
    except (ValueError, OverflowError):
        return render(
            request,
            "shared/notice.html",
            {"title": "Fecha inválida", "text": "Selecciona una semana válida."},
            status=400,
        )
    rows = plan_rows(plan, owner_date)
    comparison = None
    if request.GET.get("compare"):
        try:
            comparison_id = int(request.GET["compare"])
            if not 0 < comparison_id < 2**63:
                raise ValueError("Version out of range")
        except ValueError:
            return HttpResponse("Versión inválida", status=400)
        comparison = get_object_or_404(
            TrainingPlan, pk=comparison_id, owner=owner(request), lineage=plan.lineage
        )
    context = {
        "plan": plan,
        "days": week_days(rows, start, today),
        "start": start,
        "previous_week": previous,
        "next_week": following,
        "tree": cycle_tree(plan, rows),
        "historical": [s for s in rows if s.plan_id != plan.pk],
        "editable": not TrainingPlan.objects.filter(previous=plan).exists(),
        "versions": TrainingPlan.objects.filter(
            owner=owner(request), lineage=plan.lineage
        ).order_by("version"),
        "comparison": comparison,
        "differences": differences(comparison, plan) if comparison else (),
        "impact": impact(plan, today),
    }
    template = (
        "training/planning/_board.html"
        if request.headers.get("HX-Request") == "true"
        else "training/planning/calendar.html"
    )
    response = render(request, template, context)
    response["Cache-Control"] = "no-store"
    response["Vary"] = "HX-Request, Cookie"
    return response


@write_required
def template_new(request: HttpRequest) -> HttpResponse:
    form = TemplateForm(request.POST if request.method == "POST" else None, owner=owner(request).pk)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data
            result = plan_editor().copy(
                CopyTemplate(
                    AccountId(owner(request).pk),
                    PlanId(data["source"].pk),
                    GoalId(data["goal"].pk),
                    data["title"],
                    data["start_date"],
                    data["reason"],
                )
            )
            return redirect("plan-calendar", pk=result.id)
        except (InvalidPlanning, ValidationError) as error:
            form.add_error(None, str(error))
    return render(
        request,
        "training/planning/editor.html",
        {
            "title": "Crear desde plantilla privada",
            "subtitle": "Copia un plan propio y desplaza todas sus fechas desde el nuevo inicio. No copia resultados ni sesiones omitidas/canceladas.",
            "form": form,
        },
    )


@write_required
def plan_edit(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    form = PlanEditForm(
        request.POST if request.method == "POST" else None,
        initial={
            "title": plan.title,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "notes": plan.notes,
        },
    )
    status = 200
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            result = plan_editor().edit(
                EditPlan(
                    AccountId(owner(request).pk),
                    PlanId(pk),
                    data["title"],
                    data["start_date"],
                    data["end_date"],
                    data["notes"],
                    data["reason"],
                )
            )
            return redirect("plan-calendar", pk=result.id)
        except (InvalidPlanning, ValidationError) as error:
            form.add_error(None, str(error))
            status = 409 if isinstance(error, PlanningConflict) else 200
    return render(
        request,
        "training/planning/editor.html",
        {
            "title": "Editar plan mediante nueva versión",
            "plan": plan,
            "form": form,
            "impact": impact(plan, local_today(request)),
        },
        status=status,
    )


@write_required
def cycle_editor(request: HttpRequest, pk: int, cycle_id: int | None = None) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    cycle = get_object_or_404(Cycle, pk=cycle_id, plan=plan) if cycle_id is not None else None
    cls = CycleEditForm if cycle else CycleForm
    form = cls(request.POST if request.method == "POST" else None, plan=plan, instance=cycle)
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            candidate = form.save(commit=False)
            if cycle is None:
                save_cycle(owner(request).pk, candidate)
                return redirect("plan-calendar", pk=pk)
            result = plan_editor().edit(
                EditPlan(
                    AccountId(owner(request).pk),
                    PlanId(pk),
                    plan.title,
                    plan.start_date,
                    plan.end_date,
                    plan.notes,
                    form.cleaned_data["reason"],
                    cycle_definition(candidate),
                )
            )
            return redirect("plan-calendar", pk=result.id)
        except (InvalidPlanning, ValidationError) as error:
            form.add_error(None, str(error))
            status = 409 if isinstance(error, PlanningConflict) else 200
    return render(
        request,
        "training/planning/editor.html",
        {
            "title": "Editar ciclo mediante nueva versión" if cycle else "Añadir ciclo",
            "plan": plan,
            "form": form,
            "impact": impact(plan, local_today(request)) if cycle else None,
        },
        status=status,
    )


@write_required
def session_new(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, pk=pk, owner=owner(request))
    form = ScopedSessionForm(request.POST if request.method == "POST" else None, plan=plan)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_scheduled(owner(request).pk, form.save(commit=False))
            return redirect("scheduled-detail", pk=result)
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "training/planning/editor.html",
        {"title": "Programar sesión en este plan", "plan": plan, "form": form},
    )


@write_required
def session_action(request: HttpRequest, pk: int, action: str) -> HttpResponse:
    scheduled = get_object_or_404(PlannedSession, pk=pk, owner=owner(request))
    data = request.POST if request.method == "POST" else None
    if action == "move":
        form: RescheduleForm | ScheduledChangeForm | ScheduledEditForm = RescheduleForm(
            data,
            plan=scheduled.plan,
            initial={
                "date": scheduled.date,
                "cycle": scheduled.cycle_id,
                "revision": scheduled.revision,
            },
        )
        title = "Reprogramar sesión"
    elif action == "change":
        form = ScheduledChangeForm(
            data, owner=owner(request).pk, initial={"revision": scheduled.revision}
        )
        title = "Omitir, cancelar o sustituir sesión"
    elif action == "edit":
        form = ScheduledEditForm(
            data,
            initial={
                "title": scheduled.title,
                "notes": scheduled.notes,
                "revision": scheduled.revision,
            },
        )
        title = "Editar sesión mediante nueva versión"
    else:
        return HttpResponse(status=404)
    status = 200
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            if action == "move":
                result = planning().reschedule(
                    RescheduleSession(
                        AccountId(owner(request).pk),
                        PlannedSessionId(pk),
                        values["date"],
                        Revision(values["revision"]),
                        values["reason"],
                        CycleId(values["cycle"].pk) if values["cycle"] else None,
                    )
                )
            else:
                replacement = None
                state = ScheduleStatus.SCHEDULED
                if action == "edit":
                    replacement = replace(
                        scheduled_definition(scheduled),
                        title=values["title"],
                        notes=values["notes"],
                    )
                elif values["action"] == "replace":
                    replacement = scheduled_definition(values["replacement"])
                else:
                    state = ScheduleStatus(values["action"])
                result = planning().change_session(
                    ChangeScheduledSession(
                        AccountId(owner(request).pk),
                        PlannedSessionId(pk),
                        Revision(values["revision"]),
                        values["reason"],
                        state,
                        replacement,
                    )
                )
            return redirect("plan-calendar", pk=result.plan)
        except (InvalidPlanning, ValidationError) as error:
            form.add_error(None, str(error))
            status = 409 if isinstance(error, PlanningConflict) else 200
    return render(
        request,
        "training/planning/editor.html",
        {
            "title": title,
            "plan": scheduled.plan,
            "scheduled": scheduled,
            "form": form,
            "impact": impact(scheduled.plan, local_today(request)),
        },
        status=status,
    )
