"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.accounts.adapters.django import (
    DjangoAccounts,
    DjangoRateWindows,
    DjangoVerification,
)
from basis.modules.accounts.public import Identity
from basis.modules.athletes.adapters.enrollment import DjangoAthleteEnrollment
from basis.modules.billing.adapters.enrollment import DjangoBillingEnrollment


def identity() -> Identity:
    return Identity(
        DjangoAccounts(),
        DjangoAthleteEnrollment(),
        DjangoBillingEnrollment(),
        DjangoVerification(),
        DjangoRateWindows(),
        DjangoUnitOfWork,
        DjangoClock(),
    )
