import base64
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from standardwebhooks.webhooks import Webhook

from training.ai import INPUT_RATE, LIMITS, OUTPUT_RATE, enqueue, process_one, settle
from training.billing import ProviderUnavailable, checkout, reconcile
from training.models import (
    AIJob,
    AIServiceState,
    BillingAccount,
    TrialFund,
    UsagePeriod,
    WebhookReceipt,
)

from .factories import account


@override_settings(POLAR_PRODUCT_ID="basis-monthly", POLAR_ACCESS_TOKEN="test-not-a-credential")
class BillingTests(TestCase):
    @patch("training.billing.polar_request")
    def test_first_seen_paid_subscription_remembers_its_trial(self, request):
        request.return_value = self.state(
            "active", trial_start=(timezone.now() - timedelta(days=7)).isoformat()
        )
        self.assertFalse(self.user.billing.trial_used)
        self.assertTrue(reconcile(self.user).trial_used)

    def setUp(self):
        self.user = account()

    def state(self, status="active", **changes):
        row = {
            "id": "subscription",
            "product_id": "basis-monthly",
            "status": status,
            "current_period_start": (timezone.now() - timedelta(days=1)).isoformat(),
            "current_period_end": (timezone.now() + timedelta(days=29)).isoformat(),
            "trial_end": (timezone.now() + timedelta(days=6)).isoformat(),
            "cancel_at_period_end": False,
        }
        row.update(changes)
        return {
            "id": "customer-athlete",
            "external_id": str(self.user.athlete.public_id),
            "active_subscriptions": [row] if status else [],
        }

    @patch("training.billing.polar_request")
    def test_authoritative_reconcile_and_no_access_from_redirect(self, request):
        self.client.force_login(self.user)
        self.user.billing.status = "inactive"
        self.user.billing.save()
        self.assertEqual(self.client.get("/billing/?checkout=returned").status_code, 200)
        self.user.billing.refresh_from_db()
        self.assertFalse(self.user.billing.entitled)
        request.return_value = self.state("trialing")
        row = reconcile(self.user)
        self.assertTrue(row.entitled)
        self.assertTrue(row.trial_used)
        request.return_value = self.state(None)
        row = reconcile(self.user)
        self.assertFalse(row.entitled)
        self.assertTrue(row.trial_used)

    @patch("training.billing.polar_request")
    def test_cancel_keeps_access_until_period_end_and_product_filtered(self, request):
        request.return_value = self.state(cancel_at_period_end=True)
        row = reconcile(self.user)
        self.assertTrue(row.entitled)
        self.assertTrue(row.cancel_at_period_end)
        request.return_value = self.state(product_id="other-product")
        self.assertFalse(reconcile(self.user).entitled)

    @patch("training.billing.polar_request")
    def test_checkout_selects_server_product_and_verifies_price_trial(self, request):
        billing = self.user.billing
        billing.status = "inactive"
        billing.save()
        product = {
            "recurring_interval": "month",
            "trial_interval": "day",
            "trial_interval_count": 7,
            "prices": [{"price_amount": 500, "price_currency": "usd", "tax_behavior": "exclusive"}],
        }
        request.side_effect = [product, {"url": "https://sandbox.polar.sh/checkout/test"}]
        self.assertTrue(checkout(self.user).startswith("https://sandbox.polar.sh/"))
        self.assertTrue(checkout(self.user).startswith("https://sandbox.polar.sh/"))
        self.assertEqual(request.call_count, 2)
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["products"], ["basis-monthly"])
        self.assertTrue(payload["allow_trial"])
        product["prices"][0]["price_amount"] = 600
        BillingAccount.objects.filter(owner=self.user).update(
            checkout_url="", checkout_expires_at=None
        )
        request.side_effect = [product]
        with self.assertRaises(ProviderUnavailable):
            checkout(self.user)

    @override_settings(
        POLAR_WEBHOOK_SECRET="whsec_"
        + base64.b64encode(b"basis-test-secret-for-signature").decode()
    )
    @patch("training.billing.polar_request")
    def test_signed_webhook_replay_and_out_of_order_use_current_state(self, request):
        request.return_value = self.state()
        self.assertEqual(
            self.client.post(
                "/webhooks/polar/", data="{}", content_type="application/json"
            ).status_code,
            400,
        )
        now = timezone.now()
        body = json.dumps(
            {
                "type": "customer.state_changed",
                "data": {"external_id": str(self.user.athlete.public_id)},
            }
        )
        from django.conf import settings

        def send(event_id):
            signature = Webhook(settings.POLAR_WEBHOOK_SECRET).sign(event_id, now, body)
            return self.client.post(
                "/webhooks/polar/",
                data=body,
                content_type="application/json",
                HTTP_WEBHOOK_ID=event_id,
                HTTP_WEBHOOK_TIMESTAMP=str(int(now.timestamp())),
                HTTP_WEBHOOK_SIGNATURE=signature,
            )

        self.assertEqual(send("evt-1").status_code, 200)
        self.assertEqual(send("evt-1").status_code, 200)
        self.assertEqual(request.call_count, 1)
        request.return_value = self.state(None)
        self.assertEqual(send("older-delivery").status_code, 200)
        self.user.billing.refresh_from_db()
        self.assertFalse(self.user.billing.entitled)
        self.assertEqual(WebhookReceipt.objects.count(), 2)


