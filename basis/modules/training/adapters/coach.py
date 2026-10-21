"""Training-owned projections and common planning gateway for the coach."""

from datetime import date, timedelta

from basis.modules.training.adapters.models import Goal, Session, TrainingPlan
from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..application.coach import (
    CoachBasePlan,
    CoachGoal,
    CoachRecentSession,
    CoachVariables,
    TrainingCoachContext,
)
from ..application.planning import CreatePlan, Planning
from ..domain.planning import PlanDefinition
from ..domain.progress import report
from ..domain.sports import VARIABLES
from .progress import DjangoProgressRepository


class DjangoTrainingCoachContexts:
    def read(self, owner: AccountId, today: date) -> TrainingCoachContext:
        repo = DjangoProgressRepository()
        return TrainingCoachContext(
            tuple(
                CoachGoal(
                    GoalId(g.pk),
                    g.title,
                    g.sport,
                    g.target_date,
                    g.target_value,
                    g.target_unit,
                    g.baseline_value,
                    g.baseline_date,
                    g.priority,
                )
                for g in Goal.objects.filter(owner_id=owner)
            ),
            tuple(
                CoachRecentSession(
                    s.date,
                    s.duration_seconds,
                    s.duration_protocol,
                    s.reported_rpe,
                    tuple(sorted({b.sport for b in s.blocks.all()})),
                )
                for s in Session.objects.filter(
                    owner_id=owner, date__gte=today - timedelta(days=14)
                ).prefetch_related("blocks")[:14]
            ),
            report(repo.sessions(owner), repo.scheduled(owner, today), today),
        )

    def selected(self, owner: AccountId, plan: PlanId) -> CoachBasePlan | None:
        row = TrainingPlan.objects.filter(
            pk=plan, owner_id=owner, next_version__isnull=True
        ).first()
        return (
            CoachBasePlan(
                PlanId(row.pk),
                row.title,
                row.version,
                GoalId(row.goal_id),
                row.start_date,
                row.end_date,
            )
            if row
            else None
        )

    def variables(self) -> tuple[CoachVariables, ...]:
        return tuple(
            CoachVariables(
                sport, tuple((key, spec.unit or spec.kind) for key, spec in variables.items())
            )
            for sport, variables in VARIABLES.items()
        )


class DjangoCoachPlanning:
    def __init__(self, planning: Planning) -> None:
        self.planning = planning

    def preview(self, owner: AccountId, definition: PlanDefinition) -> None:
        self.planning.preview(CreatePlan(owner, definition))

    def create(
        self, owner: AccountId, definition: PlanDefinition, previous: PlanId | None
    ) -> PlanId:
        return self.planning.create(
            CreatePlan(
                owner, definition, previous, "Aceptación explícita de propuesta" if previous else ""
            )
        ).id

    def has_successor(self, owner: AccountId, previous: PlanId) -> bool:
        return TrainingPlan.objects.filter(owner_id=owner, previous_id=previous).exists()
