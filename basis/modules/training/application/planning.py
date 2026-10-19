"""Planning coordination through concrete ports and explicit units of work."""

from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol

from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId, PlannedSessionId, Revision
from basis.shared.ports import Clock, UnitOfWork

from ..domain.planning import (
    CycleDefinition,
    GoalData,
    PlanDefinition,
    PlanHeader,
    PlanSnapshot,
    ScheduledDefinition,
    ScheduledState,
    require_reschedulable,
    revision_definition,
    validate_definition,
    validate_goal,
)
from .execution import WriteAuthorization


@dataclass(frozen=True)
class CreatePlan:
    owner: AccountId
    definition: PlanDefinition
    previous: PlanId | None = None


@dataclass(frozen=True)
class RevisePlan:
    owner: AccountId
    plan: PlanId


@dataclass(frozen=True)
class SaveGoal:
    owner: AccountId
    data: GoalData


@dataclass(frozen=True)
class AddCycle:
    owner: AccountId
    plan: PlanId
    data: CycleDefinition
    parent: CycleId | None = None


@dataclass(frozen=True)
class ScheduleSession:
    owner: AccountId
    plan: PlanId
    cycle: CycleId
    data: ScheduledDefinition


@dataclass(frozen=True)
class RescheduleSession:
    owner: AccountId
    session: PlannedSessionId
    date: date
    revision: Revision


class PlanRepository(Protocol):
    def snapshot(self, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot: ...
    def create(
        self, owner: AccountId, data: PlanDefinition, previous: PlanHeader | None
    ) -> PlanHeader: ...
    def save_goal(self, owner: AccountId, data: GoalData) -> GoalId: ...
    def add_cycle(self, command: AddCycle) -> CycleId: ...
    def schedule(self, command: ScheduleSession) -> PlannedSessionId: ...
    def scheduled(
        self, owner: AccountId, id: PlannedSessionId, *, lock: bool
    ) -> ScheduledState: ...
    def reschedule(self, current: ScheduledState, date: date) -> ScheduledState: ...
    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]: ...


class Planning:
    def __init__(
        self,
        repository: PlanRepository,
        authorization: WriteAuthorization,
        uow: Callable[[], UnitOfWork],
        clock: Clock,
    ) -> None:
        self.repository, self.authorization, self.uow, self.clock = (
            repository,
            authorization,
            uow,
            clock,
        )

    def create(self, command: CreatePlan) -> PlanHeader:
        # Creation is also used by rollback-only AI validation. Entry adapters retain
        # existing write-access checks; persistence always scopes goal/previous to owner.
        with self.uow() as work:
            previous = (
                self.repository.snapshot(command.owner, command.previous, lock=False).header
                if command.previous is not None
                else None
            )
            validate_definition(command.definition)
            result = self.repository.create(command.owner, command.definition, previous)
            work.commit()
            return result

    def preview(self, command: CreatePlan) -> None:
        with self.uow():
            self.create(command)

    def revise(self, command: RevisePlan) -> PlanHeader:
        with self.uow() as work:
            self.authorization.require(command.owner)
            snapshot = self.repository.snapshot(command.owner, command.plan, lock=True)
            definition = revision_definition(snapshot, self.clock.today())
            validate_definition(definition)
            result = self.repository.create(command.owner, definition, snapshot.header)
            work.commit()
            return result

    def save_goal(self, command: SaveGoal) -> GoalId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            validate_goal(command.data)
            result = self.repository.save_goal(command.owner, command.data)
            work.commit()
            return result

    def add_cycle(self, command: AddCycle) -> CycleId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self.repository.add_cycle(command)
            work.commit()
            return result

    def schedule(self, command: ScheduleSession) -> PlannedSessionId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self.repository.schedule(command)
            work.commit()
            return result

    def reschedule(self, command: RescheduleSession) -> ScheduledState:
        with self.uow() as work:
            self.authorization.require(command.owner)
            current = self.repository.scheduled(command.owner, command.session, lock=True)
            require_reschedulable(current, command.revision)
            result = self.repository.reschedule(current, command.date)
            work.commit()
            return result

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        return self.repository.calendar(owner, start, end)
