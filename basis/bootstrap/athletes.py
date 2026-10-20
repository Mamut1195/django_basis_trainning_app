"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.modules.athletes.adapters.django import (
    DjangoAthleteRecords,
)
from basis.modules.athletes.public import (
    Athletes,
)


def athletes() -> Athletes:
    return Athletes(DjangoAthleteRecords(), write_authorization(), DjangoUnitOfWork)
