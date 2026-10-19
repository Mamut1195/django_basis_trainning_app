"""Account locking contract shared with budget coordination."""

from typing import Protocol

from basis.shared.identifiers import AccountId


class AccountLocks(Protocol):
    def lock(self, owner: AccountId) -> None: ...
