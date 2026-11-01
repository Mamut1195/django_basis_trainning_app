"""Compose the independent read-only strength mark ports."""

from basis.modules.athletes.adapters.marks import DjangoMeasuredMarks
from basis.modules.athletes.public import MeasuredMarks
from basis.modules.catalog.adapters.presentation import DjangoExerciseChoices
from basis.modules.catalog.public import ExerciseChoices
from basis.modules.training.adapters.marks import DjangoEstimatedMarks
from basis.modules.training.public import EstimatedMarks


def measured_marks() -> MeasuredMarks:
    return DjangoMeasuredMarks()


def estimated_marks() -> EstimatedMarks:
    return DjangoEstimatedMarks()


def exercise_choices() -> ExerciseChoices:
    return DjangoExerciseChoices()
