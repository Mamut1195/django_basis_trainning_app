"""Serialize a single account's reservations using its existing auth row."""

from django.contrib.auth import get_user_model

from basis.shared.identifiers import AccountId


class DjangoAccountLocks:
    def lock(self, owner: AccountId) -> None:
        get_user_model().objects.select_for_update().get(pk=owner)
