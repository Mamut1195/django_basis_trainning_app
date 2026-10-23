"""Independent elapsed-pace examples, using the frozen local Metrics clause."""

from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from basis.modules.training.domain.execution import Metric, MetricName
from basis.modules.training.domain.sports import (
    InvalidSportMetrics,
    pace_seconds,
    validate_sport_metrics,
)


class RunningPaceTests(TestCase):
    def test_independent_examples_and_rounding_error(self) -> None:
        for duration, distance, expected in (
            ("1500", "5000", "300.00"),
            ("1800", "5000", "360.00"),
            ("60", "400", "150.00"),
            ("1", "3", "333.33"),
        ):
            with self.subTest(duration=duration, distance=distance):
                result = pace_seconds(Decimal(distance), Decimal(duration))
                self.assertEqual(result, Decimal(expected))
                assert result is not None
                exact = Decimal(duration) * 1000 / Decimal(distance)
                self.assertLessEqual(abs(result - exact), Decimal("0.005"))

    def test_unknown_zero_and_positive_scaling(self) -> None:
        for distance, duration in ((None, None), (None, Decimal(0)), (Decimal(0), Decimal(60))):
            self.assertIsNone(pace_seconds(distance, duration))
        self.assertIsNone(pace_seconds(Decimal(5000), None))
        self.assertEqual(pace_seconds(Decimal(5000), Decimal(0)), Decimal("0.00"))
        for factor in (Decimal("0.1"), Decimal(1), Decimal(7), Decimal(100)):
            self.assertEqual(
                pace_seconds(Decimal(5000) * factor, Decimal(1800) * factor), Decimal("360.00")
            )
        self.assertEqual(pace_seconds(Decimal(10000), Decimal(1800)), Decimal("180.00"))
        self.assertEqual(pace_seconds(Decimal(5000), Decimal(3600)), Decimal("720.00"))

    def test_pause_validation_and_no_deduction(self) -> None:
        metrics = (
            Metric(MetricName.DURATION_SECONDS, Decimal(1800)),
            Metric(MetricName.DISTANCE_M, Decimal(5000)),
            Metric(MetricName.PAUSE_SECONDS, Decimal(120)),
        )
        self.assertEqual(validate_sport_metrics("running", metrics), metrics)
        self.assertEqual(pace_seconds(Decimal(5000), Decimal(1800)), Decimal("360.00"))
        with self.assertRaises(InvalidSportMetrics):
            validate_sport_metrics(
                "running",
                (
                    Metric(MetricName.DURATION_SECONDS, Decimal(5)),
                    Metric(MetricName.PAUSE_SECONDS, Decimal(6)),
                ),
            )

    def test_scoped_running_text_files_use_lf(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "basis/modules/training/domain/sports.py",
            "basis/modules/training/adapters/templatetags/training_tags.py",
            "basis/modules/training/adapters/templates/training/execution/_metrics.html",
            "basis/modules/training/adapters/templates/training/execution/_intervals.html",
            "tests_architecture/test_running.py",
            "tests/regression/test_running.py",
            "tests/regression/test_running_browser.py",
            "tests/regression/test_endurance.py",
            "docs/RUNNING_VERIFICATION.md",
        ):
            with self.subTest(path=relative):
                content = (root / relative).read_bytes()
                self.assertNotIn(b"\r", content)
                self.assertTrue(content.endswith(b"\n"))
