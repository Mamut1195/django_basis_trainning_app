"""Owner-selected export rows; foreign persistence schemas never leave this adapter."""

from django.db.models import Q

from basis.adapters.django.export import export_section
from basis.shared.export import ExportSection
from basis.shared.identifiers import AccountId

from .models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)


class DjangoTrainingExport:
    def read(self, owner: AccountId) -> tuple[ExportSection, ...]:
        return (
            export_section(Goal.objects.filter(owner_id=owner), "goal", "training.goal"),
            export_section(
                TrainingPlan.objects.filter(owner_id=owner), "trainingplan", "training.trainingplan"
            ),
            export_section(Cycle.objects.filter(plan__owner_id=owner), "cycle", "training.cycle"),
            export_section(
                PlannedSession.objects.filter(owner_id=owner),
                "plannedsession",
                "training.plannedsession",
            ),
            export_section(Session.objects.filter(owner_id=owner), "session", "training.session"),
            export_section(
                Block.objects.filter(Q(session__owner_id=owner) | Q(planned__owner_id=owner)),
                "block",
                "training.block",
            ),
            export_section(
                StrengthSet.objects.filter(
                    Q(block__session__owner_id=owner) | Q(block__planned__owner_id=owner)
                ),
                "strengthset",
                "training.strengthset",
            ),
            export_section(
                Interval.objects.filter(
                    Q(block__session__owner_id=owner) | Q(block__planned__owner_id=owner)
                ),
                "interval",
                "training.interval",
            ),
            export_section(
                TrekTrip.objects.filter(owner_id=owner), "trektrip", "training.trektrip"
            ),
            export_section(
                TrekStage.objects.filter(trip__owner_id=owner), "trekstage", "training.trekstage"
            ),
        )
