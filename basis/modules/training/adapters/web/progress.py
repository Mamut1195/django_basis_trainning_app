"""Owner-scoped progress periods and source sessions."""

from datetime import date, timedelta

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner
from basis.bootstrap.training_dates import owner_date
from basis.shared.identifiers import AccountId

from ..actions import progress_report
from ..models import Session, TrekTrip


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
            "source_sessions": Paginator(sessions, 20).get_page(request.GET.get("page")),
            "report": progress_report(account, start, end),
            **presentation.progress_history(account.pk),
            "trips": TrekTrip.objects.filter(owner=account),
        },
    )
