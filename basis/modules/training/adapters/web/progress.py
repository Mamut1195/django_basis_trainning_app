"""Owner-scoped progress periods and source sessions."""

from datetime import date, timedelta

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner
from basis.bootstrap.training_dates import owner_date
from basis.shared.identifiers import AccountId

from ..actions import progress_report
from ..calendar import calendar_status, effective_sessions
from ..models import PlannedSession, Session, TrekTrip


class ProgressPeriodForm(forms.Form):
    period = forms.ChoiceField(
        label="Período",
        choices=[("all", "Acumulado"), ("day", "Día"), ("week", "Semana ISO"), ("range", "Rango")],
    )
    reference = forms.DateField(
        label="Fecha de referencia", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    start = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self) -> dict[str, object]:
        data = super().clean() or {}
        if data.get("period") == "range":
            start, end = data.get("start"), data.get("end")
            if not start or not end:
                raise forms.ValidationError("Indica ambas fechas del rango.")
            if start > end:
                raise forms.ValidationError("La fecha inicial no puede superar la final.")
        return data


def agenda_rows(
    account: AccountId, rows: list[PlannedSession], today: date
) -> list[dict[str, object]]:
    roots = {row.origin_id or row.pk for row in rows}
    by_root: dict[int, list[Session]] = {root: [] for root in roots}
    if roots:
        executions = (
            Session.objects.filter(owner_id=account)
            .filter(Q(planned_id__in=roots) | Q(planned__origin_id__in=roots))
            .select_related("planned")
            .order_by("date", "pk")
        )
        for execution in executions:
            planned = execution.planned
            if planned is not None:
                by_root[planned.origin_id or planned.pk].append(execution)
    return [
        {
            "planned": row,
            "state": calendar_status(row, today),
            "exclusion_reason": (
                "Cancelada y futura"
                if row.status == "cancelled" and row.date > today
                else "Cancelada"
                if row.status == "cancelled"
                else "Fecha futura"
                if row.date > today
                else ""
            ),
            "executions": by_root[row.origin_id or row.pk],
        }
        for row in rows
    ]


@login_required
def progress(request: HttpRequest) -> HttpResponse:
    account = owner(request)
    today = owner_date(AccountId(account.pk), timezone.now())
    params = request.GET.copy()
    if "period" not in params:
        params["period"] = "all"
    form = ProgressPeriodForm(params)
    if not form.is_valid():
        return render(
            request,
            "training/progress/index.html",
            {"period_form": form, "period_valid": False},
            status=400,
        )
    period = form.cleaned_data["period"]
    reference: date = form.cleaned_data["reference"] or today
    if period in ("day", "week"):
        params["reference"] = reference.isoformat()
    start: date | None = None
    end: date | None = None
    if period == "day":
        start = end = reference
    elif period == "week":
        start = reference - timedelta(days=reference.weekday())
        try:
            end = start + timedelta(days=6)
        except OverflowError:
            form.add_error("reference", "La semana excede el rango de fechas admitido.")
            return render(
                request,
                "training/progress/index.html",
                {"period_form": form, "period_valid": False},
                status=400,
            )
    elif period == "range":
        start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    sessions = Session.objects.filter(owner_id=account.pk).order_by("-date", "-created_at", "-pk")
    if start is not None and end is not None:
        sessions = sessions.filter(date__range=(start, end))
    effective = effective_sessions(AccountId(account.pk), owner_date)
    selected = [
        row
        for row in effective
        if (start is None or row.date >= start) and (end is None or row.date <= end)
    ]
    agenda_page = Paginator(selected, 20).get_page(request.GET.get("agenda_page"))
    entries = agenda_rows(AccountId(account.pk), list(agenda_page.object_list), today)
    agenda_params = params.copy()
    agenda_params.pop("agenda_page", None)
    params.pop("page", None)
    return render(
        request,
        "training/progress/index.html",
        {
            "period_form": form,
            "period_valid": True,
            "period_start": start,
            "period_end": end,
            "detail_query": params.urlencode(),
            "agenda_query": agenda_params.urlencode(),
            "agenda_page": agenda_page,
            "agenda_entries": entries,
            "source_sessions": Paginator(sessions, 20).get_page(request.GET.get("page")),
            "report": progress_report(account, start, end),
            **presentation.progress_history(account.pk),
            "trips": TrekTrip.objects.filter(owner=account),
        },
    )
