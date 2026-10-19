"""Catalog persistence over existing tables; protected deletion remains Django's."""

from dataclasses import fields
from typing import Protocol, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from basis.shared.identifiers import AccountId, ClassificationId, ExerciseId
from daily_trainning_app.models import Classification, Exercise

from ..domain.catalog import (
    CatalogDenied,
    ClassificationData,
    ExerciseData,
    catalog_allowed,
    valid_muscle_names,
)


class LegacySave(Protocol):
    def save(self) -> None: ...


def exercise_data(row: Exercise) -> ExerciseData:
    if not valid_muscle_names(row.musculos_principales):
        raise ValidationError({"musculos_principales": "Usa una lista de nombres musculares."})
    return ExerciseData(
        ClassificationId(row.classification_id),
        row.nombre,
        row.video,
        row.descripcion,
        row.nivel_fatiga,
        row.patron_movimiento,
        tuple(row.musculos_principales),
        row.equipo,
        row.variante,
        row.archivado,
    )


class DjangoCatalogAuthorization:
    def require_write(self, actor: AccountId) -> None:
        row = get_user_model().objects.get(pk=actor)
        if not catalog_allowed(row.is_authenticated, row.is_staff, False):
            raise CatalogDenied


class DjangoCatalogRepository:
    def classification(self, id: ClassificationId) -> ClassificationData:
        return ClassificationData(Classification.objects.get(pk=id).nombre)

    def exercise(self, id: ExerciseId) -> ExerciseData:
        return exercise_data(Exercise.objects.get(pk=id))

    def save_classification(
        self, data: ClassificationData, id: ClassificationId | None
    ) -> ClassificationId:
        row = Classification() if id is None else Classification.objects.get(pk=id)
        row.nombre = data.nombre
        row.save()
        return ClassificationId(row.pk)

    def save_exercise(self, data: ExerciseData, id: ExerciseId | None) -> ExerciseId:
        row = Exercise() if id is None else Exercise.objects.get(pk=id)
        for field in fields(data):
            name = field.name
            value = getattr(data, name)
            if name == "classification":
                name = "classification_id"
            elif name == "musculos_principales":
                value = list(value)
            setattr(row, name, value)
        # Transitional signature only: execute Exercise.full_clean + save unchanged.
        cast(LegacySave, row).save()
        return ExerciseId(row.pk)

    def delete_classification(self, id: ClassificationId) -> None:
        Classification.objects.get(pk=id).delete()

    def delete_exercise(self, id: ExerciseId) -> None:
        Exercise.objects.get(pk=id).delete()
