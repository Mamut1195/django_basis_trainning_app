"""Django entry actions for execution, plan versions and progress."""

from django.contrib.auth.base_user import AbstractBaseUser

from basis.bootstrap import planning
from basis.bootstrap import progress as progress_application
from basis.bootstrap import training as execution
from basis.modules.training.public import Unavailable

from .models import PlannedSession, Session, TrainingPlan, TrekTrip


def session_snapshot(session: Session) -> dict[str, object]:
    return execution.snapshot(session.owner_id, session.pk)



def start_session(owner: AbstractBaseUser, planned: PlannedSession) -> Session:
    try:
        state = execution.start(owner.pk, planned.pk)
    except Unavailable as exc:
        raise PlannedSession.DoesNotExist(str(exc)) from None
    return Session.objects.get(pk=state.id)


def revise_plan(owner: AbstractBaseUser, plan: TrainingPlan) -> TrainingPlan:
    return planning.revise(owner.pk, plan.pk)


def progress_report(owner: AbstractBaseUser) -> dict[str, object]:
    return progress_application.report(owner.pk)


def trip_summary(trip: TrekTrip) -> dict[str, object]:
    return progress_application.trip_summary(trip.owner_id, trip.pk)
