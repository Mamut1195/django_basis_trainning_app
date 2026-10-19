"""Preserve DRF's existing write-denial exception at the infrastructure boundary."""

from rest_framework.exceptions import PermissionDenied  # type: ignore[import-untyped]

from basis.shared.identifiers import AccountId

from ..application.service import Billing


class DjangoWriteAuthorization:
    def __init__(self, billing: Billing) -> None:
        self.billing = billing

    def require(self, owner: AccountId) -> None:
        if not self.billing.can_write(owner):
            raise PermissionDenied(
                "Necesitas verificar el correo y tener una prueba o suscripci\u00f3n activa para registrar entrenamiento. Tu historial sigue disponible."
            )
