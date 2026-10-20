"""Existing HTTP synchronization responses; authentication and CSRF stay in Django."""

import json
from collections.abc import Callable
from uuid import UUID

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from rest_framework.exceptions import PermissionDenied

from basis.shared.identifiers import AccountId

from .wire import Conflict, mapping


def sync_response(
    raw: bytes,
    owner: AccountId,
    public_id: UUID,
    synchronize: Callable[[AccountId, object, object], dict[str, object]],
) -> JsonResponse:
    try:
        decoded: object = json.loads(raw)
        if not isinstance(decoded, dict) or not isinstance(decoded.get("session"), dict):
            raise ValidationError("Formato inv\u00e1lido.")
        body = mapping(decoded)
        if body.get("account") != str(public_id):
            return JsonResponse({"detail": "La cola pertenece a otra cuenta."}, status=403)
        return JsonResponse(
            {"session": synchronize(owner, body.get("mutation_id"), body["session"])}
        )
    except Conflict as error:
        return JsonResponse(
            {
                "detail": "Hay otra versi\u00f3n. Revisa ambas antes de resolver.",
                "current": error.current,
            },
            status=409,
        )
    except (ValidationError, ValueError, KeyError, TypeError) as error:
        detail = error.messages if isinstance(error, ValidationError) else ["Datos inv\u00e1lidos"]
        return JsonResponse({"detail": detail}, status=400)
    except PermissionDenied as error:
        return JsonResponse({"detail": str(error.detail)}, status=403)
