"""Empty billing account initialization; commercial policy remains for ARCH-06."""

from basis.modules.billing.adapters.models import BillingAccount
from basis.shared.identifiers import AccountId


class DjangoBillingEnrollment:
    def enroll(self, account: AccountId) -> None:
        BillingAccount.objects.create(owner_id=account)
