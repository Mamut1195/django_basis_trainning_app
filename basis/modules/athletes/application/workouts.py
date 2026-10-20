"""Compose athlete history policy with the public training metric calculation."""

from decimal import Decimal

from basis.modules.training.public import (
    METRICS_VERSION,
    ReferenceContext,
    calculate_strength_metrics,
    reference_is_frozen,
    reference_matches,
)
from basis.shared.identifiers import MeasuredRMId

from ..domain.records import WorkoutData
from ..domain.workouts import (
    InvalidAthleteField,
    WorkoutCalculation,
    WorkoutContext,
    WorkoutMetrics,
    WorkoutReferenceDecision,
)


def decide_workout_reference(
    current: ReferenceContext,
    previous: ReferenceContext | None,
    previous_reference: MeasuredRMId | None,
    previous_metrics_version: str,
) -> WorkoutReferenceDecision:
    reuse_previous = previous is not None and reference_is_frozen(
        current == previous, previous_reference, previous_metrics_version
    )
    return WorkoutReferenceDecision(reuse_previous, previous_reference if reuse_previous else None)


def validate_workout_reference(
    reference: ReferenceContext | None, current: ReferenceContext
) -> None:
    if reference is not None and not reference_matches(reference, current):
        raise InvalidAthleteField("rm_referencia", "Referencia RM ajena, incompatible o futura.")


def calculate_workout(data: WorkoutData, context: WorkoutContext) -> WorkoutCalculation:
    previous = context.previous
    current = ReferenceContext(context.athlete, data.exercise, data.fecha)
    decision = decide_workout_reference(
        current,
        ReferenceContext(previous.athlete, previous.data.exercise, previous.data.fecha)
        if previous is not None
        else None,
        previous.reference.id if previous is not None and previous.reference is not None else None,
        previous.metrics_version if previous is not None else "",
    )
    if previous is not None and decision.reuse_previous:
        reference = previous.reference
    else:
        reference = context.dated_reference
    validate_workout_reference(
        ReferenceContext(reference.athlete, reference.data.exercise, reference.data.fecha_registro)
        if reference is not None
        else None,
        current,
    )
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
