"""MAM-816 audit gaps: synthetic notifications and actual Django web flows, not LIVE."""

import json
from collections.abc import Mapping
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.billing import billing
from basis.modules.billing.adapters.models import BillingAccount, WebhookReceipt
from basis.modules.billing.adapters.polar import API_VERSION
from basis.modules.billing.adapters.recovery import process_pending
from basis.modules.billing.public import Checkout, ProviderUnavailable
from basis.shared.identifiers import AccountId
from tests.regression.factories import account
from tests.regression.test_billing_polar import ORG, PRODUCT, SECRET, product, signature, state


@override_settings(
    POLAR_PRODUCT_ID=PRODUCT,
    POLAR_ORGANIZATION_ID=ORG,
    POLAR_ACCESS_TOKEN="synthetic-not-a-credential",
    POLAR_WEBHOOK_SECRET=SECRET,
    POLAR_SANDBOX=True,
    PUBLIC_URL="https://basis.test",
)
class PolarAuditAcceptanceTests(TestCase):
    def setUp(self) -> None:
        # Fail closed if a test misses the injected requester seam.
        transport = patch(
            "basis.modules.billing.adapters.polar.httpx.Client",
            side_effect=AssertionError(
                "Unexpected provider transport in synthetic acceptance test"
            ),
        )
        transport.start()
        self.addCleanup(transport.stop)
        self.owner = account("polar-audit", status="inactive")
        self.other = account("polar-audit-other", status="inactive")
        self.public = self.owner.athlete.public_id
        self.customer = "customer-polar-audit"
        self.client.force_login(self.owner)

    def send(self, event_id: str, kind: str, **snapshot: object) -> int:
        data: dict[str, object] = {
            "customer_id": self.customer,
            "organization_id": ORG,
            "customer": {"external_id": str(self.public)},
        }
        data.update(snapshot)
        body = json.dumps({"api_version": API_VERSION, "type": kind, "data": data}).encode()
        return self.client.post(
            "/webhooks/polar/",
            data=body,
            content_type="application/json",
            headers=signature(body, event_id),
        ).status_code

    def test_renewal_notification_replaces_expired_period_from_customer_state_only(self) -> None:
        now = timezone.now()
        BillingAccount.objects.filter(owner=self.owner).update(
            status="active",
            period_start=now - timedelta(days=31),
            period_end=now - timedelta(days=1),
        )
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
        before_other = BillingAccount.objects.filter(owner=self.other).values().get()
        start, end = now - timedelta(hours=1), now + timedelta(days=30)
        authoritative = state(
            self.public,
            customer=self.customer,
            current_period_start=start.isoformat(),
            current_period_end=end.isoformat(),
        )
        with patch(
            "basis.modules.billing.adapters.actions.polar_request", return_value=authoritative
        ) as provider:
            self.assertEqual(
                self.send("renewal", "subscription.cycled", status="unpaid", amount=0), 202
            )
            provider.assert_not_called()
            self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
            process_pending()
        provider.assert_called_once_with("GET", f"customers/external/{self.public}/state")
        current = BillingAccount.objects.get(owner=self.owner)
        self.assertTrue(current.entitled)
        self.assertEqual((current.period_start, current.period_end), (start, end))
        self.assertEqual(current.status, "active")
        self.assertIsNotNone(WebhookReceipt.objects.get(event_id="renewal").processed_at)
        self.assertEqual(
            BillingAccount.objects.filter(owner=self.other).values().get(), before_other
        )

    def test_scheduled_cancellation_keeps_current_access_then_revocation_removes_it(self) -> None:
        end = timezone.now() + timedelta(days=3)
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            side_effect=[
                state(
                    self.public,
                    customer=self.customer,
                    cancel_at_period_end=True,
                    current_period_end=end.isoformat(),
                ),
                state(self.public, rows=[], customer=self.customer),
            ],
        ) as provider:
            self.assertEqual(self.send("scheduled", "subscription.canceled"), 202)
            process_pending()
            current = BillingAccount.objects.get(owner=self.owner)
            self.assertTrue(current.entitled)
            self.assertTrue(current.cancel_at_period_end)
            self.assertEqual(current.period_end, end)
            self.assertEqual(self.send("effective", "subscription.revoked"), 202)
            self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
            process_pending()
        self.assertEqual(provider.call_count, 2)
        current.refresh_from_db()
        self.assertFalse(current.entitled)
        self.assertEqual(current.status, "inactive")
        self.assertIsNone(current.period_end)
        self.assertEqual(WebhookReceipt.objects.filter(processed_at__isnull=False).count(), 2)

    def test_inverted_event_snapshots_and_replay_cannot_restore_revoked_access(self) -> None:
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            side_effect=[
                state(self.public, customer=self.customer),
                state(self.public, rows=[], customer=self.customer),
            ],
        ) as provider:
            # Delayed revoked notification after reactivation: current GET wins.
            self.assertEqual(
                self.send("old-revoked", "subscription.revoked", status="canceled"), 202
            )
            process_pending()
            self.assertTrue(BillingAccount.objects.get(owner=self.owner).entitled)
            # Delayed activation after effective revocation: current GET still wins.
            self.assertEqual(self.send("old-active", "subscription.active", status="active"), 202)
            process_pending()
            self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
            self.assertEqual(
                self.send("old-revoked", "subscription.revoked", status="canceled"), 200
            )
            process_pending()
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(WebhookReceipt.objects.count(), 2)
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)

    def test_nonpayment_notifications_cannot_grant_from_invoice_or_event_status(self) -> None:
        for i, status in enumerate(("past_due", "unpaid")):
            with self.subTest(status=status):
                BillingAccount.objects.filter(owner=self.owner).update(
                    status="active",
                    period_start=timezone.now() - timedelta(days=1),
                    period_end=timezone.now() + timedelta(days=29),
                    needs_reconciliation=False,
                )
                self.assertTrue(BillingAccount.objects.get(owner=self.owner).entitled)
                with patch(
                    "basis.modules.billing.adapters.actions.polar_request",
                    return_value=state(self.public, customer=self.customer, status=status),
                ) as provider:
                    self.assertEqual(
                        self.send(
                            f"nonpayment-{i}", "subscription.past_due", status="active", amount=None
                        ),
                        202,
                    )
                    self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
                    process_pending()
                provider.assert_called_once()
                self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
                self.assertIsNotNone(
                    WebhookReceipt.objects.get(event_id=f"nonpayment-{i}").processed_at
                )

    def test_checkout_web_ignores_client_purchase_fields_and_return_cannot_grant(self) -> None:
        calls: list[tuple[str, str, Mapping[str, object] | None]] = []

        def provider(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
            calls.append((method, path, json))
            if method == "GET":
                return product()
            return {
                "url": "https://sandbox.polar.sh/checkout/synthetic-audit",
                "expires_at": (timezone.now() + timedelta(minutes=20)).isoformat(),
            }

        with patch("basis.modules.billing.adapters.actions.polar_request", side_effect=provider):
            response = self.client.post(
                "/billing/checkout/",
                {
                    "owner": self.other.pk,
                    "external_customer_id": str(self.other.athlete.public_id),
                    "products": "foreign-product",
                    "price_id": "foreign-price",
                    "amount": "1",
                    "allow_trial": "false",
                    "return_url": "https://attacker.test",
                    "success_url": "https://attacker.test",
                },
            )
        self.assertRedirects(
            response,
            "https://sandbox.polar.sh/checkout/synthetic-audit",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            [(method, path) for method, path, _ in calls],
            [("GET", "products/" + PRODUCT), ("POST", "checkouts/")],
        )
        payload = calls[-1][2]
        assert payload is not None
        self.assertEqual(payload["products"], [PRODUCT])
        self.assertEqual(payload["external_customer_id"], str(self.public))
        self.assertEqual(payload["customer_email"], self.owner.email)
        self.assertIs(payload["allow_trial"], True)
        self.assertIs(payload["allow_discount_codes"], False)
        self.assertEqual(payload["return_url"], "https://basis.test/billing/")
        self.assertEqual(payload["success_url"], "https://basis.test/billing/?checkout=returned")
        self.assertNotIn("amount", payload)
        self.assertNotIn("price_id", payload)
        before = list(BillingAccount.objects.order_by("pk").values())
        with patch("basis.modules.billing.adapters.actions.polar_request") as external:
            self.assertEqual(
                self.client.get(
                    "/billing/?checkout=returned&status=active&paid=true&amount=500"
                ).status_code,
                200,
            )
        external.assert_not_called()
        self.assertEqual(list(BillingAccount.objects.order_by("pk").values()), before)
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
        self.assertFalse(BillingAccount.objects.get(owner=self.other).entitled)

    def test_checkout_rejects_wrong_currency_tax_price_and_trial_before_purchase(self) -> None:
        invalid: list[dict[str, object]] = [
            product(recurring_interval="year"),
            product(trial_interval="week"),
            product(trial_interval_count=6),
            product(is_archived=True),
        ]
        for field, value in (
            ("price_currency", "eur"),
            ("price_amount", 501),
            ("tax_behavior", "inclusive"),
            ("amount_type", "custom"),
        ):
            raw = product()
            prices = raw["prices"]
            assert isinstance(prices, list) and isinstance(prices[0], dict)
            prices[0][field] = value
            invalid.append(raw)
        for raw in invalid:
            # Explicit injection: bootstrap's default requester is not the web action seam.
            with (
                self.subTest(product=raw),
                patch(
                    "basis.modules.billing.adapters.actions.polar_request", return_value=raw
                ) as provider,
            ):
                with self.assertRaises(ProviderUnavailable):
                    billing(provider).checkout(Checkout(AccountId(self.owner.pk), self.owner.email))
                provider.assert_called_once_with("GET", "products/" + PRODUCT)
        self.assertIsNone(BillingAccount.objects.get(owner=self.owner).checkout_attempt)

    def test_checkout_portal_and_refresh_require_login_post_and_csrf(self) -> None:
        anonymous = Client(enforce_csrf_checks=True)
        login = anonymous.get("/accounts/login/")
        csrf = login.cookies["csrftoken"].value
        authenticated = Client(enforce_csrf_checks=True)
        authenticated.force_login(self.owner)
        with patch("basis.modules.billing.adapters.actions.polar_request") as provider:
            for action in ("checkout", "portal", "refresh"):
                path = f"/billing/{action}/"
                with self.subTest(action=action):
                    self.assertEqual(anonymous.get(path).status_code, 302)
                    self.assertEqual(
                        anonymous.post(path, {"csrfmiddlewaretoken": csrf}).status_code, 302
                    )
                    self.assertEqual(authenticated.get(path).status_code, 405)
                    self.assertEqual(authenticated.post(path).status_code, 403)
        provider.assert_not_called()

    def test_incomplete_configuration_disables_checkout_and_provider_network(self) -> None:
        for missing in ("POLAR_ACCESS_TOKEN", "POLAR_PRODUCT_ID", "POLAR_ORGANIZATION_ID"):
            with (
                self.subTest(missing=missing),
                override_settings(**{missing: ""}),
                patch("basis.modules.billing.adapters.polar.httpx.Client") as transport,
            ):
                page = self.client.get("/billing/")
                self.assertContains(page, "Las suscripciones todavía no están habilitadas.")
                self.assertNotContains(page, 'action="/billing/checkout/"')
                for action in ("checkout", "portal", "refresh"):
                    result = self.client.post(f"/billing/{action}/", follow=True)
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.redirect_chain, [("/billing/", 302)])
                    self.assertContains(
                        result,
                        "antes de continuar"
                        if missing == "POLAR_ORGANIZATION_ID"
                        else "no están configurados",
                    )
                transport.assert_not_called()
                self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
