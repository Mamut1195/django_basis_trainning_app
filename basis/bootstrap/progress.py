"""Progress and trekking composition for typed Django input adapters."""

from basis.bootstrap.billing import write_authorization
from basis.bootstrap.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.training.adapters.models import TrekStage, TrekTrip
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.modules.training.adapters.progress_wire import encode_progress, encode_trip
from basis.modules.training.public import (
    AddStage,
    CreateTrip,
    Progress,
    ReadProgress,
    ReadTrip,
    StageData,
    TripData,
)
from basis.shared.identifiers import AccountId, SessionId, TrekStageId, TrekTripId


def progress() -> Progress:
    return Progress(
        DjangoProgressRepository(), write_authorization(), DjangoUnitOfWork, DjangoClock()
    )


def report(owner: int) -> dict[str, object]:
    return encode_progress(progress().read(ReadProgress(AccountId(owner))))


def trip_summary(owner: int, trip: int) -> dict[str, object]:
    return encode_trip(progress().trip(ReadTrip(AccountId(owner), TrekTripId(trip))))


def save_trip(owner: int, row: TrekTrip) -> TrekTripId:
    return progress().create_trip(CreateTrip(AccountId(owner), TripData(row.title, row.notes)))


def save_stage(owner: int, row: TrekStage) -> TrekStageId:
    return progress().add_stage(
        AddStage(
            AccountId(owner),
            TrekTripId(row.trip_id),
            StageData(
                SessionId(row.session_id), row.order, row.overnight_altitude_m, row.recovery_notes
            ),
        )
    )
