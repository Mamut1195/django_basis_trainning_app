"""Translate native catalog admin permissions to the application authorizer."""

from typing import Literal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from basis.shared.identifiers import AccountId


class DjangoCatalogAdminAuthorization:
    def __init__(
        self,
        resource: Literal["classification", "exercise"],
        operation: Literal["add", "change", "delete"],
    ) -> None:
        self.resource, self.operation = resource, operation

    def require_write(self, actor: AccountId) -> None:
        user = get_user_model().objects.get(pk=actor)
        if (
            not user.is_active
            or not user.is_staff
            or not user.has_perm(f"basis_catalog.{self.operation}_{self.resource}")
        ):
            raise PermissionDenied
