"""Shared plan/version contract for memory and Django repositories."""

from dataclasses import replace
from typing import Callable

from basis.modules.training.application.planning import PlanRepository
from basis.modules.training.public import CreatePlan, PlanDefinition, Planning, RevisePlan
from basis.shared.identifiers import AccountId, PlannedSessionId


class PlanningContract:
    service: Planning
    repository: PlanRepository
    owner: AccountId
    definition: PlanDefinition
    count_plans: Callable[[], int]
    mark_executed: Callable[[PlannedSessionId], None]

    def test_contract_definition_creates_private_prescription_without_results(self) -> None:
        result = self.service.create(CreatePlan(self.owner, self.definition))
        saved = self.repository.snapshot(self.owner, result.id, lock=False)
        assert saved.header.owner == self.owner and saved.header.version == 1
        assert [(c.kind, c.title, c.start_date, c.end_date) for c in saved.definition.cycles] == [
            (c.kind, c.title, c.start_date, c.end_date) for c in self.definition.cycles
        ]
        assert len(saved.definition.sessions) == 3
        for session in saved.definition.sessions:
            assert session.source_id is not None and session.blocks[0].actual == ()
            assert session.blocks[0].target == self.definition.sessions[0].blocks[0].target

    def test_contract_preview_leaves_no_rows(self) -> None:
        self.service.preview(CreatePlan(self.owner, self.definition))
        assert self.count_plans() == 0

    def test_contract_revision_keeps_history_and_only_unexecuted_future_sessions(self) -> None:
        original = self.service.create(CreatePlan(self.owner, self.definition))
        before = self.repository.snapshot(self.owner, original.id, lock=False)
        executed = before.definition.sessions[0].source_id
        assert executed is not None
        self.mark_executed(executed)
        revised = self.service.revise(RevisePlan(self.owner, original.id))
        after = self.repository.snapshot(self.owner, original.id, lock=False)
        current = self.repository.snapshot(self.owner, revised.id, lock=False)
        assert revised.previous == original.id and revised.lineage == original.lineage
        assert revised.version == original.version + 1
        assert after.definition == before.definition and executed in after.executed
        assert after.has_successor
        assert [s.title for s in current.definition.sessions] == ["future"]
        assert tuple(replace(b, id=None) for b in current.definition.sessions[0].blocks) == tuple(
            replace(b, id=None) for b in before.definition.sessions[1].blocks
        )
