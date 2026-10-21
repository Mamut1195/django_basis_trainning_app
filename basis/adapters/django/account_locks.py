"""Shared account-row lock, including deferred FK checks at transaction commit.

The identifier is AUTH_USER_MODEL.pk, never an athlete/profile identifier. This
helper must run inside the operation's transaction and before its aggregate locks.
It does not grant authorization or change an existing outer transaction's lifetime.
"""

from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS

from basis.shared.identifiers import AccountId


def lock_account(owner: AccountId, using: str = DEFAULT_DB_ALIAS) -> None:
    get_user_model().objects.using(using).select_for_update().get(pk=owner)
