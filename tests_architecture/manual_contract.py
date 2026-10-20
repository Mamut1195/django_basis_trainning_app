"""Atomic manual-write behavior shared by permissive memory and Django ports."""

from datetime import date
from decimal import Decimal
from typing import Callable

from basis.modules.training.application.manual import (
    AddBlock,
    CreateManualSession,
    ManualTraining,
    SaveBlockMetrics,
)
from basis.modules.training.domain.execution import Metric, MetricName, Unavailable
from basis.modules.training.domain.manual import (
    ManualConflict,
    ManualSessionData,
    ParentRef,
    SessionParent,
)
from basis.shared.identifiers import AccountId, BlockId, Revision, SessionId


class ManualContract:
    service: ManualTraining
    owner: AccountId
    other: AccountId
    counts: Callable[[], tuple[int, int]]
    revision: Callable[[ParentRef], int]
    first_block: Callable[[SessionId], BlockId]
    fail_write: Callable[[str], None]

    def create(self) -> SessionId:
        return self.service.create(CreateManualSession(self.owner,
            ManualSessionData("Manual", date(2026, 1, 1), 0, reported_rpe=Decimal(0)),
            "running", "Run"))

    def test_contract_manual_session_and_initial_block_commit_together(self) -> None:
        id = self.create()
        assert self.counts() == (1, 1)
        assert self.revision(SessionParent(id)) == 1

    def test_contract_initial_block_failure_rolls_back_session(self) -> None:
        self.fail_write("add_block")
        try:
            self.create()
        except OSError:
            pass
        else:
            raise AssertionError("Expected initial block failure")
        assert self.counts() == (0, 0)

    def test_contract_block_and_revision_commit_together(self) -> None:
        id = self.create()
        self.service.add_block(AddBlock(self.owner, SessionParent(id), Revision(1), "cycling", "Ride"))
        assert self.counts() == (1, 2)
        assert self.revision(SessionParent(id)) == 2

    def test_contract_stale_revision_cannot_create_child(self) -> None:
        id = self.create()
        try:
            self.service.add_block(AddBlock(self.owner, SessionParent(id), Revision(0), "running", "Run"))
        except ManualConflict:
            pass
        else:
            raise AssertionError("Expected revision conflict")
        assert self.counts() == (1, 1)
        assert self.revision(SessionParent(id)) == 1

    def test_contract_child_failure_rolls_back_parent_revision(self) -> None:
        id = self.create()
        self.fail_write("save_metrics")
        try:
            self.service.save_metrics(SaveBlockMetrics(self.owner, self.first_block(id), Revision(1),
                (Metric(MetricName.DURATION_SECONDS, Decimal(0)),)))
        except OSError:
            pass
        else:
            raise AssertionError("Expected child write failure")
        assert self.revision(SessionParent(id)) == 1

    def test_contract_owner_guard_does_not_depend_on_repository_filters(self) -> None:
        id = self.create()
        try:
            self.service.add_block(AddBlock(self.other, SessionParent(id), Revision(1), "running", "Foreign"))
        except Unavailable:
            pass
        else:
            raise AssertionError("Expected owner guard")
        assert self.counts() == (1, 1)
        assert self.revision(SessionParent(id)) == 1
