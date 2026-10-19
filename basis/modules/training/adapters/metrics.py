"""Loose legacy numeric and JSON input conversion; pure rules use typed values."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from ..domain.execution import Metric, MetricName
from ..domain.sports import (
    VARIABLES,
    InvalidSportMetrics,
    decimal_internal_load,
    pace_seconds,
    validate_metric,
    validate_sport_metrics,
)
from ..domain.strength import (
    MetricsInputError,
    StrengthMetrics,
    calculate_strength_metrics,
    estimated_1rm,
    external_volume,
)


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


def calculate_legacy_strength(
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
    return calculate_strength_metrics(
        sets=typed_sets,
        reps=typed_reps,
        weight_kg=weight,
        reference_rm_kg=None
        if reference_rm_kg is None
        else decimal_input(reference_rm_kg, "rm_referencia"),
        observed_rpe=rpe,
        target_rpe=target,
    )


def external_volume_legacy(
    load_type: str, actual_kg: object, actual_reps: object
) -> Decimal | None:
    if load_type != "external" or actual_kg is None or actual_reps is None:
        return None
    return external_volume(
        load_type, decimal_input(actual_kg, "peso"), count_input(actual_reps, "reps")
    )


def estimated_1rm_legacy(
    load_type: str, kind: str, actual_kg: object, actual_reps: int | None, actual_rpe: object
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
    return estimated_1rm(
        load_type,
        kind,
        decimal_input(actual_kg, "peso"),
        count_input(actual_reps, "reps"),
        decimal_input(actual_rpe, "rpe_real"),
    )


def validate_metrics(sport: str, data: object) -> dict[str, str]:
    if sport not in VARIABLES or not isinstance(data, dict):
        raise ValidationError("Disciplina o variables inválidas.")
    unknown = set(data) - set(VARIABLES[sport])
    if unknown:
        raise ValidationError("Variables no admitidas: " + ", ".join(sorted(unknown)))
    metrics: list[Metric] = []
    for key, value in data.items():
        if value is None or value == "":
            continue
        spec = VARIABLES[sport][key]
        if spec.kind in ("text", "choice"):
            if not isinstance(value, str):
                raise ValidationError({key: "Texto o selección inválida."})
            parsed: Decimal | str = value
        else:
            try:
                if isinstance(value, bool):
                    raise InvalidOperation
                parsed = Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                raise ValidationError({key: "Valor fuera de rango."}) from None
        try:
            metrics.append(validate_metric(sport, Metric(MetricName(key), parsed)))
        except InvalidSportMetrics as error:
            raise ValidationError({key: str(error)}) from error
    try:
        result = validate_sport_metrics(sport, tuple(metrics))
    except InvalidSportMetrics as error:
        raise ValidationError({error.field: str(error)} if error.field else str(error)) from error
    return {metric.name.value: str(metric.value) for metric in result}


def pace_seconds_legacy(data: dict[str, str], per_metres: int = 1000) -> Decimal | None:
    distance = Decimal(data["distance_m"]) if data.get("distance_m") is not None else None
    duration = (
        Decimal(data["duration_seconds"]) if data.get("duration_seconds") is not None else None
    )
    return pace_seconds(distance, duration, per_metres)


def internal_load_legacy(duration_seconds: object, reported_rpe: object) -> Decimal | None:
    # Existing callers may supply Decimal, string or a legacy float.
    if duration_seconds is None or reported_rpe is None:
        return None
    return decimal_internal_load(Decimal(str(duration_seconds)), Decimal(str(reported_rpe)))
