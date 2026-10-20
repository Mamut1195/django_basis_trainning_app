"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.modules.training.adapters.planning import (
    DjangoPlanRepository,
)
from basis.modules.training.public import (
    Planning,
)


def planning() -> Planning:
    return Planning(DjangoPlanRepository(), write_authorization(), DjangoUnitOfWork, DjangoClock())
