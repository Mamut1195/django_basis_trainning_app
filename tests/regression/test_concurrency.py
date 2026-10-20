from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import TypeVar

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from basis.modules.coach.adapters.actions import enqueue
from basis.modules.coach.adapters.models import TrialFund, UsagePeriod
from basis.modules.sync.adapters.models import SyncReceipt

from .contracts import SessionDocument, required, session_snapshot, sync_session
from .factories import account, session

T = TypeVar("T")


@skipUnlessDBFeature("has_select_for_update")
@override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-a-credential")
class ConcurrencyTests(TransactionTestCase):
    def parallel(self, operations: list[Callable[[], T]]) -> list[T]:
        barrier = threading.Barrier(len(operations))

        def execute(operation: Callable[[], T]) -> T:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(execute, operations))

    def ask(self, owner_id: int) -> str:
        try:
            enqueue(get_user_model().objects.get(pk=owner_id), "short", "Consulta", uuid.uuid4())
            return "created"
        except ValidationError:
            return "limited"

    def test_two_requests_cannot_overdraw_same_personal_budget(self) -> None:
        owner = account()
        UsagePeriod.objects.create(
            owner=owner,
            key=required(owner.billing.period_start).isoformat(),
            spent=Decimal("0.995"),
        )
        results = self.parallel([lambda: self.ask(owner.pk), lambda: self.ask(owner.pk)])
        self.assertCountEqual(results, ["created", "limited"])
        usage = UsagePeriod.objects.get(owner=owner)
        self.assertLessEqual(usage.spent + usage.reserved, 1)

    def test_two_accounts_cannot_overdraw_global_trial_fund(self) -> None:
        first, second = account("first", status="trialing"), account("second", status="trialing")
        TrialFund.objects.create(month=timezone.now().strftime("%Y-%m"), cap=Decimal("0.004"))
        results = self.parallel([lambda: self.ask(first.pk), lambda: self.ask(second.pk)])
        self.assertCountEqual(results, ["created", "limited"])
        self.assertLessEqual(TrialFund.objects.get().reserved, Decimal("0.004"))

    def test_same_sync_operation_in_two_connections_is_acknowledged_once(self) -> None:
        owner = account()
        item = session(owner)
        payload = session_snapshot(item)
        key = uuid.uuid4()

        def send() -> SessionDocument:
            return sync_session(get_user_model().objects.get(pk=owner.pk), key, payload)

        results = self.parallel([send, send])
        self.assertEqual(results[0], results[1])
        self.assertEqual(SyncReceipt.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.revision, 2)
