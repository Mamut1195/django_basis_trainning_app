"""Stable bounded exercise ordering, including historical archived exercises."""

from basis.modules.catalog.adapters.models import Exercise
from basis.shared.identifiers import ExerciseId

from ..application.coach import CoachExercise


class DjangoCoachExercises:
    def read(self) -> tuple[CoachExercise, ...]:
        return tuple(
            CoachExercise(ExerciseId(e.pk), e.nombre) for e in Exercise.objects.order_by("pk")[:50]
        )
