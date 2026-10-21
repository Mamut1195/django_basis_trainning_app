"""Owner-scoped training context and planning gateway for coach proposals."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..domain.planning import PlanDefinition
from ..domain.progress import ProgressReport


@dataclass(frozen=True)
class CoachGoal:
    id: GoalId
    title: str
    sport: str
    target_date: date | None
    target_value: Decimal | None
    target_unit: str
    baseline_value: Decimal | None
    baseline_date: date | None
    priority: str


@dataclass(frozen=True)
class CoachRecentSession:
    date: date
    duration_seconds: int | None
    duration_protocol: str
    rpe: Decimal | None
    sports: tuple[str, ...]
    id: str | None = None
    status: str | None = None
    planned: int | None = None


@dataclass(frozen=True)
class CoachBasePlan:
    id: PlanId
    title: str
    version: int
    goal_id: GoalId
    start_date: date
    end_date: date


@dataclass(frozen=True)
class TrainingCoachContext:
    goals: tuple[CoachGoal, ...]
    recent: tuple[CoachRecentSession, ...]
    progress: ProgressReport


@dataclass(frozen=True)
class CoachVariables:
    sport: str
    variables: tuple[tuple[str, str], ...]


class TrainingCoachContexts(Protocol):
    def read(self, owner: AccountId, today: date) -> TrainingCoachContext: ...
    def selected(self, owner: AccountId, plan: PlanId) -> CoachBasePlan | None: ...
    def variables(self) -> tuple[CoachVariables, ...]: ...


class CoachPlanning(Protocol):
    def preview(self, owner: AccountId, definition: PlanDefinition) -> None: ...
    def create(
        self, owner: AccountId, definition: PlanDefinition, previous: PlanId | None
    ) -> PlanId: ...
    def has_successor(self, owner: AccountId, previous: PlanId) -> bool: ...
