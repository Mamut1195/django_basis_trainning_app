"""Proposal persistence and model-answer decoding at the JSON boundary."""

import json
from typing import Callable

from django.core.exceptions import ValidationError

from basis.modules.coach.adapters.models import PlanProposal
from basis.modules.training.public import InvalidPlanning, PlanDefinition, PlanningUnavailable
from basis.shared.identifiers import AccountId, JobId, PlanId, ProposalId

from ..application.proposals import CreateProposal, Proposals
from ..domain.jobs import CoachInvalid, Job
from ..domain.proposals import Proposal, ProposalUnavailable


class DjangoProposalRepository:
    def __init__(self, decode: Callable[[object], PlanDefinition], source: object = None) -> None:
        self.decode, self.source = decode, source

    def get(self, owner: AccountId, id: ProposalId, *, definition: bool = True) -> Proposal:
        try:
            row = PlanProposal.objects.select_for_update().get(pk=id, owner_id=owner)
        except PlanProposal.DoesNotExist as error:
            raise ProposalUnavailable from error
        return Proposal(
            ProposalId(row.pk),
            owner,
            JobId(row.job_id),
            self.decode(row.content) if definition and row.status == "pending" else None,
            PlanId(row.base_plan_id) if row.base_plan_id else None,
            row.status,
            PlanId(row.accepted_plan_id) if row.accepted_plan_id else None,
        )

    def _source(self, definition: PlanDefinition) -> object:
        # The adapter retains exact input JSON, including optional-key omission and
        # numeric spelling; it may persist it only after the core validates this definition.
        if self.source is None or self.decode(self.source) != definition:
            raise ValueError("Proposal source does not match the validated definition")
        return self.source

    def save(self, proposal: Proposal, *, edited: bool = False) -> None:
        if proposal.status == "rejected" and not edited:
            # Rejection historically updates only pending status, without a plan
            # preview or unrelated historical relation validation.
            PlanProposal.objects.filter(
                pk=proposal.id, owner_id=proposal.owner, status="pending"
            ).update(status="rejected")
            return
        row = PlanProposal.objects.get(pk=proposal.id, owner_id=proposal.owner)
        row.status, row.accepted_plan_id = proposal.status, proposal.accepted_plan
        if edited:
            if proposal.definition is None:
                raise ValueError("Edited proposal requires a definition")
            row.content = self._source(proposal.definition)
        row.save()

    def create(self, command: CreateProposal) -> ProposalId:
        row = PlanProposal.objects.create(
            owner_id=command.owner,
            job_id=command.job,
            base_plan_id=command.base_plan,
            content=self._source(command.definition),
        )
        return ProposalId(row.pk)


class DjangoProposalSink:
    def __init__(
        self, build: Callable[[object], Proposals], decode: Callable[[object], PlanDefinition]
    ) -> None:
        self.build, self.decode = build, decode

    def complete(self, job: Job) -> bool:
        try:
            if job.answer is None:
                return False
            value: object = json.loads(job.answer)
            if isinstance(value, dict) and set(value) == {"question"}:
                return True
            definition = self.decode(value)
            self.build(value).create(CreateProposal(job.owner, job.id, definition, job.base_plan))
            return True
        except (ValueError, ValidationError, CoachInvalid, InvalidPlanning, PlanningUnavailable):
            return False
