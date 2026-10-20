"""Django JSON serialization with stable outward model labels."""

import json
from typing import cast

from django.core.serializers import serialize
from django.db.models import Model, QuerySet

from basis.shared.export import ExportSection


def export_section(rows: QuerySet[Model], key: str, label: str) -> ExportSection:
    values = cast(list[dict[str, object]], json.loads(serialize("json", rows)))
    for row in values:
        row["model"] = label
    return ExportSection(key, tuple(values))
