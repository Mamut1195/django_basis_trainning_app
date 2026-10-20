"""Owner-scoped persistence over typed athlete models."""

from dataclasses import fields

from django.db import models

from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    UserExerciseRM,
    Wellness,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import WorkoutData as WorkoutRow
from basis.shared.identifiers import (
    AccountId,
    MeasuredRMId,
    MeasurementId,
    SportProfileId,
    WellnessId,
    WorkoutId,
)

from ..domain.records import (
    AthleteUnavailable,
    MeasuredRMData,
    MeasurementData,
    PreferencesData,
    ProfileData,
    SportData,
    WellnessData,
    WorkoutData,
)


def persist(row: models.Model) -> None:
    row.save()


def assign(
    row: models.Model,
    data: ProfileData
    | PreferencesData
    | SportData
    | WellnessData
    | MeasurementData
    | MeasuredRMData
    | WorkoutData,
) -> None:
    for field in fields(data):
        name = field.name
        value = getattr(data, name)
        if name == "exercise":
            name = "exercise_id"
        if name == "availability":
            value = list(value)
        setattr(row, name, value)



def profile_data(row: Athlete) -> ProfileData:
    return ProfileData(
        row.nombre,
        row.titulo,
        row.pais,
        row.ciudad,
        row.especialidad,
        row.edad,
        row.peso,
        row.objetivos,
        row.descripcion,
    )


def preferences_data(row: AthleteSettings) -> PreferencesData:
    return PreferencesData(
        tuple(row.availability),
        row.minutes_per_session,
        row.equipment,
        row.limitations,
        row.timezone_name,
    )


def sport_data(row: SportProfile) -> SportData:
    return SportData(
        row.sport, row.experience, row.threshold, row.threshold_unit, row.measured_on, row.method
    )


def wellness_data(row: Wellness) -> WellnessData:
    return WellnessData(
        row.date,
        row.sleep_hours,
        row.sleep_quality,
        row.fatigue,
        row.stress,
        row.soreness,
        row.readiness,
        row.pain_regions,
        row.pain_score,
        row.resting_hr_bpm,
        row.hrv_ms,
        row.hrv_method,
        row.notes,
    )


class DjangoAthleteRecords:
    def athlete(self, owner: AccountId) -> Athlete:
        row = Athlete.objects.filter(account_id=owner).first()
        if row is None:
            raise AthleteUnavailable
        return row

    def profile(self, owner: AccountId) -> ProfileData:
        return profile_data(self.athlete(owner))

    def save_profile(self, owner: AccountId, data: ProfileData) -> None:
        row = self.athlete(owner)
        assign(row, data)
        persist(row)

    def preferences(self, owner: AccountId) -> PreferencesData:
        row, _ = AthleteSettings.objects.get_or_create(owner_id=owner)
        return preferences_data(row)

    def save_preferences(self, owner: AccountId, data: PreferencesData) -> None:
        row, _ = AthleteSettings.objects.get_or_create(owner_id=owner)
        assign(row, data)
        persist(row)

    def save_sport(
        self, owner: AccountId, data: SportData, id: SportProfileId | None
    ) -> SportProfileId:
        row = (
            SportProfile(owner_id=owner)
            if id is None
            else SportProfile.objects.filter(owner_id=owner, pk=id).first()
        )
        if row is None:
            raise AthleteUnavailable
        assign(row, data)
        persist(row)
        return SportProfileId(row.pk)

    def save_wellness(
        self, owner: AccountId, data: WellnessData, id: WellnessId | None
    ) -> WellnessId:
        row = (
            Wellness(owner_id=owner)
            if id is None
            else Wellness.objects.filter(owner_id=owner, pk=id).first()
        )
        if row is None:
            raise AthleteUnavailable
        assign(row, data)
        persist(row)
        return WellnessId(row.pk)

    def save_measurement(self, owner: AccountId, data: MeasurementData) -> MeasurementId:
        row = Measurement(owner_id=owner)
        assign(row, data)
        persist(row)
        return MeasurementId(row.pk)

    def save_rm(
        self, owner: AccountId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId:
        athlete = self.athlete(owner)
        row = (
            UserExerciseRM(user=athlete)
            if id is None
            else UserExerciseRM.objects.filter(user__account_id=owner, pk=id).first()
        )
        if row is None:
            raise AthleteUnavailable
        assign(row, data)
        persist(row)
        return MeasuredRMId(row.pk)

    def save_workout(self, owner: AccountId, data: WorkoutData, id: WorkoutId | None) -> WorkoutId:
        athlete = self.athlete(owner)
        row = (
            WorkoutRow(user=athlete)
            if id is None
            else WorkoutRow.objects.filter(user__account_id=owner, pk=id).first()
        )
        if row is None:
            raise AthleteUnavailable
        assign(row, data)
        persist(row)
        return WorkoutId(row.pk)
