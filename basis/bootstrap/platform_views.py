from __future__ import annotations

import hashlib
import json
from typing import cast

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Model, Q, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone

from basis.bootstrap.web_framework import owner, public_id
from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    UserExerciseRM,
    Wellness,
    WorkoutData,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.coach.adapters.models import AIJob, PlanProposal
from basis.modules.training.adapters.models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)


def export_rows(queryset: QuerySet[Model], external_label: str) -> list[dict[str, object]]:
    """Keep export-v1 model tags stable while internal app labels evolve."""
    from django.core.serializers import serialize

    rows = cast(list[dict[str, object]], json.loads(serialize("json", queryset)))
    for row in rows:
        row["model"] = external_label
    return rows


@login_required
def export_data(request: HttpRequest) -> HttpResponse:
    models: list[type[Model]] = [
        AthleteSettings,
        AIJob,
        PlanProposal,
        Goal,
        TrainingPlan,
        Cycle,
        PlannedSession,
        Session,
        Block,
        StrengthSet,
        Interval,
        Wellness,
        Measurement,
        SportProfile,
        TrekTrip,
        TrekStage,
        WorkoutData,
        UserExerciseRM,
    ]
    result: dict[str, object] = {
        "schema": "basis-export-v1",
        "exported_at": timezone.now().isoformat(),
    }
    result["athlete"] = export_rows(
        Athlete.objects.filter(account=owner(request)), "daily_trainning_app.user"
    )
    for model in models:
        if model in (WorkoutData, UserExerciseRM):
            queryset = model._default_manager.filter(user__account=owner(request))
        elif model is Cycle:
            queryset = model._default_manager.filter(plan__owner=owner(request))
        elif model is Block:
            queryset = model._default_manager.filter(
                Q(session__owner=owner(request)) | Q(planned__owner=owner(request))
            )
        elif model in (StrengthSet, Interval):
            queryset = model._default_manager.filter(
                Q(block__session__owner=owner(request)) | Q(block__planned__owner=owner(request))
            )
        elif model is TrekStage:
            queryset = model._default_manager.filter(trip__owner=owner(request))
        else:
            queryset = model._default_manager.filter(owner=owner(request))
        external_area = (
            "daily_trainning_app" if model in (WorkoutData, UserExerciseRM) else "training"
        )
        result[str(model._meta.model_name)] = export_rows(
            queryset, external_area + "." + str(model._meta.model_name)
        )
    response = JsonResponse(result)
    response["Content-Disposition"] = 'attachment; filename="basis-entrenamiento.json"'
    return response


@login_required
def csrf_api(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"account": str(public_id(request)), "token": get_token(request)})


def manifest(request: HttpRequest) -> HttpResponse:
    from basis.bootstrap.brand import IDENTITY

    return JsonResponse(
        {
            "id": "/",
            "name": "BASIS Training",
            "short_name": "BASIS",
            "lang": "es",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": IDENTITY["colors"]["background"],
            "theme_color": IDENTITY["colors"]["primary"],
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {
                    "src": "/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request: HttpRequest) -> HttpResponse:
    files = [
        *sorted((settings.BASE_DIR / "assets").rglob("*")),
        settings.BASE_DIR / "templates/base.html",
        settings.BASE_DIR / "templates/cotton/brand.html",
        settings.BASE_DIR / "templates/training/offline.html",
        settings.BASE_DIR / "templates/service-worker.js",
        settings.BASE_DIR / "requirements.txt",
    ]
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.read_bytes())
    response = render(
        request,
        "service-worker.js",
        {"shell_version": digest.hexdigest()[:16]},
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def health(request: HttpRequest) -> HttpResponse:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
