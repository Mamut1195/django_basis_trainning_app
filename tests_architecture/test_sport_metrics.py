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


class HikingMetricsTests(unittest.TestCase):
    def numeric_metrics(self, **values: str) -> tuple[Metric, ...]:
        return tuple(Metric(MetricName(key), Decimal(value)) for key, value in values.items())

    def test_elevation_balance_and_maximum_legs(self) -> None:
        valid: tuple[dict[str, str], ...] = (
            {},
            {"ascent_m": "0", "descent_m": "0"},
            {"start_altitude_m": "2000", "end_altitude_m": "2000"},
            {"start_altitude_m": "2000", "end_altitude_m": "2200", "ascent_m": "200"},
            {"start_altitude_m": "2200", "end_altitude_m": "2000", "descent_m": "200"},
            {"start_altitude_m": "2000", "max_altitude_m": "2300", "ascent_m": "300"},
            {"end_altitude_m": "2000", "max_altitude_m": "2300", "descent_m": "300"},
            {"max_altitude_m": "2300", "ascent_m": "0", "descent_m": "0"},
            {"start_altitude_m": "0", "end_altitude_m": "0", "ascent_m": "0"},
            {
                "start_altitude_m": "2000",
                "max_altitude_m": "2300",
                "end_altitude_m": "2100",
                "ascent_m": "400",
                "descent_m": "300",
            },
            {
                "start_altitude_m": "0",
                "max_altitude_m": "0",
                "end_altitude_m": "-10.25",
                "ascent_m": "0",
                "descent_m": "10.25",
            },
            {
                "start_altitude_m": "-20.10",
                "max_altitude_m": "10.25",
                "end_altitude_m": "-20.10",
                "ascent_m": "40.35",
                "descent_m": "40.35",
            },
            {
                "start_altitude_m": "-20.10",
                "end_altitude_m": "-10.05",
                "ascent_m": "10.05",
                "descent_m": "0",
            },
        )
        for values in valid:
            with self.subTest(values=values):
                metrics = self.numeric_metrics(**values)
                self.assertEqual(validate_sport_metrics("hiking", metrics), metrics)
        invalid = (
            {"start_altitude_m": "2000", "end_altitude_m": "2200", "ascent_m": "199.99"},
            {"start_altitude_m": "2200", "end_altitude_m": "2000", "descent_m": "199.99"},
            {"start_altitude_m": "2000", "max_altitude_m": "2300", "ascent_m": "299.99"},
            {"end_altitude_m": "2000", "max_altitude_m": "2300", "descent_m": "299.99"},
            {"start_altitude_m": "0", "max_altitude_m": "1", "ascent_m": "0"},
            {"end_altitude_m": "0", "max_altitude_m": "1", "descent_m": "0"},
            {"start_altitude_m": "2000", "max_altitude_m": "1999"},
            {"end_altitude_m": "2000", "max_altitude_m": "1999"},
            {
                "start_altitude_m": "2000",
                "end_altitude_m": "2100",
                "ascent_m": "400",
                "descent_m": "299.99",
            },
            {
                "start_altitude_m": "2000",
                "end_altitude_m": "2000",
                "ascent_m": "100",
                "descent_m": "0",
            },
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", self.numeric_metrics(**values))

    def test_time_rule_preserves_partial_data_and_unclassified_time(self) -> None:
        for values in (
            {"duration_seconds": "100", "moving_seconds": "80", "pause_seconds": "20"},
            {"duration_seconds": "100", "moving_seconds": "70", "pause_seconds": "20"},
            {"duration_seconds": "0", "moving_seconds": "0", "pause_seconds": "0"},
            {"duration_seconds": "100", "moving_seconds": "100"},
            {"moving_seconds": "100", "pause_seconds": "20"},
        ):
            with self.subTest(values=values):
                metrics = self.numeric_metrics(**values)
                self.assertEqual(validate_sport_metrics("hiking", metrics), metrics)
        for values in (
            {"duration_seconds": "100", "moving_seconds": "80", "pause_seconds": "21"},
            {"duration_seconds": "100", "moving_seconds": "101"},
            {"duration_seconds": "100", "pause_seconds": "101"},
            {"duration_seconds": "-1"},
            {"moving_seconds": "-1"},
            {"pause_seconds": "-1"},
            {"distance_m": "-1"},
            {"ascent_m": "-1"},
            {"descent_m": "-1"},
            {"pack_kg": "-0.01"},
        ):
            with self.subTest(values=values), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", self.numeric_metrics(**values))

    def test_difficulty_requires_all_three_nonblank_components(self) -> None:
        components = (
            Metric(MetricName.DIFFICULTY_SCALE, " Escala declarada "),
            Metric(MetricName.DIFFICULTY_GRADE, " Grado propio "),
            Metric(MetricName.DIFFICULTY_SOURCE, " Fuente manual ficticia "),
        )
        normalized = tuple(Metric(item.name, str(item.value).strip()) for item in components)
        self.assertEqual(validate_sport_metrics("hiking", components), normalized)
        for mask in range(1, 7):
            partial = tuple(item for i, item in enumerate(components) if mask & (1 << i))
            with self.subTest(mask=mask), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", partial)
        for index in range(3):
            blank = tuple(
                Metric(item.name, "   ") if i == index else item
                for i, item in enumerate(components)
            )
            with self.subTest(index=index), self.assertRaises(InvalidSportMetrics):
                validate_sport_metrics("hiking", blank)
