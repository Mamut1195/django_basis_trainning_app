"""Compatibility conversion and validation order at the framework boundary."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from basis.modules.training.adapters.metrics import (
    calculate_legacy_strength as calculate_strength_metrics,
)
from basis.modules.training.adapters.metrics import internal_load_legacy as internal_load
from basis.modules.training.adapters.metrics import validate_metrics
from basis.modules.training.adapters.models import StrengthSet
from basis.modules.training.public import MetricsInputError


class MetricsBoundaryTests(SimpleTestCase):
    def test_fractional_duration_uses_decimal_text_and_missing_short_circuits(self) -> None:
        self.assertEqual(internal_load(0.3, 3), Decimal("0.02"))
        self.assertEqual(internal_load(0.9, 3), Decimal("0.04"))
        self.assertIsNone(internal_load(None, "not-a-number"))
        self.assertIsNone(internal_load("not-a-number", None))

    def test_legacy_strength_coercion_and_error_precedence(self) -> None:
        result = calculate_strength_metrics(sets="3", reps=5.0, weight_kg="80.25", observed_rpe=10)
        self.assertEqual(result.estimated_1rm_kg, Decimal("93.63"))
        for changes, field in (
            ({"sets": True}, "sets"),
            ({"weight_kg": "-1", "observed_rpe": "bad"}, "peso"),
            ({"observed_rpe": 11, "target_rpe": "bad"}, "rpe_real"),
            ({"target_rpe": 11, "reference_rm_kg": "bad"}, "rpe_objetivo"),
        ):
            with self.subTest(changes=changes), self.assertRaises(MetricsInputError) as error:
                calculate_strength_metrics(**({"sets": 1, "reps": 1, "weight_kg": "1"} | changes))
            self.assertEqual(error.exception.field, field)

    def test_unsaved_model_numeric_values_use_the_same_conversion(self) -> None:
        self.assertEqual(
            StrengthSet(actual_kg=Decimal("80.25"), actual_reps=5, actual_rpe=10).estimated_1rm,
            Decimal("93.63"),
        )
        self.assertIsNone(
            StrengthSet(actual_kg=Decimal(80), actual_reps=5, actual_rpe="10").estimated_1rm
        )

    def test_metric_error_shape_order_and_zero(self) -> None:
        self.assertEqual(
            validate_metrics(
                "hiking", {"distance_m": 0, "duration_seconds": None, "terrain": " road "}
            ),
            {"distance_m": "0", "terrain": "road"},
        )
        with self.assertRaises(ValidationError) as error:
            validate_metrics("hiking", {"distance_m": -1, "ascent_m": "bad"})
        self.assertEqual(error.exception.message_dict, {"distance_m": ["Valor fuera de rango."]})
        with self.assertRaises(ValidationError) as error:
            validate_metrics("cycling", {"environment": " indoor ", "distance_m": True})
        self.assertEqual(
            error.exception.message_dict, {"environment": ["Texto o selección inválida."]}
        )
