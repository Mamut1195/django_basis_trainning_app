from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from basis.adapters.web.framework import owner, public_id
from basis.modules.sync.adapters.input_actions import synchronize
from basis.modules.sync.adapters.payload_wire import sync_response
from basis.shared.identifiers import AccountId


@login_required
@require_POST
def sync_api(request: HttpRequest) -> HttpResponse:
    return sync_response(
        request.body, AccountId(owner(request).pk), public_id(request), synchronize
    )


def offline(request: HttpRequest) -> HttpResponse:
    from dataclasses import asdict

    from basis.modules.training.public import VARIABLES

    schema = {
        sport: {key: asdict(spec) for key, spec in metrics.items()}
        for sport, metrics in VARIABLES.items()
    }
    return render(request, "sync/offline/index.html", {"offline_schema": schema})
