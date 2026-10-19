"""Planning composition and narrow legacy ORM/form compatibility bindings."""

from datetime import date

from django.core.exceptions import ValidationError

from basis.bootstrap.billing import write_authorization
from basis.bootstrap.transactions import DjangoClock, DjangoUnitOfWork
from basis.modules.training.adapters.plan_wire import INVALID, proposal_definition
from basis.modules.training.adapters.planning import (
    DjangoPlanRepository,
    cycle_definition,
    goal_data,
)
from basis.modules.training.public import (
    AddCycle,
    CreatePlan,
    InvalidPlanning,
    PlanDefinition,
    Planning,
    PlanningUnavailable,
    RescheduleSession,
    RevisePlan,
    SaveGoal,
    ScheduledDefinition,
    ScheduleSession,
)
from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId, PlannedSessionId, Revision
from training.models import Cycle, Goal, PlannedSession, TrainingPlan


def planning() -> Planning:
    return Planning(
        DjangoPlanRepository(), write_authorization(), DjangoUnitOfWork, DjangoClock()
    )


def build_proposal(
    owner: int, content: object, previous: int | None = None, *, preview: bool = False
) -> TrainingPlan | None:
    try:
        command = CreatePlan(
            AccountId(owner),
            proposal_definition(content),
            PlanId(previous) if previous is not None else None,
        )
        if preview:
            planning().preview(command)
            return None
        result = planning().create(command)
        return TrainingPlan.objects.get(pk=result.id)
    except Goal.DoesNotExist:
        raise ValidationError(INVALID) from None
    except InvalidPlanning as error:
        raise ValidationError(str(error)) from error


def revise(owner: int, plan: int) -> TrainingPlan:
    try:
        result = planning().revise(RevisePlan(AccountId(owner), PlanId(plan)))
        return TrainingPlan.objects.get(pk=result.id)
    except PlanningUnavailable as error:
        raise TrainingPlan.DoesNotExist from error
    except InvalidPlanning as error:
        raise ValidationError(str(error)) from error


def save_manual_plan(owner: int, row: TrainingPlan) -> int:
    try:
        result = planning().create(
            CreatePlan(
                AccountId(owner),
                PlanDefinition(
                    GoalId(row.goal_id), row.title, row.start_date, row.end_date, row.notes
                ),
            )
        )
        return result.id
    except InvalidPlanning as error:
        raise ValidationError(str(error)) from error


def save_goal(owner: int, row: Goal) -> int:
    return planning().save_goal(SaveGoal(AccountId(owner), goal_data(row)))


def save_cycle(owner: int, row: Cycle) -> None:
    row.pk = planning().add_cycle(
        AddCycle(
            AccountId(owner),
            PlanId(row.plan_id),
            cycle_definition(row),
            CycleId(row.parent_id) if row.parent_id is not None else None,
        )
    )


def save_scheduled(owner: int, row: PlannedSession) -> int:
    return planning().schedule(
        ScheduleSession(
            AccountId(owner),
            PlanId(row.plan_id),
            CycleId(row.cycle_id),
            ScheduledDefinition(str(row.cycle_id), row.title, row.date, notes=row.notes),
        )
    )


def reschedule(owner: int, session: int, date: date, revision: int) -> None:
    try:
        planning().reschedule(
            RescheduleSession(AccountId(owner), PlannedSessionId(session), date, Revision(revision))
        )
    except InvalidPlanning as error:
        raise ValidationError(str(error)) from error
