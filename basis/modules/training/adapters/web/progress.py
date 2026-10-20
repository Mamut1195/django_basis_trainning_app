"""HTTP presentation for training progress."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from basis.adapters.web import presentation
from basis.adapters.web.framework import owner

from ..actions import progress_report
from ..models import (
    TrekTrip,
)


@login_required
def progress(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "training/progress/index.html",
        {
            "report": progress_report(owner(request)),
            **presentation.progress_history(owner(request).pk),
            "trips": TrekTrip.objects.filter(owner=owner(request)),
        },
    )
