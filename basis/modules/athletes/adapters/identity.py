"""Athlete-owned account identity projection."""

from uuid import UUID

from .models import User


def public_id(owner: int) -> UUID:
    return User.objects.get(account_id=owner).public_id
