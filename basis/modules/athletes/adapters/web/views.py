from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_safe

from basis.adapters.web.framework import owner, write_required
from basis.adapters.web.presentation import profile_goals
from basis.modules.athletes.adapters.django import wellness_rows
from basis.modules.athletes.adapters.local_dates import owner_local_date
from basis.modules.athletes.adapters.models import (
    Measurement,
    SportProfile,
    User,
    UserExerciseRM,
    Wellness,
)
from basis.modules.athletes.adapters.record_actions import (
    preferences_row,
    save_observation,
    save_preferences,
    save_profile,
    save_rm,
)
from basis.modules.athletes.adapters.web.access import can_edit_personal, personal_required
from basis.modules.athletes.adapters.web.forms import (
    AthleteForm,
    MeasurementForm,
    PreferencesForm,
    RMForm,
    SportProfileForm,
    WellnessForm,
    WellnessRangeForm,
)
from basis.shared.identifiers import AccountId


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    athlete = get_object_or_404(User, account_id=owner(request).pk)
    preferences = preferences_row(owner(request).pk)
    goals = profile_goals(owner(request).pk)
    return render(
        request,
        "athletes/profile/detail.html",
        {
            "preferences": preferences,
            "sports": SportProfile.objects.filter(owner=owner(request)),
            "goals": goals,
            "configuration_ready": bool(
                (goals or (athlete.objetivos or "").strip()) and preferences.availability
            ),
            "personal_access": can_edit_personal(owner(request).pk),
            "available_days": [
                label
                for day, label in enumerate(
                    ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"), 1
                )
                if day in preferences.availability
            ],
            "latest_measurement": Measurement.objects.filter(
                owner=owner(request), origin="measured"
            )
            .order_by("-date", "-pk")
            .first(),
        },
    )


@personal_required
def profile_edit(request: HttpRequest) -> HttpResponse:
    form = AthleteForm(
        request.POST or None, instance=User.objects.get(account_id=owner(request).pk)
    )
    if request.method == "POST" and form.is_valid():
        try:
            save_profile(owner(request).pk, form.save(commit=False))
            return redirect("profile")
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "shared/form.html", {"title": "Tu perfil", "form": form})


@personal_required
def preferences_edit(request: HttpRequest) -> HttpResponse:
    preferences = preferences_row(owner(request).pk)
    form = PreferencesForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        save_preferences(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "shared/form.html", {"title": "Disponibilidad y equipo", "form": form})


@write_required
def rm_new(request: HttpRequest) -> HttpResponse:
    form = RMForm(
        request.POST or None,
        instance=UserExerciseRM(user=User.objects.get(account_id=owner(request).pk)),
    )
    if request.method == "POST" and form.is_valid():
        save_rm(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(
        request,
        "shared/form.html",
        {
            "title": "Registrar 1RM medido",
            "subtitle": "Registra una medición real con su fecha. No es una estimación de la app.",
            "form": form,
        },
    )


def owned_new(request: HttpRequest, resource: str) -> HttpResponse:
    # Wellness stays under its existing commercial training policy.
    guard = personal_required if resource in ("sport", "measurement") else write_required
    return guard(_owned_new)(request, resource)


def _owned_new(request: HttpRequest, resource: str) -> HttpResponse:
    mapping = {
        "sport": (SportProfile, SportProfileForm, "Experiencia y umbral"),
        "wellness": (Wellness, WellnessForm, "Cómo te sientes"),
        "measurement": (Measurement, MeasurementForm, "Registrar peso"),
    }
    if resource not in mapping:
        return HttpResponse(status=404)
    model, cls, title = mapping[resource]
    instance = model(owner=owner(request))
    if resource == "wellness":
        moment = request.GET.get("moment")
        instance = Wellness(
            owner=owner(request),
            date=owner_local_date(owner(request).pk),
            moment=moment if moment in ("before", "after") else "day",
        )
    form = cls(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        instance = form.save(commit=False)
        try:
            save_observation(owner(request).pk, instance)
            return redirect(
                "profile" if resource in ("sport", "measurement") else "wellness-history"
            )
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "shared/form.html",
        {
            "title": title,
            "form": form,
            "subtitle": "Solo un registro para tu seguimiento. Todos los datos de bienestar son opcionales."
            if resource == "wellness"
            else "",
        },
    )


@write_required
def wellness_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(Wellness, pk=pk, owner=owner(request))
    form = WellnessForm(request.POST if request.method == "POST" else None, instance=row)
    if request.method == "POST" and form.is_valid():
        try:
            save_observation(owner(request).pk, form.save(commit=False))
            return redirect("wellness-history")
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "shared/form.html",
        {
            "title": "Editar check-in",
            "form": form,
            "subtitle": "Solo un registro para tu seguimiento.",
        },
    )


@login_required
def wellness_history(request: HttpRequest) -> HttpResponse:
    today = owner_local_date(owner(request).pk)
    form = WellnessRangeForm(
        {
            "start": request.GET.get("start", (today - timedelta(days=29)).isoformat()),
            "end": request.GET.get("end", today.isoformat()),
        }
    )
    rows = wellness_rows(AccountId(owner(request).pk))
    valid = form.is_valid()
    if valid:
        rows = rows.filter(date__range=(form.cleaned_data["start"], form.cleaned_data["end"]))
    else:
        rows = rows.none()
    return render(
        request,
        "athletes/profile/wellness.html",
        {"form": form, "wellness_records": Paginator(rows, 20).get_page(request.GET.get("page"))},
        status=200 if valid else 400,
    )


@personal_required
def sport_edit(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(SportProfile, pk=pk, owner=owner(request))
    form = SportProfileForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        try:
            save_observation(owner(request).pk, form.save(commit=False))
            return redirect("profile")
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, "shared/form.html", {"title": "Editar disciplina", "form": form})


@login_required
def measurement_history(request: HttpRequest) -> HttpResponse:
    get_object_or_404(User, account_id=owner(request).pk)
    rows = Measurement.objects.filter(owner=owner(request)).order_by(
        F("date").desc(nulls_last=True), "-pk"
    )
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    chart_rows = [row for row in page if row.date is not None and row.weight_kg > 0]
    return render(
        request,
        "athletes/profile/measurements.html",
        {
            "measurements": page,
            "chart_rows": chart_rows,
            "chart_max": max((row.weight_kg for row in chart_rows), default=None),
            "personal_access": can_edit_personal(owner(request).pk),
        },
    )


@login_required
@require_safe
def measured_rm_detail(request: HttpRequest, pk: int) -> HttpResponse:
    row = get_object_or_404(
        UserExerciseRM.objects.select_related("exercise"), pk=pk, user__account_id=owner(request).pk
    )
    return render(request, "athletes/profile/measured_rm_detail.html", {"record": row})
