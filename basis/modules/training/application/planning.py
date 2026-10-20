"""Planning coordination through concrete ports and explicit units of work."""

from dataclasses import dataclass, replace
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
    require_current_plan,
    require_plan_ownership,
    require_reschedulable,
    revision_definition,
    validate_cycle,
    validate_definition,
    validate_goal,
    validate_schedule,
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


@dataclass(frozen=True)
class CycleCreationContext:
    plan_start: date
    plan_end: date
    parent: CycleDefinition | None
    same_plan: bool
    has_successor: bool = False


@dataclass(frozen=True)
class ScheduleCreationContext:
    cycle: CycleDefinition
    same_plan: bool
    has_successor: bool = False


class PlanRepository(Protocol):
    def goal_owner(self, goal: GoalId) -> AccountId | None: ...
    def snapshot(self, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot: ...
    def create(
        self, owner: AccountId, data: PlanDefinition, previous: PlanHeader | None
    ) -> PlanHeader: ...
    def save_goal(self, owner: AccountId, data: GoalData) -> GoalId: ...
    def cycle_context(self, command: AddCycle) -> CycleCreationContext: ...
    def add_cycle(self, command: AddCycle) -> CycleId: ...
    def schedule_context(self, command: ScheduleSession) -> ScheduleCreationContext: ...
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

    def _create_validated(self, command: CreatePlan) -> PlanHeader:
        previous = (
            self.repository.snapshot(command.owner, command.previous, lock=False).header
            if command.previous is not None
            else None
        )
        validate_definition(command.definition)
        require_plan_ownership(
            command.owner, self.repository.goal_owner(command.definition.goal), previous
        )
        return self.repository.create(command.owner, command.definition, previous)

    def create(self, command: CreatePlan) -> PlanHeader:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self._create_validated(command)
            work.commit()
            return result

    def preview(self, command: CreatePlan) -> None:
        # Validation deliberately has no commercial guard and never commits.
        with self.uow():
            self._create_validated(command)

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
            context = self.repository.cycle_context(command)
            require_current_plan(context.has_successor)
            data = replace(
                command.data, parent=context.parent.key if context.parent is not None else None
            )
            validate_cycle(
                data,
                context.plan_start,
                context.plan_end,
                context.parent,
                same_plan=context.same_plan,
            )
            result = self.repository.add_cycle(command)
            work.commit()
            return result

    def schedule(self, command: ScheduleSession) -> PlannedSessionId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            context = self.repository.schedule_context(command)
            require_current_plan(context.has_successor)
            validate_schedule(command.data, context.cycle, same_plan=context.same_plan)
            result = self.repository.schedule(command)
            work.commit()
            return result

    def reschedule(self, command: RescheduleSession) -> ScheduledState:
        with self.uow() as work:
            self.authorization.require(command.owner)
            current = self.repository.scheduled(command.owner, command.session, lock=True)
            require_reschedulable(current, command.revision)
            validate_schedule(replace(current.definition, date=command.date), current.cycle)
            result = self.repository.reschedule(current, command.date)
            work.commit()
            return result

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        return self.repository.calendar(owner, start, end)
