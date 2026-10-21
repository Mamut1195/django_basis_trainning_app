"""Public values for selecting the athlete's current plans and goals."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, GoalId, PlanId


@dataclass(frozen=True)
class PlanChoice:
    pk: PlanId
    title: str
    version: int


@dataclass(frozen=True)
class GoalSummary:
    title: str
    sport: str
    priority: str
    target_value: Decimal | None
    target_unit: str
    target_date: date | None
    baseline_value: Decimal | None
    baseline_date: date | None


class TrainingPresentation(Protocol):
    def plans(self, owner: AccountId) -> tuple[PlanChoice, ...]: ...
    def goal_choices(self, owner: AccountId) -> tuple[tuple[GoalId, str], ...]: ...
    def goals(self, owner: AccountId) -> tuple[GoalSummary, ...]: ...


@dataclass(frozen=True)
class PlanSummary:
    pk: int
    owner_id: int
    title: str


class PlanSummaries(Protocol):
    def read(self, owner: AccountId, plan: int) -> PlanSummary: ...
