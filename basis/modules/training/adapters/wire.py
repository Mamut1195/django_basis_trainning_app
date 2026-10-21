"""Legacy JSON conversion only; application contracts contain typed values."""

from dataclasses import fields
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping, cast
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import DateField

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId

from ..application.execution import Change, RecordSession, SessionChanges
from ..domain.execution import (
    AdaptationField,
    AdaptationPresence,
    BlockData,
    DurationProtocol,
    IntervalData,
    Metric,
    MetricName,
    SessionState,
    SessionStatus,
    StrengthData,
)


def object_map(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValidationError("Formato inválido.")
    return cast(dict[str, object], value)


def sequence(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValidationError("Formato inválido.")
    return cast(list[object], value)


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValidationError("Texto inválido.")
    return value


def integer(value: object) -> int:
    if not isinstance(value, bool) and isinstance(value, (str, int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValidationError("Número entero inválido.") from None
        if number.is_finite() and number == number.to_integral_value():
            return int(number)
    raise ValidationError("Número entero inválido.")


def optional_integer(value: object) -> int | None:
    return None if value is None else integer(value)


def optional_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool):
        raise ValidationError("Número decimal inválido.")
    try:
        return None if value is None else Decimal(str(value))
    except InvalidOperation:
        raise ValidationError("Número decimal inválido.") from None


def block_identity(value: object) -> int | None:
    if isinstance(value, str):
        try:
            Decimal(value)
        except InvalidOperation:
            return None  # Legacy client-local label, never a server identity.
    return optional_integer(value)


def day(value: object) -> date:
    result = DateField().to_python(value)
    if not isinstance(result, date):
        raise ValidationError("Fecha inválida.")
    return result


def metrics(value: object) -> tuple[Metric, ...]:
    result: list[Metric] = []
    for key, raw in object_map(value).items():
        if raw is None or raw == "":
            continue
        try:
            name = MetricName(key)
        except ValueError:
            raise ValidationError("Variables no admitidas: " + key) from None
        if isinstance(raw, bool):
            raise ValidationError({key: "Valor fuera de rango."})
        if key in TEXT_METRICS:
            metric_value: Decimal | str = text(raw)
        else:
            parsed = optional_decimal(raw)
            assert parsed is not None
            metric_value = parsed
        result.append(Metric(name, metric_value))
    return tuple(result)


def encode_metrics(values: tuple[Metric, ...]) -> dict[str, str]:
    return {item.name.value: str(item.value) for item in values}


def scalar(value: object) -> object:
    return str(value) if isinstance(value, Decimal) else value


def encode_strength(row: StrengthData) -> dict[str, object]:
    return {field.name: scalar(getattr(row, field.name)) for field in fields(row)}


def encode_interval(row: IntervalData) -> dict[str, object]:
    return {
        "id": row.id,
        "source": row.source,
        "repetitions": row.repetitions,
        "target": encode_metrics(row.target),
        "actual": encode_metrics(row.actual),
        "rest_seconds": row.rest_seconds,
        "actual_rest_seconds": row.actual_rest_seconds,
        "target_rpe": scalar(row.target_rpe),
        "actual_rpe": scalar(row.actual_rpe),
    }


def encode_block(block: BlockData) -> dict[str, object]:
    return {
        "id": block.id,
        "source": block.source,
        "order": block.order,
        "sport": block.sport,
        "title": block.title,
        "target": encode_metrics(block.target),
        "actual": encode_metrics(block.actual),
        "notes": block.notes,
        "sets": [encode_strength(s) for s in block.sets],
        "intervals": [encode_interval(i) for i in block.intervals],
    }


def encode_session(state: SessionState) -> dict[str, object]:
    return {
        "id": str(state.id),
        "revision": int(state.revision),
        "title": state.title,
        "date": state.date.isoformat(),
        "status": state.status.value,
        "duration_seconds": state.duration_seconds,
        "duration_protocol": state.duration_protocol.value,
        "reported_rpe": scalar(state.reported_rpe),
        "notes": state.notes,
        "planned": state.planned,
        "blocks": [encode_block(block) for block in state.blocks],
    }


TEXT_METRICS = frozenset(
    (
        "session_type",
        "surface",
        "terrain",
        "difficulty_scale",
        "difficulty_grade",
        "difficulty_source",
        "equipment",
        "environment",
        "stroke",
        "drill",
    )
)


def strength(value: object) -> StrengthData:
    row = object_map(value)
    if set(row) - {f.name for f in fields(StrengthData)}:
        raise ValidationError("Variables de serie o intervalo inválidas.")
    return StrengthData(
        exercise=integer(row.get("exercise")),
        kind=text(row.get("kind", "work")),
        load_type=text(row.get("load_type", "external")),
        tempo=text(row.get("tempo", "")),
        range_of_motion=text(row.get("range_of_motion", "")),
        side=text(row.get("side", "both")),
        group=text(row.get("group", "")),
        target_reps=optional_integer(row.get("target_reps")),
        target_reps_min=optional_integer(row.get("target_reps_min")),
        target_reps_max=optional_integer(row.get("target_reps_max")),
        actual_reps=optional_integer(row.get("actual_reps")),
        target_rir=optional_integer(row.get("target_rir")),
        actual_rir=optional_integer(row.get("actual_rir")),
        rest_seconds=optional_integer(row.get("rest_seconds")),
        actual_rest_seconds=optional_integer(row.get("actual_rest_seconds")),
        isometric_seconds=optional_integer(row.get("isometric_seconds")),
        target_isometric_seconds=optional_integer(row.get("target_isometric_seconds")),
        target_percent_rm=optional_decimal(row.get("target_percent_rm")),
        target_kg=optional_decimal(row.get("target_kg")),
        actual_kg=optional_decimal(row.get("actual_kg")),
        bodyweight_kg=optional_decimal(row.get("bodyweight_kg")),
        target_rpe=optional_decimal(row.get("target_rpe")),
        actual_rpe=optional_decimal(row.get("actual_rpe")),
        rm_reference=optional_integer(row.get("rm_reference")),
        id=optional_integer(row.get("id")),
        source=optional_integer(row.get("source")),
        actual_exercise=optional_integer(row.get("actual_exercise")),
        actual_load_type=optional_text(row.get("actual_load_type")),
        actual_kind=optional_text(row.get("actual_kind")),
        actual_tempo=optional_text(row.get("actual_tempo")),
        actual_range_of_motion=optional_text(row.get("actual_range_of_motion")),
        actual_side=optional_text(row.get("actual_side")),
        actual_group=optional_text(row.get("actual_group")),
        adaptation_reason=text(row.get("adaptation_reason", "")),
    )


def optional_text(value: object) -> str | None:
    return None if value is None else text(value)


def interval(value: object) -> IntervalData:
    row = object_map(value)
    if set(row) - {f.name for f in fields(IntervalData)}:
        raise ValidationError("Variables de serie o intervalo inválidas.")
    return IntervalData(
        id=optional_integer(row.get("id")),
        source=optional_integer(row.get("source")),
        repetitions=integer(row.get("repetitions", 1)),
        target=metrics(row.get("target", {})),
        actual=metrics(row.get("actual", {})),
        rest_seconds=optional_integer(row.get("rest_seconds")),
        actual_rest_seconds=optional_integer(row.get("actual_rest_seconds")),
        target_rpe=optional_decimal(row.get("target_rpe")),
        actual_rpe=optional_decimal(row.get("actual_rpe")),
    )


def blocks(value: object) -> tuple[BlockData, ...]:
    rows = sequence(value)
    if not 1 <= len(rows) <= 30:
        raise ValidationError("Una sesión necesita entre 1 y 30 bloques.")
    result: list[BlockData] = []
    for raw in rows:
        row = object_map(raw)
        if set(row) - {
            "id",
            "source",
            "order",
            "sport",
            "title",
            "target",
            "actual",
            "notes",
            "sets",
            "intervals",
        }:
            raise ValidationError("Formato de bloque inválido.")
        sets = sequence(row.get("sets", []))
        intervals = sequence(row.get("intervals", []))
        if len(sets) > 100 or len(intervals) > 100:
            raise ValidationError("Demasiadas series o intervalos.")
        result.append(
            BlockData(
                # Temporary string IDs from the original offline client carry no
                # server identity. Integer IDs are authoritative and parent-scoped.
                id=block_identity(row.get("id")),
                source=optional_integer(row.get("source")),
                sport=text(row.get("sport", "")),
                title=text(row.get("title", "")),
                target=metrics(row.get("target", {})),
                actual=metrics(row.get("actual", {})),
                notes=text(row.get("notes", "")),
                sets=tuple(strength(s) for s in sets),
                intervals=tuple(interval(i) for i in intervals),
            )
        )
    return tuple(result)


def decode_record(owner: AccountId, payload: Mapping[str, object]) -> RecordSession:
    changes = SessionChanges(
        blocks=blocks(payload.get("blocks")),
        adaptation_presence=adaptation_presence(payload.get("blocks")),
        title=Change(text(payload["title"])) if "title" in payload else None,
        date=Change(day(payload["date"])) if "date" in payload else None,
        status=Change(SessionStatus(text(payload["status"]))) if "status" in payload else None,
        planned=PlannedSessionId(integer(payload["planned"])) if payload.get("planned") else None,
        duration_seconds=Change(optional_integer(payload["duration_seconds"]))
        if "duration_seconds" in payload
        else None,
        duration_protocol=Change(DurationProtocol(text(payload["duration_protocol"])))
        if "duration_protocol" in payload
        else None,
        reported_rpe=Change(optional_decimal(payload["reported_rpe"]))
        if "reported_rpe" in payload
        else None,
        notes=Change(text(payload["notes"])) if "notes" in payload else None,
    )
    return RecordSession(
        owner, SessionId(UUID(text(payload["id"]))), Revision(integer(payload["revision"])), changes
    )


def adaptation_presence(raw: object) -> AdaptationPresence:
    return tuple(
        tuple(
            frozenset(field for field in AdaptationField if field.value in object_map(row))
            for row in sequence(object_map(block).get("sets", []))
        )
        for block in sequence(raw)
    )
