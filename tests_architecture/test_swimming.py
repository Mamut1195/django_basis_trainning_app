"""Independent analytical swimming examples under the frozen local Metrics clause."""

from datetime import date
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.domain.execution import (
    DurationProtocol,
    IntervalData,
    Metric,
    MetricName,
)
from basis.modules.training.domain.manual import (
    ManualInvalid,
    ParentState,
    SessionParent,
    validate_interval,
)
from basis.modules.training.domain.progress import ProgressBlock, ProgressSession, report
from basis.modules.training.domain.sports import (
    VARIABLES,
    InvalidSportMetrics,
    pace_seconds,
    validate_sport_metrics,
)
from basis.shared.identifiers import AccountId, Revision, SessionId


class SwimmingTests(TestCase):
    def test_analytical_literals_half_even_and_error_bound(self) -> None:
        # Independent hand calculations: t[s] * 100 / d[m], not another production call.
        for duration, distance, expected in (
            ("1200", "800", "150.00"),
            ("100", "50", "200.00"),
            ("1", "3", "33.33"),
            ("1", "32", "3.12"),  # 3.125 -> half-even, not half-up.
            ("0", "800", "0.00"),
            ("1", "1000000", "0.00"),
        ):
            with self.subTest(duration=duration, distance=distance):
                result = pace_seconds(Decimal(distance), Decimal(duration), per_metres=100)
                self.assertEqual(result, Decimal(expected))
                assert result is not None
                exact = Decimal(duration) * 100 / Decimal(distance)
                self.assertLessEqual(abs(result - exact), Decimal("0.005"))

    def test_unknown_zero_scaling_and_inverse_distance(self) -> None:
        for distance, duration in (
            (None, None),
            (None, Decimal(0)),
            (Decimal(800), None),
            (Decimal(0), Decimal(1200)),
            (Decimal(0), Decimal(0)),
        ):
            self.assertIsNone(pace_seconds(distance, duration, per_metres=100))
        for factor in (Decimal("0.01"), Decimal(1), Decimal(7), Decimal(100)):
            self.assertEqual(
                pace_seconds(Decimal(800) * factor, Decimal(1200) * factor, per_metres=100),
                Decimal("150.00"),
            )
        self.assertEqual(pace_seconds(Decimal(1600), Decimal(1200), 100), Decimal("75.00"))
        self.assertEqual(pace_seconds(Decimal(800), Decimal(2400), 100), Decimal("300.00"))
        self.assertEqual(pace_seconds(Decimal(800), Decimal(1200)), Decimal("1500.00"))

    def test_every_numeric_swimming_boundary_and_integer_counts(self) -> None:
        self.assertEqual(validate_sport_metrics("swimming", ()), ())
        for name, spec in VARIABLES["swimming"].items():
            if spec.kind == "text":
                continue
            for value in (Decimal(0), Decimal(spec.maximum)):
                metric = Metric(MetricName(name), value)
                self.assertEqual(validate_sport_metrics("swimming", (metric,)), (metric,))
            for invalid_value in (
                Decimal(-1),
                Decimal(spec.maximum + 1),
                Decimal("NaN"),
                Decimal("Infinity"),
                Decimal("-Infinity"),
                "True",
            ):
                with (
                    self.subTest(name=name, value=invalid_value),
                    self.assertRaises(InvalidSportMetrics),
                ):
                    validate_sport_metrics("swimming", (Metric(MetricName(name), invalid_value),))
        for name in (MetricName.LAPS, MetricName.STROKES):
            with self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("swimming", (Metric(name, Decimal("1.5")),))

    def test_text_compatibility_optional_hr_and_inconsistent_hr(self) -> None:
        for name in (MetricName.STROKE, MetricName.DRILL):
            self.assertEqual(
                validate_sport_metrics("swimming", (Metric(name, "  Estilo libre propio  "),)),
                (Metric(name, "Estilo libre propio"),),
            )
            for invalid in (Decimal(1), "x" * 501):
                with self.assertRaises(InvalidSportMetrics):
                    validate_sport_metrics("swimming", (Metric(name, invalid),))
        metrics = (
            Metric(MetricName.DISTANCE_M, Decimal(800)),
            Metric(MetricName.DURATION_SECONDS, Decimal(1200)),
            Metric(MetricName.POOL_LENGTH_M, Decimal(25)),
            Metric(MetricName.LAPS, Decimal(31)),  # No forced pool*lap equality.
        )
        self.assertEqual(validate_sport_metrics("swimming", metrics), metrics)
        with self.assertRaises(InvalidSportMetrics):
            validate_sport_metrics(
                "swimming",
                (
                    Metric(MetricName.HEART_RATE_BPM, Decimal(160)),
                    Metric(MetricName.MAX_HEART_RATE_BPM, Decimal(150)),
                ),
            )
        with self.assertRaises(InvalidSportMetrics):
            validate_sport_metrics("swimming", (Metric(MetricName.POWER_W, Decimal(1)),))

    def test_interval_rest_and_repetitions_do_not_modify_elapsed_pace(self) -> None:
        parent = ParentState(
            SessionParent(SessionId(UUID(int=814))), AccountId(1), date(2026, 10, 26), Revision(1)
        )
        for rest in (None, 0, 60):
            row = IntervalData(
                repetitions=4,
                rest_seconds=60,
                actual_rest_seconds=rest,
                actual=(
                    Metric(MetricName.DURATION_SECONDS, Decimal(100)),
                    Metric(MetricName.DISTANCE_M, Decimal(50)),
                ),
            )
            validate_interval("swimming", parent, row)
            self.assertEqual(pace_seconds(Decimal(50), Decimal(100), 100), Decimal("200.00"))
        for row in (
            IntervalData(repetitions=True),
            IntervalData(repetitions=0),
            IntervalData(repetitions=1001),
            IntervalData(rest_seconds=-1),
            IntervalData(actual_rest_seconds=True),
        ):
            with self.assertRaises(ManualInvalid):
                validate_interval("swimming", parent, row)

    def test_pure_completed_block_authority_and_laps_only_unknown(self) -> None:
        def result(actual: tuple[Metric, ...], completed: bool = True) -> Decimal | None:
            rows = (
                ProgressSession(
                    SessionId(UUID(int=814)),
                    completed,
                    DurationProtocol.ELAPSED,
                    blocks=(ProgressBlock("swimming", actual),),
                ),
            )
            progress = report(rows, (), date(2026, 10, 26))
            if not completed:
                self.assertEqual(progress.sessions, 0)
                self.assertEqual(progress.sports, ())
                return None
            return progress.sports[0].distance_m

        laps = (
            Metric(MetricName.LAPS, Decimal(32)),
            Metric(MetricName.POOL_LENGTH_M, Decimal(25)),
        )
        self.assertIsNone(result(laps))
        self.assertEqual(result((*laps, Metric(MetricName.DISTANCE_M, Decimal(700)))), Decimal(700))
        self.assertEqual(result((Metric(MetricName.DISTANCE_M, Decimal(0)),)), Decimal(0))
        self.assertIsNone(result((Metric(MetricName.DISTANCE_M, Decimal(800)),), False))
