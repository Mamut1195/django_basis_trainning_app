"""Policies shared by persistence hooks and application validation need no Django."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.domain.execution import (
    BlockData,
    IntervalData,
    InvalidExecution,
    StrengthData,
    validate_component_sport,
)
from basis.modules.training.domain.planning import (
    InvalidPlanning,
    validate_plan_version,
    validate_prescribed_results,
    validate_prescription,
)
from basis.modules.training.domain.strength import validate_strength_reference
from basis.shared.identifiers import AccountId, ExerciseId, LineageId


class PersistencePolicyTests(TestCase):
    def test_successor_requires_same_lineage_and_exact_next_version(self) -> None:
        lineage = LineageId(UUID(int=1))
        validate_plan_version(lineage, 1, None, None)
        validate_plan_version(lineage, 3, lineage, 2)
        for previous, version in ((lineage, 2), (LineageId(UUID(int=2)), 3)):
            with (
                self.subTest(previous=previous, version=version),
                self.assertRaises(InvalidPlanning),
            ):
                validate_plan_version(lineage, version, previous, 2)

    def test_zero_actual_result_is_present_and_prescription_guard_is_shared(self) -> None:
        validate_prescribed_results(False)
        with self.assertRaises(InvalidPlanning):
            validate_prescribed_results(True)
        block = BlockData(sport="strength", sets=(StrengthData(exercise=1),))
        validate_prescription((block,))
        for row in (
            replace(block.sets[0], actual_kg=Decimal(0)),
            replace(block.sets[0], actual_reps=0),
            replace(block.sets[0], actual_rpe=Decimal(0)),
            replace(block.sets[0], actual_rir=0),
            replace(block.sets[0], actual_rest_seconds=0),
            replace(block.sets[0], isometric_seconds=0),
        ):
            with self.subTest(row=row), self.assertRaises(InvalidPlanning):
                validate_prescription((replace(block, sets=(row,)),))
        with self.assertRaises(InvalidPlanning):
            validate_prescription(
                (BlockData(sport="running", intervals=(IntervalData(actual_rpe=Decimal(0)),)),)
            )

    def test_strength_and_interval_components_match_their_sport(self) -> None:
        validate_component_sport("strength", strength=True)
        validate_component_sport("running", strength=False)
        for sport, strength in (("running", True), ("strength", False)):
            with self.subTest(sport=sport), self.assertRaises(InvalidExecution):
                validate_component_sport(sport, strength=strength)

    def test_measured_reference_requires_owner_exercise_and_nonfuture_date(self) -> None:
        today = date(2026, 10, 19)
        owner, exercise = AccountId(1), ExerciseId(2)
        validate_strength_reference(owner, exercise, today, owner, exercise, today)
        for ref_owner, ref_exercise, ref_date in (
            (None, None, None),
            (AccountId(3), exercise, today),
            (owner, ExerciseId(3), today),
            (owner, exercise, today + timedelta(days=1)),
        ):
            with (
                self.subTest(owner=ref_owner, exercise=ref_exercise),
                self.assertRaises(ValueError),
            ):
                validate_strength_reference(
                    ref_owner, ref_exercise, ref_date, owner, exercise, today
                )
