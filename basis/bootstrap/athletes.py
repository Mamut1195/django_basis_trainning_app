"""Composition factories; input conversion belongs to adapters."""

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.bootstrap.billing import write_authorization
from basis.modules.athletes.adapters.billing import DjangoBillingProfiles
from basis.modules.athletes.adapters.django import (
    DjangoAthleteRecords,
)
from basis.modules.athletes.adapters.personal_access import (
    DjangoPersonalAuthorization,
    DjangoPersonalIdentities,
)
from basis.modules.athletes.public import (
    Athletes,
    PersonalAuthorization,
)


def athletes() -> Athletes:
    return Athletes(
        DjangoAthleteRecords(), write_authorization(), DjangoUnitOfWork, personal_authorization()
    )


def personal_authorization() -> DjangoPersonalAuthorization:
    return DjangoPersonalAuthorization(
        PersonalAuthorization(DjangoPersonalIdentities(DjangoBillingProfiles()))
    )
