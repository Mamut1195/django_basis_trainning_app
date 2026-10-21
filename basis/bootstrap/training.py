"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock
from basis.bootstrap.billing import write_authorization
from basis.bootstrap.training_dates import owner_date
from basis.modules.training.adapters.django import (
    DjangoSessionRepository,
    UUIDSessionIds,
)
from basis.modules.training.adapters.locking import TrainingUnitOfWork
from basis.modules.training.public import (
    Training,
)


def training() -> Training:
    return Training(
        DjangoSessionRepository(),
        TrainingUnitOfWork,
        write_authorization(),
        DjangoClock(),
        UUIDSessionIds(),
        owner_date,
    )
