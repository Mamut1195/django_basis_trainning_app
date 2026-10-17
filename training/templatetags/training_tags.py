from django import template

from training.domain import VARIABLES

register = template.Library()


@register.filter
def metric_rows(block, source="actual"):
    definitions = VARIABLES.get(block.sport, {})
    return [
        {"label": definitions[key].label, "value": value, "unit": definitions[key].unit}
        for key, value in getattr(block, source).items()
        if key in definitions
    ]
