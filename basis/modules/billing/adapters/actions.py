"""Django input actions with explicitly injected billing and provider services."""

from collections.abc import Mapping

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from basis.bootstrap.billing import billing
from basis.modules.billing.adapters.polar import request, safe_provider_url
from basis.modules.billing.public import (
    Checkout,
    OwnerBilling,
    ProviderUnavailable,
    VerificationRequired,
)
from basis.shared.identifiers import AccountId

from .models import BillingAccount

__all__ = (
    "ProviderUnavailable",
    "checkout",
    "portal",
    "polar_request",
    "reconcile",
    "safe_provider_url",
)


def polar_request(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
    return request(
        method,
        path,
        token=settings.POLAR_ACCESS_TOKEN,
        product_id=settings.POLAR_PRODUCT_ID,
        sandbox=settings.POLAR_SANDBOX,
        json=json,
    )


def checkout(owner: AbstractUser) -> str:
    try:
        return billing(polar_request).checkout(Checkout(AccountId(owner.pk), owner.email))
    except VerificationRequired as exc:
        raise ValidationError(str(exc)) from None


def portal(owner: AbstractUser) -> str:
    try:
        return billing(polar_request).portal(OwnerBilling(AccountId(owner.pk)))
    except VerificationRequired as exc:
        raise ValidationError(str(exc)) from None


def reconcile(owner: AbstractUser) -> BillingAccount:
    billing(polar_request).reconcile(OwnerBilling(AccountId(owner.pk)))
    # Return the persisted account for the billing adapter presentation.
    return BillingAccount.objects.get(owner_id=owner.pk)
