"""Read projections and owner-scoped trekking persistence on stable tables."""

from collections.abc import Callable
from datetime import date, datetime

from basis.modules.training.adapters.models import Session, TrekStage, TrekTrip
from basis.shared.identifiers import AccountId, SessionId, TrekStageId, TrekTripId

from ..application.progress import AddStage, CreateTrip, EditStage
from ..domain.execution import DurationProtocol
from ..domain.progress import ProgressBlock, ProgressSession, ScheduledProgress, StageRecovery
from ..domain.trekking import TrekkingUnavailable
from .django import save_validated
from .wire import metrics


def progress_session(row: Session) -> ProgressSession:
    stage = getattr(row, "trek_stage", None)
    # A malformed administrative link must not expose another account's trip.
    recovery = (
        StageRecovery(
            TrekTripId(stage.trip_id),
            TrekStageId(stage.pk),
            stage.order,
            stage.overnight_altitude_m,
            stage.recovery_notes,
        )
        if stage is not None and stage.trip.owner_id == row.owner_id
        else None
    )
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
                tuple((s.actual_load_type or s.load_type) == "external" for s in b.sets.all()),
            )
            for b in row.blocks.all()
        ),
        row.date,
        recovery,
    )


class DjangoProgressRepository:
    def __init__(self, local_date: Callable[[AccountId, datetime], date] | None = None) -> None:
        self.local_date = local_date

    def sessions(
        self, owner: AccountId, start: date | None = None, end: date | None = None
    ) -> tuple[ProgressSession, ...]:
        query = Session.objects.filter(owner_id=owner, status="completed")
        if start is not None and end is not None:
            query = query.filter(date__range=(start, end))
        rows = query.select_related("trek_stage__trip").prefetch_related("blocks__sets")
        return tuple(progress_session(s) for s in rows)

    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]:
        from .calendar import effective_sessions, has_completed_execution

        rows = effective_sessions(owner, self.local_date)
        return tuple(
            ScheduledProgress(
                s.date,
                has_completed_execution(s),
                None,
            )
            for s in rows
            if s.date <= today and s.status != "cancelled"
        )

    def stages(self, owner: AccountId, trip: TrekTripId) -> tuple[ProgressSession, ...]:
        if not TrekTrip.objects.filter(pk=trip, owner_id=owner).exists():
            raise TrekkingUnavailable("El trekking no existe.")
        rows = (
            TrekStage.objects.filter(trip_id=trip, session__owner_id=owner)
            .select_related("session__trek_stage__trip")
            .prefetch_related("session__blocks__sets")
        )
        return tuple(progress_session(s.session) for s in rows)

    def create_trip(self, command: CreateTrip) -> TrekTripId:
        row = TrekTrip(owner_id=command.owner, title=command.data.title, notes=command.data.notes)
        save_validated(row)
        return TrekTripId(row.pk)

    def add_stage(self, command: AddStage) -> TrekStageId:
        from basis.adapters.django.account_locks import lock_account

        lock_account(command.owner, TrekTrip.objects.db)
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

    def edit_stage(self, command: EditStage) -> None:
        from basis.adapters.django.account_locks import lock_account

        lock_account(command.owner, TrekTrip.objects.db)
        trip = (
            TrekTrip.objects.select_for_update()
            .filter(pk=command.trip, owner_id=command.owner)
            .first()
        )
        if trip is None:
            raise TrekkingUnavailable("El trekking no existe.")
        row = TrekStage.objects.select_for_update().filter(pk=command.stage, trip=trip).first()
        if row is None:
            raise TrekkingUnavailable("La etapa no existe.")
        row.order = command.order
        row.overnight_altitude_m = command.overnight_altitude_m
        row.recovery_notes = command.recovery_notes
        save_validated(row)
