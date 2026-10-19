"""Empty billing account initialization; commercial policy remains for ARCH-06."""

from basis.shared.identifiers import AccountId
from training.models import BillingAccount


class DjangoBillingEnrollment:
    def enroll(self, account: AccountId) -> None:
        BillingAccount.objects.create(owner_id=account)
