"""Owner-selected export rows; foreign persistence schemas never leave this adapter."""

from basis.adapters.django.export import export_section
from basis.shared.export import ExportSection
from basis.shared.identifiers import AccountId

from .models import AIJob, PlanProposal


class DjangoCoachExport:
    def read(self, owner: AccountId) -> tuple[ExportSection, ...]:
        return (
            export_section(AIJob.objects.filter(owner_id=owner), "aijob", "training.aijob"),
            export_section(
                PlanProposal.objects.filter(owner_id=owner), "planproposal", "training.planproposal"
            ),
        )
