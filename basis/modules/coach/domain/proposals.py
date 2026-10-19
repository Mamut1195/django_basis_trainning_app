"""Proposal state is separate from its private athlete plan instance."""

from dataclasses import dataclass

from basis.modules.training.public import PlanDefinition
from basis.shared.identifiers import AccountId, JobId, PlanId, ProposalId


@dataclass(frozen=True)
class Proposal:
    id: ProposalId
    owner: AccountId
    job: JobId
    definition: PlanDefinition | None
    base_plan: PlanId | None
    status: str
    accepted_plan: PlanId | None


class ProposalUnavailable(Exception):
    pass
