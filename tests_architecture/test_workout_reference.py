"""History selection is identical for application and defensive persistence paths."""

import unittest
from datetime import date, timedelta
from decimal import Decimal

from basis.modules.athletes.public import (
    InvalidAthleteField,
    MeasuredReference,
    MeasuredRMData,
    PreviousWorkout,
    WorkoutContext,
    WorkoutData,
    WorkoutReferenceDecision,
    calculate_workout,
    decide_workout_reference,
    validate_workout_reference,
)
from basis.modules.training.public import METRICS_VERSION, ReferenceContext
from basis.shared.identifiers import AthleteId, ExerciseId, MeasuredRMId


class WorkoutReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.day = date(2026, 10, 19)
        self.current = ReferenceContext(AthleteId(1), ExerciseId(2), self.day)
        self.data = WorkoutData(ExerciseId(2), self.day, 3, 5, Decimal("50"), 8.0, Decimal("8"))
        self.reference = MeasuredReference(
            MeasuredRMId(7), AthleteId(1), MeasuredRMData(ExerciseId(2), Decimal("100"), self.day)
        )

    def test_reference_and_calculated_absence_are_frozen(self) -> None:
        for reference in (None, MeasuredRMId(7)):
            for version in (METRICS_VERSION, "legacy-volume-v2"):
                with self.subTest(reference=reference, version=version):
                    decision = decide_workout_reference(
                        self.current, self.current, reference, version
                    )
                    self.assertTrue(decision.reuse_previous)
                    self.assertEqual(decision.reference, reference)
        self.assertFalse(
            decide_workout_reference(
                self.current, self.current, None, "legacy-unverified"
            ).reuse_previous
        )

    def test_each_history_dimension_change_selects_a_new_reference(self) -> None:
        previous_contexts = (
            None,
            ReferenceContext(AthleteId(3), ExerciseId(2), self.day),
            ReferenceContext(AthleteId(1), ExerciseId(3), self.day),
            ReferenceContext(AthleteId(1), ExerciseId(2), self.day - timedelta(days=1)),
        )
        for previous in previous_contexts:
            with self.subTest(previous=previous):
                decision = decide_workout_reference(
                    self.current, previous, MeasuredRMId(7), METRICS_VERSION
                )
                self.assertFalse(decision.reuse_previous)
                self.assertIsNone(decision.reference)

    def test_decision_cannot_reuse_a_reference_in_a_fresh_context(self) -> None:
        with self.assertRaises(ValueError):
            WorkoutReferenceDecision(False, MeasuredRMId(7))

    def test_reference_compatibility_rejects_each_foreign_or_future_dimension(self) -> None:
        validate_workout_reference(None, self.current)
        validate_workout_reference(self.current, self.current)
        for reference in (
            ReferenceContext(AthleteId(3), ExerciseId(2), self.day),
            ReferenceContext(AthleteId(1), ExerciseId(3), self.day),
            ReferenceContext(AthleteId(1), ExerciseId(2), self.day + timedelta(days=1)),
        ):
            with self.subTest(reference=reference), self.assertRaises(InvalidAthleteField):
                validate_workout_reference(reference, self.current)

    def test_new_reference_does_not_change_calculated_history_with_frozen_absence(self) -> None:
        previous = PreviousWorkout(AthleteId(1), self.data, None, METRICS_VERSION)
        calculation = calculate_workout(
            self.data, WorkoutContext(AthleteId(1), previous, self.reference)
        )
        self.assertIsNone(calculation.reference)
        self.assertIsNone(calculation.metrics.relative_intensity_percent)
        self.assertEqual(calculation.metrics.total_reps, 15)
        self.assertEqual(calculation.metrics.load_kg_reps, Decimal("750"))
        fresh = calculate_workout(self.data, WorkoutContext(AthleteId(1), None, self.reference))
        self.assertEqual(fresh.reference, MeasuredRMId(7))
        self.assertEqual(fresh.metrics.relative_intensity_percent, Decimal("50"))
