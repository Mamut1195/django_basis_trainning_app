"""Atomic proposal acceptance/edit/reject through the shared planning contract."""

from dataclasses import dataclass, replace
from typing import Callable, Protocol

from basis.modules.training.public import CoachPlanning, PlanDefinition
from basis.shared.identifiers import AccountId, JobId, PlanId, ProposalId
from basis.shared.ports import UnitOfWork

from ..domain.jobs import CoachInvalid
from ..domain.proposals import Proposal, require_review


@dataclass(frozen=True)
class AcceptProposal:
    owner: AccountId
    proposal: ProposalId
    expected_review: str | None = None


@dataclass(frozen=True)
class EditAndAcceptProposal:
    owner: AccountId
    proposal: ProposalId
    definition: PlanDefinition
    expected_review: str | None = None


@dataclass(frozen=True)
class CreateProposal:
    owner: AccountId
    job: JobId
    definition: PlanDefinition
    base_plan: PlanId | None


class ProposalAuthorization(Protocol):
    def require(self, owner: AccountId) -> None: ...


class ProposalRepository(Protocol):
    def get(self, owner: AccountId, id: ProposalId, *, definition: bool = True) -> Proposal: ...
    def save(self, proposal: Proposal, *, edited: bool = False) -> None: ...
    def create(self, command: CreateProposal) -> ProposalId: ...


class ProposalChecks(Protocol):
    def validate(
        self, owner: AccountId, job: JobId, definition: PlanDefinition, base: PlanId | None
    ) -> None: ...


class Proposals:
    def __init__(
        self,
        repository: ProposalRepository,
        planning: CoachPlanning,
        authorization: ProposalAuthorization,
        uow: Callable[[], UnitOfWork],
        checks: ProposalChecks | None = None,
    ) -> None:
        self.repository, self.planning, self.authorization, self.uow = (
            repository,
            planning,
            authorization,
            uow,
        )
        self.checks = checks

    def _check(self, proposal: Proposal) -> None:
        if proposal.definition is None:
            raise CoachInvalid("La propuesta pendiente no tiene definición.")
        if self.checks is not None:
            self.checks.validate(
                proposal.owner, proposal.job, proposal.definition, proposal.base_plan
            )

    def validate(self, owner: AccountId, definition: PlanDefinition) -> None:
        self.planning.preview(owner, definition)

    def create(self, command: CreateProposal) -> ProposalId:
        with self.uow() as work:
            if self.checks is not None:
                self.checks.validate(
                    command.owner, command.job, command.definition, command.base_plan
                )
            # Preview shares the same outer transaction and retained context locks.
            self.validate(command.owner, command.definition)
            result = self.repository.create(command)
            work.commit()
            return result

    def _accept(self, proposal: Proposal) -> PlanId:
        if proposal.status == "accepted":
            if proposal.accepted_plan is None:
                raise CoachInvalid("La propuesta aceptada no tiene plan.")
            return proposal.accepted_plan
        if proposal.status != "pending":
            raise CoachInvalid("Esta propuesta ya fue rechazada.")
        if proposal.base_plan is not None and self.planning.has_successor(
            proposal.owner, proposal.base_plan
        ):
            raise CoachInvalid(
                "El plan cambi\u00f3 desde la propuesta. Revisa una nueva versi\u00f3n."
            )
        if proposal.definition is None:
            raise CoachInvalid("La propuesta pendiente no tiene definici\u00f3n.")
        self._check(proposal)
        result = self.planning.create(proposal.owner, proposal.definition, proposal.base_plan)
        self.repository.save(replace(proposal, status="accepted", accepted_plan=result))
        return result

    def accept(self, command: AcceptProposal) -> PlanId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            proposal = self.repository.get(command.owner, command.proposal)
            require_review(proposal, command.expected_review)
            result = self._accept(proposal)
            work.commit()
            return result

    def edit_and_accept(self, command: EditAndAcceptProposal) -> PlanId:
        with self.uow() as work:
            self.authorization.require(command.owner)
            proposal = self.repository.get(command.owner, command.proposal, definition=False)
            require_review(proposal, command.expected_review)
            if proposal.status != "pending":
                raise CoachInvalid("La propuesta ya se resolvi\u00f3.")
            proposal = replace(proposal, definition=command.definition)
            self._check(proposal)
            self.validate(command.owner, command.definition)
            self.repository.save(proposal, edited=True)
            result = self._accept(proposal)
            work.commit()
            return result

    def reject(self, command: AcceptProposal) -> None:
        with self.uow() as work:
            self.authorization.require(command.owner)
            proposal = self.repository.get(command.owner, command.proposal, definition=False)
            require_review(proposal, command.expected_review)
            if command.expected_review is not None and proposal.status == "accepted":
                raise CoachInvalid("La propuesta ya fue aceptada. No se puede descartar.")
            if proposal.status == "pending":
                self.repository.save(replace(proposal, status="rejected"))
            work.commit()

    def review(self, command: AcceptProposal, definition: PlanDefinition | None = None) -> Proposal:
        # A rollback-only preview never inserts a visible plan or calendar entry.
        with self.uow():
            self.authorization.require(command.owner)
            proposal = self.repository.get(command.owner, command.proposal)
            require_review(proposal, command.expected_review)
            if proposal.status != "pending":
                raise CoachInvalid("La propuesta ya se resolvió.")
            if proposal.base_plan is not None and self.planning.has_successor(
                proposal.owner, proposal.base_plan
            ):
                raise CoachInvalid("El plan cambió desde la propuesta. Revisa una nueva versión.")
            if definition is not None:
                proposal = replace(proposal, definition=definition)
            self._check(proposal)
            assert proposal.definition is not None
            self.validate(proposal.owner, proposal.definition)
            return proposal
