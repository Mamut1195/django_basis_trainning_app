"""HTTP presentation for training trekking."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from basis.adapters.web.framework import owner, write_required
from basis.bootstrap.progress import progress
from basis.modules.training.adapters.progress_actions import save_stage, save_trip
from basis.modules.training.application.progress import EditStage
from basis.modules.training.domain.trekking import TrekkingUnavailable
from basis.modules.training.public import VARIABLES
from basis.shared.identifiers import AccountId, TrekStageId, TrekTripId

from ..actions import trip_summary
from ..models import (
    TrekStage,
    TrekTrip,
)
from .forms import (
    TrekStageEditForm,
    TrekStageForm,
    TrekTripForm,
)


@login_required
def trip_detail(request: HttpRequest, pk: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
    summary = trip_summary(trip)
    totals = cast(dict[str, Decimal | None], summary["totals"])
    display_totals = [
        (VARIABLES["hiking"][key].label, VARIABLES["hiking"][key].unit, value)
        for key, value in totals.items()
    ]
    return render(
        request,
        "training/trekking/detail.html",
        {
            "trip": trip,
            "summary": summary,
            "display_totals": display_totals,
            "stages": trip.stages.select_related("session"),
        },
    )


@write_required
def stage_new(request: HttpRequest, pk: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
    form = TrekStageForm(request.POST or None, trip=trip)
    if request.method == "POST" and form.is_valid():
        try:
            save_stage(owner(request).pk, form.save(commit=False))
            return redirect("trip-detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
        except TrekkingUnavailable as error:
            raise Http404 from error
    return render(request, "shared/form.html", {"title": "Añadir etapa de trekking", "form": form})


@write_required
def trip_new(request: HttpRequest) -> HttpResponse:
    form = TrekTripForm(request.POST or None, instance=TrekTrip(owner=owner(request)))
    if request.method == "POST" and form.is_valid():
        return redirect("trip-detail", pk=save_trip(owner(request).pk, form.save(commit=False)))
    return render(request, "shared/form.html", {"title": "Nuevo trekking", "form": form})


@write_required
def stage_edit(request: HttpRequest, pk: int, stage_id: int) -> HttpResponse:
    trip = get_object_or_404(TrekTrip, pk=pk, owner=owner(request))
    stage = get_object_or_404(TrekStage, pk=stage_id, trip=trip)
    form = TrekStageEditForm(request.POST or None, instance=stage)
    if request.method == "POST" and form.is_valid():
        try:
            progress().edit_stage(
                EditStage(
                    AccountId(owner(request).pk),
                    TrekTripId(pk),
                    TrekStageId(stage_id),
                    form.cleaned_data["order"],
                    form.cleaned_data["overnight_altitude_m"],
                    form.cleaned_data["recovery_notes"],
                )
            )
            return redirect("trip-detail", pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
        except TrekkingUnavailable as error:
            raise Http404 from error
    return render(request, "shared/form.html", {"title": "Corregir etapa", "form": form})
