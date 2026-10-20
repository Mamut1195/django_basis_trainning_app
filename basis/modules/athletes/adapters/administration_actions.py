from collections.abc import Iterable

from django.db import models

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.athletes.adapters.administration import (
    DjangoAdministrativeAuthorization,
    DjangoAdministrativeRecords,
)
from basis.modules.athletes.adapters.django import profile_data, workout_data
from basis.modules.athletes.adapters.models import User, UserExerciseRM, WorkoutData
from basis.modules.athletes.adapters.record_actions import translate_errors
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
from basis.shared.identifiers import (
    AccountId,
    AthleteId,
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
