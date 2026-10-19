"""Read projections and owner-scoped trekking persistence on stable tables."""

from datetime import date

from django.db.models.functions import TruncDate

from basis.shared.identifiers import AccountId, SessionId, TrekStageId, TrekTripId
from training.models import PlannedSession, Session, TrekStage, TrekTrip

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
    def sessions(self, owner: AccountId) -> tuple[ProgressSession, ...]:
        rows = Session.objects.filter(owner_id=owner, status="completed").prefetch_related(
            "blocks__sets", "blocks__intervals"
        )
        return tuple(progress_session(s) for s in rows)

    def scheduled(self, owner: AccountId, today: date) -> tuple[ScheduledProgress, ...]:
        # Database date conversion preserves Django's current timezone and historical
        # __date semantics rather than truncating UTC timestamps in the domain.
        rows = (
            PlannedSession.objects.filter(owner_id=owner, date__lte=today)
            .annotate(replacement_date=TruncDate("plan__next_version__created_at"))
            .prefetch_related("executions")
        )
        return tuple(
            ScheduledProgress(
                s.date,
                any(e.status == "completed" for e in s.executions.all()),
                s.replacement_date,
            )
            for s in rows
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
