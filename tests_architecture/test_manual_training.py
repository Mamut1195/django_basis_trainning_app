"""Pure cases run against ports that intentionally do not validate business rules."""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Self
from unittest import TestCase
from uuid import UUID

from basis.modules.athletes.public import RMReference
from basis.modules.training.application.manual import (
    AddBlock,
    BlockContext,
    IntervalContext,
    ManualTraining,
    SaveBlockMetrics,
    SaveInterval,
    SaveStrength,
    StrengthContext,
)
from basis.modules.training.domain.execution import (
    IntervalData,
    Metric,
    MetricName,
    StrengthData,
    Unavailable,
)
from basis.modules.training.domain.manual import (
    ManualInvalid,
    ManualSessionData,
    ParentRef,
    ParentState,
    PlannedParent,
    SessionParent,
)
from basis.modules.training.domain.planning import InvalidPlanning
from basis.modules.training.domain.sports import InvalidSportMetrics
from basis.shared.identifiers import (
    AccountId,
    BlockId,
    ExerciseId,
    IntervalId,
    MeasuredRMId,
    PlannedSessionId,
    Revision,
    SessionId,
    StrengthSetId,
)
from tests_architecture.manual_contract import ManualContract


@dataclass
class MemoryState:
    parents: dict[ParentRef, ParentState] = field(default_factory=dict)
    blocks: dict[BlockId, BlockContext] = field(default_factory=dict)
    strengths: dict[StrengthSetId, StrengthContext] = field(default_factory=dict)
    intervals: dict[IntervalId, IntervalContext] = field(default_factory=dict)
    metrics: dict[BlockId, tuple[Metric, ...]] = field(default_factory=dict)
    sessions: dict[SessionId, ManualSessionData] = field(default_factory=dict)
    next_id: int = 1


class MemoryRepository:
    def __init__(self) -> None:
        self.state = MemoryState()
        self.failures: set[str] = set()
        self.locks: list[ParentRef] = []

    def parent(self, ref: ParentRef, *, lock: bool) -> ParentState | None:
        if lock:
            self.locks.append(ref)
        return self.state.parents.get(ref)

    def block(self, id: BlockId) -> BlockContext | None:
        return self.state.blocks.get(id)

    def strength(self, id: StrengthSetId) -> StrengthContext | None:
        return self.state.strengths.get(id)

    def interval(self, id: IntervalId) -> IntervalContext | None:
        return self.state.intervals.get(id)

    def block_count(self, ref: ParentRef) -> int:
        return sum(row.parent == ref for row in self.state.blocks.values())

    def create_session(self, id: SessionId, owner: AccountId, data: ManualSessionData) -> None:
        self.state.sessions[id] = data
        self.state.parents[SessionParent(id)] = ParentState(
            SessionParent(id), owner, data.date, Revision(1)
        )

    def add_block(self, ref: ParentRef, sport: str, title: str, order: int) -> BlockId:
        if "add_block" in self.failures:
            raise OSError("block failure")
        id = BlockId(self.state.next_id)
        self.state.next_id += 1
        self.state.blocks[id] = BlockContext(id, ref, sport)
        return id

    def advance(self, ref: ParentRef, revision: Revision) -> None:
        self.state.parents[ref] = replace(self.state.parents[ref], revision=revision)

    def save_metrics(self, block: BlockId, metrics: tuple[Metric, ...], *, actual: bool) -> None:
        if "save_metrics" in self.failures:
            raise OSError("metrics failure")
        self.state.metrics[block] = metrics

    def strength_count(self, block: BlockId) -> int:
        return sum(row.block == block for row in self.state.strengths.values())

    def interval_count(self, block: BlockId) -> int:
        return sum(row.block == block for row in self.state.intervals.values())

    def save_strength(
        self, block: BlockId, data: StrengthData, row: StrengthSetId | None, order: int | None
    ) -> StrengthSetId:
        id = row if row is not None else StrengthSetId(len(self.state.strengths) + 1)
        self.state.strengths[id] = StrengthContext(block, data)
        return id

    def save_interval(
        self, block: BlockId, data: IntervalData, row: IntervalId | None, order: int | None
    ) -> IntervalId:
        id = row if row is not None else IntervalId(len(self.state.intervals) + 1)
        self.state.intervals[id] = IntervalContext(block, data)
        return id


