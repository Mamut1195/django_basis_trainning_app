"""Compose athlete history policy with the public training metric calculation."""

from decimal import Decimal

from basis.modules.training.public import (
    METRICS_VERSION,
    ReferenceContext,
    calculate_strength_metrics,
    reference_is_frozen,
    reference_matches,
)

from ..domain.records import WorkoutData
from ..domain.workouts import (
    InvalidAthleteField,
    WorkoutCalculation,
    WorkoutContext,
    WorkoutMetrics,
)


def calculate_workout(data: WorkoutData, context: WorkoutContext) -> WorkoutCalculation:
    previous = context.previous
    same_context = previous is not None and (
        previous.athlete == context.athlete
        and previous.data.exercise == data.exercise
        and previous.data.fecha == data.fecha
    )
    if previous is not None and reference_is_frozen(
        same_context,
        previous.reference.id if previous.reference is not None else None,
        previous.metrics_version,
    ):
        reference = previous.reference
    else:
        reference = context.dated_reference
    if reference is not None and not reference_matches(
        ReferenceContext(reference.athlete, reference.data.exercise, reference.data.fecha_registro),
        ReferenceContext(context.athlete, data.exercise, data.fecha),
    ):
        raise InvalidAthleteField("rm_referencia", "Referencia RM ajena, incompatible o futura.")
    metrics = calculate_strength_metrics(
        sets=data.sets,
        reps=data.reps,
        weight_kg=data.peso,
        reference_rm_kg=reference.data.peso_maximo_rm if reference is not None else None,
        observed_rpe=data.rpe_real,
        target_rpe=Decimal(str(data.rpe_objetivo)),
    )
    return WorkoutCalculation(
        reference.id if reference is not None else None,
        WorkoutMetrics(
            metrics.total_reps,
            metrics.load_kg_reps,
            metrics.relative_intensity_percent,
            metrics.relative_volume,
            metrics.estimated_1rm_kg,
        ),
        METRICS_VERSION,
    )
