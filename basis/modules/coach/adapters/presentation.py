"""Coach-owned usage dashboard read adapter."""

from basis.shared.identifiers import AccountId

from ..application.presentation import UsageSummary
from .models import UsagePeriod


class DjangoCoachPresentation:
    def usage(self, owner: AccountId) -> UsageSummary | None:
        row = UsagePeriod.objects.filter(owner_id=owner).order_by("-pk").first()
        return UsageSummary(row.short_count, row.plan_count) if row else None
