"""Pure arithmetic for homogeneous legacy strength records (no ORM or I/O)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

METRICS_VERSION = "legacy-strength-v3"
QUANTUM = Decimal("0.01")
# Portable PositiveIntegerField range and the existing DecimalField(14, 2).
MAX_TOTAL_REPS = 2_147_483_647
MAX_LOAD_KG_REPS = Decimal("999999999999.99")


class MetricsInputError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def _decimal(value, field):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MetricsInputError(field, "Indica un número decimal finito.") from None
    if not result.is_finite():
        raise MetricsInputError(field, "Indica un número decimal finito.")
    return result


def _count(value, field):
    result = _decimal(value, field)
    if isinstance(value, bool) or result < 0 or result != result.to_integral_value():
        raise MetricsInputError(field, "Indica un entero mayor o igual a cero.")
    return int(result)


@dataclass(frozen=True)
class StrengthMetrics:
    total_reps: int
    load_kg_reps: Decimal
    relative_intensity_percent: Decimal | None
    relative_volume: Decimal | None
    estimated_1rm_kg: Decimal | None


def calculate_strength_metrics(
    *, sets, reps, weight_kg, reference_rm_kg=None, observed_rpe=None, target_rpe=None
):
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
