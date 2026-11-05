"""Composition for the owner-facing coach diagnosis.

Reads a five-week session window (the prompt context keeps its own short window) through
the training adapter and delegates to the deterministic diagnosis. Multi-sport sessions are
excluded instead of being summed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from basis.modules.coach.application.diagnosis import Diagnosis, diagnose
from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
from basis.modules.training.adapters.diagnosis import read_window
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
    return diagnose(
        window.samples,
        adherence_percent=adherence,
        recent_rpe=tuple(row.rpe for row in context.recent),
        excluded_sessions=window.excluded,
    )
