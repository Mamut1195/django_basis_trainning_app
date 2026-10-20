"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.modules.training.adapters.django import (
    DjangoSessionRepository,
    UUIDSessionIds,
)
from basis.modules.training.public import (
    Training,
)


def training() -> Training:
    return Training(
        DjangoSessionRepository(),
        DjangoUnitOfWork,
        write_authorization(),
        DjangoClock(),
        UUIDSessionIds(),
    )
