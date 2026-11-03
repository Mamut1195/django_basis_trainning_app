"""Stable bounded exercise ordering, including historical archived exercises."""

from django.db import transaction
from django.db.transaction import TransactionManagementError

from basis.modules.catalog.adapters.models import Exercise
from basis.shared.identifiers import ExerciseId

from ..application.coach import CoachExercise
from ..domain.catalog import InvalidCatalogData


class DjangoCoachExercises:
    def read_for_acceptance(self, referenced: tuple[ExerciseId, ...]) -> tuple[CoachExercise, ...]:
        if not transaction.get_connection(Exercise.objects.db).in_atomic_block:
            raise TransactionManagementError("Acceptance context requires an open unit of work")
        requested = set(referenced)
        existing = set(
            Exercise.objects.select_for_update()
            .filter(pk__in=requested)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if existing != requested:
            raise InvalidCatalogData("Un ejercicio referenciado ya no está disponible.")
        return self.read()

    def read(self) -> tuple[CoachExercise, ...]:
        return tuple(
            CoachExercise(ExerciseId(e.pk), e.nombre) for e in Exercise.objects.order_by("pk")[:50]
        )
