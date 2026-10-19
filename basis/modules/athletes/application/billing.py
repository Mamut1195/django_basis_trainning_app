"""Narrow public identity projection needed by commercial use cases."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from basis.shared.identifiers import AccountId


@dataclass(frozen=True)
class BillingProfile:
    owner: AccountId
    public_id: UUID
    email_verified: bool


class BillingProfiles(Protocol):
    def get(self, owner: AccountId) -> BillingProfile | None: ...

    def owner_for(self, public_id: UUID) -> AccountId | None: ...
