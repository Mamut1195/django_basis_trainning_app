"""Pure execution tests. Runs without Django, network, settings or a database."""

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import TracebackType
from typing import Self
from unittest import TestCase
from uuid import UUID

from basis.modules.training.public import (
    BlockData,
    Change,
    ExecutionConflict,
    FinishSession,
    InvalidExecution,
    Metric,
    MetricName,
    Prescription,
    ReadSession,
    RecordSession,
    SessionChanges,
    SessionState,
    SessionStatus,
    StartSession,
    StrengthData,
    Training,
    Unavailable,
)
from basis.shared.identifiers import AccountId, PlannedSessionId, Revision, SessionId
from tests_architecture.repository_contract import RepositoryContract

OWNER = AccountId(1)
OTHER = AccountId(2)
PLAN = PlannedSessionId(3)
SID = SessionId(UUID("12345678-1234-1234-1234-123456789012"))
TODAY = date(2026, 10, 19)
BLOCK = BlockData("running", "Run", target=(Metric(MetricName.DISTANCE_M, Decimal("5000")),))


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[SessionId, SessionState] = {}
        self.planned = Prescription(PLAN, OWNER, "Scheduled", (BLOCK,))
        self.events: list[str] = []

    def lock_owner(self, owner: AccountId) -> None:
        self.events.append("lock-account")

    def prescription(self, owner: AccountId, planned: PlannedSessionId) -> Prescription:
        self.events.append("lock-planned")
        if owner != self.planned.owner or planned != self.planned.id:
            raise Unavailable()
        return self.planned

    def active(self, owner: AccountId, planned: PlannedSessionId) -> SessionState | None:
        return next(
            (
                s
                for s in self.rows.values()
                if s.owner == owner
                and s.planned == planned
                and s.status == SessionStatus.IN_PROGRESS
            ),
            None,
        )

    def get(
        self, session: SessionId, *, lock: bool, owner: AccountId | None = None
    ) -> SessionState | None:
        self.events.append("lock-session" if lock else "read")
        # Deliberately permissive: core ownership guards must still work when a
        # port accepts but does not implement the optional SQL scoping hint.
        return self.rows.get(session)

    def save(self, state: SessionState) -> SessionState:
        self.rows[state.id] = state
        return state

    def check_plan(self, owner: AccountId, planned: PlannedSessionId) -> None:
        if owner != self.planned.owner or planned != self.planned.id:
            raise InvalidExecution("Prescripción no disponible.")


class FakeWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.before = dict(repository.rows)
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
        if exc_type or not self.committed:
            self.repository.rows = self.before


class FakeClock:
    def today(self) -> date:
        return TODAY

    def now(self) -> datetime:
        return datetime(2026, 10, 19, tzinfo=timezone.utc)


class FixedIds:
    def new(self) -> SessionId:
        return SID


class FakeAuthorization:
    def __init__(self) -> None:
        self.allowed = True

    def require(self, owner: AccountId) -> None:
        if not self.allowed:
            raise PermissionError("Access expired")


class ExecutionTests(TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.authorization = FakeAuthorization()
        self.service = Training(
            self.repository,
            lambda: FakeWork(self.repository),
            self.authorization,
            FakeClock(),
            FixedIds(),
        )

    def start(self) -> SessionState:
        return self.service.start(StartSession(OWNER, PLAN))

    def test_start_copies_prescription_without_actuals_or_invented_measurements(self) -> None:
        started = self.start()
        self.assertEqual(self.repository.events[:2], ["lock-account", "lock-planned"])
        self.assertEqual(started.id, SID)
        self.assertEqual(started.date, TODAY)
        self.assertEqual(started.blocks[0].target, BLOCK.target)
        self.assertEqual(started.blocks[0].actual, ())
        self.assertIsNone(started.reported_rpe)
        self.assertIsNone(started.duration_seconds)
        self.assertEqual(self.start(), started)
        self.assertEqual(len(self.repository.rows), 1)
        self.assertEqual(self.repository.planned.blocks, (BLOCK,))

    def test_record_zero_then_clear_and_finish_preserves_target(self) -> None:
        started = self.start()
        zero = SessionChanges(
            started.blocks, duration_seconds=Change(0), reported_rpe=Change(Decimal(0))
        )
        recorded = self.service.record(RecordSession(OWNER, SID, Revision(1), zero))
        self.assertEqual(recorded.revision, 2)
        self.assertEqual(recorded.duration_seconds, 0)
        self.assertEqual(recorded.reported_rpe, 0)
        self.assertEqual(self.repository.events[-2:], ["lock-account", "lock-session"])
        final = self.service.finish(
            FinishSession(
                OWNER, SID, Revision(2), SessionChanges(recorded.blocks, reported_rpe=Change(None))
            )
        )
        self.assertEqual(final.status, SessionStatus.COMPLETED)
        self.assertIsNone(final.reported_rpe)
        self.assertEqual(final.duration_seconds, 0)
        self.assertEqual(final.blocks[0].target, BLOCK.target)
        with self.assertRaises(ExecutionConflict):
            self.service.record(RecordSession(OWNER, SID, final.revision, zero))
        self.assertEqual(self.repository.rows[SID], final)

    def test_stale_revision_and_foreign_owner_do_not_write(self) -> None:
        initial = self.start()
        for owner, revision, error in (
            (OWNER, Revision(0), ExecutionConflict),
            (OTHER, Revision(1), Unavailable),
        ):
            with self.assertRaises(error):
                self.service.record(RecordSession(owner, SID, revision, SessionChanges((BLOCK,))))
            self.assertEqual(self.repository.rows[SID], initial)
        with self.assertRaises(Unavailable):
            self.service.read(ReadSession(OTHER, SID))

    def test_expired_access_cannot_write_but_can_read(self) -> None:
        initial = self.start()
        self.authorization.allowed = False
        self.assertEqual(self.service.read(ReadSession(OWNER, SID)), initial)
        with self.assertRaises(PermissionError):
            self.service.record(RecordSession(OWNER, SID, Revision(1), SessionChanges((BLOCK,))))
        self.assertEqual(self.repository.rows[SID], initial)

    def test_new_session_requires_zero_revision_and_blocks(self) -> None:
        with self.assertRaises(InvalidExecution):
            self.service.record(RecordSession(OWNER, SID, Revision(1), SessionChanges((BLOCK,))))
        with self.assertRaises(InvalidExecution):
            self.service.record(RecordSession(OWNER, SID, Revision(0), SessionChanges(())))
        created = self.service.record(
            RecordSession(OWNER, SID, Revision(0), SessionChanges((BLOCK,)))
        )
        self.assertEqual(created.revision, 1)

    def test_prescription_actuals_stay_optional_for_strength(self) -> None:
        self.repository.planned = replace(
            self.repository.planned,
            blocks=(
                BlockData(
                    "strength",
                    sets=(StrengthData(exercise=2, target_kg=Decimal("80.25"), target_reps=5),),
                ),
            ),
        )
        row = self.start().blocks[0].sets[0]
        self.assertEqual(row.target_kg, Decimal("80.25"))
        self.assertIsNone(row.actual_kg)
        self.assertIsNone(row.actual_reps)
        self.assertIsNone(row.actual_rpe)


class FakeRepositoryTests(RepositoryContract, TestCase):
    def setUp(self) -> None:
        repo = FakeRepository()
        self.repository = repo
        self.make_uow = lambda: FakeWork(repo)
        self.initial = SessionState(SID, OWNER, TODAY, title="Session", blocks=(BLOCK,))