class MemoryWork:
    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository
        self.original = deepcopy(repository.state)
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
        if kind is not None or not self.committed:
            self.repository.state = self.original


class Authorization:
    def __init__(self) -> None:
        self.denied = False

    def require(self, owner: AccountId) -> None:
        if self.denied:
            raise PermissionError("Write access denied")


class Ids:
    def new(self) -> SessionId:
        return SessionId(UUID(int=1))


class References:
    reference: RMReference | None = None

    def get(self, reference: MeasuredRMId) -> RMReference | None:
        return self.reference


class PureManualTests(ManualContract, TestCase):
    def setUp(self) -> None:
        self.repository = MemoryRepository()
        self.references = References()
        self.owner, self.other = AccountId(1), AccountId(2)
        self.authorization = Authorization()
        self.service = ManualTraining(
            self.repository,
            lambda: MemoryWork(self.repository),
            self.authorization,
            Ids(),
            self.references,
        )
        self.counts = lambda: (
            len(self.repository.state.sessions),
            len(self.repository.state.blocks),
        )
        self.revision = lambda ref: self.repository.state.parents[ref].revision
        self.first_block = lambda id: next(
            row.id
            for row in self.repository.state.blocks.values()
            if row.parent == SessionParent(id)
        )
        self.fail_write = self.repository.failures.add

    def test_locked_revision_and_child_failure_share_one_unit_of_work(self) -> None:
        id = self.create()
        self.service.save_metrics(
            SaveBlockMetrics(
                self.owner,
                self.first_block(id),
                Revision(1),
                (Metric(MetricName.DURATION_SECONDS, Decimal(0)),),
            )
        )
        self.assertEqual(self.repository.locks, [SessionParent(id)])
        self.assertEqual(self.repository.state.metrics[self.first_block(id)][0].value, Decimal(0))

    def test_completed_and_frozen_parents_rejected_with_permissive_repository(self) -> None:
        id = self.create()
        ref = SessionParent(id)
        self.repository.state.parents[ref] = replace(
            self.repository.state.parents[ref], completed=True
        )
        with self.assertRaises(ManualInvalid):
            self.service.inspect(self.owner, ref)
        with self.assertRaises(Unavailable):
            self.service.inspect_metadata(self.owner, ref)
        planned = PlannedParent(PlannedSessionId(10))
        self.repository.state.parents[planned] = ParentState(
            planned, self.owner, date.today(), Revision(1), frozen=True
        )
        with self.assertRaises(ManualInvalid):
            self.service.add_block(AddBlock(self.owner, planned, Revision(1), "running", "Run"))
        self.assertEqual(self.repository.state.parents[planned].revision, 1)

    def test_manual_blocks_do_not_inherit_offline_block_count_limit(self) -> None:
        id = self.create()
        for revision in range(1, 35):
            self.service.add_block(
                AddBlock(self.owner, SessionParent(id), Revision(revision), "running", "Run")
            )
        self.assertEqual(self.counts(), (1, 35))

    def test_invalid_metrics_roll_back_revision_before_any_child_write(self) -> None:
        id = self.create()
        with self.assertRaises(InvalidSportMetrics):
            self.service.save_metrics(
                SaveBlockMetrics(
                    self.owner,
                    self.first_block(id),
                    Revision(1),
                    (Metric(MetricName.DISTANCE_M, Decimal(-1)),),
                )
            )
        self.assertEqual(self.revision(SessionParent(id)), 1)
        self.assertFalse(self.repository.state.metrics)

    def strength_block(self) -> BlockId:
        id = self.create()
        block = self.first_block(id)
        self.repository.state.blocks[block] = replace(
            self.repository.state.blocks[block], sport="strength"
        )
        return block

    def test_strength_sport_and_prescribed_results_are_core_rules(self) -> None:
        id = self.create()
        with self.assertRaises(ManualInvalid):
            self.service.save_strength(
                SaveStrength(self.owner, self.first_block(id), Revision(1), StrengthData(1))
            )
        block = self.strength_block()
        planned = PlannedParent(PlannedSessionId(10))
        self.repository.state.parents[planned] = ParentState(
            planned, self.owner, date.today(), Revision(1)
        )
        self.repository.state.blocks[block] = replace(
            self.repository.state.blocks[block], parent=planned
        )
        with self.assertRaises(InvalidPlanning):
            self.service.save_strength(
                SaveStrength(self.owner, block, Revision(1), StrengthData(1, actual_reps=0))
            )

    def test_measured_rm_ownership_compatibility_and_date_are_core_rules(self) -> None:
        block = self.strength_block()
        self.references.reference = RMReference(self.other, ExerciseId(1), date(2025, 1, 1))
        with self.assertRaises(ValueError):
            self.service.save_strength(
                SaveStrength(self.owner, block, Revision(1), StrengthData(1, rm_reference=4))
            )
        self.assertFalse(self.repository.state.strengths)
        self.assertEqual(next(iter(self.repository.state.parents.values())).revision, 1)

    def test_executed_prescription_fields_immutable_even_if_input_adapter_permits_them(
        self,
    ) -> None:
        block = self.strength_block()
        parent = self.repository.state.blocks[block].parent
        self.repository.state.parents[parent] = replace(
            self.repository.state.parents[parent], from_prescription=True
        )
        row = StrengthSetId(3)
        original = StrengthData(1, target_kg=Decimal(30))
        self.repository.state.strengths[row] = StrengthContext(block, original)
        with self.assertRaises(ManualInvalid):
            self.service.save_strength(
                SaveStrength(
                    self.owner, block, Revision(1), replace(original, target_kg=Decimal(40)), row
                )
            )
        self.service.save_strength(
            SaveStrength(
                self.owner, block, Revision(1), replace(original, actual_kg=Decimal(0)), row
            )
        )
        self.assertEqual(self.repository.state.strengths[row].data.actual_kg, Decimal(0))

    def test_interval_prescription_and_sport_guard_are_core_rules(self) -> None:
        block = self.strength_block()
        with self.assertRaises(ManualInvalid):
            self.service.save_interval(SaveInterval(self.owner, block, Revision(1), IntervalData()))
        self.repository.state.blocks[block] = replace(
            self.repository.state.blocks[block], sport="running"
        )
        parent = self.repository.state.blocks[block].parent
        self.repository.state.parents[parent] = replace(
            self.repository.state.parents[parent], from_prescription=True
        )
        row = IntervalId(3)
        original = IntervalData(target=(Metric(MetricName.DURATION_SECONDS, Decimal(30)),))
        self.repository.state.intervals[row] = IntervalContext(block, original)
        with self.assertRaises(ManualInvalid):
            self.service.save_interval(
                SaveInterval(self.owner, block, Revision(1), replace(original, repetitions=2), row)
            )

    def test_core_rejects_nonfinite_and_excess_precision_without_orm_validation(self) -> None:
        block = self.strength_block()
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("1.001")):
            with self.subTest(value=value), self.assertRaises(ManualInvalid):
                self.service.save_strength(
                    SaveStrength(self.owner, block, Revision(1), StrengthData(1, actual_kg=value))
                )
        self.assertFalse(self.repository.state.strengths)
        self.assertEqual(next(iter(self.repository.state.parents.values())).revision, 1)

    def test_child_row_from_another_block_cannot_be_reassigned(self) -> None:
        block = self.strength_block()
        row = StrengthSetId(3)
        self.repository.state.strengths[row] = StrengthContext(BlockId(99), StrengthData(1))
        with self.assertRaises(Unavailable):
            self.service.save_strength(
                SaveStrength(self.owner, block, Revision(1), StrengthData(1), row)
            )
        self.assertEqual(self.repository.state.strengths[row].block, 99)
        self.assertEqual(next(iter(self.repository.state.parents.values())).revision, 1)

    def test_write_authorization_is_enforced_by_case_not_only_web_decorator(self) -> None:
        self.authorization.denied = True
        with self.assertRaises(PermissionError):
            self.create()
        self.assertEqual(self.counts(), (0, 0))
        self.authorization.denied = False
        id = self.create()
        self.authorization.denied = True
        with self.assertRaises(PermissionError):
            self.service.add_block(
                AddBlock(self.owner, SessionParent(id), Revision(1), "running", "Run")
            )
        self.assertEqual(self.revision(SessionParent(id)), 1)
        self.assertEqual(self.counts(), (1, 1))
