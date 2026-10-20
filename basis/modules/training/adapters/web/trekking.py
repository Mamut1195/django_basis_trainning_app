"""HTTP presentation for training trekking."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from basis.adapters.web.framework import owner, write_required
from basis.modules.training.adapters.progress_actions import save_stage, save_trip

from ..actions import trip_summary
from ..models import (
    TrekTrip,
)
from .forms import (
    TrekStageForm,
    TrekTripForm,
)


@login_required
def trip_detail(request: HttpRequest, pk: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
    return render(
        request,
        "training/trekking/detail.html",
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
    return render(request, "shared/form.html", {"title": "Añadir etapa de trekking", "form": form})


@write_required
def trip_new(request: HttpRequest) -> HttpResponse:
    form = TrekTripForm(request.POST or None, instance=TrekTrip(owner=owner(request)))
    if request.method == "POST" and form.is_valid():
        return redirect("trip-detail", pk=save_trip(owner(request).pk, form.save(commit=False)))
    return render(request, "shared/form.html", {"title": "Nuevo trekking", "form": form})
