"""Coach HTTP input actions use public planning projections and injected decoding."""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from basis.bootstrap.coach import proposal_decoder, proposals
from basis.bootstrap.presentation import plan_summaries
from basis.modules.coach.adapters.models import PlanProposal
from basis.modules.coach.application.proposals import AcceptProposal, EditAndAcceptProposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import ProposalUnavailable
from basis.modules.training.public import InvalidPlanning, PlanSummary
from basis.shared.identifiers import AccountId, ProposalId


def accept_proposal(owner: AbstractUser, proposal_id: int) -> PlanSummary:
    try:
        result = proposals().accept(AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id)))
        return plan_summaries().read(AccountId(owner.pk), result)
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except (CoachInvalid, InvalidPlanning) as error:
        raise ValidationError(str(error)) from None


def edit_and_accept_proposal(owner: AbstractUser, proposal_id: int, content: object) -> PlanSummary:
    try:
        result = proposals(content).edit_and_accept(
            EditAndAcceptProposal(
                AccountId(owner.pk), ProposalId(proposal_id), proposal_decoder()(content)
            )
        )
        return plan_summaries().read(AccountId(owner.pk), result)
    except (CoachInvalid, InvalidPlanning) as error:
        raise ValidationError(str(error)) from None


def reject_proposal(owner: AbstractUser, proposal_id: int) -> None:
    proposals().reject(AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id)))
