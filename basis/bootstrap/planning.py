"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock
from basis.bootstrap.billing import write_authorization
from basis.bootstrap.training_dates import owner_date
from basis.modules.training.adapters.locking import TrainingUnitOfWork
from basis.modules.training.adapters.planning import (
    DjangoPlanRepository,
)
from basis.modules.training.public import (
    Planning,
)


def planning() -> Planning:
    return Planning(
        DjangoPlanRepository(owner_date),
        write_authorization(),
        TrainingUnitOfWork,
        DjangoClock(),
        owner_date,
    )
