"""Strength arithmetic and historical reference policies without Django."""

import unittest
from datetime import date
from decimal import ROUND_DOWN, Decimal, localcontext

from basis.modules.training.domain.strength import (
    MetricsInputError,
    ReferenceContext,
    calculate_strength_metrics,
    estimated_1rm,
    external_volume,
    reference_is_frozen,
    reference_matches,
    validate_repetition_prescription,
)
from basis.shared.identifiers import AthleteId, ExerciseId


class StrengthMetricsTests(unittest.TestCase):
    def test_precision_missing_and_effort_eligibility(self) -> None:
        with localcontext() as context:
            context.rounding = ROUND_DOWN
            result = calculate_strength_metrics(
                sets=3,
                reps=5,
                weight_kg=Decimal("80.25"),
                reference_rm_kg=Decimal(100),
                observed_rpe=Decimal(10),
            )
        self.assertEqual(result.load_kg_reps, Decimal("1203.75"))
        self.assertEqual(result.estimated_1rm_kg, Decimal("93.63"))
        self.assertEqual(result.relative_volume, Decimal("1203.75"))
        absent = calculate_strength_metrics(
            sets=1, reps=5, weight_kg=Decimal(80), target_rpe=Decimal(10)
        )
        self.assertIsNone(absent.relative_intensity_percent)
        self.assertIsNone(absent.estimated_1rm_kg)
        zero = calculate_strength_metrics(
            sets=0, reps=5, weight_kg=Decimal(80), reference_rm_kg=Decimal(100)
        )
        self.assertEqual(zero.relative_intensity_percent, Decimal(0))
        self.assertIsNone(zero.estimated_1rm_kg)

    def test_detailed_effort_and_load_protocol(self) -> None:
        self.assertEqual(external_volume("external", Decimal("2.5"), 3), Decimal("7.50"))
        self.assertIsNone(external_volume("bodyweight", Decimal(80), 5))
        self.assertIsNone(external_volume("external", None, 5))
        self.assertIsNone(estimated_1rm("external", "warmup", Decimal(80), 5, Decimal(10)))
        self.assertIsNone(estimated_1rm("external", "work", Decimal(80), 11, Decimal(10)))
        self.assertEqual(
            estimated_1rm("external", "work", Decimal(80), 1, Decimal(10)), Decimal("80.00")
        )

    def test_finite_and_storage_limits(self) -> None:
        for weight in (
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-1"),
            Decimal("9999999999999"),
        ):
            with self.subTest(weight=weight), self.assertRaises(MetricsInputError):
                calculate_strength_metrics(sets=1, reps=1, weight_kg=weight)
        with self.assertRaises(MetricsInputError):
            calculate_strength_metrics(sets=2147483647, reps=2, weight_kg=Decimal(0))

    def test_ranges_and_historical_reference_decisions(self) -> None:
        for args in (
            (None, 1, None, None, False),
            (1, 1, 2, None, False),
            (None, None, None, Decimal(50), False),
        ):
            with self.assertRaises(ValueError):
                validate_repetition_prescription(*args)
        context = ReferenceContext(AthleteId(1), ExerciseId(2), date(2026, 10, 1))
        self.assertTrue(reference_matches(context, context))
        self.assertFalse(
            reference_matches(context, ReferenceContext(AthleteId(2), ExerciseId(2), context.date))
        )
        self.assertFalse(
            reference_matches(
                context, ReferenceContext(AthleteId(1), ExerciseId(2), date(2026, 9, 1))
            )
        )
        self.assertTrue(reference_is_frozen(True, None, "legacy-strength-v3"))
        self.assertTrue(reference_is_frozen(True, None, "legacy-volume-v2"))
        self.assertFalse(reference_is_frozen(False, 1, "legacy-strength-v3"))
