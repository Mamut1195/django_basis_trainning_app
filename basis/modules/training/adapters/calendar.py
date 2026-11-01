"""One effective calendar for agenda and adherence; historical rows stay queryable."""

from collections.abc import Callable
from datetime import date, datetime

from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from basis.shared.identifiers import AccountId

from .locking import intent_executions
from .models import PlannedSession, Session, TrainingPlan


def effective_sessions(
    owner: AccountId, local_date: Callable[[AccountId, datetime], date] | None = None
) -> tuple[PlannedSession, ...]:
    executions = Session.objects.filter(owner_id=owner).filter(
        Q(planned_id=OuterRef("_intent_root")) | Q(planned__origin_id=OuterRef("_intent_root"))
    )
    rows = (
        PlannedSession.objects.filter(owner_id=owner)
        .select_related("plan", "cycle")
        .annotate(_intent_root=Coalesce("origin_id", "pk"))
        .annotate(
            _has_execution=Exists(executions),
            _has_completed_execution=Exists(executions.filter(status="completed")),
        )
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
    cutoffs: dict[int, date] = {}
    for planned in latest.values():
        successor = successors.get(planned.plan_id)
        if successor is not None and not has_execution(planned):
            # Legacy copies have no provable source link. Preserve their former
            # cutoff semantics rather than guessing lineage by title/date.
            if successor.pk not in cutoffs:
                cutoffs[successor.pk] = successor.effective_on or (
                    local_date(owner, successor.created_at)
                    if local_date
                    else timezone.localtime(successor.created_at).date()
                )
            cutoff = cutoffs[successor.pk]
            if planned.date >= cutoff:
                continue
        result.append(planned)
    return tuple(sorted(result, key=lambda row: (row.date, row.pk)))


def has_execution(row: PlannedSession) -> bool:
    annotated = getattr(row, "_has_execution", None)
    return annotated if isinstance(annotated, bool) else intent_executions(row).exists()


def has_completed_execution(row: PlannedSession) -> bool:
    annotated = getattr(row, "_has_completed_execution", None)
    return (
        annotated
        if isinstance(annotated, bool)
        else intent_executions(row).filter(status="completed").exists()
    )


def calendar_status(row: PlannedSession, today: date) -> str:
    if has_completed_execution(row):
        return "Completada"
    if has_execution(row):
        return "En curso"
    return {"skipped": "Omitida", "cancelled": "Cancelada"}.get(
        row.status, "Pendiente pasada" if row.date < today else "Programada"
    )
