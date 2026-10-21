"""Training-owned choices used in composed screens."""

from basis.modules.training.application.presentation import PlanSummary
from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..application.presentation import GoalSummary, PlanChoice
from .models import Goal, TrainingPlan


class DjangoTrainingPresentation:
    def plans(self, owner: AccountId) -> tuple[PlanChoice, ...]:
        return tuple(
            PlanChoice(PlanId(row.pk), row.title, row.version)
            for row in TrainingPlan.objects.filter(owner_id=owner, next_version__isnull=True)
        )

    def goal_choices(self, owner: AccountId) -> tuple[tuple[GoalId, str], ...]:
        return tuple((GoalId(row.pk), str(row)) for row in Goal.objects.filter(owner_id=owner))

    def goals(self, owner: AccountId) -> tuple[GoalSummary, ...]:
        return tuple(
            GoalSummary(
                row.title,
                row.get_sport_display(),
                row.get_priority_display(),
                row.target_value,
                row.target_unit,
                row.target_date,
                row.baseline_value,
                row.baseline_date,
            )
            for row in Goal.objects.filter(owner_id=owner).order_by("pk")
        )


class DjangoPlanSummaries:
    def read(self, owner: AccountId, plan: int) -> PlanSummary:
        row = TrainingPlan.objects.get(pk=plan, owner_id=owner)
        return PlanSummary(row.pk, row.owner_id, row.title)
