"""Compatibility facade for the typed commercial write-access policy."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser

from basis.bootstrap.billing import billing, write_authorization
from basis.shared.identifiers import AccountId


def can_write(user: AbstractBaseUser | AnonymousUser) -> bool:
    if not user.is_authenticated or user.pk is None:
        return False
    return billing().can_write(AccountId(user.pk))


def require_write_access(user: AbstractBaseUser | AnonymousUser) -> None:
    # Anonymous users take the same denial path as authenticated users without access.
    write_authorization().require(AccountId(user.pk if user.pk is not None else 0))
