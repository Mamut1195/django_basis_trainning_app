"""Only empty-account initialization is needed before the billing migration."""

from typing import Protocol

from basis.shared.identifiers import AccountId


class BillingEnrollment(Protocol):
    def enroll(self, account: AccountId) -> None: ...
