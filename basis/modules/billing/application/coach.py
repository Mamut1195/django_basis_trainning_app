"""Read and lock commercial state without exposing billing persistence."""

from typing import Protocol

from basis.shared.identifiers import AccountId

from ..domain.records import BillingState


class CoachBilling(Protocol):
    def lock(self, owner: AccountId) -> BillingState | None: ...

    def get(self, owner: AccountId) -> BillingState | None: ...
