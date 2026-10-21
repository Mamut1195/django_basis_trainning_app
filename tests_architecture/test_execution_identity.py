"""Intention protection is a core rule, even with permissive persistence."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase

from basis.modules.training.domain.execution import (
    BlockData,
    IntervalData,
    InvalidExecution,
    Metric,
    MetricName,
    StrengthData,
)
from basis.modules.training.domain.execution_updates import reconcile_blocks
from basis.modules.training.domain.manual import require_interval_prescription
from basis.modules.training.public import RecordSession, SessionChanges, StartSession, Training
from tests_architecture.test_execution import (
    OWNER,
    PLAN,
    FakeAuthorization,
    FakeClock,
    FakeRepository,
    FakeWork,
    FixedIds,
)


class ExecutionIdentityPolicyTests(TestCase):
    def test_manual_and_sync_treat_metric_key_order_as_the_same_intention(self) -> None:
        target = (
            Metric(MetricName.DISTANCE_M, Decimal(1000)),
            Metric(MetricName.DURATION_SECONDS, Decimal(300)),
        )
        original = IntervalData(id=3, target=target)
        candidate = replace(original, target=tuple(reversed(target)))
        require_interval_prescription(original, candidate)
        block = BlockData("running", "A", id=2, intervals=(original,))
        reconcile_blocks((block,), (replace(block, intervals=(candidate,)),), frozen=True)

    def test_every_prescribed_semantic_field_is_frozen(self) -> None:
        original = StrengthData(1, id=11, source=8, target_reps=5, target_kg=Decimal(80))
        block = BlockData("strength", "A", id=2, sets=(original,), source=1)
        for candidate in (
            replace(original, exercise=2),
            replace(original, kind="failed"),
            replace(original, load_type="assisted"),
            replace(original, tempo="x"),
            replace(original, range_of_motion="partial"),
            replace(original, side="left"),
            replace(original, group="B"),
            replace(original, target_kg=Decimal(1)),
            replace(original, target_reps=99),
        ):
            with self.subTest(candidate=candidate), self.assertRaises(InvalidExecution):
                reconcile_blocks(
                    (block,),
                    (replace(block, sets=(candidate,)),),
                    frozen=True,
                )

    def test_actual_adaptation_and_legacy_identity_do_not_replace_intention(self) -> None:
        row = StrengthData(1, id=11, source=8, target_reps=5, target_kg=Decimal(80))
        block = BlockData("strength", "A", id=2, sets=(row,), source=1)
        actual = replace(
            row,
            id=None,
            source=None,
            actual_reps=4,
            actual_kg=Decimal(75),
            actual_exercise=2,
            adaptation_reason="Equipo distinto",
        )
        changed = reconcile_blocks(
            (block,), (replace(block, id=None, source=None, sets=(actual,)),), frozen=True
        )[0]
        self.assertEqual((changed.id, changed.sets[0].id, changed.sets[0].source), (2, 11, 8))
        self.assertEqual(changed.sets[0].exercise, 1)
        self.assertEqual(changed.sets[0].target_kg, Decimal(80))

    def test_unknown_identity_missing_rows_and_reason_are_rejected(self) -> None:
        row = StrengthData(1, id=11)
        block = BlockData("strength", "A", id=2, sets=(row,))
        for candidate in (
            replace(block, id=999),
            replace(block, sets=()),
            replace(block, sets=(replace(row, actual_kind="failed"),)),
        ):
            with self.assertRaises(InvalidExecution):
                reconcile_blocks((block,), (candidate,), frozen=True)


class ExecutionServiceIdentityTests(TestCase):
    def test_bulk_guard_runs_without_any_orm(self) -> None:
        repository = FakeRepository()
        service = Training(
            repository, lambda: FakeWork(repository), FakeAuthorization(), FakeClock(), FixedIds()
        )
        repository.planned = replace(
            repository.planned,
            blocks=(
                BlockData(
                    "strength", "A", sets=(StrengthData(1, target_reps=5, target_kg=Decimal(80)),)
                ),
            ),
        )
        state = service.start(StartSession(OWNER, PLAN))
        bad = replace(state.blocks[0], sets=(replace(state.blocks[0].sets[0], target_reps=99),))
        with self.assertRaises(InvalidExecution):
            service.record(RecordSession(OWNER, state.id, state.revision, SessionChanges((bad,))))
        self.assertEqual(repository.rows[state.id], state)
