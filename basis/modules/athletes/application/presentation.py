"""Read values used by composed dashboards without exposing persistence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId

from ..domain.records import MeasurementData, WellnessData


@dataclass(frozen=True)
class ExerciseName:
    nombre: str


@dataclass(frozen=True)
class HistoricalWorkout:
    fecha: date
    exercise: ExerciseName
    sets: int
    reps: int
    peso: Decimal
    rpe_real: Decimal | None


@dataclass(frozen=True)
class AthleteHistory:
    legacy_records: tuple[HistoricalWorkout, ...]
    wellness_records: tuple[WellnessData, ...]
    measurements: tuple[MeasurementData, ...]


class AthletePresentation(Protocol):
    def wellness(self, owner: AccountId, day: date) -> WellnessData | None: ...
    def history(self, owner: AccountId) -> AthleteHistory: ...
