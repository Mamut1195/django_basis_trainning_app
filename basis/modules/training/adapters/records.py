"""Owner-scoped personal records for every exercise and sport.

Computed from completed sessions; no materialized mark table yet. Unknown values
stay ``None`` so the UI can say "sin registro" instead of inventing a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db import transaction

from basis.modules.catalog.public import ExerciseChoices
from basis.shared.identifiers import AccountId

from .models import PersonalRecord, Session, StrengthSet


@dataclass(frozen=True)
class StrengthRecord:
    name: str
    metric: str
    value: Decimal | None
    detail: str
    achieved_on: date | None
    session_id: str | None
    key: str = ""


@dataclass(frozen=True)
class SportRecord:
    sport: str
    label: str
    metric: str
    display: str
    achieved_on: date
    session_id: str
    key: str = ""


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _one_rm(kg: Decimal, reps: int) -> Decimal | None:
    if not 1 <= reps <= 12:
        return None
    return (kg * (1 + Decimal(reps) / 30)).quantize(Decimal("0.01"))


def strength_records(
    account: AccountId, choices: ExerciseChoices, query: str = ""
) -> tuple[StrengthRecord, ...]:
    catalog = [
        (int(exercise_id), name)
        for exercise_id, name, archived in choices.all()
        if not archived and (not query or query.lower() in name.lower())
    ]
    rows = (
        StrengthSet.objects.filter(
            block__session__owner_id=account,
            block__session__status="completed",
            actual_reps__gt=0,
        )
        .select_related("block__session", "exercise", "actual_exercise")
        .order_by("-block__session__date", "-pk")
    )
    best: dict[int, tuple[Decimal, str, str, date, str]] = {}
    best_reps: dict[int, tuple[int, str, date, str]] = {}
    for row in rows:
        assert row.actual_reps is not None
        session = row.block.session
        if session is None:
            continue
        exercise_id = row.actual_exercise_id or row.exercise_id
        load_type = row.actual_load_type or row.load_type
        if load_type == "external" and row.actual_kg is not None:
            estimate = _one_rm(row.actual_kg, row.actual_reps)
            if estimate is not None:
                current = best.get(exercise_id)
                if current is None or estimate > current[0]:
                    best[exercise_id] = (
                        estimate,
                        f"{row.actual_kg} kg × {row.actual_reps}",
                        str(session.pk),
                        session.date,
                        session.title,
                    )
        current_reps = best_reps.get(exercise_id)
        if current_reps is None or row.actual_reps > current_reps[0]:
            best_reps[exercise_id] = (
                row.actual_reps,
                str(session.pk),
                session.date,
                session.title,
            )
    records: list[StrengthRecord] = []
    for exercise_id, name in sorted(catalog, key=lambda item: item[1]):
        load = best.get(exercise_id)
        reps = best_reps.get(exercise_id)
        if load is not None:
            records.append(
                StrengthRecord(
                    name,
                    "1RM estimado",
                    load[0],
                    f"{load[1]} · {load[4]}",
                    load[3],
                    load[2],
                    str(exercise_id),
                )
            )
        elif reps is not None:
            records.append(
                StrengthRecord(
                    name,
                    "Mejor serie",
                    Decimal(reps[0]),
                    f"{reps[0]} repeticiones · {reps[3]}",
                    reps[2],
                    reps[1],
                    str(exercise_id),
                )
            )
        else:
            records.append(
                StrengthRecord(name, "Sin registro", None, "", None, None, str(exercise_id))
            )
    return tuple(records)


def sport_records(account: AccountId) -> tuple[SportRecord, ...]:
    sessions = Session.objects.filter(owner_id=account, status="completed").prefetch_related(
        "blocks"
    )
    best_distance: dict[str, tuple[Decimal, date, str]] = {}
    best_ascent: dict[str, tuple[Decimal, date, str]] = {}
    best_pace: dict[str, tuple[Decimal, date, str]] = {}
    labels: dict[str, str] = {}
    for session in sessions:
        for block in session.blocks.all():
            labels[block.sport] = block.get_sport_display()
            actual = block.actual if isinstance(block.actual, dict) else {}
            distance = _decimal(actual.get("distance_m"))
            ascent = _decimal(actual.get("ascent_m"))
            if distance is not None and distance > 0:
                current = best_distance.get(block.sport)
                if current is None or distance > current[0]:
                    best_distance[block.sport] = (distance, session.date, str(session.pk))
                if session.duration_seconds and distance >= 1000:
                    pace = Decimal(session.duration_seconds) / (distance / 1000)
                    current_pace = best_pace.get(block.sport)
                    if current_pace is None or pace < current_pace[0]:
                        best_pace[block.sport] = (pace, session.date, str(session.pk))
            if ascent is not None and ascent > 0:
                current = best_ascent.get(block.sport)
                if current is None or ascent > current[0]:
                    best_ascent[block.sport] = (ascent, session.date, str(session.pk))
    records: list[SportRecord] = []
    for sport in sorted(labels):
        label = labels[sport]
        if sport in best_distance:
            distance_best = best_distance[sport]
            records.append(
                SportRecord(
                    sport,
                    label,
                    "Mayor distancia",
                    f"{distance_best[0] / 1000:.1f} km",
                    distance_best[1],
                    distance_best[2],
                    sport,
                )
            )
        if sport in best_pace:
            pace_best = best_pace[sport]
            seconds = int(round(pace_best[0]))
            records.append(
                SportRecord(
                    sport,
                    label,
                    "Mejor ritmo",
                    f"{seconds // 60}:{seconds % 60:02d} /km",
                    pace_best[1],
                    pace_best[2],
                    sport,
                )
            )
        if sport in best_ascent:
            ascent_best = best_ascent[sport]
            records.append(
                SportRecord(
                    sport,
                    label,
                    "Mayor desnivel",
                    f"{ascent_best[0]:.0f} m",
                    ascent_best[1],
                    ascent_best[2],
                    sport,
                )
            )
    return tuple(records)


def rebuild(account: AccountId, choices: ExerciseChoices) -> int:
    """Replace the materialized marks for one account from completed sessions."""
    rows: list[PersonalRecord] = []
    for record in strength_records(account, choices):
        if record.value is None:
            continue
        unit = "kg" if record.metric == "1RM estimado" else "rep"
        rows.append(
            PersonalRecord(
                owner_id=account,
                kind="strength",
                context=record.key,
                label=record.name,
                metric=record.metric,
                value=record.value,
                display=f"{record.value:.1f} {unit}",
                detail=record.detail,
                achieved_on=record.achieved_on,
                session_id=record.session_id,
            )
        )
    for sport_record in sport_records(account):
        rows.append(
            PersonalRecord(
                owner_id=account,
                kind="sport",
                context=sport_record.key,
                label=sport_record.label,
                metric=sport_record.metric,
                display=sport_record.display,
                achieved_on=sport_record.achieved_on,
                session_id=sport_record.session_id,
            )
        )
    with transaction.atomic():
        PersonalRecord.objects.filter(owner_id=account).delete()
        PersonalRecord.objects.bulk_create(rows)
    return len(rows)


def ensure_records(account: AccountId, choices: ExerciseChoices) -> int:
    """Backfill once for accounts that predate the materialized table."""
    if PersonalRecord.objects.filter(owner_id=account).exists():
        return 0
    if not Session.objects.filter(owner_id=account, status="completed").exists():
        return 0
    return rebuild(account, choices)


def stored_strength(
    account: AccountId, choices: ExerciseChoices, query: str = ""
) -> tuple[StrengthRecord, ...]:
    catalog = [
        (int(exercise_id), name)
        for exercise_id, name, archived in choices.all()
        if not archived and (not query or query.lower() in name.lower())
    ]
    rows = {
        (row.context, row.metric): row
        for row in PersonalRecord.objects.filter(owner_id=account, kind="strength")
    }
    records: list[StrengthRecord] = []
    for exercise_id, name in sorted(catalog, key=lambda item: item[1]):
        row = rows.get((str(exercise_id), "1RM estimado")) or rows.get(
            (str(exercise_id), "Mejor serie")
        )
        if row is None:
            records.append(
                StrengthRecord(name, "Sin registro", None, "", None, None, str(exercise_id))
            )
            continue
        records.append(
            StrengthRecord(
                name,
                row.metric,
                row.value,
                row.detail,
                row.achieved_on,
                str(row.session_id) if row.session_id else None,
                str(exercise_id),
            )
        )
    return tuple(records)


def stored_sports(account: AccountId) -> tuple[SportRecord, ...]:
    return tuple(
        SportRecord(
            row.context,
            row.label,
            row.metric,
            row.display,
            row.achieved_on or date.today(),
            str(row.session_id) if row.session_id else "",
            row.context,
        )
        for row in PersonalRecord.objects.filter(owner_id=account, kind="sport").order_by(
            "context", "metric"
        )
    )


def grouped_sports(rows: Iterable[SportRecord]) -> tuple[tuple[str, tuple[SportRecord, ...]], ...]:
    groups: dict[str, list[SportRecord]] = {}
    for row in rows:
        groups.setdefault(row.sport, []).append(row)
    return tuple((sport, tuple(items)) for sport, items in sorted(groups.items()))
