"""Owner-scoped profile and observation workflows."""

from dataclasses import dataclass
from typing import Callable, Protocol

from basis.shared.identifiers import (
    AccountId,
    AthleteId,
    MeasuredRMId,
    MeasurementId,
    SportProfileId,
    WellnessId,
    WorkoutId,
)
from basis.shared.ports import UnitOfWork

from ..domain.records import (
    MeasuredRMData,
    MeasuredRMState,
    MeasurementData,
    PreferencesData,
    ProfileData,
    SportData,
    WellnessData,
    WorkoutData,
    normalized_profile,
    require_adult,
    require_unchanged_rm,
    validate_sport,
    validate_wellness,
)
from ..domain.workouts import (
    WorkoutCalculation,
    WorkoutContext,
    require_positive_rm,
    validate_preferences,
)
from .workouts import calculate_workout


class WriteAuthorization(Protocol):
    def require(self, owner: AccountId) -> None: ...


class AthleteRecords(Protocol):
    def profile(self, owner: AccountId) -> ProfileData: ...
    def save_profile(self, owner: AccountId, data: ProfileData) -> None: ...
    def preferences(self, owner: AccountId) -> PreferencesData: ...
    def timezone_exists(self, name: str) -> bool: ...
    def rm_context(
        self, owner: AccountId, id: MeasuredRMId | None
    ) -> tuple[AthleteId, MeasuredRMState | None]: ...
    def workout_context(
        self, owner: AccountId, data: WorkoutData, id: WorkoutId | None
    ) -> WorkoutContext: ...
    def save_preferences(self, owner: AccountId, data: PreferencesData) -> None: ...
    def save_sport(
        self, owner: AccountId, data: SportData, id: SportProfileId | None
    ) -> SportProfileId: ...
    def save_wellness(
        self, owner: AccountId, data: WellnessData, id: WellnessId | None
    ) -> WellnessId: ...
    def save_measurement(self, owner: AccountId, data: MeasurementData) -> MeasurementId: ...
    def save_rm(
        self, owner: AccountId, data: MeasuredRMData, id: MeasuredRMId | None
    ) -> MeasuredRMId: ...
    def save_workout(
        self,
        owner: AccountId,
        data: WorkoutData,
        id: WorkoutId | None,
        calculation: WorkoutCalculation,
    ) -> WorkoutId: ...


@dataclass(frozen=True)
class EditProfile:
    owner: AccountId
    data: ProfileData


@dataclass(frozen=True)
class EditPreferences:
    owner: AccountId
    data: PreferencesData


@dataclass(frozen=True)
class RecordSport:
    owner: AccountId
    data: SportData
    id: SportProfileId | None = None


@dataclass(frozen=True)
class RecordWellness:
    owner: AccountId
    data: WellnessData
    id: WellnessId | None = None


@dataclass(frozen=True)
class RecordMeasurement:
    owner: AccountId
    data: MeasurementData


@dataclass(frozen=True)
class RecordRM:
    owner: AccountId
    data: MeasuredRMData
    id: MeasuredRMId | None = None


@dataclass(frozen=True)
class RecordWorkout:
    owner: AccountId
    data: WorkoutData
    id: WorkoutId | None = None


class Athletes:
    def __init__(
        self,
        records: AthleteRecords,
        authorization: WriteAuthorization,
        uow: Callable[[], UnitOfWork],
    ) -> None:
        self.records, self.authorization, self.uow = records, authorization, uow

    def profile(self, owner: AccountId) -> ProfileData:
        return self.records.profile(owner)

    def preferences(self, owner: AccountId) -> PreferencesData:
        with self.uow() as work:
            result = self.records.preferences(owner)
            work.commit()
            return result

    def edit_profile(self, command: EditProfile) -> None:
        with self.uow() as work:
            self.authorization.require(command.owner)
            require_adult(command.data.edad)
            self.records.save_profile(command.owner, normalized_profile(command.data))
            work.commit()

    def edit_preferences(self, command: EditPreferences) -> None:
        with self.uow() as work:
            self.authorization.require(command.owner)
            validate_preferences(
                command.data, self.records.timezone_exists(command.data.timezone_name)
            )
            self.records.save_preferences(command.owner, command.data)
            work.commit()

    def record_sport(self, command: RecordSport) -> SportProfileId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            validate_sport(command.data)
            result = self.records.save_sport(command.owner, command.data, command.id)
            work.commit()
            return result

    def record_wellness(self, command: RecordWellness) -> WellnessId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            validate_wellness(command.data)
            result = self.records.save_wellness(command.owner, command.data, command.id)
            work.commit()
            return result

    def record_measurement(self, command: RecordMeasurement) -> MeasurementId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self.records.save_measurement(command.owner, command.data)
            work.commit()
            return result

    def record_rm(self, command: RecordRM) -> MeasuredRMId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            athlete, previous = self.records.rm_context(command.owner, command.id)
            require_positive_rm(command.data.peso_maximo_rm)
            if previous is not None:
                require_unchanged_rm(previous, MeasuredRMState(athlete, command.data))
            result = self.records.save_rm(command.owner, command.data, command.id)
            work.commit()
            return result

    def record_workout(self, command: RecordWorkout) -> WorkoutId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            context = self.records.workout_context(command.owner, command.data, command.id)
            calculation = calculate_workout(command.data, context)
            result = self.records.save_workout(command.owner, command.data, command.id, calculation)
            work.commit()
            return result
