"""One effective calendar for agenda and adherence; historical rows stay queryable."""

from collections.abc import Callable
from datetime import date, datetime

from django.utils import timezone

from basis.shared.identifiers import AccountId

from .locking import intent_executions
from .models import PlannedSession, TrainingPlan


def effective_sessions(
    owner: AccountId, local_date: Callable[[AccountId, datetime], date] | None = None
) -> tuple[PlannedSession, ...]:
    rows = (
        PlannedSession.objects.filter(owner_id=owner)
        .select_related("plan", "cycle")
        .order_by("plan__version", "pk")
    )
    latest: dict[int, PlannedSession] = {}
    for row in rows:
        latest[row.origin_id or row.pk] = row
    successors = {
        p.previous_id: p
        for p in TrainingPlan.objects.filter(owner_id=owner, previous_id__isnull=False)
    }
    result = []
    for row in latest.values():
        successor = successors.get(row.plan_id)
        if successor is not None and not intent_executions(row).exists():
            # Legacy copies have no provable source link. Preserve their former
            # cutoff semantics rather than guessing lineage by title/date.
            cutoff = successor.effective_on or (
                local_date(owner, successor.created_at)
                if local_date
                else timezone.localtime(successor.created_at).date()
            )
            if row.date >= cutoff:
                continue
        result.append(row)
    return tuple(sorted(result, key=lambda row: (row.date, row.pk)))


def calendar_status(row: PlannedSession, today: date) -> str:
    executions = intent_executions(row)
    if executions.filter(status="completed").exists():
        return "Completada"
    if executions.exists():
        return "En curso"
    return {"skipped": "Omitida", "cancelled": "Cancelada"}.get(
        row.status, "Pendiente pasada" if row.date < today else "Programada"
    )
