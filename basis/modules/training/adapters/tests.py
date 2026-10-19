"""Real persistence/web compatibility tests; uses only Django's temporary test DB."""

from dataclasses import replace
from decimal import Decimal
from typing import Callable, cast
from unittest.mock import patch
from uuid import UUID, uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.training import training
from basis.modules.training.adapters.django import DjangoSessionRepository, DjangoUnitOfWork
from basis.modules.training.adapters.wire import encode_session
from basis.modules.training.public import (
    BlockData,
    Change,
    ExecutionConflict,
    FinishSession,
    Metric,
    MetricName,
    ReadSession,
    RecordSession,
    SessionChanges,
    SessionState,
    SessionStatus,
    StartSession,
    Unavailable,
)
from basis.shared.identifiers import AccountId, PlannedSessionId, SessionId
from daily_trainning_app.models import User as Athlete
from tests_architecture.repository_contract import RepositoryContract
from training.models import Block, Cycle, Goal, PlannedSession, Session, SyncReceipt, TrainingPlan
from training.services import sync_session


def account(name: str) -> User:
    user = User.objects.create_user(username=name, email=name + "@example.test")
    Athlete.objects.create(
        account=user,
        nombre=name,
        email=user.email,
        fecha_inicio=timezone.localdate(),
        email_verified=True,
        edad=25,
    )
    return user


