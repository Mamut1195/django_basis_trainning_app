"""Server-owned reference capture and strict snapshot codec."""

from dataclasses import asdict
from datetime import date

from basis.modules.athletes.public import SportThresholds
from basis.shared.identifiers import AccountId

from ..domain.thresholds import ThresholdSnapshot
from .wire import day, integer, object_map, optional_decimal, text

_references: SportThresholds | None = None


def configure_thresholds(references: SportThresholds) -> None:
    global _references
    _references = references


def capture(
    owner: AccountId, sport: str, through: date, *, using: str = "default"
) -> ThresholdSnapshot | None:
    if _references is None:
        raise RuntimeError("Sport threshold reader has not been configured.")
    row = _references.current(owner, sport, through, using=using)
    return ThresholdSnapshot(**asdict(row)) if row is not None else None


def encode_snapshot(value: ThresholdSnapshot | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        **asdict(value),
        "value": str(value.value),
        "measured_on": value.measured_on.isoformat(),
    }


def decode_snapshot(value: object) -> ThresholdSnapshot | None:
    if value is None:
        return None
    row = object_map(value)
    from django.core.exceptions import ValidationError

    if set(row) != {
        "profile_id",
        "sport",
        "value",
        "unit",
        "measured_on",
        "method",
        "kind",
        "source",
    }:
        raise ValidationError("Referencia de umbral inválida.")
    number = optional_decimal(row["value"])
    if number is None or not number.is_finite():
        raise ValidationError("Referencia de umbral inválida.")
    return ThresholdSnapshot(
        integer(row["profile_id"]),
        text(row["sport"]),
        number,
        text(row["unit"]),
        day(row["measured_on"]),
        text(row["method"]),
        text(row["kind"]),
        text(row["source"]),
    )
