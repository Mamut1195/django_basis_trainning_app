"""Typed Django authentication and permission glue shared by input adapters."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, cast
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as AccountUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from basis.modules.athletes.adapters.identity import public_id as athlete_public_id
from basis.modules.billing.adapters.access import can_write
from basis.modules.sync.adapters.actions import Conflict as Conflict
from basis.modules.sync.adapters.actions import sync_session as sync_session

P = ParamSpec("P")


def owner(request: HttpRequest) -> AccountUser:
    return cast(AccountUser, request.user)


def public_id(request: HttpRequest) -> UUID:
    return athlete_public_id(owner(request).pk)


def write_required(view: Callable[P, HttpResponse]) -> Callable[P, HttpResponse]:
    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        request = cast(HttpRequest, args[0])
        if not can_write(request.user):
            return render(
                request,
                "shared/notice.html",
                {
                    "title": "Tu historial sigue disponible",
                    "text": "Verifica tu correo y activa la prueba o suscripción para registrar entrenamiento.",
                    "billing_link": True,
                },
                status=403,
            )
        return view(*args, **kwargs)

    return cast(Callable[P, HttpResponse], login_required(wrapped))