@override_settings(DEVELOPMENT_ACCESS=True)
class DjangoExecutionTests(RepositoryContract, TestCase):
    def setUp(self) -> None:
        self.user = account("execution")
        self.owner = AccountId(self.user.pk)
        self.repository = DjangoSessionRepository()
        self.make_uow = DjangoUnitOfWork
        self.initial = SessionState(
            SessionId(uuid4()),
            self.owner,
            timezone.localdate(),
            title="Run",
            blocks=(
                BlockData(
                    "running",
                    title="Easy",
                    target=(Metric(MetricName.DISTANCE_M, Decimal("5000")),),
                ),
            ),
        )
        self.service = training()

    def persist(self) -> SessionState:
        with self.make_uow() as work:
            result = self.repository.save(self.initial)
            work.commit()
        return result

    def prescription(self) -> PlannedSession:
        today = timezone.localdate()
        goal = Goal.objects.create(owner=self.user, title="Base", sport="running")
        plan = TrainingPlan.objects.create(
            owner=self.user, goal=goal, title="Plan", start_date=today, end_date=today
        )
        parent: Cycle | None = None
        for kind in ("macro", "meso", "micro"):
            parent = Cycle.objects.create(
                plan=plan, parent=parent, kind=kind, title=kind, start_date=today, end_date=today
            )
        assert parent is not None
        scheduled = PlannedSession.objects.create(
            owner=self.user, plan=plan, cycle=parent, title="Scheduled", date=today
        )
        Block.objects.create(
            planned=scheduled, sport="running", title="Target", target={"distance_m": "5000.50"}
        )
        return scheduled

    def test_start_reuses_active_and_preserves_prescription_without_results(self) -> None:
        scheduled = self.prescription()
        command = StartSession(self.owner, PlannedSessionId(scheduled.pk))
        first = self.service.start(command)
        second = self.service.start(command)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(first.blocks[0].actual, ())
        self.assertIsNone(first.reported_rpe)
        self.assertEqual(first.blocks[0].target[0].value, Decimal("5000.50"))
        self.assertEqual(Block.objects.get(planned=scheduled).target, {"distance_m": "5000.50"})

    def test_owned_read_and_write_cannot_cross_accounts(self) -> None:
        stored = self.persist()
        other = AccountId(account("other").pk)
        with self.assertRaises(Unavailable):
            self.service.read(ReadSession(other, stored.id))
        with self.assertRaises(Unavailable):
            self.service.record(
                RecordSession(other, stored.id, stored.revision, SessionChanges(stored.blocks))
            )
        self.assertEqual(self.repository.get(stored.id, lock=False), stored)

    def test_record_zero_clear_and_finish_then_reject_changes(self) -> None:
        stored = self.persist()
        changed = self.service.record(
            RecordSession(
                self.owner,
                stored.id,
                stored.revision,
                SessionChanges(
                    stored.blocks, duration_seconds=Change(0), reported_rpe=Change(Decimal(0))
                ),
            )
        )
        self.assertEqual(changed.duration_seconds, 0)
        self.assertEqual(changed.reported_rpe, 0)
        final = self.service.finish(
            FinishSession(
                self.owner,
                stored.id,
                changed.revision,
                SessionChanges(changed.blocks, reported_rpe=Change(None)),
            )
        )
        self.assertEqual(final.status, SessionStatus.COMPLETED)
        self.assertIsNone(final.reported_rpe)
        self.assertEqual(final.revision, 3)
        with self.assertRaises(ExecutionConflict):
            self.service.record(
                RecordSession(self.owner, stored.id, final.revision, SessionChanges(final.blocks))
            )
        self.assertEqual(self.repository.get(stored.id, lock=False), final)

    def test_invalid_child_rolls_back_revision_and_all_children(self) -> None:
        stored = self.persist()
        bad = replace(stored.blocks[0], sport="not-a-sport")
        with self.assertRaises(ValidationError):
            self.service.record(
                RecordSession(self.owner, stored.id, stored.revision, SessionChanges((bad,)))
            )
        self.assertEqual(self.repository.get(stored.id, lock=False), stored)

    def test_receipt_failure_rolls_back_inner_committed_session(self) -> None:
        stored = self.persist()
        payload = encode_session(stored)
        payload["notes"] = "must roll back"
        # Temporary signature bridge to legacy receipt coordinator, until ARCH-08.
        synchronize = cast(
            Callable[[User, UUID, dict[str, object]], dict[str, object]], sync_session
        )
        with patch(
            "training.services.SyncReceipt.objects.create",
            side_effect=RuntimeError("receipt failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt failed"):
                synchronize(self.user, uuid4(), payload)
        self.assertEqual(self.repository.get(stored.id, lock=False), stored)
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_web_completion_retry_conflict_and_decimal_json(self) -> None:
        stored = self.persist()
        self.client.force_login(self.user)
        payload = encode_session(stored)
        payload.update({"status": "completed", "reported_rpe": "5.5", "duration_seconds": 0})
        key = str(uuid4())
        body = {
            "account": str(Athlete.objects.get(account=self.user).public_id),
            "mutation_id": key,
            "session": payload,
        }
        first = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["session"]["reported_rpe"], "5.5")
        second = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(second.json(), first.json())
        self.assertEqual(SyncReceipt.objects.count(), 1)
        body["mutation_id"] = str(uuid4())
        conflict = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["current"]["status"], "completed")
        self.assertEqual(SyncReceipt.objects.count(), 1)
        self.assertEqual(self.client.get(f"/api/sessions/{stored.id}/snapshot/").status_code, 200)

    def test_snapshot_preserves_nonconsecutive_block_order(self) -> None:
        stored = self.persist()
        Block.objects.filter(session_id=stored.id).update(order=7)
        restored = self.service.read(ReadSession(self.owner, stored.id))
        blocks = encode_session(restored)["blocks"]
        self.assertIsInstance(blocks, list)
        self.assertEqual(cast(list[dict[str, object]], blocks)[0]["order"], 7)

    def test_stale_invalid_body_still_returns_conflict_before_decoding(self) -> None:
        stored = self.persist()
        self.client.force_login(self.user)
        payload = encode_session(stored)
        payload.update({"revision": 0, "blocks": "invalid"})
        response = self.client.post(
            "/api/sync/",
            {
                "account": str(Athlete.objects.get(account=self.user).public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.repository.get(stored.id, lock=False), stored)
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_offline_temporary_block_identifiers_and_order_are_ignored_on_write(self) -> None:
        stored = self.persist()
        self.client.force_login(self.user)
        payload = encode_session(stored)
        rows = cast(list[dict[str, object]], payload["blocks"])
        rows[0].update({"id": "local-temporary-block", "order": "client-local-order"})
        response = self.client.post(
            "/api/sync/",
            {
                "account": str(Athlete.objects.get(account=self.user).public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["blocks"][0]["order"], 1)
        self.assertEqual(SyncReceipt.objects.count(), 1)
