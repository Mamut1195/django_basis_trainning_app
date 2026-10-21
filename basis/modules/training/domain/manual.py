"""Policies for incremental manual training, independent of offline limits."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId

from .execution import DurationProtocol, IntervalData, InvalidExecution, StrengthData, Unavailable
from .execution_updates import (
    STRENGTH_INTENT,
    preserve_interval,
    preserve_strength,
    validate_adaptation,
)
from .planning import validate_prescribed_results
from .sports import VARIABLES, validate_sport_metrics
from .strength import validate_repetition_prescription


@dataclass(frozen=True)
class SessionParent:
    id: SessionId


@dataclass(frozen=True)
class PlannedParent:
    id: PlannedSessionId


type ParentRef = SessionParent | PlannedParent


@dataclass(frozen=True)
class ParentState:
    ref: ParentRef
    owner: AccountId
    date: date
    revision: Revision
    completed: bool = False
    frozen: bool = False
    from_prescription: bool = False
    versioned_intent: bool = False


@dataclass(frozen=True)
class ManualSessionData:
    title: str
    date: date
    duration_seconds: int | None = None
    duration_protocol: DurationProtocol = DurationProtocol.ELAPSED
    reported_rpe: Decimal | None = None
    notes: str = ""


class ManualInvalid(Exception):
    pass


def require_versioned_edit(parent: ParentState, changed: bool) -> None:
    if isinstance(parent.ref, PlannedParent) and changed and not parent.versioned_intent:
        raise ManualInvalid(
            "Crea una nueva versión del plan con motivo antes de cambiar la prescripción original."
        )


class ManualConflict(Exception):
    def __init__(self, current: ParentState) -> None:
        self.current = current
        super().__init__("Training parent revision conflict")


class EmptyPrescription(Exception):
    pass


@dataclass(frozen=True)
class FormPolicy:
    strength_read_only: tuple[str, ...]
    interval_read_only: tuple[str, ...]


def form_policy(parent: ParentState) -> FormPolicy:
    if not parent.from_prescription:
        return FormPolicy((), ())
    return FormPolicy(
        STRENGTH_INTENT,
        ("repetitions", "rest_seconds", "target_rpe"),
    )


def require_parent(current: ParentState | None, owner: AccountId) -> ParentState:
    if current is None or current.owner != owner:
        raise Unavailable("La sesión no está disponible.")
    if current.completed:
        raise ManualInvalid("Esta ejecución está completada y se conserva como historial.")
    if current.frozen:
        raise ManualInvalid("Crea otra versión del plan para cambiar la prescripción.")
    return current


def next_revision(current: ParentState, owner: AccountId, expected: Revision) -> Revision:
    if current.owner != owner:
        raise Unavailable("La sesión no está disponible.")
    if current.revision != expected:
        raise ManualConflict(current)
    if current.completed:
        raise ManualInvalid("La sesión ya se completó.")
    require_parent(current, owner)
    return Revision(expected + 1)


def validate_heading(sport: str, title: str) -> None:
    if sport not in VARIABLES or not title or len(title) > 160:
        raise ManualInvalid("Disciplina o nombre de bloque inválidos.")


def validate_session(data: ManualSessionData) -> None:
    if not data.title or len(data.title) > 160:
        raise ManualInvalid("Nombre de sesión inválido.")
    if data.duration_seconds is not None and not 0 <= data.duration_seconds <= 604800:
        raise ManualInvalid("Duración fuera de rango.")
    decimal_range(data.reported_rpe, Decimal(0), Decimal(10))


def decimal_range(
    value: Decimal | None, minimum: Decimal, maximum: Decimal, places: int = 1
) -> None:
    if value is not None and (not value.is_finite() or not minimum <= value <= maximum):
        raise ManualInvalid("Valor fuera de rango.")
    if value is not None:
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -places:
            raise ManualInvalid("Demasiados decimales.")


def validate_strength(sport: str, parent: ParentState, data: StrengthData) -> None:
    try:
        validate_adaptation(data)
    except InvalidExecution as error:
        raise ManualInvalid(str(error)) from error
    validate_repetition_prescription(
        data.target_reps,
        data.target_reps_min,
        data.target_reps_max,
        data.target_percent_rm,
        data.rm_reference is not None,
    )
    if sport != "strength":
        raise ManualInvalid("Las series de fuerza requieren un bloque de fuerza.")
    if (
        data.kind not in {"warmup", "work", "failed"}
        or data.load_type not in {"external", "bodyweight", "assisted"}
        or data.side not in {"both", "left", "right"}
    ):
        raise ManualInvalid("Tipo de serie, carga o lado inválidos.")
    for value in (
        data.target_reps,
        data.target_reps_min,
        data.target_reps_max,
        data.actual_reps,
        data.rest_seconds,
        data.actual_rest_seconds,
        data.isometric_seconds,
        data.target_isometric_seconds,
    ):
        if value is not None and (type(value) is not int or not 0 <= value <= 2147483647):
            raise ManualInvalid("Repeticiones o duración fuera de rango.")
    for value in (data.target_rir, data.actual_rir):
        if value is not None and (type(value) is not int or not 0 <= value <= 20):
            raise ManualInvalid("RIR fuera de rango.")
    for load in (data.target_kg, data.actual_kg):
        decimal_range(load, Decimal(0), Decimal("99999.99"), places=2)
    decimal_range(data.bodyweight_kg, Decimal("0.01"), Decimal("9999.99"), places=2)
    decimal_range(data.target_percent_rm, Decimal(0), Decimal(200), places=2)
    decimal_range(data.target_rpe, Decimal(0), Decimal(10))
    decimal_range(data.actual_rpe, Decimal(0), Decimal(10))
    if len(data.tempo) > 30 or len(data.range_of_motion) > 80 or len(data.group) > 80:
        raise ManualInvalid("Texto de serie demasiado largo.")
    if isinstance(parent.ref, PlannedParent):
        if (
            any(
                getattr(data, name) is not None
                for name in (
                    "actual_exercise",
                    "actual_load_type",
                    "actual_kind",
                    "actual_tempo",
                    "actual_range_of_motion",
                    "actual_side",
                    "actual_group",
                )
            )
            or data.adaptation_reason
        ):
            raise ManualInvalid("Una prescripción no contiene adaptaciones realizadas.")
        validate_prescribed_results(
            any(
                v is not None
                for v in (
                    data.actual_kg,
                    data.actual_reps,
                    data.actual_rpe,
                    data.actual_rir,
                    data.actual_rest_seconds,
                    data.isometric_seconds,
                )
            )
        )


def require_strength_prescription(current: StrengthData, candidate: StrengthData) -> None:
    try:
        preserve_strength(current, candidate)
    except InvalidExecution as error:
        raise ManualInvalid(str(error)) from error


def validate_interval(sport: str, parent: ParentState, data: IntervalData) -> None:
    if sport == "strength":
        raise ManualInvalid("Usa series para fuerza.")
    if not 1 <= data.repetitions <= 1000:
        raise ManualInvalid("Repeticiones fuera de rango.")
    for value in (data.rest_seconds, data.actual_rest_seconds):
        if value is not None and not 0 <= value <= 2147483647:
            raise ManualInvalid("Descanso fuera de rango.")
    decimal_range(data.target_rpe, Decimal(0), Decimal(10))
    decimal_range(data.actual_rpe, Decimal(0), Decimal(10))
    validate_sport_metrics(sport, data.target)
    validate_sport_metrics(sport, data.actual)
    if isinstance(parent.ref, PlannedParent):
        validate_prescribed_results(
            bool(data.actual) or data.actual_rpe is not None or data.actual_rest_seconds is not None
        )


def require_interval_prescription(current: IntervalData, candidate: IntervalData) -> None:
    try:
        preserve_interval(current, candidate)
    except InvalidExecution as error:
        raise ManualInvalid(str(error)) from error
