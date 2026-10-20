"""Convert athlete record scalars before invoking the public strength calculation."""

from decimal import Decimal, InvalidOperation

from basis.modules.training.public import MetricsInputError, StrengthMetrics
from basis.modules.training.public import calculate_strength_metrics as calculate_typed


def decimal_input(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise MetricsInputError(field, "Indica un número decimal finito.") from None
    if not result.is_finite():
        raise MetricsInputError(field, "Indica un número decimal finito.")
    return result


def count_input(value: object, field: str) -> int:
    result = decimal_input(value, field)
    if isinstance(value, bool) or result < 0 or result != result.to_integral_value():
        raise MetricsInputError(field, "Indica un entero mayor o igual a cero.")
    return int(result)


def calculate_strength_metrics(
    *,
    sets: object,
    reps: object,
    weight_kg: object,
    reference_rm_kg: object = None,
    observed_rpe: object = None,
    target_rpe: object = None,
) -> StrengthMetrics:
    # Preserve legacy error precedence before converting later optional inputs.
    typed_sets, typed_reps = count_input(sets, "sets"), count_input(reps, "reps")
    weight = decimal_input(weight_kg, "peso")
    if weight < 0:
        raise MetricsInputError("peso", "La carga no puede ser negativa.")
    rpe = None if observed_rpe is None else decimal_input(observed_rpe, "rpe_real")
    if rpe is not None and not 0 <= rpe <= 10:
        raise MetricsInputError("rpe_real", "El RPE observado debe estar entre 0 y 10.")
    target = None if target_rpe is None else decimal_input(target_rpe, "rpe_objetivo")
    if target is not None and not 0 <= target <= 10:
        raise MetricsInputError("rpe_objetivo", "El RPE objetivo debe estar entre 0 y 10.")
    return calculate_typed(
        sets=typed_sets,
        reps=typed_reps,
        weight_kg=weight,
        reference_rm_kg=None
        if reference_rm_kg is None
        else decimal_input(reference_rm_kg, "rm_referencia"),
        observed_rpe=rpe,
        target_rpe=target,
    )
