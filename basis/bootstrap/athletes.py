"""Athlete composition and typed Django form/serializer input bindings."""

from collections.abc import Callable, Mapping
from functools import wraps
from typing import ParamSpec, TypeVar

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from basis.bootstrap.billing import write_authorization
from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.athletes.adapters.django import (
    DjangoAthleteRecords,
    preferences_data,
    profile_data,
    sport_data,
    wellness_data,
)
from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    UserExerciseRM,
    Wellness,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import WorkoutData as WorkoutRow
from basis.modules.athletes.public import (
    Athletes,
    EditPreferences,
    EditProfile,
    InvalidAthleteData,
    InvalidAthleteField,
    MeasuredRMData,
    MeasurementData,
    RecordMeasurement,
    RecordRM,
    RecordSport,
    RecordWellness,
    RecordWorkout,
    WorkoutData,
)
from basis.modules.training.public import MetricsInputError
from basis.shared.identifiers import (
    AccountId,
    ExerciseId,
    MeasuredRMId,
    SportProfileId,
    WellnessId,
    WorkoutId,
)

P = ParamSpec("P")
R = TypeVar("R")


def translate_errors(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except InvalidAthleteField as error:
            raise ValidationError({error.field: str(error)}) from error
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error
        except MetricsInputError as error:
            field = NON_FIELD_ERRORS if error.field in WorkoutRow.METRIC_FIELDS else error.field
            raise ValidationError({field: f"{error.field}: {error}"}) from error

    return wrapped


def preferences_row(owner: int) -> AthleteSettings:
    athletes().preferences(AccountId(owner))
    return AthleteSettings.objects.get(owner_id=owner)


def athletes() -> Athletes:
    return Athletes(DjangoAthleteRecords(), write_authorization(), DjangoUnitOfWork)


@translate_errors
def save_profile(owner: int, row: Athlete) -> None:
    athletes().edit_profile(EditProfile(AccountId(owner), profile_data(row)))


@translate_errors
def save_preferences(owner: int, row: AthleteSettings) -> None:
    athletes().edit_preferences(EditPreferences(AccountId(owner), preferences_data(row)))


@translate_errors
def save_observation(owner: int, row: SportProfile | Wellness | Measurement) -> None:
    service, account = athletes(), AccountId(owner)
    if isinstance(row, SportProfile):
        row.pk = service.record_sport(
            RecordSport(
                account, sport_data(row), SportProfileId(row.pk) if row.pk is not None else None
            )
        )
    elif isinstance(row, Wellness):
        row.pk = service.record_wellness(
            RecordWellness(
                account, wellness_data(row), WellnessId(row.pk) if row.pk is not None else None
            )
        )
    else:
        row.pk = service.record_measurement(
            RecordMeasurement(account, MeasurementData(row.date, row.weight_kg, row.notes))
        )


@translate_errors
def save_rm(owner: int, row: UserExerciseRM) -> None:
    row.pk = athletes().record_rm(
        RecordRM(
            AccountId(owner),
            MeasuredRMData(ExerciseId(row.exercise_id), row.peso_maximo_rm, row.fecha_registro),
        )
    )


@translate_errors
def write_legacy_rm(
    owner: int, values: Mapping[str, object], row: UserExerciseRM | None = None
) -> UserExerciseRM:
    candidate = row if row is not None else UserExerciseRM()
    for name, value in values.items():
        setattr(candidate, name, value)
    id = athletes().record_rm(
        RecordRM(
            AccountId(owner),
            MeasuredRMData(
                ExerciseId(candidate.exercise_id),
                candidate.peso_maximo_rm,
                candidate.fecha_registro,
            ),
            MeasuredRMId(row.pk) if row is not None else None,
        )
    )
    return UserExerciseRM.objects.get(pk=id)


@translate_errors
def write_legacy_workout(
    owner: int, values: Mapping[str, object], row: WorkoutRow | None = None
) -> WorkoutRow:
    candidate = row if row is not None else WorkoutRow()
    for name, value in values.items():
        setattr(candidate, name, value)
    id = athletes().record_workout(
        RecordWorkout(
            AccountId(owner),
            WorkoutData(
                ExerciseId(candidate.exercise_id),
                candidate.fecha,
                candidate.sets,
                candidate.reps,
                candidate.peso,
                candidate.rpe_objetivo,
                candidate.rpe_real,
            ),
            WorkoutId(row.pk) if row is not None else None,
        )
    )
    return WorkoutRow.objects.get(pk=id)
