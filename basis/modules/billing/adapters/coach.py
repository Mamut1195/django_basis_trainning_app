"""Existing billing-row lock for account budget coordination."""

from basis.shared.identifiers import AccountId
from training.models import BillingAccount

from ..domain.records import BillingState
from .django import billing_state


class DjangoCoachBilling:
    def lock(self, owner: AccountId) -> BillingState | None:
        row = BillingAccount.objects.select_for_update().filter(owner_id=owner).first()
        return billing_state(row) if row is not None else None

    def get(self, owner: AccountId) -> BillingState | None:
        row = BillingAccount.objects.filter(owner_id=owner).first()
        return billing_state(row) if row is not None else None
