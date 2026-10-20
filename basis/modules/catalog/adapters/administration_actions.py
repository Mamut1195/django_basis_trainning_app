from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.catalog.adapters.administration import DjangoCatalogAdminAuthorization
from basis.modules.catalog.adapters.django import DjangoCatalogRepository, exercise_data
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.catalog.application.administration import (
    CatalogAdministration,
    DeleteClassifications,
    DeleteExercises,
)
from basis.modules.catalog.public import (
    Catalog,
    ClassificationData,
    InvalidCatalogData,
    SaveClassification,
    SaveExercise,
)
from basis.shared.identifiers import (
    AccountId,
    ClassificationId,
    ExerciseId,
)


def copy_persisted(target: models.Model, source: models.Model) -> None:
    for field in source._meta.concrete_fields:
        setattr(target, field.attname, getattr(source, field.attname))
    target._state.adding, target._state.db = False, source._state.db


def save_admin_classification(actor: int, row: Classification, change: bool) -> None:
    service = Catalog(
        DjangoCatalogRepository(),
        DjangoCatalogAdminAuthorization("classification", "change" if change else "add"),
        DjangoUnitOfWork,
    )
    id = service.save_classification(
        SaveClassification(
            AccountId(actor),
            ClassificationData(row.nombre),
            ClassificationId(row.pk) if change else None,
        )
    )
    copy_persisted(row, Classification.objects.get(pk=id))


def save_admin_exercise(actor: int, row: Exercise, change: bool) -> None:
    service = Catalog(
        DjangoCatalogRepository(),
        DjangoCatalogAdminAuthorization("exercise", "change" if change else "add"),
        DjangoUnitOfWork,
    )
    try:
        id = service.save_exercise(
            SaveExercise(
                AccountId(actor), exercise_data(row), ExerciseId(row.pk) if change else None
            )
        )
    except InvalidCatalogData as error:
        raise ValidationError({error.field: str(error)}) from error
    copy_persisted(row, Exercise.objects.get(pk=id))


def delete_admin_classifications(actor: int, ids: Iterable[int]) -> None:
    service = CatalogAdministration(
        DjangoCatalogRepository(),
        DjangoCatalogAdminAuthorization("classification", "delete"),
        DjangoUnitOfWork,
    )
    service.delete_classifications(
        DeleteClassifications(AccountId(actor), tuple(ClassificationId(id) for id in ids))
    )


def delete_admin_exercises(actor: int, ids: Iterable[int]) -> None:
    service = CatalogAdministration(
        DjangoCatalogRepository(),
        DjangoCatalogAdminAuthorization("exercise", "delete"),
        DjangoUnitOfWork,
    )
    service.delete_exercises(DeleteExercises(AccountId(actor), tuple(ExerciseId(id) for id in ids)))
