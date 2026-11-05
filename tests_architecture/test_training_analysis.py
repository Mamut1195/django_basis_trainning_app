"""Pure training-analysis math: no database, no provider, no clock."""

from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase

from basis.modules.training.domain.analysis import (
    LoadSample,
    SetRecord,
    TrendPoint,
    WeeklyMuscleSets,
    adherence,
    consecutive_above,
    estimated_1rm_rir,
    load_ratio,
    monotony,
    muscle_gaps,
    rolling_mean,
    slope_per_week,
    strain,
    volume_by_muscle,
    week_start,
    weekly_loads,
)


def day(offset: int) -> date:
    return date(2026, 11, 2) + timedelta(days=offset)


class WeeklyLoadTests(TestCase):
    def test_sports_and_protocols_are_never_summed(self) -> None:
        rows = weekly_loads(
            (
                LoadSample(day(0), "hiking", "elapsed", 10_800, Decimal(4)),
                LoadSample(day(1), "cycling", "elapsed", 3_600, Decimal(6)),
                LoadSample(day(2), "hiking", "moving", 7_200, Decimal(4)),
            )
        )
        self.assertEqual(len(rows), 3)
        loads = {(row.sport, row.protocol): row.load for row in rows}
        self.assertEqual(
            loads,
            {
                ("hiking", "elapsed"): Decimal("720.00"),
                ("hiking", "moving"): Decimal("480.00"),
                ("cycling", "elapsed"): Decimal("360.00"),
            },
        )
        self.assertNotIn(Decimal("1080.00"), loads.values())

    def test_missing_rpe_is_coverage_and_not_zero(self) -> None:
        rows = weekly_loads((LoadSample(day(0), "running", "elapsed", 1_800, None),))
        self.assertEqual(rows[0].load, Decimal("0.00"))
        self.assertEqual((rows[0].known, rows[0].missing), (0, 1))

    def test_week_start_is_monday(self) -> None:
        self.assertEqual(week_start(date(2026, 11, 4)), date(2026, 11, 2))


class RollingAndRatioTests(TestCase):
    def test_rolling_mean_ignores_unknown_and_waits_for_minimum(self) -> None:
        values = (Decimal("400"), None, Decimal("500"), Decimal("600"))
        self.assertEqual(rolling_mean(values, 4, minimum=3), Decimal("500.00"))
        self.assertIsNone(rolling_mean(values, 4))
        self.assertIsNone(rolling_mean((None, None), 2))

    def test_load_ratio_and_consecutive_weeks(self) -> None:
        baseline = Decimal("500")
        self.assertEqual(load_ratio(Decimal("720"), baseline), Decimal("1.440"))
        self.assertIsNone(load_ratio(Decimal("720"), None))
        self.assertIsNone(load_ratio(Decimal("1"), Decimal("0")))
        ratios = (Decimal("1.0"), Decimal("1.3"), Decimal("1.4"))
        self.assertEqual(consecutive_above(ratios, Decimal("1.2")), 2)
        self.assertEqual(consecutive_above((Decimal("1.3"), Decimal("1.1")), Decimal("1.2")), 0)


class MonotonyTests(TestCase):
    def test_rest_days_are_real_zeros_and_unknown_blocks_the_value(self) -> None:
        varied = (
            Decimal("100"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
        )
        value = monotony(varied)
        self.assertIsNotNone(value)
        assert value is not None
        self.assertLess(value, Decimal("1"))
        self.assertIsNone(monotony((Decimal("100"),) * 7))
        unknown: list[Decimal | None] = list(varied)
        unknown[3] = None
        self.assertIsNone(monotony(unknown))
        self.assertIsNone(monotony(varied[:6]))

    def test_strain_multiplies_load_by_monotony(self) -> None:
        self.assertEqual(strain(Decimal("720"), Decimal("0.5")), Decimal("360.00"))
        self.assertIsNone(strain(Decimal("720"), None))


class TrendTests(TestCase):
    def test_slope_per_week_uses_least_squares(self) -> None:
        points = (
            TrendPoint(day(0), Decimal("100")),
            TrendPoint(day(7), Decimal("110")),
            TrendPoint(day(14), Decimal("120")),
        )
        self.assertEqual(slope_per_week(points), Decimal("10.00"))
        self.assertIsNone(slope_per_week(points[:2]))


class OneRepMaxTests(TestCase):
    def test_rir_adjusted_epley(self) -> None:
        self.assertEqual(estimated_1rm_rir(Decimal("100"), 5, 2), Decimal("123.33"))
        self.assertEqual(estimated_1rm_rir(Decimal("100"), 1, 0), Decimal("103.33"))

    def test_out_of_range_is_unknown(self) -> None:
        self.assertIsNone(estimated_1rm_rir(Decimal("100"), 13, 0))
        self.assertIsNone(estimated_1rm_rir(Decimal("100"), 5, 11))
        self.assertIsNone(estimated_1rm_rir(Decimal("0"), 5, 2))
        self.assertIsNone(estimated_1rm_rir(None, 5, 2))


class VolumeTests(TestCase):
    def test_sets_count_per_muscle_and_bodyweight_is_missing_kg_reps(self) -> None:
        rows = volume_by_muscle(
            (
                SetRecord(("chest",), "external", Decimal("50"), 10),
                SetRecord(("chest", "triceps"), "bodyweight", None, 8),
            )
        )
        by_muscle = {row.muscle: row for row in rows}
        self.assertEqual(by_muscle["chest"].sets, Decimal("2"))
        self.assertEqual(by_muscle["chest"].kg_reps, Decimal("500.00"))
        self.assertEqual((by_muscle["chest"].known_sets, by_muscle["chest"].missing_sets), (1, 1))
        self.assertEqual(by_muscle["triceps"].sets, Decimal("1"))
        self.assertIsNone(by_muscle["triceps"].kg_reps)

    def test_muscle_gap_counts_checked_weeks(self) -> None:
        rows = (
            WeeklyMuscleSets(day(0), "chest", Decimal("3")),
            WeeklyMuscleSets(day(7), "chest", Decimal("2")),
        )
        gaps = muscle_gaps(rows, ("chest", "back"))
        self.assertEqual([(gap.muscle, gap.weeks) for gap in gaps], [("back", 2)])


class AdherenceTests(TestCase):
    def test_percent_and_empty_period(self) -> None:
        self.assertEqual(adherence(4, 3).percent, Decimal("75.00"))
        self.assertIsNone(adherence(0, 0).percent)
        with self.assertRaises(ValueError):
            adherence(2, 3)
