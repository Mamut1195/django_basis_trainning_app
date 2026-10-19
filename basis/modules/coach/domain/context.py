"""Immutable, authorized context: observations remain typed and optional."""

from dataclasses import dataclass
from datetime import datetime

from basis.modules.athletes.public import AthleteCoachContext
from basis.modules.catalog.public import CoachExercise
from basis.modules.training.public import CoachBasePlan, CoachVariables, TrainingCoachContext


@dataclass(frozen=True)
class CoachContext:
    snapshot_at: datetime
    athlete: AthleteCoachContext
    training: TrainingCoachContext
    exercises: tuple[CoachExercise, ...] | None = None
    variables: tuple[CoachVariables, ...] | None = None
    base_plan: CoachBasePlan | None = None
