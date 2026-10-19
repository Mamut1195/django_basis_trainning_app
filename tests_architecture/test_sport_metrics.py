"""Sport units, absent values and related measurements without Django."""

import unittest
from decimal import Decimal

from basis.modules.training.domain.execution import Metric, MetricName
from basis.modules.training.domain.sports import (
    InvalidSportMetrics,
    internal_load,
    pace_seconds,
    validate_sport_metrics,
)


class SportMetricsTests(unittest.TestCase):
    def test_pace_and_internal_load_preserve_absence_and_zero(self) -> None:
        self.assertEqual(pace_seconds(Decimal(5000), Decimal(1500)), Decimal("300.00"))
        self.assertIsNone(pace_seconds(Decimal(0), Decimal(1500)))
        self.assertEqual(pace_seconds(Decimal(50), Decimal(0), 100), Decimal("0.00"))
        self.assertIsNone(internal_load(None, Decimal(5)))
        self.assertEqual(internal_load(600, Decimal(0)), Decimal("0.00"))
        self.assertEqual(internal_load(600, Decimal("5.5")), Decimal("55.00"))

    def test_sport_ranges_and_finite_values(self) -> None:
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal(-501), Decimal(9001)):
            with self.subTest(value=value), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", (Metric(MetricName.MAX_ALTITUDE_M, value),))
        with self.assertRaises(InvalidSportMetrics):
            validate_sport_metrics("swimming", (Metric(MetricName.LAPS, Decimal("1.5")),))
        with self.assertRaises(InvalidSportMetrics):
            validate_sport_metrics("strength", (Metric(MetricName.DISTANCE_M, Decimal(1)),))

    def test_related_measured_values(self) -> None:
        examples = (
            (
                Metric(MetricName.DURATION_SECONDS, Decimal(100)),
                Metric(MetricName.MOVING_SECONDS, Decimal(100)),
                Metric(MetricName.PAUSE_SECONDS, Decimal(1)),
            ),
            (
                Metric(MetricName.START_ALTITUDE_M, Decimal(100)),
                Metric(MetricName.MAX_ALTITUDE_M, Decimal(99)),
            ),
            (
                Metric(MetricName.HEART_RATE_BPM, Decimal(100)),
                Metric(MetricName.MAX_HEART_RATE_BPM, Decimal(99)),
            ),
            (Metric(MetricName.DIFFICULTY_SCALE, "SAC"),),
        )
        for values in examples:
            with self.subTest(values=values), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", values)
        self.assertEqual(
            validate_sport_metrics("running", (Metric(MetricName.SURFACE, " road "),)),
            (Metric(MetricName.SURFACE, "road"),),
        )
