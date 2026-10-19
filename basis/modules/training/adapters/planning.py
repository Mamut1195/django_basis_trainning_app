"""Planning persistence over stable Django tables and validated model hooks."""

from dataclasses import fields
from datetime import date

from basis.shared.identifiers import (
    AccountId,
    CycleId,
    GoalId,
    LineageId,
    PlanId,
    PlannedSessionId,
    Revision,
)
from training.models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
)

from ..application.planning import AddCycle, ScheduleSession
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
)
from .django import block_state, save_validated
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
        row.executions.exists(),
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
    def snapshot(self, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot:
        query = TrainingPlan.objects.filter(owner_id=owner, pk=plan)
        row = (query.select_for_update() if lock else query).first()
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
            PlannedSessionId(id)
            for id in Session.objects.filter(planned__plan_id=plan).values_list(
                "planned_id", flat=True
            )
            if id is not None
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
            item = PlannedSession.objects.create(
                owner_id=owner,
                plan=row,
                cycle=cycles[scheduled.cycle_key],
                title=scheduled.title,
                date=scheduled.date,
                notes=scheduled.notes,
            )
            save_prescription(item, scheduled.blocks)
        return plan_header(row)

    def save_goal(self, owner: AccountId, data: GoalData) -> GoalId:
        values = {field.name: getattr(data, field.name) for field in fields(GoalData)}
        row = Goal.objects.create(owner_id=owner, **values)
        return GoalId(row.pk)

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
        row = (query.select_for_update() if lock else query).first()
        if row is None:
            raise PlanningUnavailable
        return scheduled_state(row)

    def reschedule(self, current: ScheduledState, date: date) -> ScheduledState:
        row = PlannedSession.objects.get(pk=current.id, owner_id=current.owner)
        row.date, row.revision = date, int(current.revision) + 1
        save_validated(row)
        return scheduled_state(row)

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        return tuple(
            scheduled_state(row)
            for row in PlannedSession.objects.filter(
                owner_id=owner, date__gte=start, date__lte=end
            ).order_by("date", "pk")
        )
