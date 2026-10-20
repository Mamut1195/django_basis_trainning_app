"""Administrative policies run with typed permissive ports and no framework."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.athletes.application.administration import (
    AdministrativeProfile,
    AthleteAdministration,
    DeleteAdministrativeProfiles,
    Operation,
    Resource,
    SaveAdministrativeProfile,
    SaveAdministrativeRM,
    SaveAdministrativeWorkout,
)
from basis.modules.athletes.domain.records import (
    InvalidAthleteData,
    MeasuredRMData,
    MeasuredRMState,
    ProfileData,
    WorkoutData,
)
from basis.modules.athletes.domain.workouts import WorkoutCalculation, WorkoutContext
from basis.shared.identifiers import AccountId, AthleteId, ExerciseId, MeasuredRMId, WorkoutId
from tests_architecture.test_billing import Memory

ACTOR, ATHLETE = AccountId(1), AthleteId(7)
TODAY = date(2026, 10, 19)


class Authorization:
    allowed = True

    def require(self, actor: AccountId, resource: Resource, operation: Operation) -> None:
        if not self.allowed:
            raise PermissionError


class Records:
    def __init__(self) -> None:
        self.profile: AdministrativeProfile | None = None
        self.previous: MeasuredRMState | None = None
        self.calculation: WorkoutCalculation | None = None
        self.deleted: tuple[AthleteId, ...] = ()
        self.rm_written = False

    def save_profile(self, data: AdministrativeProfile, id: AthleteId | None) -> AthleteId:
        self.profile = data
        return ATHLETE

    def rm_previous(self, id: MeasuredRMId | None) -> MeasuredRMState | None:
        return self.previous

    def save_rm(
        self, athlete: AthleteId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId:
        self.rm_written = True
        return MeasuredRMId(1)

    def workout_context(
        self, athlete: AthleteId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext:
        return WorkoutContext(athlete, None, None)

    def save_workout(
        self,
        athlete: AthleteId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId:
        self.calculation = calculation
        return WorkoutId(1)

    def delete_profiles(self, ids: tuple[AthleteId, ...]) -> None:
        self.deleted = ids

    def delete_rms(self, ids: tuple[MeasuredRMId, ...]) -> None:
        raise NotImplementedError

    def delete_workouts(self, ids: tuple[WorkoutId, ...]) -> None:
        raise NotImplementedError


class AthleteAdministrativeTests(TestCase):
    def setUp(self) -> None:
        self.records, self.authorization, self.work = Records(), Authorization(), Memory()
        self.service = AthleteAdministration(self.records, self.authorization, lambda: self.work)
        profile = ProfileData("  legacy profile ", None, None, None, None, 16, None, None, None)
        self.profile = AdministrativeProfile(
            None, UUID(int=1), False, "legacy@example.test", TODAY, profile
        )

    def test_staff_permission_is_required_before_administrative_save_or_delete(self) -> None:
        self.authorization.allowed = False
        with self.assertRaises(PermissionError):
            self.service.save_profile(SaveAdministrativeProfile(ACTOR, self.profile))
        with self.assertRaises(PermissionError):
            self.service.delete_profiles(DeleteAdministrativeProfiles(ACTOR, (ATHLETE,)))
        self.assertIsNone(self.records.profile)
        self.assertEqual(self.records.deleted, ())
        self.assertFalse(self.work.committed)

    def test_unlinked_profile_and_workout_policy_execute_without_Django(self) -> None:
        self.service.save_profile(SaveAdministrativeProfile(ACTOR, self.profile))
        assert self.records.profile is not None
        self.assertIsNone(self.records.profile.account)
        self.assertEqual(self.records.profile.profile.edad, 16)
        self.assertEqual(self.records.profile.profile.nombre, "Legacy Profile")
        data = WorkoutData(ExerciseId(1), TODAY, 2, 5, Decimal(80), 0.0, Decimal(10))
        self.service.save_workout(SaveAdministrativeWorkout(ACTOR, ATHLETE, data))
        assert self.records.calculation is not None
        self.assertEqual(self.records.calculation.metrics.load_kg_reps, Decimal("800.00"))
        self.assertTrue(self.work.committed)

    def test_immutable_measured_rm_rejects_before_permissive_admin_writer(self) -> None:
        data = MeasuredRMData(ExerciseId(1), Decimal(100), TODAY)
        self.records.previous = MeasuredRMState(ATHLETE, data)
        with self.assertRaises(InvalidAthleteData):
            self.service.save_rm(
                SaveAdministrativeRM(
                    ACTOR, ATHLETE, replace(data, peso_maximo_rm=Decimal(101)), MeasuredRMId(1)
                )
            )
        self.assertFalse(self.records.rm_written)
