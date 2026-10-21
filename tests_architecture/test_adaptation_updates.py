"""Portable mutation presence and observation rules, without ORM or providers."""

from dataclasses import replace
from decimal import Decimal
from typing import cast
from unittest import TestCase

from basis.modules.training.domain.execution import (
    AdaptationField,
    BlockData,
    InvalidExecution,
    StrengthData,
)
from basis.modules.training.domain.execution_updates import (
    reconcile_adaptation,
    reconcile_blocks,
    validate_adaptation,
)


class AdaptationPresencePolicyTests(TestCase):
    def setUp(self) -> None:
        self.current = StrengthData(
            1,
            id=4,
            source=3,
            target_reps=5,
            target_kg=Decimal(80),
            actual_reps=4,
            actual_kg=Decimal(75),
            actual_rpe=Decimal(10),
            actual_exercise=2,
            actual_load_type="assisted",
            actual_kind="failed",
            actual_tempo="2-0-2-0",
            actual_range_of_motion="partial",
            actual_side="left",
            actual_group="B",
            adaptation_reason="Observed assistance",
        )

    def test_absence_is_not_none_and_keeps_existing_observation(self) -> None:
        legacy = replace(
            self.current,
            actual_exercise=None,
            actual_load_type=None,
            actual_kind=None,
            actual_tempo=None,
            actual_range_of_motion=None,
            actual_side=None,
            actual_group=None,
            adaptation_reason="",
            actual_reps=0,
            actual_kg=None,
        )
        merged = reconcile_adaptation(self.current, legacy, frozenset())
        self.assertEqual(
            (
                merged.actual_exercise,
                merged.actual_load_type,
                merged.actual_kind,
                merged.adaptation_reason,
            ),
            (2, "assisted", "failed", "Observed assistance"),
        )
        self.assertEqual((merged.actual_reps, merged.actual_kg), (0, None))
        self.assertEqual(
            (
                merged.actual_tempo,
                merged.actual_range_of_motion,
                merged.actual_side,
                merged.actual_group,
            ),
            ("2-0-2-0", "partial", "left", "B"),
        )

    def test_explicit_clear_is_rejected_even_if_reason_is_fresh(self) -> None:
        for candidate, field in (
            (replace(self.current, actual_load_type=None), AdaptationField.LOAD_TYPE),
            (replace(self.current, actual_kind=""), AdaptationField.KIND),
            (replace(self.current, actual_exercise=None), AdaptationField.EXERCISE),
            (
                replace(self.current, actual_tempo="", adaptation_reason="Fresh"),
                AdaptationField.TEMPO,
            ),
        ):
            if field == AdaptationField.TEMPO:
                previous = replace(self.current, actual_tempo="3-1-1-0")
            else:
                previous = self.current
            with self.assertRaises(InvalidExecution):
                reconcile_adaptation(
                    previous,
                    replace(candidate, adaptation_reason="Fresh reason"),
                    frozenset({field, AdaptationField.REASON}),
                )

    def test_partial_change_requires_explicit_nonempty_reason_and_preserves_other_fields(
        self,
    ) -> None:
        candidate = replace(self.current, actual_kind="work")
        with self.assertRaises(InvalidExecution):
            reconcile_adaptation(self.current, candidate, frozenset({AdaptationField.KIND}))
        with self.assertRaises(InvalidExecution):
            reconcile_adaptation(
                self.current, replace(candidate, adaptation_reason="  "), frozenset(AdaptationField)
            )
        merged = reconcile_adaptation(
            self.current,
            replace(candidate, adaptation_reason="Observed assisted working set"),
            frozenset({AdaptationField.KIND, AdaptationField.REASON}),
        )
        self.assertEqual(
            (merged.actual_exercise, merged.actual_load_type, merged.actual_kind),
            (2, "assisted", "work"),
        )
        self.assertEqual((merged.exercise, merged.kind, merged.load_type), (1, "work", "external"))

    def test_full_unchanged_typed_snapshot_and_empty_new_creation_are_valid(self) -> None:
        self.assertEqual(reconcile_adaptation(self.current, self.current), self.current)
        fresh = StrengthData(1, actual_reps=0, actual_kg=Decimal(0))
        self.assertEqual(reconcile_adaptation(None, fresh, frozenset()), fresh)
        validate_adaptation(fresh)

    def test_actual_field_types_are_checked_in_the_pure_policy(self) -> None:
        invalid = (
            replace(self.current, actual_exercise=cast(int, True)),
            replace(self.current, actual_exercise=cast(int, Decimal("2.5"))),
            replace(self.current, actual_kind=cast(str, True)),
            replace(self.current, actual_tempo=cast(str, 13)),
            replace(self.current, actual_range_of_motion=cast(str, [])),
            replace(self.current, adaptation_reason=cast(str, None)),
        )
        for row in invalid:
            with self.assertRaises(InvalidExecution):
                validate_adaptation(row)

    def test_presence_is_typed_and_has_exact_block_row_shape(self) -> None:
        block = BlockData("strength", "A", id=1, sets=(self.current,))
        with self.assertRaises(InvalidExecution):
            reconcile_blocks((block,), (block,), frozen=True, adaptation_presence=())
        with self.assertRaises(InvalidExecution):
            reconcile_adaptation(
                self.current,
                self.current,
                cast(frozenset[AdaptationField], frozenset({"actual_kind"})),
            )
        with self.assertRaises(InvalidExecution):
            reconcile_blocks(
                (block,),
                (block,),
                frozen=True,
                adaptation_presence=cast(
                    tuple[tuple[frozenset[AdaptationField], ...], ...], ((None,),)
                ),
            )

    def test_reason_itself_cannot_be_erased_but_explicit_text_can_repeat(self) -> None:
        with self.assertRaises(InvalidExecution):
            reconcile_adaptation(
                self.current,
                replace(self.current, adaptation_reason=""),
                frozenset({AdaptationField.REASON}),
            )
        previous = replace(self.current, adaptation_reason="por dolor")
        for kind, reason in (
            ("work", "por dolor"),
            ("warmup", "por dolor"),
            ("failed", " POR DOLOR "),
        ):
            observed = reconcile_adaptation(
                previous,
                replace(previous, actual_kind=kind, adaptation_reason=reason),
                frozenset({AdaptationField.KIND, AdaptationField.REASON}),
            )
            self.assertEqual((observed.actual_kind, observed.adaptation_reason), (kind, reason))
            self.assertEqual(
                (observed.id, observed.source, observed.exercise, observed.target_kg),
                (4, 3, 1, Decimal(80)),
            )
            previous = observed
