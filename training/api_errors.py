from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


def exception_handler(exc, context):
    if isinstance(exc, ValidationError):
        return Response(getattr(exc, "message_dict", {"detail": exc.messages}), status=400)
    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "Este elemento tiene historial y no puede eliminarse."}, status=409
        )
    return drf_handler(exc, context)
