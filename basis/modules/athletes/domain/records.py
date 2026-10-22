"""Typed athlete data; absent observations remain distinct from zero."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from basis.shared.identifiers import AccountId, AthleteId, ExerciseId
from basis.shared.text import normalized_name


class AthleteUnavailable(Exception):
    pass


class InvalidAthleteData(Exception):
    pass


@dataclass(frozen=True)
class ProfileData:
    nombre: str
    titulo: str | None
    pais: str | None
    ciudad: str | None
    especialidad: str | None
    edad: int | None
    peso: Decimal | None
    objetivos: str | None
    descripcion: str | None


@dataclass(frozen=True)
class PreferencesData:
    availability: tuple[int, ...]
    minutes_per_session: int
    equipment: str
    limitations: str
    timezone_name: str


@dataclass(frozen=True)
class SportData:
    sport: str
    experience: str
    threshold: Decimal | None
    threshold_unit: str
    measured_on: date | None
    method: str
    threshold_kind: str = ""
    threshold_source: str = ""


@dataclass(frozen=True)
class WellnessData:
    date: date
    sleep_hours: Decimal | None
    sleep_quality: int | None
    fatigue: int | None
    stress: int | None
    soreness: int | None
    readiness: int | None
    pain_regions: str
    pain_score: int | None
    resting_hr_bpm: int | None
    hrv_ms: Decimal | None
    hrv_method: str
    notes: str


@dataclass(frozen=True)
class MeasurementData:
    date: date
    weight_kg: Decimal
    notes: str


def validate_measurement(data: MeasurementData, today: date) -> None:
    if not data.weight_kg.is_finite() or not Decimal("0.01") <= data.weight_kg <= 500:
        raise InvalidAthleteData(
            "El peso medido debe estar entre 0,01 y 500 kg; cero no es ausencia."
        )
    validate_observation_date(data.date, today)


def validate_observation_date(measured_on: date, today: date) -> None:
    if measured_on > today:
        raise InvalidAthleteData("Una medición realizada no puede tener fecha futura.")


@dataclass(frozen=True)
class MeasuredRMData:
    exercise: ExerciseId
    peso_maximo_rm: Decimal
    fecha_registro: date


@dataclass(frozen=True)
class WorkoutData:
    exercise: ExerciseId
    fecha: date
    sets: int
    reps: int
    peso: Decimal
    rpe_objetivo: float
    rpe_real: Decimal | None


def require_adult(age: int | None) -> None:
    if age is not None and not 18 <= age <= 120:
        raise InvalidAthleteData("La aplicación está dirigida a personas adultas.")


def validate_sport(data: SportData) -> None:
    if data.sport not in {"strength", "cardio", "running", "cycling", "swimming", "hiking"}:
        raise InvalidAthleteData("Disciplina inválida.")
    if data.threshold is not None and (
        not isinstance(data.threshold, Decimal)
        or not data.threshold.is_finite()
        or not Decimal("0.01") <= data.threshold <= Decimal("999999.99")
    ):
        raise InvalidAthleteData("Umbral fuera del rango decimal declarado.")
    if data.threshold is not None and (
        not data.threshold_unit or not data.measured_on or not data.method.strip()
    ):
        raise InvalidAthleteData("Un umbral requiere unidad, fecha y método.")
    allowed = {
        "strength": set(),
        "cardio": {"bpm"},
        "running": {"bpm", "seconds_km"},
        "cycling": {"bpm", "watts"},
        "swimming": {"bpm", "seconds_100m"},
        "hiking": {"bpm"},
    }
    if data.threshold_unit and data.threshold_unit not in allowed.get(data.sport, set()):
        raise InvalidAthleteData("Unidad de umbral incompatible con la disciplina.")
    if data.threshold_kind not in {"", "measured", "estimated"}:
        raise InvalidAthleteData("Indica si el umbral es medido o estimado.")
    if data.threshold is None and any(
        (
            data.threshold_unit,
            data.measured_on,
            data.threshold_kind,
            data.threshold_source,
        )
    ):
        raise InvalidAthleteData("Los metadatos de umbral requieren un valor; ausencia no es cero.")


def validate_wellness(data: WellnessData) -> None:
    if data.hrv_ms is not None and not data.hrv_method:
        raise InvalidAthleteData("Indica el método de medición HRV.")
    if data.pain_score is not None and data.pain_score > 0 and not data.pain_regions:
        raise InvalidAthleteData("Indica dónde sientes dolor.")


@dataclass(frozen=True)
class MeasuredRMState:
    athlete: AthleteId
    data: MeasuredRMData


def require_unchanged_rm(previous: MeasuredRMState, current: MeasuredRMState) -> None:
    if previous != current:
        raise InvalidAthleteData(
            "El RM es una medici\u00f3n hist\u00f3rica. Registra otra medici\u00f3n con su fecha."
        )


def require_legacy_link(
    current: AccountId | None,
    requested: AccountId,
    has_other_profile: bool,
    profile_email: str,
    account_email: str,
) -> None:
    if current is not None and current != requested:
        raise InvalidAthleteData("El perfil ya est\u00e1 vinculado a otra cuenta.")
    if has_other_profile:
        raise InvalidAthleteData(
            "La cuenta ya tiene otro perfil. No se fusiona autom\u00e1ticamente."
        )
    if profile_email.casefold() != account_email.casefold():
        raise InvalidAthleteData(
            "Los correos no coinciden. Verifica la titularidad antes de continuar."
        )


def valid_availability(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(type(day) is int and day in range(1, 8) for day in value)
        and len(set(value)) == len(value)
    )


def normalized_profile(data: ProfileData) -> ProfileData:
    return replace(
        data,
        nombre=normalized_name(data.nombre) if data.nombre else data.nombre,
        titulo=normalized_name(data.titulo) if data.titulo else data.titulo,
        pais=normalized_name(data.pais) if data.pais else data.pais,
        ciudad=normalized_name(data.ciudad) if data.ciudad else data.ciudad,
        especialidad=normalized_name(data.especialidad) if data.especialidad else data.especialidad,
    )
