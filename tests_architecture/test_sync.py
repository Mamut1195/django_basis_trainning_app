"""Pure synchronization orchestration: replay ordering and atomic receipt writes."""

from dataclasses import replace
from types import TracebackType
from typing import Self
from unittest import TestCase
from uuid import UUID

from basis.modules.sync.application.operations import SyncCommand, Synchronization
from basis.modules.sync.domain.operations import InvalidSynchronization, MutationIdentity, Receipt
from basis.modules.training.public import (
    Change,
    ExecutionConflict,
    InvalidExecution,
    SessionChanges,
    SessionState,
    Training,
    Unavailable,
)
from basis.shared.identifiers import AccountId, MutationId, PayloadDigest, Revision
from tests_architecture.sync_contract import ReceiptContract
from tests_architecture.test_execution import (
    BLOCK,
    OWNER,
    SID,
    TODAY,
    FakeAuthorization,
    FakeClock,
    FakeRepository,
    FixedIds,
)

MUTATION = MutationId(UUID("00000000-0000-0000-0000-000000000008"))
DIGEST = PayloadDigest("a" * 64)


class MemoryReceipts:
    def __init__(self) -> None:
        self.rows: dict[tuple[AccountId, MutationId], Receipt] = {}
        self.fail_save = False

    def get(self, owner: AccountId, mutation: MutationId) -> Receipt | None:
        return self.rows.get((owner, mutation))

    def save(self, receipt: Receipt) -> None:
        if self.fail_save:
            raise RuntimeError("receipt unavailable")
        self.rows[receipt.owner, receipt.mutation] = receipt


class MemoryWork:
    def __init__(self, receipts: MemoryReceipts, sessions: FakeRepository) -> None:
        self.receipts, self.sessions = receipts, sessions
        self.before_receipts = dict(receipts.rows)
        self.before_sessions = dict(sessions.rows)
        self.committed = False

    def __enter__(self) -> Self:
        return self

    def commit(self) -> None:
        self.committed = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self.committed:
            self.receipts.rows = self.before_receipts
            self.sessions.rows = self.before_sessions


class Locks:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def lock(self, owner: AccountId) -> None:
        self.events.append("account")


class Source:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.digest = DIGEST
        self.expected = Revision(0)
        self.fail_identity = False
        self.fail_revision = False
        self.fail_changes = False

    def identity(self) -> MutationIdentity:
        self.events.append("identity")
        if self.fail_identity:
            raise ValueError("invalid identity")
        return MutationIdentity(MUTATION, SID, self.digest)

    def revision(self) -> Revision:
        self.events.append("revision")
        if self.fail_revision:
            raise ValueError("invalid shape")
        return self.expected

    def changes(self) -> SessionChanges:
        self.events.append("changes")
        if self.fail_changes:
            raise ValueError("invalid changes")
        return SessionChanges((BLOCK,), title=Change("Original"))


class SyncTests(ReceiptContract, TestCase):
    repository: MemoryReceipts

    def setUp(self) -> None:
        self.repository = MemoryReceipts()
        self.sessions = FakeRepository()
        self.make_uow = lambda: MemoryWork(self.repository, self.sessions)
        self.initial = Receipt(
            OWNER,
            MUTATION,
            DIGEST,
            SessionState(SID, OWNER, TODAY, duration_seconds=0, blocks=(replace(BLOCK, id=41),)),
        )
        self.events: list[str] = []
        self.source = Source(self.events)
        self.authorization = FakeAuthorization()
        training = Training(
            self.sessions, self.make_uow, self.authorization, FakeClock(), FixedIds()
        )
        self.service = Synchronization(
            self.repository, self.make_uow, Locks(self.events), self.authorization, training
        )
        self.command = SyncCommand(OWNER, self.source)

    def test_first_write_records_then_replay_returns_original_snapshot(self) -> None:
        result = self.service.execute(self.command)
        self.sessions.rows[SID] = replace(result, title="Later", revision=Revision(2))
        self.authorization.allowed = False
        self.source.fail_revision = self.source.fail_changes = True
        self.events.clear()
        assert self.service.execute(self.command) == result
        assert self.events == ["account", "identity"]
        assert len(self.repository.rows) == 1

    def test_different_digest_rejected_before_current_access_or_shape(self) -> None:
        self.service.execute(self.command)
        self.source.digest = PayloadDigest("b" * 64)
        self.authorization.allowed = False
        self.source.fail_revision = True
        with self.assertRaises(InvalidSynchronization):
            self.service.execute(self.command)

    def test_identity_still_validated_before_replay(self) -> None:
        self.service.execute(self.command)
        self.source.fail_identity = True
        with self.assertRaises(ValueError):
            self.service.execute(self.command)

    def test_authorization_precedes_revision_validation(self) -> None:
        self.authorization.allowed = False
        self.source.fail_revision = True
        with self.assertRaises(PermissionError):
            self.service.execute(self.command)
        assert self.events == ["account", "identity"]

    def test_conflict_precedes_deferred_changes(self) -> None:
        self.sessions.rows[SID] = self.initial.result
        self.source.fail_changes = True
        with self.assertRaises(ExecutionConflict):
            self.service.execute(self.command)
        assert "changes" not in self.events
        assert not self.repository.rows

    def test_foreign_session_precedes_deferred_changes(self) -> None:
        self.sessions.rows[SID] = replace(self.initial.result, owner=AccountId(2))
        self.source.fail_changes = True
        with self.assertRaises(Unavailable):
            self.service.execute(self.command)
        assert "changes" not in self.events

    def test_new_nonzero_revision_rejected_before_changes(self) -> None:
        self.source.expected = Revision(1)
        self.source.fail_changes = True
        with self.assertRaises(InvalidExecution):
            self.service.execute(self.command)
        assert "changes" not in self.events

    def test_receipt_failure_rolls_back_inner_committed_session(self) -> None:
        self.repository.fail_save = True
        with self.assertRaises(RuntimeError):
            self.service.execute(self.command)
        assert not self.sessions.rows and not self.repository.rows

    def test_late_conversion_failure_leaves_no_partial_rows(self) -> None:
        self.source.fail_changes = True
        with self.assertRaises(ValueError):
            self.service.execute(self.command)
        assert not self.sessions.rows and not self.repository.rows
