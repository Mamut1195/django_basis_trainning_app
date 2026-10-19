"""Proposal cases execute without Django, database or credentials."""

from dataclasses import replace
from datetime import date
from types import TracebackType
from typing import Self
from unittest import TestCase
from uuid import UUID

from basis.modules.coach.application.proposals import (
    AcceptProposal,
    CreateProposal,
    EditAndAcceptProposal,
    Proposals,
)
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import Proposal, ProposalUnavailable
from basis.modules.training.public import PlanDefinition
from basis.shared.identifiers import AccountId, GoalId, JobId, PlanId, ProposalId

OWNER = AccountId(1)
DEFINITION = PlanDefinition(GoalId(1), "Private", date(2026, 10, 1), date(2026, 10, 8))


class MemoryProposals:
    def __init__(self) -> None:
        self.row = Proposal(
            ProposalId(1), OWNER, JobId(UUID(int=1)), DEFINITION, None, "pending", None
        )

    def get(self, owner: AccountId, id: ProposalId, *, definition: bool = True) -> Proposal:
        if self.row.owner != owner or self.row.id != id:
            raise ProposalUnavailable
        return self.row

    def save(self, proposal: Proposal, *, edited: bool = False) -> None:
        self.row = proposal

    def create(self, command: CreateProposal) -> ProposalId:
        self.row = Proposal(
            ProposalId(2),
            command.owner,
            command.job,
            command.definition,
            command.base_plan,
            "pending",
            None,
        )
        return self.row.id


class MemoryPlanning:
    def __init__(self) -> None:
        self.created: list[PlanDefinition] = []
        self.previews: list[PlanDefinition] = []
        self.successor = False

    def preview(self, owner: AccountId, definition: PlanDefinition) -> None:
        self.previews.append(definition)

    def create(
        self, owner: AccountId, definition: PlanDefinition, previous: PlanId | None
    ) -> PlanId:
        self.created.append(definition)
        return PlanId(5)

    def has_successor(self, owner: AccountId, previous: PlanId) -> bool:
        return self.successor


class Authorization:
    def require(self, owner: AccountId) -> None:
        if owner != OWNER:
            raise PermissionError


class Work:
    def __enter__(self) -> Self:
        return self

    def commit(self) -> None:
        pass

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass


class CoachProposalTests(TestCase):
    def setUp(self) -> None:
        self.repo, self.planning = MemoryProposals(), MemoryPlanning()
        self.service = Proposals(self.repo, self.planning, Authorization(), Work)

    def test_acceptance_replays_same_private_plan_without_recreation(self) -> None:
        command = AcceptProposal(OWNER, ProposalId(1))
        self.assertEqual(self.service.accept(command), PlanId(5))
        self.assertEqual(self.service.accept(command), PlanId(5))
        self.assertEqual(self.planning.created, [DEFINITION])

    def test_rejected_proposal_cannot_create_plan(self) -> None:
        command = AcceptProposal(OWNER, ProposalId(1))
        self.service.reject(command)
        with self.assertRaises(CoachInvalid):
            self.service.accept(command)
        self.assertEqual(self.planning.created, [])

    def test_stale_base_plan_rejected_before_creation(self) -> None:
        self.repo.row = replace(self.repo.row, base_plan=PlanId(1))
        self.planning.successor = True
        with self.assertRaises(CoachInvalid):
            self.service.accept(AcceptProposal(OWNER, ProposalId(1)))
        self.assertEqual(self.repo.row.status, "pending")
        self.assertEqual(self.planning.created, [])

    def test_edit_validates_and_uses_same_definition_for_acceptance(self) -> None:
        changed = replace(DEFINITION, title="Edited")
        self.service.edit_and_accept(EditAndAcceptProposal(OWNER, ProposalId(1), changed))
        self.assertEqual(self.planning.previews, [changed])
        self.assertEqual(self.planning.created, [changed])

    def test_foreign_owner_has_no_write(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.accept(AcceptProposal(AccountId(2), ProposalId(1)))
        self.assertEqual(self.repo.row.status, "pending")

    def test_edit_cannot_reopen_accepted_proposal(self) -> None:
        self.service.accept(AcceptProposal(OWNER, ProposalId(1)))
        with self.assertRaises(CoachInvalid):
            self.service.edit_and_accept(EditAndAcceptProposal(OWNER, ProposalId(1), DEFINITION))
        self.assertEqual(len(self.planning.created), 1)
