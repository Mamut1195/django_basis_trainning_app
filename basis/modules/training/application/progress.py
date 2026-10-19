"""Progress reads and owner-scoped trekking writes through explicit ports."""

from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol

from basis.shared.identifiers import AccountId, TrekStageId, TrekTripId
from basis.shared.ports import Clock, UnitOfWork

from ..domain.progress import (
    ProgressReport,
    ProgressSession,
    ScheduledProgress,
    TrekSummary,
    report,
    summarize_trip,
)
from ..domain.trekking import StageData, TripData
from .execution import WriteAuthorization


@dataclass(frozen=True)
class ReadProgress:
    owner: AccountId


@dataclass(frozen=True)
class ReadTrip:
    owner: AccountId
    trip: TrekTripId


@dataclass(frozen=True)
class CreateTrip:
    owner: AccountId
    data: TripData


@dataclass(frozen=True)
class AddStage:
    owner: AccountId
    trip: TrekTripId
    data: StageData


class ProgressRepository(Protocol):
    def sessions(self, owner: AccountId) -> tuple[ProgressSession, ...]: ...
    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]: ...
    def stages(self, owner: AccountId, trip: TrekTripId) -> tuple[ProgressSession, ...]: ...
    def create_trip(self, command: CreateTrip) -> TrekTripId: ...
    def add_stage(self, command: AddStage) -> TrekStageId: ...


class Progress:
    def __init__(
        self,
        repository: ProgressRepository,
        authorization: WriteAuthorization,
        uow: Callable[[], UnitOfWork],
        clock: Clock,
    ) -> None:
        self.repository, self.authorization, self.uow, self.clock = (
            repository,
            authorization,
            uow,
            clock,
        )

    def read(self, command: ReadProgress) -> ProgressReport:
        today = self.clock.today()
        return report(
            self.repository.sessions(command.owner),
            self.repository.scheduled(command.owner, today),
            today,
        )

    def trip(self, command: ReadTrip) -> TrekSummary:
        return summarize_trip(self.repository.stages(command.owner, command.trip))

    def create_trip(self, command: CreateTrip) -> TrekTripId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self.repository.create_trip(command)
            work.commit()
            return result

    def add_stage(self, command: AddStage) -> TrekStageId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            result = self.repository.add_stage(command)
            work.commit()
            return result
