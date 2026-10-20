"""Public values for selecting the athlete's current plans and goals."""

from dataclasses import dataclass
from typing import Protocol

from basis.shared.identifiers import AccountId, GoalId, PlanId


@dataclass(frozen=True)
class PlanChoice:
    pk: PlanId
    title: str
    version: int


class TrainingPresentation(Protocol):
    def plans(self, owner: AccountId) -> tuple[PlanChoice, ...]: ...
    def goal_choices(self, owner: AccountId) -> tuple[tuple[GoalId, str], ...]: ...
