"""Composition for the owner-facing coach diagnosis.

Reads a five-week session window (the prompt context keeps its own short window), builds
single-sport samples and delegates to the deterministic diagnosis. Multi-sport sessions are
excluded instead of being summed.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from basis.modules.coach.application.diagnosis import Diagnosis, diagnose
from basis.modules.training.adapters.coach import DjangoTrainingCoachContexts
from basis.modules.training.adapters.models import Session
from basis.modules.training.public import LoadSample
from basis.shared.identifiers import AccountId

WINDOW_DAYS = 35


def for_owner(account: AccountId, today: date) -> Diagnosis:
    start = today - timedelta(days=WINDOW_DAYS - 1)
    sessions = (
        Session.objects.filter(owner_id=account, date__range=(start, today), status="completed")
        .prefetch_related("blocks")
        .order_by("date")
    )
    samples: list[LoadSample] = []
    excluded = 0
    for session in sessions:
        sports = {block.sport for block in session.blocks.all()}
        if len(sports) != 1:
            excluded += 1
            continue
        samples.append(
            LoadSample(
                day=session.date,
                sport=sports.pop(),
                protocol=session.duration_protocol,
                duration_seconds=session.duration_seconds,
                reported_rpe=session.reported_rpe,
            )
        )
    context = DjangoTrainingCoachContexts().read(account, today)
    adherence = (
        Decimal(str(context.progress.adherence_percent))
        if context.progress.adherence_percent is not None
        else None
    )
    return diagnose(
        samples,
        adherence_percent=adherence,
        recent_rpe=tuple(row.rpe for row in context.recent),
        excluded_sessions=excluded,
    )
