"""Module-owned HTTP guard for free personal writes, separate from billing."""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, cast

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from rest_framework.exceptions import PermissionDenied

from basis.bootstrap.athletes import personal_authorization
from basis.shared.identifiers import AccountId

P = ParamSpec("P")


def can_edit_personal(owner: int) -> bool:
    try:
        personal_authorization().require(AccountId(owner))
    except PermissionDenied:
        return False
    return True


def personal_required(view: Callable[P, HttpResponse]) -> Callable[P, HttpResponse]:
    @wraps(view)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        request = cast(HttpRequest, args[0])
        try:
            if not request.user.is_authenticated or request.user.pk is None:
                raise PermissionDenied("Inicia sesión con una cuenta activa y correo verificado.")
            personal_authorization().require(AccountId(request.user.pk))
        except PermissionDenied as error:
            return render(
                request,
                "shared/notice.html",
                {
                    "title": "Verifica tu cuenta para completar tu perfil gratuito",
                    "text": str(error.detail),
                },
                status=403,
            )
        return view(*args, **kwargs)

    return wrapped
