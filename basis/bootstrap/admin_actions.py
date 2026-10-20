"""Explicit administrative composition; input hooks never persist ORM rows."""

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models

from basis.bootstrap.athletes import translate_errors
from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.athletes.adapters.administration import (
    DjangoAdministrativeAuthorization,
    DjangoAdministrativeRecords,
)
from basis.modules.athletes.adapters.django import profile_data, workout_data
from basis.modules.athletes.adapters.models import User, UserExerciseRM, WorkoutData
from basis.modules.athletes.application.administration import (
    AdministrativeProfile,
    AthleteAdministration,
    DeleteAdministrativeProfiles,
    DeleteAdministrativeRMs,
    DeleteAdministrativeWorkouts,
    SaveAdministrativeProfile,
    SaveAdministrativeRM,
    SaveAdministrativeWorkout,
)
from basis.modules.athletes.public import MeasuredRMData
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
    AthleteId,
    ClassificationId,
    ExerciseId,
    MeasuredRMId,
    WorkoutId,
)


def athlete_admin() -> AthleteAdministration:
    return AthleteAdministration(
        DjangoAdministrativeRecords(), DjangoAdministrativeAuthorization(), DjangoUnitOfWork
    )


def copy_persisted(target: models.Model, source: models.Model) -> None:
    for field in source._meta.concrete_fields:
        setattr(target, field.attname, getattr(source, field.attname))
    target._state.adding, target._state.db = False, source._state.db


@translate_errors
def save_admin_profile(actor: int, row: User, change: bool) -> None:
    id = athlete_admin().save_profile(
        SaveAdministrativeProfile(
            AccountId(actor),
            AdministrativeProfile(
                AccountId(row.account_id) if row.account_id is not None else None,
                row.public_id,
                row.email_verified,
                row.email,
                row.fecha_inicio,
                profile_data(row),
            ),
            AthleteId(row.pk) if change else None,
        )
    )
    copy_persisted(row, User.objects.get(pk=id))


@translate_errors
def save_admin_rm(actor: int, row: UserExerciseRM, change: bool) -> None:
    id = athlete_admin().save_rm(
        SaveAdministrativeRM(
            AccountId(actor),
            AthleteId(row.user_id),
            MeasuredRMData(ExerciseId(row.exercise_id), row.peso_maximo_rm, row.fecha_registro),
            MeasuredRMId(row.pk) if change else None,
        )
    )
    copy_persisted(row, UserExerciseRM.objects.get(pk=id))


@translate_errors
def save_admin_workout(actor: int, row: WorkoutData, change: bool) -> None:
    id = athlete_admin().save_workout(
        SaveAdministrativeWorkout(
            AccountId(actor),
            AthleteId(row.user_id),
            workout_data(row),
            WorkoutId(row.pk) if change else None,
        )
    )
    copy_persisted(row, WorkoutData.objects.get(pk=id))


def delete_admin_profiles(actor: int, ids: Iterable[int]) -> None:
    athlete_admin().delete_profiles(
        DeleteAdministrativeProfiles(AccountId(actor), tuple(AthleteId(id) for id in ids))
    )


def delete_admin_rms(actor: int, ids: Iterable[int]) -> None:
    athlete_admin().delete_rms(
        DeleteAdministrativeRMs(AccountId(actor), tuple(MeasuredRMId(id) for id in ids))
    )


def delete_admin_workouts(actor: int, ids: Iterable[int]) -> None:
    athlete_admin().delete_workouts(
        DeleteAdministrativeWorkouts(AccountId(actor), tuple(WorkoutId(id) for id in ids))
    )


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
