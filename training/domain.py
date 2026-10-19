"""Compatibility facade for manual sport variables; domain rules live in BASIS."""

from basis.modules.training.adapters.metrics import (
    internal_load_legacy as internal_load,
)
from basis.modules.training.adapters.metrics import (
    pace_seconds_legacy as pace_seconds,
)
from basis.modules.training.adapters.metrics import (
    validate_metrics,
)
from basis.modules.training.public import SPORT_LABELS, SPORTS, VARIABLES, Variable

__all__ = ("SPORTS", "SPORT_LABELS", "VARIABLES", "Variable", "validate_metrics", "pace_seconds", "internal_load")
