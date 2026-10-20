"""Pure planning rules and workflows with deterministic clock and memory storage."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import TracebackType
from typing import Self
from unittest import TestCase
from uuid import UUID

from basis.modules.training.application.planning import (
    AddCycle,
    CycleCreationContext,
    ScheduleCreationContext,
    ScheduleSession,
)
from basis.modules.training.public import (
    BlockData,
    CreatePlan,
    CycleDefinition,
    CycleKind,
    GoalData,
    IntervalData,
    InvalidPlanning,
    Metric,
    MetricName,
    PlanDefinition,
    PlanHeader,
    Planning,
    PlanningUnavailable,
    PlanSnapshot,
    RescheduleSession,
    RevisePlan,
    ScheduledDefinition,
    ScheduledState,
    StrengthData,
    validate_definition,
    validate_goal,
    validate_prescription,
    validate_schedule,
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
from tests_architecture.planning_contract import PlanningContract

TODAY = date(2026, 10, 19)
OWNER = AccountId(1)
BLOCK = BlockData("running", "Run", target=(Metric(MetricName.DISTANCE_M, Decimal(0)),))


def definition(goal: GoalId) -> PlanDefinition:
    start, end = TODAY - timedelta(days=2), TODAY + timedelta(days=6)
    return PlanDefinition(
        goal,
        "Base",
        start,
        end,
        cycles=(
            CycleDefinition("ma", None, CycleKind.MACRO, "Macro", start, end),
            CycleDefinition("me", "ma", CycleKind.MESO, "Meso", start, end),
            CycleDefinition("mi", "me", CycleKind.MICRO, "Micro", start, end),
        ),
        sessions=(
            ScheduledDefinition("mi", "executed", TODAY, (BLOCK,)),
            ScheduledDefinition("mi", "future", TODAY + timedelta(days=1), (BLOCK,)),
            ScheduledDefinition("mi", "past", TODAY - timedelta(days=1), (BLOCK,)),
        ),
    )


class MemoryPlans:
    def __init__(self) -> None:
        self.rows: dict[PlanId, PlanSnapshot] = {}
        self.goal_owners: dict[GoalId, AccountId] = {GoalId(1): OWNER}
        self.schedules: dict[PlannedSessionId, ScheduledState] = {}

    def goal_owner(self, goal: GoalId) -> AccountId | None:
        return self.goal_owners.get(goal)

    def snapshot(self, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot:
        row = self.rows.get(plan)
        if row is None or row.header.owner != owner:
            raise PlanningUnavailable
        return row

    def create(
        self, owner: AccountId, data: PlanDefinition, previous: PlanHeader | None
    ) -> PlanHeader:
        id = PlanId(len(self.rows) + 1)
        header = PlanHeader(
            id,
            owner,
            previous.lineage if previous else LineageId(UUID(int=int(id))),
            previous.version + 1 if previous else 1,
            previous.id if previous else None,
        )
        schedules: list[ScheduledDefinition] = []
        for item in data.sessions:
            sid = PlannedSessionId(len(self.schedules) + 1)
            item = replace(item, source_id=sid)
            cycle = next(c for c in data.cycles if c.key == item.cycle_key)
            self.schedules[sid] = ScheduledState(sid, owner, id, Revision(1), item, cycle, False)
            schedules.append(item)
        if previous:
            self.rows[previous.id] = replace(self.rows[previous.id], has_successor=True)
        self.rows[id] = PlanSnapshot(
            header, replace(data, sessions=tuple(schedules)), frozenset(), False
        )
        return header

    def save_goal(self, owner: AccountId, data: GoalData) -> GoalId:
        raise NotImplementedError

    def cycle_context(self, command: AddCycle) -> CycleCreationContext:
        plan = self.snapshot(command.owner, command.plan, lock=False)
        parent = next(
            (cycle for cycle in plan.definition.cycles if cycle.key == str(command.parent)), None
        )
        return CycleCreationContext(
            plan.definition.start_date, plan.definition.end_date, parent, True, plan.has_successor
        )

    def schedule_context(self, command: ScheduleSession) -> ScheduleCreationContext:
        plan = self.snapshot(command.owner, command.plan, lock=False)
        cycle = next(cycle for cycle in plan.definition.cycles if cycle.key == str(command.cycle))
        return ScheduleCreationContext(cycle, True, plan.has_successor)

    def add_cycle(self, command: AddCycle) -> CycleId:
        raise NotImplementedError

    def schedule(self, command: ScheduleSession) -> PlannedSessionId:
        raise NotImplementedError

    def scheduled(self, owner: AccountId, id: PlannedSessionId, *, lock: bool) -> ScheduledState:
        row = self.schedules.get(id)
        if row is None or row.owner != owner:
            raise PlanningUnavailable
        return row

    def reschedule(self, current: ScheduledState, date: date) -> ScheduledState:
        data = replace(current.definition, date=date)
        validate_schedule(data, current.cycle)
        result = replace(current, definition=data, revision=Revision(current.revision + 1))
        self.schedules[current.id] = result
        return result

    def calendar(self, owner: AccountId, start: date, end: date) -> tuple[ScheduledState, ...]:
        return tuple(
            s
            for s in self.schedules.values()
            if s.owner == owner and start <= s.definition.date <= end
        )

    def mark_executed(self, id: PlannedSessionId) -> None:
        row = self.schedules[id]
        self.schedules[id] = replace(row, has_executions=True)
        plan = self.rows[row.plan]
        self.rows[row.plan] = replace(plan, executed=plan.executed | {id})


class MemoryWork:
    def __init__(self, repository: MemoryPlans) -> None:
        self.repository = repository
        self.before = dict(repository.rows), dict(repository.schedules)
        self.committed = False

    def __enter__(self) -> Self:
        return self

    def commit(self) -> None:
        self.committed = True

    def __exit__(
        self,
        kind: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if kind or not self.committed:
            self.repository.rows, self.repository.schedules = self.before


class Clock:
    def today(self) -> date:
        return TODAY

    def now(self) -> datetime:
        return datetime(2026, 10, 19, tzinfo=timezone.utc)


class Authorization:
    def __init__(self) -> None:
        self.allowed = True

    def require(self, owner: AccountId) -> None:
        if not self.allowed:
            raise PermissionError


class PlanningTests(PlanningContract, TestCase):
    repository: MemoryPlans

    def setUp(self) -> None:
        self.repository = MemoryPlans()
        self.authorization = Authorization()
        self.owner, self.definition = OWNER, definition(GoalId(1))
        self.service = Planning(
            self.repository, self.authorization, lambda: MemoryWork(self.repository), Clock()
        )
        self.count_plans = lambda: len(self.repository.rows)
        self.mark_executed = self.repository.mark_executed

    def test_stale_executed_and_foreign_rescheduling_never_changes_revision(self) -> None:
        plan = self.service.create(CreatePlan(self.owner, self.definition))
        current = self.repository.calendar(self.owner, TODAY, TODAY)[0]
        command = RescheduleSession(self.owner, current.id, TODAY + timedelta(days=1), Revision(0))
        with self.assertRaises(InvalidPlanning):
            self.service.reschedule(command)
        self.mark_executed(current.id)
        with self.assertRaises(InvalidPlanning):
            self.service.reschedule(replace(command, revision=Revision(1)))
        with self.assertRaises(PlanningUnavailable):
            self.service.reschedule(replace(command, owner=AccountId(2), revision=Revision(1)))
        assert self.repository.snapshot(self.owner, plan.id, lock=False).header.version == 1

    def test_write_authorization_precedes_revision(self) -> None:
        self.authorization.allowed = False
        with self.assertRaises(PermissionError):
            self.service.revise(RevisePlan(self.owner, PlanId(999)))


class PlanningPolicyTests(TestCase):
    def test_manual_empty_draft_has_no_proposal_count_or_year_limit(self) -> None:
        validate_definition(PlanDefinition(GoalId(1), "Draft", TODAY, TODAY + timedelta(days=500)))

    def test_cycle_hierarchy_and_dates_rejected(self) -> None:
        data = definition(GoalId(1))
        for invalid in (
            replace(data, end_date=TODAY - timedelta(days=3)),
            replace(data, cycles=data.cycles[:2] + (replace(data.cycles[2], parent="ma"),)),
            replace(
                data,
                cycles=data.cycles[:2]
                + (replace(data.cycles[2], end_date=TODAY + timedelta(days=7)),),
            ),
        ):
            with self.assertRaises(InvalidPlanning):
                validate_definition(invalid)

    def test_actual_zero_is_forbidden_but_target_zero_is_preserved(self) -> None:
        validate_prescription((BLOCK,))
        for block in (
            replace(BLOCK, actual=BLOCK.target),
            replace(BLOCK, sets=(StrengthData(exercise=1, actual_reps=0),)),
            replace(BLOCK, intervals=(IntervalData(actual_rest_seconds=0),)),
        ):
            with self.assertRaises(InvalidPlanning):
                validate_prescription((block,))

    def test_goal_optional_zero_still_requires_unit_and_baseline_date(self) -> None:
        data = GoalData("Goal", "running", "primary", None, None, None, "", None, "")
        validate_goal(data)
        with self.assertRaises(InvalidPlanning):
            validate_goal(replace(data, target_value=Decimal(0)))
        with self.assertRaises(InvalidPlanning):
            validate_goal(replace(data, baseline_value=Decimal(0), target_unit="m"))


class PermissiveWrites(MemoryPlans):
    """Writers deliberately do not validate business policy."""

    def __init__(self) -> None:
        super().__init__()
        data = definition(GoalId(1))
        self.cycle_read = CycleCreationContext(data.start_date, data.end_date, None, True)
        self.schedule_read = ScheduleCreationContext(data.cycles[-1], True)
        self.writes: list[str] = []

    def cycle_context(self, command: AddCycle) -> CycleCreationContext:
        return self.cycle_read

    def schedule_context(self, command: ScheduleSession) -> ScheduleCreationContext:
        return self.schedule_read

    def add_cycle(self, command: AddCycle) -> CycleId:
        self.writes.append("cycle")
        return CycleId(100)

    def schedule(self, command: ScheduleSession) -> PlannedSessionId:
        self.writes.append("schedule")
        return PlannedSessionId(100)

    def reschedule(self, current: ScheduledState, date: date) -> ScheduledState:
        self.writes.append("reschedule")
        result = replace(
            current,
            definition=replace(current.definition, date=date),
            revision=Revision(current.revision + 1),
        )
        self.schedules[current.id] = result
        return result


class PlanningIndependentValidationTests(TestCase):
    def setUp(self) -> None:
        self.repository = PermissiveWrites()
        self.authorization = Authorization()
        self.service = Planning(
            self.repository, self.authorization, lambda: MemoryWork(self.repository), Clock()
        )
        self.data = definition(GoalId(1))
        self.header = self.service.create(CreatePlan(OWNER, self.data))

    def test_invalid_cycle_is_rejected_before_permissive_writer(self) -> None:
        valid = self.data.cycles[0]
        for invalid in (
            replace(valid, kind=CycleKind.MESO),
            replace(valid, end_date=self.data.end_date + timedelta(days=1)),
        ):
            with self.subTest(cycle=invalid), self.assertRaises(InvalidPlanning):
                self.service.add_cycle(AddCycle(OWNER, self.header.id, invalid))
        self.assertEqual(self.repository.writes, [])
        self.service.add_cycle(AddCycle(OWNER, self.header.id, valid))
        self.assertEqual(self.repository.writes, ["cycle"])

    def test_invalid_schedule_is_rejected_before_permissive_writer(self) -> None:
        valid = self.data.sessions[0]
        command = ScheduleSession(OWNER, self.header.id, CycleId(1), valid)
        with self.assertRaises(InvalidPlanning):
            self.service.schedule(
                replace(command, data=replace(valid, date=self.data.end_date + timedelta(days=1)))
            )
        self.repository.schedule_read = replace(self.repository.schedule_read, same_plan=False)
        with self.assertRaises(InvalidPlanning):
            self.service.schedule(command)
        self.assertEqual(self.repository.writes, [])
        self.repository.schedule_read = replace(self.repository.schedule_read, same_plan=True)
        self.service.schedule(command)
        self.assertEqual(self.repository.writes, ["schedule"])

    def test_reschedule_policy_and_revision_precede_permissive_writer(self) -> None:
        current = next(iter(self.repository.schedules.values()))
        command = RescheduleSession(
            OWNER, current.id, self.data.end_date + timedelta(days=1), current.revision
        )
        with self.assertRaises(InvalidPlanning):
            self.service.reschedule(command)
        self.assertEqual(self.repository.writes, [])
        self.assertEqual(self.repository.schedules[current.id], current)
        with self.assertRaisesRegex(InvalidPlanning, "cambi"):
            self.service.reschedule(replace(command, revision=Revision(0)))
        self.authorization.allowed = False
        with self.assertRaises(PermissionError):
            self.service.reschedule(replace(command, revision=Revision(0)))
        self.authorization.allowed = True
        self.service.reschedule(replace(command, date=current.definition.date))
        self.assertEqual(self.repository.writes, ["reschedule"])

    def test_replaced_plan_rejects_cycle_and_schedule_before_permissive_writer(self) -> None:
        self.repository.cycle_read = replace(self.repository.cycle_read, has_successor=True)
        self.repository.schedule_read = replace(self.repository.schedule_read, has_successor=True)
        with self.assertRaisesRegex(InvalidPlanning, "posterior"):
            self.service.add_cycle(AddCycle(OWNER, self.header.id, self.data.cycles[0]))
        with self.assertRaisesRegex(InvalidPlanning, "posterior"):
            self.service.schedule(
                ScheduleSession(OWNER, self.header.id, CycleId(1), self.data.sessions[0])
            )
        self.assertEqual(self.repository.writes, [])

    def test_private_create_requires_access_but_preview_still_rolls_back_without_access(
        self,
    ) -> None:
        before = dict(self.repository.rows)
        self.authorization.allowed = False
        with self.assertRaises(PermissionError):
            self.service.create(CreatePlan(OWNER, self.data))
        self.assertEqual(self.repository.rows, before)
        self.service.preview(CreatePlan(OWNER, self.data))
        self.assertEqual(self.repository.rows, before)

    def test_foreign_goal_and_previous_are_rejected_before_permissive_writer(self) -> None:
        from unittest.mock import patch

        before = dict(self.repository.rows)
        self.repository.goal_owners[self.data.goal] = AccountId(2)
        with self.assertRaises(InvalidPlanning):
            self.service.create(CreatePlan(OWNER, self.data))
        self.repository.goal_owners[self.data.goal] = OWNER
        snapshot = self.repository.rows[self.header.id]
        foreign = replace(snapshot, header=replace(snapshot.header, owner=AccountId(2)))
        with (
            patch.object(self.repository, "snapshot", return_value=foreign),
            self.assertRaises(InvalidPlanning),
        ):
            self.service.create(CreatePlan(OWNER, self.data, self.header.id))
        self.assertEqual(self.repository.rows, before)
