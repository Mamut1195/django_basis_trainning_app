from functools import partial

from django.conf import settings

from basis.adapters.django.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.athletes.adapters.billing import DjangoBillingProfiles
from basis.modules.billing.adapters.authorization import DjangoWriteAuthorization
from basis.modules.billing.adapters.django import DjangoBillingRepository, DjangoReceipts
from basis.modules.billing.adapters.polar import PolarGateway, Requester, request
from basis.modules.billing.public import Billing, Webhooks


def billing(requester: Requester | None = None) -> Billing:
    return Billing(
        DjangoBillingRepository(),
        DjangoBillingProfiles(),
        PolarGateway(
            requester
            or partial(
                request,
                token=settings.POLAR_ACCESS_TOKEN,
                product_id=settings.POLAR_PRODUCT_ID,
                sandbox=settings.POLAR_SANDBOX,
            ),
            settings.POLAR_PRODUCT_ID,
            settings.PUBLIC_URL,
        ),
        DjangoUnitOfWork,
        DjangoClock(),
        settings.POLAR_PRODUCT_ID,
        settings.DEVELOPMENT_ACCESS,
    )


def webhooks(requester: Requester | None = None) -> Webhooks:
    return Webhooks(billing(requester), DjangoReceipts())


def write_authorization() -> DjangoWriteAuthorization:
    return DjangoWriteAuthorization(billing())
