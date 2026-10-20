"""Presentation of typed sport metric definitions."""

from typing import TypedDict, cast

from django import template

from basis.modules.training.public import VARIABLES

from ..models import Block

register = template.Library()


class MetricRow(TypedDict):
    label: str
    value: object
    unit: str


@register.filter
def metric_rows(block: Block, source: str = "actual") -> list[MetricRow]:
    definitions = VARIABLES.get(block.sport, {})
    values = cast(dict[str, object], getattr(block, source))
    return [
        {"label": definitions[key].label, "value": value, "unit": definitions[key].unit}
        for key, value in values.items()
        if key in definitions
    ]
