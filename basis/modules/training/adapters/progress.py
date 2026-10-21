"""Read projections and owner-scoped trekking persistence on stable tables."""

from collections.abc import Callable
from datetime import date, datetime

from basis.modules.training.adapters.models import Session, TrekStage, TrekTrip
from basis.shared.identifiers import AccountId, SessionId, TrekStageId, TrekTripId

from ..application.progress import AddStage, CreateTrip
from ..domain.execution import DurationProtocol
from ..domain.progress import ProgressBlock, ProgressSession, ScheduledProgress
from ..domain.trekking import TrekkingUnavailable
from .django import save_validated
from .wire import metrics


def progress_session(row: Session) -> ProgressSession:
    return ProgressSession(
        SessionId(row.pk),
        row.status == "completed",
        DurationProtocol(row.duration_protocol),
        row.duration_seconds,
        row.reported_rpe,
        tuple(
            ProgressBlock(
                b.sport,
                metrics(b.actual),
                tuple(s.external_volume_kg for s in b.sets.all()),
            )
            for b in row.blocks.all()
        ),
    )


class DjangoProgressRepository:
    def __init__(self, local_date: Callable[[AccountId, datetime], date] | None = None) -> None:
        self.local_date = local_date

    def sessions(self, owner: AccountId) -> tuple[ProgressSession, ...]:
        rows = Session.objects.filter(owner_id=owner, status="completed").prefetch_related(
            "blocks__sets", "blocks__intervals"
        )
        return tuple(progress_session(s) for s in rows)

    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]:
        from .calendar import effective_sessions
        from .locking import intent_executions

        rows = effective_sessions(owner, self.local_date)
        return tuple(
            ScheduledProgress(
                s.date,
                intent_executions(s).filter(status="completed").exists(),
                None,
            )
            for s in rows
            if s.date <= today and s.status != "cancelled"
        )

    def stages(self, owner: AccountId, trip: TrekTripId) -> tuple[ProgressSession, ...]:
        if not TrekTrip.objects.filter(pk=trip, owner_id=owner).exists():
            raise TrekkingUnavailable("El trekking no existe.")
        rows = (
            TrekStage.objects.filter(trip_id=trip)
            .select_related("session")
            .prefetch_related("session__blocks__sets")
        )
        return tuple(progress_session(s.session) for s in rows)

    def create_trip(self, command: CreateTrip) -> TrekTripId:
        row = TrekTrip(owner_id=command.owner, title=command.data.title, notes=command.data.notes)
        save_validated(row)
        return TrekTripId(row.pk)

    def add_stage(self, command: AddStage) -> TrekStageId:
        try:
            trip = TrekTrip.objects.select_for_update().get(pk=command.trip, owner_id=command.owner)
            session = Session.objects.select_for_update().get(
                pk=command.data.session, owner_id=command.owner
            )
        except (TrekTrip.DoesNotExist, Session.DoesNotExist) as error:
            raise TrekkingUnavailable("El trekking o la sesión no existe.") from error
        row = TrekStage(
            trip=trip,
            session=session,
            order=command.data.order,
            overnight_altitude_m=command.data.overnight_altitude_m,
            recovery_notes=command.data.recovery_notes,
        )
        save_validated(row)
        return TrekStageId(row.pk)
