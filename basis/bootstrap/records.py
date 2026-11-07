"""Composition for the personal-records read model."""

from basis.modules.catalog.adapters.presentation import DjangoExerciseChoices
from basis.modules.catalog.public import ExerciseChoices


def exercise_choices() -> ExerciseChoices:
    return DjangoExerciseChoices()
