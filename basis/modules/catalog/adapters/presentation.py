"""Historical names remain readable when an exercise has been archived."""

from basis.shared.identifiers import ExerciseId

from .models import Exercise


class DjangoExerciseNames:
    def names(self, exercises: tuple[ExerciseId, ...]) -> dict[ExerciseId, str]:
        return {ExerciseId(row.pk): row.nombre for row in Exercise.objects.filter(pk__in=exercises)}
