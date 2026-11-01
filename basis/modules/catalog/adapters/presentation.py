"""Historical names remain readable when an exercise has been archived."""

from basis.shared.identifiers import ExerciseId

from .models import Exercise


class DjangoExerciseNames:
    def names(self, exercises: tuple[ExerciseId, ...]) -> dict[ExerciseId, str]:
        return {ExerciseId(row.pk): row.nombre for row in Exercise.objects.filter(pk__in=exercises)}

    def fatigue(self, exercise: ExerciseId) -> str | None:
        return Exercise.objects.filter(pk=exercise).values_list("nivel_fatiga", flat=True).first()


class DjangoExerciseChoices:
    def all(self) -> tuple[tuple[ExerciseId, str, bool], ...]:
        return tuple(
            (ExerciseId(pk), name, archived)
            for pk, name, archived in Exercise.objects.order_by("nombre", "pk").values_list(
                "pk", "nombre", "archivado"
            )
        )
