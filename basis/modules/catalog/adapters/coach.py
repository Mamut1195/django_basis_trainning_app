"""Stable bounded exercise ordering, including historical archived exercises."""

from basis.shared.identifiers import ExerciseId
from daily_trainning_app.models import Exercise

from ..application.coach import CoachExercise


class DjangoCoachExercises:
    def read(self) -> tuple[CoachExercise, ...]:
        return tuple(
            CoachExercise(ExerciseId(e.pk), e.nombre) for e in Exercise.objects.order_by("pk")[:50]
        )
