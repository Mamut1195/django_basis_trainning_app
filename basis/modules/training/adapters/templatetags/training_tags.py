"""Presentation of typed sport metric definitions."""

from typing import TypedDict, cast

from django import template

from basis.modules.training.public import VARIABLES

from ..metrics import pace_seconds_legacy
from ..models import Block, Interval

register = template.Library()


class MetricRow(TypedDict):
    label: str
    value: object
    unit: str


@register.filter
def metric_rows(block: Block | Interval, source: str = "actual") -> list[MetricRow]:
    sport = block.block.sport if isinstance(block, Interval) else block.sport
    definitions = VARIABLES.get(sport, {})
    values = cast(dict[str, object], getattr(block, source))
    rows: list[MetricRow] = [
        {"label": definitions[key].label, "value": value, "unit": definitions[key].unit}
        for key, value in values.items()
        if key in definitions
    ]
    if sport == "running":
        # Legacy JSON may contain true null; do not turn absence into zero or "None".
        pace_inputs = {
            key: str(values[key])
            for key in ("distance_m", "duration_seconds")
            if values.get(key) is not None and values[key] != ""
        }
        rows.append(
            {
                "label": "Ritmo derivado transcurrido",
                "value": pace_seconds_legacy(pace_inputs),
                "unit": "s/km",
            }
        )
    return rows
