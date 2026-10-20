"""Framework-free policies for dated measured references and workout results."""

from dataclasses import dataclass
from decimal import Decimal

from basis.shared.identifiers import AthleteId, MeasuredRMId

from .records import (
    InvalidAthleteData,
    MeasuredRMData,
    PreferencesData,
    WorkoutData,
    valid_availability,
)


class InvalidAthleteField(InvalidAthleteData):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


def require_positive_rm(value: Decimal) -> None:
    if not value.is_finite() or value <= 0:
        raise InvalidAthleteData("El 1RM debe ser mayor a 0.")


def validate_preferences(data: PreferencesData, known_timezone: bool) -> None:
    if not valid_availability(list(data.availability)):
        raise InvalidAthleteField("availability", "Usa d\u00edas \u00fanicos de 1 a 7.")
    if not known_timezone:
        raise InvalidAthleteField("timezone_name", "Zona horaria desconocida.")


@dataclass(frozen=True)
class MeasuredReference:
    id: MeasuredRMId
    athlete: AthleteId
    data: MeasuredRMData


@dataclass(frozen=True)
class PreviousWorkout:
    athlete: AthleteId
    data: WorkoutData
    reference: MeasuredReference | None
    metrics_version: str


@dataclass(frozen=True)
class WorkoutContext:
    athlete: AthleteId
    previous: PreviousWorkout | None
    dated_reference: MeasuredReference | None


@dataclass(frozen=True)
class WorkoutReferenceDecision:
    """An unchanged history can freeze a measured reference, including its absence."""

    reuse_previous: bool
    reference: MeasuredRMId | None

    def __post_init__(self) -> None:
        if not self.reuse_previous and self.reference is not None:
            raise ValueError("A fresh context cannot reuse a historical reference.")


@dataclass(frozen=True)
class WorkoutMetrics:
    total_reps: int
    load_kg_reps: Decimal
    relative_intensity_percent: Decimal | None
    relative_volume: Decimal | None
    estimated_1rm_kg: Decimal | None


@dataclass(frozen=True)
class WorkoutCalculation:
    reference: MeasuredRMId | None
    metrics: WorkoutMetrics
    version: str
