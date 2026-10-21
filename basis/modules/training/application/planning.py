"""Planning coordination through concrete ports and explicit units of work."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Callable, Protocol

from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId, PlannedSessionId, Revision
from basis.shared.ports import Clock, UnitOfWork

from ..domain.planning import (
    CycleDefinition,
    GoalData,
    InvalidPlanning,
    PlanDefinition,
    PlanHeader,
    PlanSnapshot,
    ScheduledDefinition,
    ScheduledState,
    ScheduleStatus,
    require_current_plan,
    require_plan_ownership,
    require_reason,
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
    reason: str = ""


@dataclass(frozen=True)
class RevisePlan:
    owner: AccountId
    plan: PlanId
    reason: str = ""


@dataclass(frozen=True)
class RestorePlan:
    owner: AccountId
    head: PlanId
    target: PlanId
    reason: str


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
    reason: str = ""
    cycle: CycleId | None = None


@dataclass(frozen=True)
class ChangeScheduledSession:
    owner: AccountId
    session: PlannedSessionId
    revision: Revision
    reason: str
    status: ScheduleStatus = ScheduleStatus.SCHEDULED
    replacement: ScheduledDefinition | None = None


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
    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]: ...
    def annotate_change(
        self,
        plan: PlanHeader,
        reason: str,
        kind: str,
        day: date,
        restored_from: PlanId | None = None,
    ) -> None: ...


class Planning:
    def __init__(
        self,
        repository: PlanRepository,
        authorization: WriteAuthorization,
        uow: Callable[[], UnitOfWork],
        clock: Clock,
        local_date: Callable[[AccountId, datetime], date] | None = None,
    ) -> None:
        self.repository, self.authorization, self.uow, self.clock = (
            repository,
            authorization,
            uow,
            clock,
        )
        self.local_date = local_date

    def today(self, owner: AccountId) -> date:
        return self.local_date(owner, self.clock.now()) if self.local_date else self.clock.today()

    def _create_validated(self, command: CreatePlan) -> PlanHeader:
        previous = (
            self.repository.snapshot(command.owner, command.previous, lock=True).header
            if command.previous is not None
            else None
        )
        if command.previous is not None:
            require_current_plan(
                self.repository.snapshot(command.owner, command.previous, lock=False).has_successor
            )
        validate_definition(command.definition)
        require_plan_ownership(
            command.owner, self.repository.goal_owner(command.definition.goal), previous
        )
        reason = require_reason(command.reason) if previous else ""
        result = self.repository.create(command.owner, command.definition, previous)
        if previous:
            self.repository.annotate_change(result, reason, "replace", self.today(command.owner))
        return result

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
            reason = require_reason(command.reason)
            definition = revision_definition(snapshot, self.today(command.owner))
            validate_definition(definition)
            result = self.repository.create(command.owner, definition, snapshot.header)
            self.repository.annotate_change(result, reason, "revise", self.today(command.owner))
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
            # Always acquire the aggregate before the child (also used by start/manual writes).
            current = self.repository.scheduled(command.owner, command.session, lock=True)
            require_reschedulable(current, command.revision)
            reason = require_reason(command.reason)
            snapshot = self.repository.snapshot(command.owner, current.plan, lock=True)
            cycle = current.cycle
            if command.cycle is not None:
                cycle = next(
                    (c for c in snapshot.definition.cycles if c.key == str(command.cycle)), cycle
                )
                if cycle.key != str(command.cycle):
                    raise InvalidPlanning("El microciclo destino no pertenece al plan.")
            candidate = replace(current.definition, date=command.date, cycle_key=cycle.key)
            validate_schedule(candidate, cycle)
            result = self._change(snapshot, current, candidate, reason, "move")
            work.commit()
            return result

    def _change(
        self,
        snapshot: PlanSnapshot,
        current: ScheduledState,
        candidate: ScheduledDefinition,
        reason: str,
        kind: str,
    ) -> ScheduledState:
        definition = revision_definition(snapshot, self.today(current.owner))
        # An explicit change may address an unexecuted past session as well.
        sessions = tuple(s for s in definition.sessions if s.source_id != current.id) + (candidate,)
        definition = replace(definition, sessions=sessions)
        validate_definition(definition, allow_drafts=True)
        header = self.repository.create(current.owner, definition, snapshot.header)
        self.repository.annotate_change(header, reason, kind, self.today(current.owner))
        saved = self.repository.snapshot(current.owner, header.id, lock=False)
        item = next(
            s
            for s in saved.definition.sessions
            if s.origin_id == (current.definition.origin_id or current.id)
        )
        assert item.source_id is not None
        return self.repository.scheduled(current.owner, item.source_id, lock=False)

    def change_session(self, command: ChangeScheduledSession) -> ScheduledState:
        with self.uow() as work:
            self.authorization.require(command.owner)
            if command.replacement is not None and command.status != ScheduleStatus.SCHEDULED:
                raise InvalidPlanning("Cancelar u omitir no admite una sustitución.")
            current = self.repository.scheduled(command.owner, command.session, lock=True)
            require_reschedulable(current, command.revision)
            reason = require_reason(command.reason)
            snapshot = self.repository.snapshot(command.owner, current.plan, lock=True)
            candidate = replace(
                command.replacement or current.definition,
                source_id=current.id,
                origin_id=current.definition.origin_id,
                cycle_key=current.definition.cycle_key,
                date=current.definition.date,
                status=command.status,
            )
            kind = "replace" if command.replacement else command.status.value
            result = self._change(snapshot, current, candidate, reason, kind)
            work.commit()
            return result

    def restore(self, command: RestorePlan) -> PlanHeader:
        with self.uow() as work:
            self.authorization.require(command.owner)
            head = self.repository.snapshot(command.owner, command.head, lock=True)
            require_current_plan(head.has_successor)
            target = self.repository.snapshot(command.owner, command.target, lock=False)
            if target.header.lineage != head.header.lineage:
                raise InvalidPlanning("La versión elegida no pertenece a este plan.")
            reason = require_reason(command.reason)
            # Never rewind results: only future intent without executions is restored.
            definition = revision_definition(
                replace(target, has_successor=False), self.today(command.owner)
            )
            validate_definition(definition)
            result = self.repository.create(command.owner, definition, head.header)
            self.repository.annotate_change(
                result, reason, "restore", self.today(command.owner), target.header.id
            )
            work.commit()
            return result

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        return self.repository.calendar(owner, start, end)
