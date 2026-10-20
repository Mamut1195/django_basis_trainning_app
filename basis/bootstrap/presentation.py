"""Composition factories; input conversion belongs to adapters."""

from basis.modules.athletes.adapters.presentation import DjangoAthletePresentation
from basis.modules.athletes.public import AthletePresentation
from basis.modules.catalog.adapters.presentation import DjangoExerciseNames
from basis.modules.coach.adapters.presentation import DjangoCoachPresentation
from basis.modules.coach.public import CoachPresentation
from basis.modules.training.adapters.presentation import (
    DjangoPlanSummaries,
    DjangoTrainingPresentation,
)
from basis.modules.training.public import PlanSummaries, TrainingPresentation


def athlete_reads() -> AthletePresentation:
    return DjangoAthletePresentation(DjangoExerciseNames())


def training_reads() -> TrainingPresentation:
    return DjangoTrainingPresentation()


def coach_reads() -> CoachPresentation:
    return DjangoCoachPresentation()


def plan_summaries() -> PlanSummaries:
    return DjangoPlanSummaries()
