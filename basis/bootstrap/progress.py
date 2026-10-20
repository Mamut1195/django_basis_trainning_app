"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.modules.training.public import (
    Progress,
)


def progress() -> Progress:
    return Progress(
        DjangoProgressRepository(), write_authorization(), DjangoUnitOfWork, DjangoClock()
    )
