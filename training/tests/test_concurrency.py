import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from training.ai import enqueue
from training.models import SyncReceipt, TrialFund, UsagePeriod
from training.services import session_snapshot, sync_session

from .factories import account, session


@skipUnlessDBFeature("has_select_for_update")
@override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-a-credential")
class ConcurrencyTests(TransactionTestCase):
    def parallel(self, operations):
        barrier = threading.Barrier(len(operations))

        def execute(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(execute, operations))

    def ask(self, owner_id):
        try:
            enqueue(get_user_model().objects.get(pk=owner_id), "short", "Consulta", uuid.uuid4())
            return "created"
        except ValidationError:
            return "limited"

    def test_two_requests_cannot_overdraw_same_personal_budget(self):
        owner = account()
        UsagePeriod.objects.create(
            owner=owner, key=owner.billing.period_start.isoformat(), spent=Decimal("0.995")
        )
        results = self.parallel([lambda: self.ask(owner.pk), lambda: self.ask(owner.pk)])
        self.assertCountEqual(results, ["created", "limited"])
        usage = UsagePeriod.objects.get(owner=owner)
        self.assertLessEqual(usage.spent + usage.reserved, 1)

    def test_two_accounts_cannot_overdraw_global_trial_fund(self):
        first, second = account("first", status="trialing"), account("second", status="trialing")
        TrialFund.objects.create(month=timezone.now().strftime("%Y-%m"), cap=Decimal("0.004"))
        results = self.parallel([lambda: self.ask(first.pk), lambda: self.ask(second.pk)])
        self.assertCountEqual(results, ["created", "limited"])
        self.assertLessEqual(TrialFund.objects.get().reserved, Decimal("0.004"))

    def test_same_sync_operation_in_two_connections_is_acknowledged_once(self):
        owner = account()
        item = session(owner)
        payload = session_snapshot(item)
        key = uuid.uuid4()

        def send():
            return sync_session(get_user_model().objects.get(pk=owner.pk), key, payload)

        results = self.parallel([send, send])
        self.assertEqual(results[0], results[1])
        self.assertEqual(SyncReceipt.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.revision, 2)
