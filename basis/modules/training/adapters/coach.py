"""Training-owned projections and common planning gateway for the coach."""

from dataclasses import replace
from datetime import date, timedelta

from django.db.models import Exists, OuterRef

from basis.modules.training.adapters.models import Goal, PlannedSession, Session, TrainingPlan
from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..application.coach import (
    CoachBasePlan,
    CoachGoal,
    CoachRecentSession,
    CoachScope,
    CoachSessionEvidence,
    CoachVariables,
    TrainingCoachContext,
)
from ..application.planning import CreatePlan, Planning
from ..domain.planning import PlanDefinition
from ..domain.progress import report
from ..domain.sports import VARIABLES, internal_load
from .progress import progress_session


class DjangoTrainingCoachContexts:
    def read(self, owner: AccountId, today: date) -> TrainingCoachContext:
        start, session_limit, goal_limit = today - timedelta(days=13), 14, 8
        goals = tuple(
            Goal.objects.filter(owner_id=owner).order_by("priority", "pk")[: goal_limit + 1]
        )
        selected = tuple(
            Session.objects.filter(owner_id=owner, date__range=(start, today))
            .order_by("-date", "-created_at", "-pk")
            .annotate(
                _coach_owned_planned=Exists(
                    PlannedSession.objects.filter(pk=OuterRef("planned_id"), owner_id=owner)
                )
            )
            .select_related("trek_stage__trip")
            .prefetch_related("blocks__sets")[: session_limit + 1]
        )
        sessions = selected[:session_limit]
        progress = report(tuple(progress_session(s) for s in sessions), (), today)
        evidence = tuple(
            CoachSessionEvidence(
                str(c.session.id),
                c.session.date,
                tuple(sorted({b.sport for b in c.session.blocks})),
                c.session.protocol.value,
                c.session.duration_seconds,
                c.session.reported_rpe,
                internal_load(c.session.duration_seconds, c.session.reported_rpe),
                c.previous_date,
                c.days_since_previous,
                c.consecutive_days,
                c.sessions_on_date,
                replace(
                    c.session.stage_recovery,
                    recovery_notes=c.session.stage_recovery.recovery_notes[:300],
                )
                if c.session.stage_recovery
                else None,
            )
            for c in progress.context
        )
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
                for g in goals[:goal_limit]
            ),
            tuple(
                CoachRecentSession(
                    s.date,
                    s.duration_seconds,
                    s.duration_protocol,
                    s.reported_rpe,
                    tuple(sorted({b.sport for b in s.blocks.all()})),
                    str(s.pk),
                    s.status,
                    s.planned_id if getattr(s, "_coach_owned_planned") else None,
                )
                for s in sessions
            ),
            replace(progress, context=()),
            CoachScope(
                start,
                today,
                session_limit,
                goal_limit,
                len(selected) > session_limit,
                len(goals) > goal_limit,
            ),
            evidence,
        )

    def selected(self, owner: AccountId, plan: PlanId) -> CoachBasePlan | None:
        row = TrainingPlan.objects.filter(
            pk=plan, owner_id=owner, goal__owner_id=owner, next_version__isnull=True
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
