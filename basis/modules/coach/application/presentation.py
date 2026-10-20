"""Usage counters exposed to the subscription dashboard."""

from dataclasses import dataclass
from typing import Protocol

from basis.shared.identifiers import AccountId


@dataclass(frozen=True)
class UsageSummary:
    short_count: int
    plan_count: int


class CoachPresentation(Protocol):
    def usage(self, owner: AccountId) -> UsageSummary | None: ...
