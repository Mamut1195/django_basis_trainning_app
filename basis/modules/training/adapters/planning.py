"""Planning persistence over stable Django tables and validated model hooks."""

from collections.abc import Callable
from dataclasses import fields
from datetime import date, datetime

from basis.adapters.django.account_locks import lock_account
from basis.modules.training.adapters.models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    StrengthSet,
    TrainingPlan,
)
from basis.shared.identifiers import (
    AccountId,
    CycleId,
    GoalId,
    LineageId,
    PlanId,
    PlannedSessionId,
    Revision,
)

from ..application.planning import (
    AddCycle,
    CycleCreationContext,
    ScheduleCreationContext,
    ScheduleSession,
)
from ..domain.execution import BlockData, StrengthData
from ..domain.planning import (
    CycleDefinition,
    CycleKind,
    GoalData,
    PlanDefinition,
    PlanHeader,
    PlanningUnavailable,
    PlanSnapshot,
    ScheduledDefinition,
    ScheduledState,
    ScheduleStatus,
)
from .django import block_state, save_validated
from .locking import intent_executions, lock_plan, lock_scheduled
from .wire import encode_interval, encode_metrics


def goal_data(row: Goal) -> GoalData:
    return GoalData(
        row.title,
        row.sport,
        row.priority,
        row.baseline_value,
        row.baseline_date,
        row.target_date,
        row.description,
        row.target_value,
        row.target_unit,
    )


def cycle_definition(row: Cycle) -> CycleDefinition:
    return CycleDefinition(
        str(row.pk),
        str(row.parent_id) if row.parent_id is not None else None,
        CycleKind(row.kind),
        row.title,
        row.start_date,
        row.end_date,
        row.focus,
    )


def scheduled_definition(row: PlannedSession) -> ScheduledDefinition:
    return ScheduledDefinition(
        str(row.cycle_id),
        row.title,
        row.date,
        tuple(block_state(block) for block in row.blocks.all()),
        row.notes,
        PlannedSessionId(row.pk),
        PlannedSessionId(row.origin_id) if row.origin_id else None,
        ScheduleStatus(row.status),
    )


def plan_header(row: TrainingPlan) -> PlanHeader:
    return PlanHeader(
        PlanId(row.pk),
        AccountId(row.owner_id),
        LineageId(row.lineage),
        row.version,
        PlanId(row.previous_id) if row.previous_id is not None else None,
    )


def scheduled_state(row: PlannedSession) -> ScheduledState:
    return ScheduledState(
        PlannedSessionId(row.pk),
        AccountId(row.owner_id),
        PlanId(row.plan_id),
        Revision(row.revision),
        scheduled_definition(row),
        cycle_definition(row.cycle),
        intent_executions(row).exists(),
        TrainingPlan.objects.filter(previous_id=row.plan_id).exists(),
    )


def save_prescription(parent: PlannedSession, data: tuple[BlockData, ...]) -> None:
    for index, block in enumerate(data, 1):
        row = Block.objects.create(
            planned=parent,
            order=index,
            sport=block.sport,
            title=block.title,
            target=encode_metrics(block.target),
            actual=encode_metrics(block.actual),
            notes=block.notes,
        )
        for order, strength in enumerate(block.sets, 1):
            values = {
                field.name + "_id"
                if field.name in ("exercise", "rm_reference")
                else field.name: getattr(strength, field.name)
                for field in fields(StrengthData)
            }
            StrengthSet.objects.create(block=row, order=order, **values)
        for order, interval in enumerate(block.intervals, 1):
            Interval.objects.create(block=row, order=order, **encode_interval(interval))


