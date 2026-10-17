from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from .models import BillingAccount


def can_write(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, "athlete", None)
    if not profile or not profile.email_verified:
        return False
    if settings.DEVELOPMENT_ACCESS:
        return True
    billing = BillingAccount.objects.filter(owner=user).first()
    return bool(billing and billing.entitled)


def require_write_access(user):
    if not can_write(user):
        raise PermissionDenied(
            "Necesitas verificar el correo y tener una prueba o suscripción activa para registrar entrenamiento. Tu historial sigue disponible."
        )
