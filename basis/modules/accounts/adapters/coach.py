"""Serialize a single account's reservations using its existing auth row."""

from django.db import DEFAULT_DB_ALIAS

from basis.adapters.django.account_locks import lock_account
from basis.shared.identifiers import AccountId


class DjangoAccountLocks:
    def __init__(self, using: str = DEFAULT_DB_ALIAS) -> None:
        self.using = using

    def lock(self, owner: AccountId) -> None:
        lock_account(owner, self.using)
