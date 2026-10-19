"""Compatibility imports for historical strength consumers."""

from basis.modules.training.adapters.metrics import (
    calculate_legacy_strength as calculate_strength_metrics,
)
from basis.modules.training.public import METRICS_VERSION, MetricsInputError, StrengthMetrics

__all__ = ("METRICS_VERSION", "MetricsInputError", "StrengthMetrics", "calculate_strength_metrics")