class DjangoPlanRepository:
    def __init__(self, local_date: Callable[[AccountId, datetime], date] | None = None) -> None:
        self.local_date = local_date

    def goal_owner(self, goal: GoalId) -> AccountId | None:
        owner = Goal.objects.filter(pk=goal).values_list("owner_id", flat=True).first()
        return AccountId(owner) if owner is not None else None

    def snapshot(self, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot:
        query = TrainingPlan.objects.filter(owner_id=owner, pk=plan)
        if lock and query.exists():
            lock_plan(plan, query.db)
        row = query.first()
        if row is None:
            raise PlanningUnavailable
        definition = PlanDefinition(
            GoalId(row.goal_id),
            row.title,
            row.start_date,
            row.end_date,
            row.notes,
            tuple(cycle_definition(c) for c in row.cycles.all()),
            tuple(scheduled_definition(s) for s in row.sessions.all()),
        )
        executed = frozenset(
            PlannedSessionId(s.pk) for s in row.sessions.all() if intent_executions(s).exists()
        )
        return PlanSnapshot(
            plan_header(row),
            definition,
            executed,
            TrainingPlan.objects.filter(previous_id=plan).exists(),
        )

    def create(
        self, owner: AccountId, data: PlanDefinition, previous: PlanHeader | None
    ) -> PlanHeader:
        # Resolve the owned goal before insertion, preserving legacy proposal error mapping.
        lock_account(owner, TrainingPlan.objects.db)
        goal = Goal.objects.get(pk=data.goal, owner_id=owner)
        row = TrainingPlan(
            owner_id=owner,
            goal=goal,
            title=data.title,
            start_date=data.start_date,
            end_date=data.end_date,
            notes=data.notes,
        )
        if previous is not None:
            row.lineage, row.version, row.previous_id = (
                previous.lineage,
                previous.version + 1,
                previous.id,
            )
        save_validated(row)
        cycles: dict[str, Cycle] = {}
        for kind in CycleKind:
            for cycle in data.cycles:
                if cycle.kind == kind:
                    cycles[cycle.key] = Cycle.objects.create(
                        plan=row,
                        parent=cycles.get(cycle.parent) if cycle.parent is not None else None,
                        kind=cycle.kind.value,
                        title=cycle.title,
                        start_date=cycle.start_date,
                        end_date=cycle.end_date,
                        focus=cycle.focus,
                    )
        for scheduled in data.sessions:
            source = None
            if scheduled.source_id is not None:
                source = PlannedSession.objects.get(
                    pk=scheduled.source_id, owner_id=owner, plan__lineage=row.lineage
                )
            item = PlannedSession.objects.create(
                owner_id=owner,
                plan=row,
                cycle=cycles[scheduled.cycle_key],
                title=scheduled.title,
                date=scheduled.date,
                notes=scheduled.notes,
                origin_id=(source.origin_id or source.pk) if source else None,
                supersedes=source,
                status=scheduled.status.value,
                revision=source.revision + 1 if source else 1,
            )
            save_prescription(item, scheduled.blocks)
        return plan_header(row)

    def annotate_change(
        self,
        plan: PlanHeader,
        reason: str,
        kind: str,
        day: date,
        restored_from: PlanId | None = None,
    ) -> None:
        row = TrainingPlan.objects.get(pk=plan.id, owner_id=plan.owner)
        row.change_kind, row.change_reason = kind, reason
        row.changed_by_id, row.effective_on, row.restored_from_id = plan.owner, day, restored_from
        row.save()

    def save_goal(self, owner: AccountId, data: GoalData) -> GoalId:
        lock_account(owner, Goal.objects.db)
        values = {field.name: getattr(data, field.name) for field in fields(GoalData)}
        row = Goal.objects.create(owner_id=owner, **values)
        return GoalId(row.pk)

    def cycle_context(self, command: AddCycle) -> CycleCreationContext:
        plan = TrainingPlan.objects.get(pk=command.plan, owner_id=command.owner)
        lock_plan(plan.pk, plan._state.db or "default")
        parent = (
            Cycle.objects.get(pk=command.parent, plan__owner_id=command.owner)
            if command.parent is not None
            else None
        )
        return CycleCreationContext(
            plan.start_date,
            plan.end_date,
            cycle_definition(parent) if parent is not None else None,
            parent is None or parent.plan_id == plan.pk,
            TrainingPlan.objects.filter(previous_id=plan.pk).exists(),
        )

    def schedule_context(self, command: ScheduleSession) -> ScheduleCreationContext:
        plan = TrainingPlan.objects.get(pk=command.plan, owner_id=command.owner)
        lock_plan(plan.pk, plan._state.db or "default")
        cycle = Cycle.objects.get(pk=command.cycle, plan__owner_id=command.owner)
        return ScheduleCreationContext(
            cycle_definition(cycle),
            cycle.plan_id == plan.pk,
            TrainingPlan.objects.filter(previous_id=plan.pk).exists(),
        )

    def add_cycle(self, command: AddCycle) -> CycleId:
        plan = TrainingPlan.objects.get(pk=command.plan, owner_id=command.owner)
        parent = (
            Cycle.objects.get(pk=command.parent, plan__owner_id=command.owner)
            if command.parent is not None
            else None
        )
        data = command.data
        row = Cycle.objects.create(
            plan=plan,
            parent=parent,
            kind=data.kind.value,
            title=data.title,
            start_date=data.start_date,
            end_date=data.end_date,
            focus=data.focus,
        )
        return CycleId(row.pk)

    def schedule(self, command: ScheduleSession) -> PlannedSessionId:
        plan = TrainingPlan.objects.get(pk=command.plan, owner_id=command.owner)
        cycle = Cycle.objects.get(pk=command.cycle, plan__owner_id=command.owner)
        row = PlannedSession.objects.create(
            owner_id=command.owner,
            plan=plan,
            cycle=cycle,
            date=command.data.date,
            title=command.data.title,
            notes=command.data.notes,
        )
        return PlannedSessionId(row.pk)

    def scheduled(self, owner: AccountId, id: PlannedSessionId, *, lock: bool) -> ScheduledState:
        query = PlannedSession.objects.filter(pk=id, owner_id=owner)
        if lock and query.exists():
            lock_scheduled(id, query.db)
        row = query.first()
        if row is None:
            raise PlanningUnavailable
        return scheduled_state(row)

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        from .calendar import effective_sessions

        return tuple(
            scheduled_state(row)
            for row in effective_sessions(owner, self.local_date)
            if start <= row.date <= end
        )
