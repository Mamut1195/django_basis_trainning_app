from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from basis.bootstrap.athletes import save_observation, save_preferences, save_profile, save_rm
from basis.bootstrap.web_framework import owner, write_required

from .forms import (
    AthleteForm,
    MeasurementForm,
    PreferencesForm,
    RMForm,
    SportProfileForm,
    WellnessForm,
)
from .models import AthleteSettings, Measurement, SportProfile, User, UserExerciseRM, Wellness


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    preferences, _ = AthleteSettings.objects.get_or_create(owner=owner(request))
    return render(
        request,
        "training/profile.html",
        {
            "preferences": preferences,
            "sports": SportProfile.objects.filter(owner=owner(request)),
        },
    )


@write_required
def profile_edit(request: HttpRequest) -> HttpResponse:
    form = AthleteForm(
        request.POST or None, instance=User.objects.get(account_id=owner(request).pk)
    )
    if request.method == "POST" and form.is_valid():
        save_profile(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "training/form.html", {"title": "Tu perfil", "form": form})


@write_required
def preferences_edit(request: HttpRequest) -> HttpResponse:
    preferences, _ = AthleteSettings.objects.get_or_create(owner=owner(request))
    form = PreferencesForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        save_preferences(owner(request).pk, form.save(commit=False))
        return redirect("profile")
    return render(request, "training/form.html", {"title": "Disponibilidad y equipo", "form": form})


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
        "training/form.html",
        {
            "title": "Registrar 1RM medido",
            "subtitle": "Registra una medición real con su fecha. No es una estimación de la app.",
            "form": form,
        },
    )


@write_required
def owned_new(request: HttpRequest, resource: str) -> HttpResponse:
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
        instance = (
            Wellness.objects.filter(owner=owner(request), date=timezone.localdate()).first()
            or instance
        )
    form = cls(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        instance = form.save(commit=False)
        save_observation(owner(request).pk, instance)
        return (
            redirect("trip-detail", pk=instance.pk)
            if resource == "trip"
            else redirect("profile" if resource in ("goal", "sport") else "progress")
        )
    return render(request, "training/form.html", {"title": title, "form": form})
