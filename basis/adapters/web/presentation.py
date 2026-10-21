from datetime import date

from basis.bootstrap.presentation import athlete_reads, coach_reads, training_reads
from basis.modules.athletes.public import WellnessData
from basis.modules.catalog.adapters.presentation import DjangoExerciseNames
from basis.modules.coach.public import UsageSummary
from basis.modules.training.public import GoalSummary, PlanChoice
from basis.shared.identifiers import AccountId, ExerciseId, GoalId


def wellness_today(owner: int, day: date) -> WellnessData | None:
    return athlete_reads().wellness(AccountId(owner), day)


def current_plans(owner: int) -> tuple[PlanChoice, ...]:
    return training_reads().plans(AccountId(owner))


def goal_choices(owner: int) -> tuple[tuple[GoalId, str], ...]:
    return training_reads().goal_choices(AccountId(owner))


def profile_goals(owner: int) -> tuple[GoalSummary, ...]:
    return training_reads().goals(AccountId(owner))


def latest_usage(owner: int) -> UsageSummary | None:
    return coach_reads().usage(AccountId(owner))


def progress_history(owner: int) -> dict[str, object]:
    result = athlete_reads().history(AccountId(owner))
    return {
        "legacy_records": result.legacy_records,
        "wellness_records": result.wellness_records,
        "measurements": result.measurements,
    }


def exercise_fatigue(exercise: int | None) -> str:
    value = DjangoExerciseNames().fatigue(ExerciseId(exercise)) if exercise is not None else None
    return value if value is not None else "No asignado"
