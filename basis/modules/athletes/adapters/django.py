"""Owner-scoped persistence over typed athlete models."""

from dataclasses import fields
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    AthleteId,
    ExerciseId,
    MeasuredRMId,
    MeasurementId,
    SportProfileId,
    WellnessId,
    WorkoutId,
)

from ..domain.records import (
    AthleteUnavailable,
    MeasuredRMData,
    MeasuredRMState,
    MeasurementData,
    PreferencesData,
    ProfileData,
    SportData,
    WellnessData,
    WorkoutData,
)
from ..domain.workouts import MeasuredReference, PreviousWorkout, WorkoutCalculation, WorkoutContext


def workout_data(row: WorkoutRow) -> WorkoutData:
    return WorkoutData(
        ExerciseId(row.exercise_id),
        row.fecha,
        row.sets,
        row.reps,
        row.peso,
        row.rpe_objetivo,
        row.rpe_real,
    )


def measured_reference(row: UserExerciseRM | None) -> MeasuredReference | None:
    if row is None:
        return None
    return MeasuredReference(
        MeasuredRMId(row.pk),
        AthleteId(row.user_id),
        MeasuredRMData(ExerciseId(row.exercise_id), row.peso_maximo_rm, row.fecha_registro),
    )


def workout_context_for(
    athlete: Athlete, data: WorkoutData, id: WorkoutId | None
) -> WorkoutContext:
    row = (
        WorkoutRow.objects.select_for_update().filter(user=athlete, pk=id).first()
        if id is not None
        else None
    )
    if id is not None and row is None:
        raise AthleteUnavailable
    previous = (
        PreviousWorkout(
            AthleteId(row.user_id),
            workout_data(row),
            measured_reference(row.rm_referencia),
            row.metrics_version,
        )
        if row is not None
        else None
    )
    reference = (
        UserExerciseRM.objects.filter(
            user=athlete,
            exercise_id=data.exercise,
            fecha_registro__lte=data.fecha,
            peso_maximo_rm__gt=0,
        )
        .order_by("-fecha_registro", "-pk")
        .first()
    )
    return WorkoutContext(AthleteId(athlete.pk), previous, measured_reference(reference))


def apply_calculation(row: WorkoutRow, calculation: WorkoutCalculation) -> None:
    row.rm_referencia_id = calculation.reference
    metrics = calculation.metrics
    row.total_reps, row.carga = metrics.total_reps, metrics.load_kg_reps
    row.intensidad_relativa = float(metrics.relative_intensity_percent or 0)
    row.volumen_relativo = float(metrics.relative_volume or 0)
    row.rm_sesion = float(metrics.estimated_1rm_kg or 0)
    row.metrics_version = calculation.version


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

    def timezone_exists(self, name: str) -> bool:
        try:
            ZoneInfo(name)
            return True
        except (ZoneInfoNotFoundError, ValueError):
            return False

    def rm_context(
        self, owner: AccountId, id: MeasuredRMId | None
    ) -> tuple[AthleteId, MeasuredRMState | None]:
        athlete = self.athlete(owner)
        row = (
            UserExerciseRM.objects.select_for_update().filter(user=athlete, pk=id).first()
            if id is not None
            else None
        )
        if id is not None and row is None:
            raise AthleteUnavailable
        previous = (
            MeasuredRMState(
                AthleteId(row.user_id),
                MeasuredRMData(ExerciseId(row.exercise_id), row.peso_maximo_rm, row.fecha_registro),
            )
            if row is not None
            else None
        )
        return AthleteId(athlete.pk), previous

    def workout_context(
        self, owner: AccountId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext:
        return workout_context_for(self.athlete(owner), data, id)

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

    def save_workout(
        self,
        owner: AccountId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId:
        athlete = self.athlete(owner)
        row = (
            WorkoutRow(user=athlete)
            if id is None
            else WorkoutRow.objects.filter(user__account_id=owner, pk=id).first()
        )
        if row is None:
            raise AthleteUnavailable
        assign(row, data)
        apply_calculation(row, calculation)
        persist(row)
        return WorkoutId(row.pk)
