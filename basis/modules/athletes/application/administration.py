"""Explicit administrative workflows, separate from athlete commercial access."""

from dataclasses import dataclass
from datetime import date
from typing import Callable, Literal, Protocol
from uuid import UUID

from basis.shared.identifiers import AccountId, AthleteId, MeasuredRMId, WorkoutId
from basis.shared.ports import UnitOfWork

from ..domain.records import (
    MeasuredRMData,
    MeasuredRMState,
    ProfileData,
    WorkoutData,
    normalized_profile,
    require_unchanged_rm,
)
from ..domain.workouts import (
    WorkoutCalculation,
    WorkoutContext,
    require_positive_rm,
)
from .workouts import calculate_workout

Resource = Literal["profile", "rm", "workout"]
Operation = Literal["add", "change", "delete"]


class AdministrativeAuthorization(Protocol):
    def require(self, actor: AccountId, resource: Resource, operation: Operation) -> None: ...


@dataclass(frozen=True)
class AdministrativeProfile:
    account: AccountId | None
    public_id: UUID
    email_verified: bool
    email: str
    joined: date
    profile: ProfileData


@dataclass(frozen=True)
class SaveAdministrativeProfile:
    actor: AccountId
    data: AdministrativeProfile
    id: AthleteId | None = None


@dataclass(frozen=True)
class SaveAdministrativeRM:
    actor: AccountId
    athlete: AthleteId
    data: MeasuredRMData
    id: MeasuredRMId | None = None


@dataclass(frozen=True)
class SaveAdministrativeWorkout:
    actor: AccountId
    athlete: AthleteId
    data: WorkoutData
    id: WorkoutId | None = None


@dataclass(frozen=True)
class DeleteAdministrativeProfiles:
    actor: AccountId
    ids: tuple[AthleteId, ...]


@dataclass(frozen=True)
class DeleteAdministrativeRMs:
    actor: AccountId
    ids: tuple[MeasuredRMId, ...]


@dataclass(frozen=True)
class DeleteAdministrativeWorkouts:
    actor: AccountId
    ids: tuple[WorkoutId, ...]


class AdministrativeRecords(Protocol):
    def save_profile(self, data: AdministrativeProfile, id: AthleteId | None) -> AthleteId: ...
    def rm_previous(self, id: MeasuredRMId | None) -> MeasuredRMState | None: ...
    def save_rm(
        self, athlete: AthleteId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId: ...
    def workout_context(
        self, athlete: AthleteId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext: ...
    def save_workout(
        self,
        athlete: AthleteId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId: ...
    def delete_profiles(self, ids: tuple[AthleteId, ...]) -> None: ...
    def delete_rms(self, ids: tuple[MeasuredRMId, ...]) -> None: ...
    def delete_workouts(self, ids: tuple[WorkoutId, ...]) -> None: ...


class AthleteAdministration:
    def __init__(
        self,
        records: AdministrativeRecords,
        authorization: AdministrativeAuthorization,
        uow: Callable[[], UnitOfWork],
    ) -> None:
        self.records, self.authorization, self.uow = records, authorization, uow

    def save_profile(self, command: SaveAdministrativeProfile) -> AthleteId:
        from dataclasses import replace

        with self.uow() as work:
            self.authorization.require(
                command.actor, "profile", "change" if command.id is not None else "add"
            )
            result = self.records.save_profile(
                replace(command.data, profile=normalized_profile(command.data.profile)), command.id
            )
            work.commit()
            return result

    def save_rm(self, command: SaveAdministrativeRM) -> MeasuredRMId:
        with self.uow() as work:
            self.authorization.require(
                command.actor, "rm", "change" if command.id is not None else "add"
            )
            previous = self.records.rm_previous(command.id)
            require_positive_rm(command.data.peso_maximo_rm)
            if previous is not None:
                require_unchanged_rm(previous, MeasuredRMState(command.athlete, command.data))
            result = self.records.save_rm(command.athlete, command.data, command.id)
            work.commit()
            return result

    def save_workout(self, command: SaveAdministrativeWorkout) -> WorkoutId:
        with self.uow() as work:
            self.authorization.require(
                command.actor, "workout", "change" if command.id is not None else "add"
            )
            calculation = calculate_workout(
                command.data,
                self.records.workout_context(command.athlete, command.data, command.id),
            )
            result = self.records.save_workout(
                command.athlete, command.data, command.id, calculation
            )
            work.commit()
            return result

    def delete_profiles(self, command: DeleteAdministrativeProfiles) -> None:
        with self.uow() as work:
            self.authorization.require(command.actor, "profile", "delete")
            self.records.delete_profiles(command.ids)
            work.commit()

    def delete_rms(self, command: DeleteAdministrativeRMs) -> None:
        with self.uow() as work:
            self.authorization.require(command.actor, "rm", "delete")
            self.records.delete_rms(command.ids)
            work.commit()

    def delete_workouts(self, command: DeleteAdministrativeWorkouts) -> None:
        with self.uow() as work:
            self.authorization.require(command.actor, "workout", "delete")
            self.records.delete_workouts(command.ids)
            work.commit()
