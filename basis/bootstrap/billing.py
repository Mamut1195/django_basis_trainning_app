"""Compose billing repositories, profile contract, bounded Polar gateway and clock."""

from collections.abc import Mapping

from django.conf import settings

from basis.bootstrap.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.athletes.adapters.billing import DjangoBillingProfiles
from basis.modules.billing.adapters.authorization import DjangoWriteAuthorization
from basis.modules.billing.adapters.django import DjangoBillingRepository, DjangoReceipts
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.billing.adapters.polar import PolarGateway, Requester, request
from basis.modules.billing.public import Billing, OwnerBilling, Webhooks
from basis.shared.identifiers import AccountId


def _request(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
    return request(
        method,
        path,
        token=settings.POLAR_ACCESS_TOKEN,
        product_id=settings.POLAR_PRODUCT_ID,
        sandbox=settings.POLAR_SANDBOX,
        json=json,
    )


def billing(requester: Requester | None = None) -> Billing:
    return Billing(
        DjangoBillingRepository(),
        DjangoBillingProfiles(),
        PolarGateway(requester or _request, settings.POLAR_PRODUCT_ID, settings.PUBLIC_URL),
        DjangoUnitOfWork,
        DjangoClock(),
        settings.POLAR_PRODUCT_ID,
        settings.DEVELOPMENT_ACCESS,
    )


def webhooks(requester: Requester | None = None) -> Webhooks:
    return Webhooks(billing(requester), DjangoReceipts())


def write_authorization() -> DjangoWriteAuthorization:
    return DjangoWriteAuthorization(billing())


def account_row(owner: int) -> BillingAccount:
    billing().ensure(OwnerBilling(AccountId(owner)))
    return BillingAccount.objects.get(owner_id=owner)


def mark_pending(owner: int) -> None:
    billing().mark_pending(OwnerBilling(AccountId(owner)))
