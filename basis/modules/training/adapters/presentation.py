"""Training-owned choices used in composed screens."""

from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..application.presentation import PlanChoice
from .models import Goal, TrainingPlan


class DjangoTrainingPresentation:
    def plans(self, owner: AccountId) -> tuple[PlanChoice, ...]:
        return tuple(
            PlanChoice(PlanId(row.pk), row.title, row.version)
            for row in TrainingPlan.objects.filter(owner_id=owner, next_version__isnull=True)
        )

    def goal_choices(self, owner: AccountId) -> tuple[tuple[GoalId, str], ...]:
        return tuple((GoalId(row.pk), str(row)) for row in Goal.objects.filter(owner_id=owner))
