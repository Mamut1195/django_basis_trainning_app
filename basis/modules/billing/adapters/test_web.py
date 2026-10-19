"""Signed delivery, durable failure/retry and operational reconciliation contracts."""

import base64
import json
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from standardwebhooks.webhooks import Webhook

from daily_trainning_app.models import User as Athlete
from training.billing import ProviderUnavailable
from training.models import BillingAccount, WebhookReceipt


@override_settings(
    POLAR_PRODUCT_ID="approved", POLAR_ACCESS_TOKEN="not-a-credential",
    POLAR_WEBHOOK_SECRET="whsec_" + base64.b64encode(b"basis-test-signature-only").decode(),
)
class BillingWebContracts(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="billing-web", email="athlete@example.test")
        self.profile = Athlete.objects.create(
            account=self.user, nombre="billing", email=self.user.email,
            fecha_inicio=timezone.localdate(), email_verified=True, edad=25,
        )
        self.billing = BillingAccount.objects.create(owner=self.user)

    def send(self, event_id: str, external: str | None, kind: str = "customer.state_changed") -> int:
        data: dict[str, object] = {"external_id": external} if kind == "customer.state_changed" else {"customer": {"external_id": external}}
        body = json.dumps({"type": kind, "data": data})
        now = timezone.now()
        signature = Webhook(settings.POLAR_WEBHOOK_SECRET).sign(event_id, now, body)
        return self.client.post(
            "/webhooks/polar/", data=body, content_type="application/json",
            HTTP_WEBHOOK_ID=event_id, HTTP_WEBHOOK_TIMESTAMP=str(int(now.timestamp())),
            HTTP_WEBHOOK_SIGNATURE=signature,
        ).status_code

    def test_provider_failure_commits_pending_and_receipt_retry_then_replay_is_safe(self) -> None:
        with patch("training.billing.polar_request", side_effect=ProviderUnavailable("Unavailable")) as provider:
            self.assertEqual(self.send("retry", str(self.profile.public_id)), 503)
        self.assertEqual(provider.call_count, 1)
        self.billing.refresh_from_db()
        self.assertTrue(self.billing.needs_reconciliation)
        self.assertIsNone(WebhookReceipt.objects.get(event_id="retry").processed_at)
        with patch("training.billing.polar_request", return_value={
            "id": "customer", "external_id": str(self.profile.public_id), "active_subscriptions": [],
        }) as provider:
            self.assertEqual(self.send("retry", str(self.profile.public_id)), 200)
            self.assertEqual(self.send("retry", str(self.profile.public_id)), 200)
        self.assertEqual(provider.call_count, 1)
        self.billing.refresh_from_db()
        self.assertFalse(self.billing.needs_reconciliation)
        receipt = WebhookReceipt.objects.get(event_id="retry")
        self.assertIsNotNone(receipt.processed_at)
        self.assertEqual(receipt.customer_external_id, self.profile.public_id)

    def test_signed_unlinked_and_invalid_ids_are_422_with_unprocessed_receipt(self) -> None:
        with patch("training.billing.polar_request") as provider:
            for event_id, external in (("missing", str(uuid4())), ("invalid", "invalid")):
                self.assertEqual(self.send(event_id, external), 422)
                self.assertIsNone(WebhookReceipt.objects.get(event_id=event_id).processed_at)
        provider.assert_not_called()

    def test_unknown_kind_is_processed_without_resolving_customer_or_calling_provider(self) -> None:
        with patch("training.billing.polar_request") as provider:
            self.assertEqual(self.send("ignored", "invalid", "unrelated.event"), 200)
            self.assertEqual(self.send("ignored", None, "unrelated.event"), 200)
        provider.assert_not_called()
        self.assertIsNotNone(WebhookReceipt.objects.get(event_id="ignored").processed_at)

    def test_invalid_signature_and_unconfigured_webhook_create_no_receipt(self) -> None:
        self.assertEqual(self.client.post("/webhooks/polar/", data="{}", content_type="application/json").status_code, 400)
        with override_settings(POLAR_WEBHOOK_SECRET=""):
            self.assertEqual(self.client.post("/webhooks/polar/", data="{}", content_type="application/json").status_code, 503)
        self.assertFalse(WebhookReceipt.objects.exists())

    def test_reconcile_command_failure_keeps_pending_without_logging_provider_content(self) -> None:
        with patch("training.billing.polar_request", side_effect=ProviderUnavailable("private-response")):
            with self.assertRaises(CommandError) as caught:
                call_command("reconcile_billing", owner_id=self.user.pk, stdout=StringIO())
        self.billing.refresh_from_db()
        self.assertTrue(self.billing.needs_reconciliation)
        self.assertNotIn("private-response", str(caught.exception))

    def test_checkout_and_refresh_keep_login_csrf_and_redirect_contract(self) -> None:
        self.assertEqual(self.client.post("/billing/checkout/").status_code, 302)
        self.client.force_login(self.user)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post("/billing/portal/").status_code, 403)
        with patch("training.billing.polar_request", return_value={
            "customer_portal_url": "https://polar.sh/portal",
        }):
            response = self.client.post("/billing/portal/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://polar.sh/portal")
