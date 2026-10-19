"""Legacy entry bindings to typed proposal and common planning cases."""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from basis.bootstrap.coach import proposals
from basis.bootstrap.planning import build_proposal
from basis.modules.coach.application.proposals import AcceptProposal, EditAndAcceptProposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import ProposalUnavailable
from basis.modules.training.adapters.plan_wire import proposal_definition
from basis.modules.training.public import InvalidPlanning
from basis.shared.identifiers import AccountId, ProposalId

from .models import PlanProposal, TrainingPlan


def build_plan(
    owner: AbstractUser, content: object, previous: TrainingPlan | None = None
) -> TrainingPlan | None:
    return build_proposal(owner.pk, content, previous.pk if previous else None)


def validate_proposal(owner: AbstractUser, content: object) -> None:
    build_proposal(owner.pk, content, preview=True)


def accept_proposal(owner: AbstractUser, proposal_id: int) -> TrainingPlan:
    try:
        result = proposals().accept(AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id)))
        return TrainingPlan.objects.get(pk=result, owner_id=owner.pk)
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except (CoachInvalid, InvalidPlanning) as error:
        raise ValidationError(str(error)) from None


def edit_and_accept_proposal(
    owner: AbstractUser, proposal_id: int, content: object
) -> TrainingPlan:
    try:
        result = proposals(content).edit_and_accept(
            EditAndAcceptProposal(
                AccountId(owner.pk), ProposalId(proposal_id), proposal_definition(content)
            )
        )
        return TrainingPlan.objects.get(pk=result, owner_id=owner.pk)
    except (CoachInvalid, InvalidPlanning) as error:
        raise ValidationError(str(error)) from None


def reject_proposal(owner: AbstractUser, proposal_id: int) -> None:
    proposals().reject(AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id)))
