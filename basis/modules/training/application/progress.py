"""Progress reads and owner-scoped trekking writes through explicit ports."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
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
    start: date | None = None
    end: date | None = None


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


@dataclass(frozen=True)
class EditStage:
    owner: AccountId
    trip: TrekTripId
    stage: TrekStageId
    order: int
    overnight_altitude_m: Decimal | None
    recovery_notes: str


class ProgressRepository(Protocol):
    def sessions(
        self, owner: AccountId, start: date | None = None, end: date | None = None
    ) -> tuple[ProgressSession, ...]: ...
    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]: ...
    def stages(self, owner: AccountId, trip: TrekTripId) -> tuple[ProgressSession, ...]: ...
    def create_trip(self, command: CreateTrip) -> TrekTripId: ...
    def add_stage(self, command: AddStage) -> TrekStageId: ...
    def edit_stage(self, command: EditStage) -> None: ...


class Progress:
    def __init__(
        self,
        repository: ProgressRepository,
        authorization: WriteAuthorization,
        uow: Callable[[], UnitOfWork],
        clock: Clock,
        local_date: Callable[[AccountId, datetime], date] | None = None,
    ) -> None:
        self.repository, self.authorization, self.uow, self.clock = (
            repository,
            authorization,
            uow,
            clock,
        )
        self.local_date = local_date

    def read(self, command: ReadProgress) -> ProgressReport:
        if (command.start is None) != (command.end is None) or (
            command.start is not None and command.end is not None and command.start > command.end
        ):
            raise ValueError("Invalid progress date range")
        today = (
            self.local_date(command.owner, self.clock.now())
            if self.local_date
            else self.clock.today()
        )
        sessions = self.repository.sessions(command.owner, command.start, command.end)
        scheduled = self.repository.scheduled(command.owner, today)
        if command.start is not None and command.end is not None:
            scheduled = tuple(s for s in scheduled if command.start <= s.date <= command.end)
        return report(sessions, scheduled, today)

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

    def edit_stage(self, command: EditStage) -> None:
        with self.uow() as work:
            self.authorization.require(command.owner)
            self.repository.edit_stage(command)
            work.commit()
