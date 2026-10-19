"""Receipt/UoW contract and actual atomicity against a temporary database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from typing import Callable
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from basis.bootstrap.sync import synchronization, synchronize
from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.sync.domain.operations import Receipt
from basis.modules.training.public import BlockData, Metric, MetricName, SessionState
from basis.shared.identifiers import AccountId, MutationId, PayloadDigest, Revision, SessionId
from daily_trainning_app.models import User as Athlete
from tests_architecture.sync_contract import ReceiptContract
from training.models import Session, SyncReceipt
from training.services import Conflict, sync_session


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


def payload(session: SessionId, revision: int = 0) -> dict[str, object]:
    return {
        "id": str(session),
        "revision": revision,
        "title": "Original",
        "blocks": [{"sport": "running", "title": "Run", "actual": {"distance_m": "0"}}],
    }


@override_settings(DEVELOPMENT_ACCESS=True)
class DjangoReceiptTests(ReceiptContract, TestCase):
    def setUp(self) -> None:
        self.user = account("receipt")
        self.owner = AccountId(self.user.pk)
        self.repository = synchronization().repository
        self.make_uow = DjangoUnitOfWork
        self.initial = Receipt(
            self.owner,
            MutationId(uuid4()),
            PayloadDigest("a" * 64),
            SessionState(
                SessionId(uuid4()),
                self.owner,
                date(2026, 10, 19),
                duration_seconds=0,
                blocks=(
                    BlockData(
                        "running", id=41, target=(Metric(MetricName.DISTANCE_M, Decimal("0.00")),)
                    ),
                ),
            ),
        )

    def test_receipt_save_failure_rolls_back_actual_inner_committed_training(self) -> None:
        sid = SessionId(uuid4())
        with patch(
            "training.services.SyncReceipt.objects.create", side_effect=RuntimeError("receipt")
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt"):
                synchronize(self.owner, uuid4(), payload(sid))
        assert not Session.objects.filter(pk=sid).exists()
        assert not SyncReceipt.objects.exists()

    def test_receipt_save_failure_restores_existing_blocks_and_revision(self) -> None:
        sid = SessionId(uuid4())
        original = synchronize(self.owner, uuid4(), payload(sid))
        changed = payload(sid, 1)
        changed["title"] = "Changed"
        with patch(
            "training.services.SyncReceipt.objects.create", side_effect=RuntimeError("receipt")
        ):
            with self.assertRaises(RuntimeError):
                synchronize(self.owner, uuid4(), changed)
        row = Session.objects.get(pk=sid)
        assert row.title == original["title"] and row.revision == 1
        assert row.blocks.get().title == "Run"
        assert SyncReceipt.objects.count() == 1

    def test_replay_frozen_result_ignores_later_rows_and_current_access(self) -> None:
        sid, key = SessionId(uuid4()), uuid4()
        body = payload(sid)
        first = synchronize(self.owner, key, body)
        Session.objects.filter(pk=sid).update(title="Later", revision=8)
        with override_settings(DEVELOPMENT_ACCESS=False):
            restored = synchronize(self.owner, key, body)
        assert restored == first
        assert restored["title"] == "Original" and restored["revision"] == 1
        assert Session.objects.get(pk=sid).blocks.get().pk is not None

    def test_same_mutation_is_independent_for_two_owners(self) -> None:
        other = account("receipt-other")
        key = uuid4()
        first = synchronize(self.owner, key, payload(SessionId(uuid4())))
        second = synchronize(AccountId(other.pk), key, payload(SessionId(uuid4())))
        assert first["id"] != second["id"]
        assert SyncReceipt.objects.filter(mutation_id=key).count() == 2

    def test_mismatch_rejected_without_changing_original_receipt(self) -> None:
        sid, key = SessionId(uuid4()), uuid4()
        body = payload(sid)
        first = sync_session(self.user, key, body)
        body["title"] = "Different"
        with self.assertRaises(ValidationError):
            sync_session(self.user, key, body)
        assert SyncReceipt.objects.get().result == first


@skipUnlessDBFeature("has_select_for_update")
@override_settings(DEVELOPMENT_ACCESS=True)
class ReceiptConcurrencyTests(TransactionTestCase):
    def parallel(self, operations: list[Callable[[], str]]) -> list[str]:
        barrier = Barrier(len(operations))

        def execute(operation: Callable[[], str]) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(execute, operations))

    def test_competing_revision_commits_one_session_and_one_receipt(self) -> None:
        user = account("revision-race")
        owner, sid = AccountId(user.pk), SessionId(uuid4())
        original = synchronize(owner, uuid4(), payload(sid))

        def attempt(title: str) -> str:
            body = payload(sid, int(str(original["revision"])))
            body["title"] = title
            try:
                sync_session(User.objects.get(pk=owner), uuid4(), body)
                return "saved"
            except Conflict:
                return "conflict"

        results = self.parallel([lambda: attempt("First"), lambda: attempt("Second")])
        self.assertCountEqual(results, ["saved", "conflict"])
        assert Session.objects.get(pk=sid).revision == Revision(2)
        assert SyncReceipt.objects.count() == 2
