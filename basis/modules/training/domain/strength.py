"""Pure arithmetic for homogeneous legacy strength records (no ORM or I/O)."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from basis.shared.identifiers import AthleteId, ExerciseId

METRICS_VERSION = "legacy-strength-v3"
QUANTUM = Decimal("0.01")
# Portable PositiveIntegerField range and the existing DecimalField(14, 2).
MAX_TOTAL_REPS = 2_147_483_647
MAX_LOAD_KG_REPS = Decimal("999999999999.99")


class MetricsInputError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


def _decimal(value: Decimal, field: str) -> Decimal:
    if not value.is_finite():
        raise MetricsInputError(field, "Indica un número decimal finito.")
    return value


def _count(value: int, field: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise MetricsInputError(field, "Indica un entero mayor o igual a cero.")
    return value


@dataclass(frozen=True)
class StrengthMetrics:
    total_reps: int
    load_kg_reps: Decimal
    relative_intensity_percent: Decimal | None
    relative_volume: Decimal | None
    estimated_1rm_kg: Decimal | None


def calculate_strength_metrics(
    *,
    sets: int,
    reps: int,
    weight_kg: Decimal,
    reference_rm_kg: Decimal | None = None,
    observed_rpe: Decimal | None = None,
    target_rpe: Decimal | None = None,
) -> StrengthMetrics:
    """Missing reference/eligible effort yields None, never a measured zero.

    Epley applies only to a declared maximal effort (observed RPE 10),
    positive load and 1..10 reps. A single rep returns the lifted load.
    A legacy row describes equal sets; it cannot identify a particular set.
    """
    sets, reps = _count(sets, "sets"), _count(reps, "reps")
    weight = _decimal(weight_kg, "peso")
    if weight < 0:
        raise MetricsInputError("peso", "La carga no puede ser negativa.")
    rpe = None if observed_rpe is None else _decimal(observed_rpe, "rpe_real")
    if rpe is not None and not 0 <= rpe <= 10:
        raise MetricsInputError("rpe_real", "El RPE observado debe estar entre 0 y 10.")
    target = None if target_rpe is None else _decimal(target_rpe, "rpe_objetivo")
    if target is not None and not 0 <= target <= 10:
        raise MetricsInputError("rpe_objetivo", "El RPE objetivo debe estar entre 0 y 10.")
    reference = None if reference_rm_kg is None else _decimal(reference_rm_kg, "rm_referencia")
    # Historical zero RMs are unknown; do not divide by them or invent a measurement.
    if reference is not None and reference <= 0:
        reference = None
    total = sets * reps
    if total > MAX_TOTAL_REPS:
        raise MetricsInputError("total_reps", f"El total no puede superar {MAX_TOTAL_REPS}.")
    with localcontext() as context:
        context.prec = 40
        load = weight * total
        if load > MAX_LOAD_KG_REPS:
            raise MetricsInputError(
                "carga", f"La carga no puede superar {MAX_LOAD_KG_REPS} kg·rep."
            )
        load = load.quantize(QUANTUM, rounding=ROUND_HALF_UP)
        intensity = volume = estimate = None
        if reference is not None:
            ratio = weight / reference * 100 if total and weight else Decimal(0)
            intensity = ratio.quantize(QUANTUM, rounding=ROUND_HALF_UP)
            # Round the final metric, not its intermediate percentage.
            volume = (ratio * total).quantize(QUANTUM, rounding=ROUND_HALF_UP)
        if sets and weight > 0 and rpe == 10 and 1 <= reps <= 10:
            estimate = (weight if reps == 1 else weight * (30 + reps) / 30).quantize(
                QUANTUM, rounding=ROUND_HALF_UP
            )
    return StrengthMetrics(total, load, intensity, volume, estimate)


def external_volume(
    load_type: str, actual_kg: Decimal | None, actual_reps: int | None
) -> Decimal | None:
    if load_type != "external" or actual_kg is None or actual_reps is None:
        return None
    return calculate_strength_metrics(sets=1, reps=actual_reps, weight_kg=actual_kg).load_kg_reps


def estimated_1rm(
    load_type: str,
    kind: str,
    actual_kg: Decimal | None,
    actual_reps: int | None,
    actual_rpe: Decimal | None,
) -> Decimal | None:
    if (
        load_type != "external"
        or kind != "work"
        or actual_rpe != 10
        or not actual_kg
        or not actual_reps
        or actual_reps > 10
    ):
        return None
    return calculate_strength_metrics(
        sets=1, reps=actual_reps, weight_kg=actual_kg, observed_rpe=actual_rpe
    ).estimated_1rm_kg


def validate_repetition_prescription(
    fixed: int | None,
    minimum: int | None,
    maximum: int | None,
    percent_rm: Decimal | None,
    has_reference: bool,
) -> None:
    if (minimum is None) != (maximum is None) or (
        minimum is not None and maximum is not None and minimum > maximum
    ):
        raise ValueError("Indica un rango de repeticiones completo y ordenado.")
    if fixed is not None and minimum is not None:
        raise ValueError("Usa repeticiones fijas o un rango, no ambos.")
    if percent_rm is not None and not has_reference:
        raise ValueError("El porcentaje RM requiere una referencia medida.")


@dataclass(frozen=True)
class ReferenceContext:
    athlete_id: AthleteId
    exercise_id: ExerciseId
    date: date


def reference_matches(reference: ReferenceContext, workout: ReferenceContext) -> bool:
    return (
        reference.athlete_id == workout.athlete_id
        and reference.exercise_id == workout.exercise_id
        and reference.date <= workout.date
    )


def reference_is_frozen(same_context: bool, reference_id: int | None, metrics_version: str) -> bool:
    return same_context and (
        reference_id is not None or metrics_version in {METRICS_VERSION, "legacy-volume-v2"}
    )
