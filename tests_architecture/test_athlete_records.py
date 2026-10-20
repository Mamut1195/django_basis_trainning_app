"""Permissive persistence cannot bypass athlete policies or derived results."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase

from basis.modules.athletes.application.records import (
    Athletes,
    EditPreferences,
    RecordRM,
    RecordWorkout,
)
from basis.modules.athletes.domain.records import (
    InvalidAthleteData,
    MeasuredRMData,
    MeasuredRMState,
    MeasurementData,
    PreferencesData,
    ProfileData,
    SportData,
    WellnessData,
    WorkoutData,
)
from basis.modules.athletes.domain.workouts import (
    MeasuredReference,
    PreviousWorkout,
    WorkoutCalculation,
    WorkoutContext,
)
from basis.modules.training.public import METRICS_VERSION, MetricsInputError
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
from tests_architecture.test_billing import Memory
from tests_architecture.test_planning import Authorization

TODAY = date(2026, 10, 19)
OWNER, ATHLETE = AccountId(1), AthleteId(7)
WORKOUT = WorkoutData(ExerciseId(1), TODAY, 2, 5, Decimal("100"), 0.0, Decimal(10))
PREFERENCES = PreferencesData((1, 3, 5), 60, "", "", "UTC")


class PermissiveAthleteRecords:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.previous_rm: MeasuredRMState | None = None
        self.context = WorkoutContext(ATHLETE, None, None)
        self.calculation: WorkoutCalculation | None = None

    def profile(self, owner: AccountId) -> ProfileData:
        raise NotImplementedError

    def save_profile(self, owner: AccountId, data: ProfileData) -> None:
        self.writes.append("profile")

    def preferences(self, owner: AccountId) -> PreferencesData:
        return PREFERENCES

    def timezone_exists(self, name: str) -> bool:
        return name == "UTC"

    def save_preferences(self, owner: AccountId, data: PreferencesData) -> None:
        self.writes.append("preferences")

    def save_sport(
        self, owner: AccountId, data: SportData, id: SportProfileId | None
    ) -> SportProfileId:
        raise NotImplementedError

    def save_wellness(
        self, owner: AccountId, data: WellnessData, id: WellnessId | None
    ) -> WellnessId:
        raise NotImplementedError

    def save_measurement(self, owner: AccountId, data: MeasurementData) -> MeasurementId:
        raise NotImplementedError

    def rm_context(
        self, owner: AccountId, id: MeasuredRMId | None
    ) -> tuple[AthleteId, MeasuredRMState | None]:
        return ATHLETE, self.previous_rm

    def save_rm(
        self, owner: AccountId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId:
        self.writes.append("rm")
        return MeasuredRMId(1)

    def workout_context(
        self, owner: AccountId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext:
        return self.context

    def save_workout(
        self,
        owner: AccountId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId:
        self.writes.append("workout")
        self.calculation = calculation
        return WorkoutId(1)


class AthleteRecordsTests(TestCase):
    def setUp(self) -> None:
        self.records = PermissiveAthleteRecords()
        self.authorization, self.work = Authorization(), Memory()
        self.service = Athletes(self.records, self.authorization, lambda: self.work)

    def test_preferences_validate_before_permissive_writer_and_read_needs_no_commercial_access(
        self,
    ) -> None:
        for data in (
            replace(PREFERENCES, availability=(1, 1)),
            replace(PREFERENCES, timezone_name="Unknown/Zone"),
        ):
            with self.subTest(data=data), self.assertRaises(InvalidAthleteData):
                self.service.edit_preferences(EditPreferences(OWNER, data))
        self.assertEqual(self.records.writes, [])
        self.authorization.allowed = False
        self.assertEqual(self.service.preferences(OWNER), PREFERENCES)
        self.assertTrue(self.work.committed)

    def test_measured_rm_positive_and_immutable_before_permissive_writer(self) -> None:
        data = MeasuredRMData(ExerciseId(1), Decimal(100), TODAY)
        with self.assertRaises(InvalidAthleteData):
            self.service.record_rm(RecordRM(OWNER, replace(data, peso_maximo_rm=Decimal(0))))
        self.records.previous_rm = MeasuredRMState(ATHLETE, data)
        with self.assertRaises(InvalidAthleteData):
            self.service.record_rm(
                RecordRM(OWNER, replace(data, peso_maximo_rm=Decimal(101)), MeasuredRMId(1))
            )
        self.assertEqual(self.records.writes, [])
        self.service.record_rm(RecordRM(OWNER, data, MeasuredRMId(1)))
        self.assertEqual(self.records.writes, ["rm"])

    def test_workout_calculation_is_core_owned_and_absent_reference_stays_frozen(self) -> None:
        reference = MeasuredReference(
            MeasuredRMId(2), ATHLETE, MeasuredRMData(WORKOUT.exercise, Decimal(120), TODAY)
        )
        previous = PreviousWorkout(ATHLETE, WORKOUT, None, METRICS_VERSION)
        self.records.context = WorkoutContext(ATHLETE, previous, reference)
        self.service.record_workout(RecordWorkout(OWNER, WORKOUT, WorkoutId(1)))
        result = self.records.calculation
        assert result is not None
        self.assertIsNone(result.reference)
        self.assertIsNone(result.metrics.relative_intensity_percent)
        self.assertEqual(result.metrics.load_kg_reps, Decimal("1000.00"))
        self.assertEqual(result.metrics.estimated_1rm_kg, Decimal("116.67"))
        self.service.record_workout(
            RecordWorkout(OWNER, replace(WORKOUT, fecha=TODAY + timedelta(days=1)), WorkoutId(1))
        )
        assert self.records.calculation is not None
        self.assertEqual(self.records.calculation.reference, reference.id)

    def test_foreign_future_reference_and_overflow_never_reach_writer(self) -> None:
        data = MeasuredRMData(WORKOUT.exercise, Decimal(120), TODAY)
        for reference in (
            MeasuredReference(MeasuredRMId(1), AthleteId(99), data),
            MeasuredReference(
                MeasuredRMId(1), ATHLETE, replace(data, fecha_registro=TODAY + timedelta(days=1))
            ),
        ):
            self.records.context = WorkoutContext(ATHLETE, None, reference)
            with self.subTest(reference=reference), self.assertRaises(InvalidAthleteData):
                self.service.record_workout(RecordWorkout(OWNER, WORKOUT))
        self.records.context = WorkoutContext(ATHLETE, None, None)
        with self.assertRaises(MetricsInputError):
            self.service.record_workout(RecordWorkout(OWNER, replace(WORKOUT, sets=2147483647)))
        self.assertEqual(self.records.writes, [])
