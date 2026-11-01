"""Athlete-owned dashboard read adapter."""

from datetime import date

from basis.modules.catalog.public import ExerciseNames
from basis.shared.identifiers import AccountId, ExerciseId

from ..application.presentation import AthleteHistory, ExerciseName, HistoricalWorkout
from ..domain.records import MeasurementData, WellnessData
from .django import wellness_data, wellness_rows
from .models import Measurement, WorkoutData


class DjangoAthletePresentation:
    def timezone(self, owner: AccountId) -> str | None:
        from .models import AthleteSettings

        return (
            AthleteSettings.objects.filter(owner_id=owner)
            .values_list("timezone_name", flat=True)
            .first()
        )

    def __init__(self, exercises: ExerciseNames) -> None:
        self.exercises = exercises

    def wellness(self, owner: AccountId, day: date) -> WellnessData | None:
        row = wellness_rows(owner).filter(date=day).first()
        return wellness_data(row) if row else None

    def history(self, owner: AccountId) -> AthleteHistory:
        workouts = tuple(WorkoutData.objects.filter(user__account_id=owner).order_by("-fecha")[:50])
        names = self.exercises.names(tuple(ExerciseId(row.exercise_id) for row in workouts))
        return AthleteHistory(
            tuple(
                HistoricalWorkout(
                    row.fecha,
                    ExerciseName(names[ExerciseId(row.exercise_id)]),
                    row.sets,
                    row.reps,
                    row.peso,
                    row.rpe_real,
                )
                for row in workouts
            ),
            tuple(wellness_data(row) for row in wellness_rows(owner)[:14]),
            tuple(
                MeasurementData(row.date, row.weight_kg, row.notes)
                for row in Measurement.objects.filter(
                    owner_id=owner, origin="measured", date__isnull=False
                ).order_by("-date", "-pk")[:14]
                if row.date is not None
            ),
        )
