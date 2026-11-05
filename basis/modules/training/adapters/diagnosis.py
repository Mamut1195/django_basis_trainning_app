"""Read-only session window for the coach diagnosis.

The query lives in an adapter so bootstrap stays pure composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from basis.shared.identifiers import AccountId

from ..domain.analysis import LoadSample
from .models import Session


@dataclass(frozen=True)
class SampleWindow:
    samples: tuple[LoadSample, ...]
    excluded: int


def read_window(account: AccountId, today: date, days: int) -> SampleWindow:
    if days < 1:
        raise ValueError("La ventana debe ser positiva.")
    start = today - timedelta(days=days - 1)
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
    return SampleWindow(samples=tuple(samples), excluded=excluded)
