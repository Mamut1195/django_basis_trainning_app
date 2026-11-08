"""Composition for the owner-facing coach diagnosis.

Reads a five-week session window (the prompt context keeps its own short window) through
the training adapter and delegates to the deterministic diagnosis. Multi-sport sessions are
excluded instead of being summed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from basis.bootstrap.records import exercise_choices
from basis.modules.coach.application.diagnosis import Diagnosis, MarkHighlight, diagnose
from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
from basis.modules.training.adapters.diagnosis import read_window
from basis.modules.training.adapters.records import sport_records, strength_records
from basis.shared.identifiers import AccountId

WINDOW_DAYS = 35


def for_owner(account: AccountId, today: date) -> Diagnosis:
    window = read_window(account, today, WINDOW_DAYS)
    context = DjangoTrainingCoachContexts().read(account, today)
    adherence = (
        Decimal(str(context.progress.adherence_percent))
        if context.progress.adherence_percent is not None
        else None
    )
    result = diagnose(
        window.samples,
        adherence_percent=adherence,
        recent_rpe=tuple(row.rpe for row in context.recent),
        excluded_sessions=window.excluded,
    )
    highlights: list[MarkHighlight] = []
    for record in strength_records(account, exercise_choices()):
        if record.value is None:
            continue
        unit = "kg" if record.metric == "1RM estimado" else "rep"
        highlights.append(
            MarkHighlight(
                record.name, record.metric, f"{record.value:.1f} {unit}", record.achieved_on
            )
        )
    for sport_record in sport_records(account):
        highlights.append(
            MarkHighlight(
                sport_record.label,
                sport_record.metric,
                sport_record.display,
                sport_record.achieved_on,
            )
        )
    highlights.sort(key=lambda item: item.achieved_on or date.min, reverse=True)
    selected: list[MarkHighlight] = []
    seen: set[str] = set()
    for mark in highlights:
        if mark.name in seen:
            continue
        seen.add(mark.name)
        selected.append(mark)
        if len(selected) == 3:
            break
    return replace(result, marks=tuple(selected))
