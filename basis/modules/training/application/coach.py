"""Owner-scoped training context and planning gateway for coach proposals."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..domain.planning import PlanDefinition
from ..domain.progress import ProgressReport, StageRecovery


@dataclass(frozen=True)
class CoachScope:
    start: Date
    end: Date
    session_limit: int
    goal_limit: int
    sessions_truncated: bool = False
    goals_truncated: bool = False
    # The minimal projection does not consult the unbounded effective calendar.
    adherence_included: bool = False


@dataclass(frozen=True)
class CoachSessionEvidence:
    id: str
    date: Date | None
    sports: tuple[str, ...]
    protocol: str
    duration_seconds: int | None
    reported_rpe: Decimal | None
    internal_load: Decimal | None
    previous_date: Date | None
    days_since_previous: int | None
    consecutive_days: int | None
    sessions_on_date: int | None
    stage_recovery: StageRecovery | None = None


@dataclass(frozen=True)
class CoachGoal:
    id: GoalId
    title: str
    sport: str
    target_date: Date | None
    target_value: Decimal | None
    target_unit: str
    baseline_value: Decimal | None
    baseline_date: Date | None
    priority: str


@dataclass(frozen=True)
class CoachRecentSession:
    date: Date
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
    start_date: Date
    end_date: Date


@dataclass(frozen=True)
class TrainingCoachContext:
    goals: tuple[CoachGoal, ...]
    recent: tuple[CoachRecentSession, ...]
    progress: ProgressReport
    scope: CoachScope | None = None
    evidence: tuple[CoachSessionEvidence, ...] = ()


@dataclass(frozen=True)
class CoachVariables:
    sport: str
    variables: tuple[tuple[str, str], ...]


class TrainingCoachContexts(Protocol):
    def read(self, owner: AccountId, today: Date) -> TrainingCoachContext: ...
    def read_for_acceptance(
        self, owner: AccountId, today: Date, base_plan: PlanId | None
    ) -> TrainingCoachContext:
        """Caller holds account/UoW and athlete locks; lock goals before base plan."""
        ...

    def selected(self, owner: AccountId, plan: PlanId) -> CoachBasePlan | None: ...
    def variables(self) -> tuple[CoachVariables, ...]: ...


class CoachPlanning(Protocol):
    def preview(self, owner: AccountId, definition: PlanDefinition) -> None: ...
    def create(
        self, owner: AccountId, definition: PlanDefinition, previous: PlanId | None
    ) -> PlanId: ...
    def has_successor(self, owner: AccountId, previous: PlanId) -> bool: ...