@override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-a-credential")
class AIBudgetTests(TestCase):
    def setUp(self):
        self.user = account()

    def enqueue(self, kind="short", owner=None):
        return enqueue(owner or self.user, kind, "¿Cómo organizo mi próxima semana?", uuid.uuid4())

    def test_exact_reservation_idempotency_and_personal_cap(self):
        key = uuid.uuid4()
        first = enqueue(self.user, "short", "Consulta", key)
        self.assertEqual(enqueue(self.user, "short", "Consulta", key).pk, first.pk)
        self.assertEqual(
            first.reservation, LIMITS["short"][0] * INPUT_RATE + LIMITS["short"][1] * OUTPUT_RATE
        )
        usage = first.usage_period
        usage.spent = Decimal("0.997")
        usage.save()
        with self.assertRaises(ValidationError):
            self.enqueue()
        self.assertEqual(AIJob.objects.count(), 1)

    def test_action_quotas_and_trial_lifetime(self):
        first = self.enqueue()
        usage = first.usage_period
        usage.short_count = 200
        usage.save()
        with self.assertRaises(ValidationError):
            self.enqueue()
        trial = account("trial", status="trialing")
        first = self.enqueue("plan", trial)
        self.assertEqual(first.usage_period.key, "trial-lifetime")
        with self.assertRaises(ValidationError):
            self.enqueue("plan", trial)
        trial.billing.period_start = timezone.now()
        trial.billing.save()
        with self.assertRaises(ValidationError):
            self.enqueue("plan", trial)

    def test_global_trial_fund_and_personal_trial_budget(self):
        trial = account("trial", status="trialing")
        fund = TrialFund.objects.create(
            month=timezone.now().strftime("%Y-%m"), spent=Decimal("4.999")
        )
        with self.assertRaises(ValidationError):
            self.enqueue(owner=trial)
        fund.spent = 0
        fund.save()
        UsagePeriod.objects.create(
            owner=trial, key="trial-lifetime", is_trial=True, spent=Decimal("0.029")
        )
        with self.assertRaises(ValidationError):
            self.enqueue(owner=trial)

    def test_trial_and_paid_periods_are_separate(self):
        trial = account("trial", status="trialing")
        job = self.enqueue(owner=trial)
        trial.billing.status = "active"
        trial.billing.save()
        paid = self.enqueue(owner=trial)
        self.assertNotEqual(job.usage_period_id, paid.usage_period_id)
        self.assertFalse(paid.usage_period.is_trial)

    def test_ambiguous_result_holds_reservation_and_cannot_settle_twice(self):
        job = self.enqueue()
        job.status = "running"
        job.save()
        result = settle(job.pk)
        self.assertEqual(result.status, "uncertain")
        job.usage_period.refresh_from_db()
        self.assertEqual(job.usage_period.reserved, job.reservation)
        self.assertEqual(settle(job.pk, definitive=True, error="late").status, "uncertain")

    def test_actual_usage_settles_conservatively_and_release_remainder(self):
        job = self.enqueue()
        job.status = "running"
        job.save()
        payload = {
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "prompt_cache_hit_tokens": 200,
            },
            "model": "reported-flash-version",
            "choices": [{"finish_reason": "stop", "message": {"content": "Respuesta"}}],
        }
        job = settle(job.pk, payload)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.reported_model, "reported-flash-version")
        job.usage_period.refresh_from_db()
        self.assertEqual(job.usage_period.reserved, 0)
        self.assertEqual(job.usage_period.spent, Decimal("0.00036120"))

    def test_unexpected_usage_trips_circuit_breaker(self):
        job = self.enqueue()
        job.status = "running"
        job.save()
        settle(job.pk, {"usage": {"prompt_tokens": 999999, "completion_tokens": 100}})
        self.assertTrue(AIServiceState.objects.get().blocked)
        with self.assertRaises(ProviderUnavailable):
            self.enqueue()

    @patch("training.ai.httpx.Client")
    def test_worker_makes_one_call_and_timeout_is_not_retried(self, client):
        job = self.enqueue()
        client.return_value.__enter__.return_value.post.side_effect = httpx.ReadTimeout("timeout")
        self.assertTrue(process_one())
        self.assertFalse(process_one())
        self.assertEqual(client.return_value.__enter__.return_value.post.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "uncertain")

    def test_context_never_contains_another_accounts_data(self):
        from training.ai import context_snapshot
        from training.models import Goal

        other = account("private")
        Goal.objects.create(owner=other, title="Private goal", sport="running")
        context = context_snapshot(self.user)
        self.assertNotIn("Private goal", json.dumps(context))
        self.assertNotIn(other.email, json.dumps(context))

    @override_settings(AI_ENABLED=False)
    def test_disabled_provider_never_creates_jobs(self):
        with self.assertRaises(ProviderUnavailable):
            self.enqueue()
        self.assertFalse(AIJob.objects.exists())
