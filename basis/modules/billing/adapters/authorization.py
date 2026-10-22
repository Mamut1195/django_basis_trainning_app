"""Preserve DRF's existing write-denial exception at the infrastructure boundary."""

from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.exceptions import PermissionDenied

from basis.adapters.django.account_locks import lock_account
from basis.shared.identifiers import AccountId

from ..application.service import Billing


class DjangoWriteAuthorization:
    def __init__(self, billing: Billing) -> None:
        self.billing = billing

    def require(self, owner: AccountId) -> None:
        # Input-layer preflight may run in autocommit. Actual mutations enter an
        # application UoW and retain this common account lock through persistence.
        if connection.in_atomic_block and get_user_model().objects.filter(pk=owner).exists():
            lock_account(owner)
        if not self.billing.can_write(owner):
            raise PermissionDenied(
                "Necesitas verificar el correo y tener una prueba o suscripci\u00f3n activa para registrar entrenamiento. Tu historial sigue disponible."
            )
