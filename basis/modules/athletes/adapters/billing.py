"""Read-only athlete-owned billing identity projection."""

from uuid import UUID

from basis.shared.identifiers import AccountId
from daily_trainning_app.models import User as Athlete

from ..application.billing import BillingProfile


class DjangoBillingProfiles:
    def get(self, owner: AccountId) -> BillingProfile | None:
        row = Athlete.objects.filter(account_id=owner).first()
        return BillingProfile(owner, row.public_id, row.email_verified) if row else None

    def owner_for(self, public_id: UUID) -> AccountId | None:
        row = Athlete.objects.filter(public_id=public_id, account__isnull=False).first()
        return AccountId(row.account_id) if row and row.account_id is not None else None
