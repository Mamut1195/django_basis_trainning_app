"""Focused cycling policies without Django, providers or inferred measurements."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.application.manual import (
    BlockContext,
    IntervalContext,
    ManualTraining,
    SaveBlockMetrics,
    SaveInterval,
)
from basis.modules.training.domain.execution import IntervalData, Metric, MetricName, Unavailable
from basis.modules.training.domain.manual import ManualInvalid, ParentState, SessionParent
from basis.modules.training.domain.sports import InvalidSportMetrics, validate_sport_metrics
from basis.shared.identifiers import AccountId, BlockId, IntervalId, Revision, SessionId
from tests_architecture.test_manual_training import (
    Authorization,
    Ids,
    MemoryRepository,
    MemoryWork,
    References,
)


class CyclingDomainTests(TestCase):
    def test_distance_duration_are_not_power_cadence_or_heart_rate(self) -> None:
        for duration, distance in ((600, 10000), (7200, 1000), (0, 0)):
            for environment in ("indoor", "outdoor"):
                with self.subTest(duration=duration, distance=distance, environment=environment):
                    metrics = (
                        Metric(MetricName.DURATION_SECONDS, Decimal(duration)),
                        Metric(MetricName.DISTANCE_M, Decimal(distance)),
                        Metric(MetricName.ENVIRONMENT, environment),
                    )
                    self.assertEqual(validate_sport_metrics("cycling", metrics), metrics)
        self.assertEqual(validate_sport_metrics("cycling", ()), ())
        for name in (MetricName.POWER_W, MetricName.CADENCE_RPM, MetricName.HEART_RATE_BPM):
            zero = (Metric(name, Decimal(0)),)
            self.assertEqual(validate_sport_metrics("cycling", zero), zero)

    def test_cycling_rejects_foreign_units_nonfinite_and_invalid_choices(self) -> None:
        for metric in (
            Metric(MetricName.POWER_W, "200 W"),
            Metric(MetricName.POWER_W, Decimal("NaN")),
            Metric(MetricName.POWER_W, Decimal(3001)),
            Metric(MetricName.CADENCE_RPM, Decimal(-1)),
            Metric(MetricName.CADENCE_RPM, Decimal(251)),
            Metric(MetricName.CADENCE_SPM, Decimal(80)),
            Metric(MetricName.HEART_RATE_BPM, Decimal(251)),
            Metric(MetricName.ENVIRONMENT, "Exterior"),
        ):
            with self.subTest(metric=metric), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("cycling", (metric,))

    def setUp(self) -> None:
        # Existing permissive repository contract proves the case, not fake validation.
        self.repository = MemoryRepository()
        self.owner, self.other = AccountId(813), AccountId(814)
        self.parent = SessionParent(SessionId(UUID(int=813)))
        self.block = BlockId(813)
        self.row = IntervalId(813)
        self.repository.state.parents[self.parent] = ParentState(
            self.parent, self.owner, date(2026, 10, 23), Revision(1), from_prescription=True
        )
        self.target = (Metric(MetricName.POWER_W, Decimal(200)),)
        self.repository.state.blocks[self.block] = BlockContext(
            self.block, self.parent, "cycling", self.target
        )
        self.original = IntervalData(
            repetitions=3, target=self.target, rest_seconds=0, target_rpe=Decimal(5)
        )
        self.repository.state.intervals[self.row] = IntervalContext(self.block, self.original)
        self.service = ManualTraining(
            self.repository,
            lambda: MemoryWork(self.repository),
            Authorization(),
            Ids(),
            References(),
        )

    def test_interval_actual_zero_does_not_change_prescribed_target_or_rest(self) -> None:
        actual = replace(
            self.original,
            actual=(Metric(MetricName.POWER_W, Decimal(0)),),
            actual_rest_seconds=0,
            actual_rpe=Decimal(0),
        )
        self.service.save_interval(
            SaveInterval(self.owner, self.block, Revision(1), actual, self.row)
        )
        saved = self.repository.state.intervals[self.row].data
        self.assertEqual(saved.target, self.target)
        self.assertEqual((saved.repetitions, saved.rest_seconds, saved.target_rpe), (3, 0, 5))
        self.assertEqual(saved.actual, (Metric(MetricName.POWER_W, Decimal(0)),))
        self.assertEqual((saved.actual_rest_seconds, saved.actual_rpe), (0, Decimal(0)))
        for changes in (
            {"target": (Metric(MetricName.POWER_W, Decimal(999)),)},
            {"repetitions": 99},
            {"rest_seconds": 99},
            {"target_rpe": Decimal(9)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ManualInvalid):
                self.service.save_interval(
                    SaveInterval(
                        self.owner, self.block, Revision(2), replace(saved, **changes), self.row
                    )
                )
        self.assertEqual(self.repository.state.intervals[self.row].data, saved)
        self.assertEqual(self.repository.state.parents[self.parent].revision, 2)

    def test_foreign_owner_reads_and_writes_roll_back_with_permissive_port(self) -> None:
        before = deepcopy(self.repository.state)
        with self.assertRaises(Unavailable):
            self.service.inspect(self.other, self.parent)
        with self.assertRaises(Unavailable):
            self.service.save_metrics(
                SaveBlockMetrics(
                    self.other,
                    self.block,
                    Revision(1),
                    (Metric(MetricName.POWER_W, Decimal(999)),),
                )
            )
        with self.assertRaises(Unavailable):
            self.service.save_interval(
                SaveInterval(self.other, self.block, Revision(1), self.original, self.row)
            )
        self.assertEqual(self.repository.state, before)
