"""Catalog composition and typed serializer input bindings."""

from collections.abc import Mapping

from django.core.exceptions import ValidationError

from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.catalog.adapters.django import (
    DjangoCatalogAuthorization,
    DjangoCatalogRepository,
    exercise_data,
)
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.catalog.public import (
    Catalog,
    ClassificationData,
    InvalidCatalogData,
    SaveClassification,
    SaveExercise,
)
from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId


def catalog() -> Catalog:
    return Catalog(DjangoCatalogRepository(), DjangoCatalogAuthorization(), DjangoUnitOfWork)


def save_classification(
    actor: int, values: Mapping[str, object], row: Classification | None = None
) -> Classification:
    candidate = row if row is not None else Classification()
    for name, value in values.items():
        setattr(candidate, name, value)
    id = catalog().save_classification(
        SaveClassification(
            AccountId(actor),
            ClassificationData(candidate.nombre),
            ClassificationId(row.pk) if row is not None else None,
        )
    )
    return Classification.objects.get(pk=id)


def save_exercise(
    actor: int, values: Mapping[str, object], row: Exercise | None = None
) -> Exercise:
    candidate = row if row is not None else Exercise()
    for name, value in values.items():
        setattr(candidate, name, value)
    try:
        id = catalog().save_exercise(
            SaveExercise(
                AccountId(actor),
                exercise_data(candidate),
                ExerciseId(row.pk) if row is not None else None,
            )
        )
    except InvalidCatalogData as error:
        raise ValidationError({error.field: str(error)}) from error
    return Exercise.objects.get(pk=id)
