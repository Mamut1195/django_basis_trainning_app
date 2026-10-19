"""Trekking stage invariants independent of persistence and forms."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from basis.shared.identifiers import AccountId, SessionId


class InvalidTrekking(ValueError):
    pass


class TrekkingUnavailable(LookupError):
    pass


@dataclass(frozen=True)
class StageNeighbour:
    order: int
    date: date


@dataclass(frozen=True)
class TripData:
    title: str
    notes: str = ""


@dataclass(frozen=True)
class StageData:
    session: SessionId
    order: int
    overnight_altitude_m: Decimal | None = None
    recovery_notes: str = ""


def validate_stage(
    trip_owner: AccountId,
    session_owner: AccountId,
    has_hiking: bool,
    order: int,
    session_date: date,
    neighbours: tuple[StageNeighbour, ...],
) -> None:
    if trip_owner != session_owner:
        raise InvalidTrekking("La etapa pertenece a otra cuenta.")
    if not has_hiking:
        raise InvalidTrekking("La etapa debe tener al menos un bloque de hiking.")
    if any(
        (s.order < order and s.date > session_date) or (s.order > order and s.date < session_date)
        for s in neighbours
    ):
        raise InvalidTrekking("Las fechas de etapas deben seguir su orden.")
