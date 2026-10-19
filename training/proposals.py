
from django.core.exceptions import ValidationError
from django.db import transaction

from basis.bootstrap.planning import build_proposal

from .access import require_write_access
from .models import PlanProposal, TrainingPlan


def build_plan(owner, content, previous=None):
    return build_proposal(owner.pk, content, previous.pk if previous else None)


def validate_proposal(owner, content):
    build_proposal(owner.pk, content, preview=True)


@transaction.atomic
def accept_proposal(owner, proposal_id):
    require_write_access(owner)
    proposal = PlanProposal.objects.select_for_update().get(pk=proposal_id, owner=owner)
    if proposal.status == "accepted":
        return proposal.accepted_plan
    if proposal.status != "pending":
        raise ValidationError("Esta propuesta ya fue rechazada.")
    if proposal.base_plan_id and TrainingPlan.objects.filter(previous=proposal.base_plan).exists():
        raise ValidationError("El plan cambió desde la propuesta. Revisa una nueva versión.")
    plan = build_plan(owner, proposal.content, previous=proposal.base_plan)
    proposal.status, proposal.accepted_plan = "accepted", plan
    proposal.save()
    return plan
