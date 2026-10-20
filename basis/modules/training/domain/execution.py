"""Immutable execution state. No framework, wire dictionaries or providers."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DurationProtocol(StrEnum):
    ELAPSED = "elapsed"
    MOVING = "moving"


class MetricName(StrEnum):
    DURATION_SECONDS = "duration_seconds"
    DISTANCE_M = "distance_m"
    HEART_RATE_BPM = "heart_rate_bpm"
    MAX_HEART_RATE_BPM = "max_heart_rate_bpm"
    SESSION_TYPE = "session_type"
    SURFACE = "surface"
    MOVING_SECONDS = "moving_seconds"
    PAUSE_SECONDS = "pause_seconds"
    ASCENT_M = "ascent_m"
    DESCENT_M = "descent_m"
    START_ALTITUDE_M = "start_altitude_m"
    MAX_ALTITUDE_M = "max_altitude_m"
    END_ALTITUDE_M = "end_altitude_m"
    PACK_KG = "pack_kg"
    TERRAIN = "terrain"
    DIFFICULTY_SCALE = "difficulty_scale"
    DIFFICULTY_GRADE = "difficulty_grade"
    DIFFICULTY_SOURCE = "difficulty_source"
    EQUIPMENT = "equipment"
    CADENCE_SPM = "cadence_spm"
    POWER_W = "power_w"
    CADENCE_RPM = "cadence_rpm"
    ENVIRONMENT = "environment"
    STROKE = "stroke"
    POOL_LENGTH_M = "pool_length_m"
    LAPS = "laps"
    STROKES = "strokes"
    DRILL = "drill"


@dataclass(frozen=True)
class Metric:
    name: MetricName
    value: Decimal | str


@dataclass(frozen=True)
class StrengthData:
    exercise: int
    kind: str = "work"
    load_type: str = "external"
    tempo: str = ""
    range_of_motion: str = ""
    side: str = "both"
    group: str = ""
    target_reps: int | None = None
    target_reps_min: int | None = None
    target_reps_max: int | None = None
    actual_reps: int | None = None
    target_rir: int | None = None
    actual_rir: int | None = None
    rest_seconds: int | None = None
    actual_rest_seconds: int | None = None
    isometric_seconds: int | None = None
    target_isometric_seconds: int | None = None
    target_percent_rm: Decimal | None = None
    target_kg: Decimal | None = None
    actual_kg: Decimal | None = None
    bodyweight_kg: Decimal | None = None
    target_rpe: Decimal | None = None
    actual_rpe: Decimal | None = None
    rm_reference: int | None = None


@dataclass(frozen=True)
class IntervalData:
    repetitions: int = 1
    target: tuple[Metric, ...] = ()
    actual: tuple[Metric, ...] = ()
    rest_seconds: int | None = None
    actual_rest_seconds: int | None = None
    target_rpe: Decimal | None = None
    actual_rpe: Decimal | None = None


@dataclass(frozen=True)
class BlockData:
    sport: str
    title: str = ""
    id: int | None = None
    order: int = 1
    target: tuple[Metric, ...] = ()
    actual: tuple[Metric, ...] = ()
    notes: str = ""
    sets: tuple[StrengthData, ...] = ()
    intervals: tuple[IntervalData, ...] = ()


@dataclass(frozen=True)
class Prescription:
    id: PlannedSessionId
    owner: AccountId
    title: str
    blocks: tuple[BlockData, ...]


@dataclass(frozen=True)
class SessionState:
    id: SessionId
    owner: AccountId
    date: date
    title: str = ""
    revision: Revision = Revision(1)
    status: SessionStatus = SessionStatus.IN_PROGRESS
    planned: PlannedSessionId | None = None
    duration_seconds: int | None = None
    duration_protocol: DurationProtocol = DurationProtocol.ELAPSED
    reported_rpe: Decimal | None = None
    notes: str = ""
    blocks: tuple[BlockData, ...] = ()


class Unavailable(Exception):
    pass


class InvalidExecution(Exception):
    pass


class ExecutionConflict(Exception):
    def __init__(self, current: SessionState) -> None:
        self.current = current
        super().__init__("Execution revision or completed-state conflict")


def require_editable(current: SessionState, owner: AccountId, expected: Revision) -> Revision:
    if current.owner != owner:
        raise Unavailable("La sesión no está disponible.")
    if current.revision != expected or current.status == SessionStatus.COMPLETED:
        raise ExecutionConflict(current)
    return Revision(expected + 1)


def start_execution(prescription: Prescription, session_id: SessionId, today: date) -> SessionState:
    return SessionState(
        id=session_id,
        owner=prescription.owner,
        date=today,
        title=prescription.title,
        planned=prescription.id,
        blocks=tuple(replace(b, id=None) for b in prescription.blocks),
    )


def validate_component_sport(sport: str, *, strength: bool) -> None:
    if strength and sport != "strength":
        raise InvalidExecution("Las series de fuerza requieren un bloque de fuerza.")
    if not strength and sport == "strength":
        raise InvalidExecution("Usa series para fuerza.")
