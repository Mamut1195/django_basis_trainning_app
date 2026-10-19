"""Polar wire contracts use injected requesters and HTTPX MockTransport only."""

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

import httpx
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from basis.shared.identifiers import AccountId

from ..domain.records import BillingState, ProviderUnavailable, reconcile_state
from .polar import PolarGateway, request, safe_provider_url


class FakeRequester:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[str, str, Mapping[str, object] | None]] = []

    def __call__(
        self, method: str, path: str, *, json: Mapping[str, object] | None = None
    ) -> object:
        self.calls.append((method, path, json))
        return self.response


class PolarContracts(SimpleTestCase):
    def setUp(self) -> None:
        self.public_id = UUID("12345678-1234-1234-1234-123456789012")

    def test_checkout_payload_is_server_owned_and_default_expiry_is_thirty_minutes(self) -> None:
        requester = FakeRequester({"url": "https://sandbox.polar.sh/checkout"})
        gateway = PolarGateway(requester, "approved", "https://basis.test")
        before = timezone.now()
        link = gateway.checkout(self.public_id, "athlete@example.test", False)
        self.assertEqual(requester.calls, [("POST", "checkouts/", {
            "products": ["approved"], "external_customer_id": str(self.public_id),
            "customer_email": "athlete@example.test", "allow_trial": False,
            "success_url": "https://basis.test/billing/?checkout=returned",
            "return_url": "https://basis.test/billing/",
        })])
        self.assertIsNotNone(link.expires_at)
        assert link.expires_at is not None
        self.assertGreaterEqual(link.expires_at, before + timedelta(minutes=30))
        self.assertLessEqual(link.expires_at, timezone.now() + timedelta(minutes=30))

    def test_invalid_expiry_remains_absent_and_portal_payload_is_exact(self) -> None:
        requester = FakeRequester({"url": "https://polar.sh/x", "expires_at": "invalid"})
        gateway = PolarGateway(requester, "approved", "https://basis.test")
        self.assertIsNone(gateway.checkout(self.public_id, "a@test", True).expires_at)
        requester.response = {"customer_portal_url": "https://polar.sh/portal"}
        self.assertEqual(gateway.portal(self.public_id), "https://polar.sh/portal")
        self.assertEqual(requester.calls[-1], ("POST", "customer-sessions/", {
            "external_customer_id": str(self.public_id), "return_url": "https://basis.test/billing/",
        }))

    def test_url_allowlist_rejects_external_insecure_and_suffix_lookalikes(self) -> None:
        for url in ("", "http://polar.sh/x", "https://polar.sh.attacker.test", "//polar.sh/x"):
            with self.subTest(url=url), self.assertRaises(ProviderUnavailable):
                safe_provider_url(url)
        self.assertEqual(safe_provider_url("https://checkout.polar.sh/x"), "https://checkout.polar.sh/x")

    def test_numeric_strings_are_not_accepted_as_price_or_trial_counts(self) -> None:
        requester = FakeRequester({"prices": [{"price_amount": "500"}], "trial_interval_count": "7"})
        gateway = PolarGateway(requester, "approved", "https://basis.test")
        self.assertIsNone(gateway.product().prices[0].amount_cents)
        self.assertIsNone(gateway.product().trial_days)
        requester.response = {"prices": [{"price_amount": 500.0}], "trial_interval_count": 7}
        self.assertEqual(gateway.product().prices[0].amount_cents, Decimal(500))
        self.assertEqual(gateway.product().trial_days, Decimal(7))

    def test_customer_conversion_preserves_raw_period_order_and_trial_history(self) -> None:
        end = "2026-11-01T00:00:00+02:00"
        requester = FakeRequester({"id": "customer", "external_id": str(self.public_id),
            "active_subscriptions": [{"id": "subscription", "product_id": "approved", "status": "active", "current_period_end": end,
                "trial_start": "first-trial", "cancel_at_period_end": True},
                {"id": "later-instant", "product_id": "approved", "status": "active", "current_period_end": "2026-10-31T23:00:00+00:00"}]})
        gateway = PolarGateway(requester, "approved", "https://basis.test")
        subscription = gateway.customer(self.public_id).subscriptions[0]
        self.assertEqual(subscription.period_end_key, end)
        self.assertTrue(subscription.trial_started)
        self.assertTrue(subscription.cancel_at_period_end)
        selected = reconcile_state(BillingState(AccountId(1)), gateway.customer(self.public_id), str(self.public_id), "approved", timezone.now())
        self.assertEqual(selected.subscription_id, "subscription")
        self.assertEqual(requester.calls[0][1], "customers/external/" + str(self.public_id) + "/state")

    def test_only_selected_subscription_relevant_calendar_errors_are_raised(self) -> None:
        requester = FakeRequester({"id": "customer", "external_id": str(self.public_id),
            "active_subscriptions": [
                {"product_id": "foreign", "status": "active", "current_period_start": "2026-02-30T00:00:00+00:00"},
                {"product_id": "approved", "status": "active", "current_period_end": "2026-11-01",
                    "trial_end": "2026-02-30T00:00:00+00:00"},
            ]})
        gateway = PolarGateway(requester, "approved", "https://basis.test")
        current = BillingState(AccountId(1))
        result = reconcile_state(current, gateway.customer(self.public_id), str(self.public_id), "approved", timezone.now())
        self.assertEqual(result.status, "active")
        requester.response = {"id": "customer", "external_id": str(self.public_id),
            "active_subscriptions": [{"product_id": "approved", "status": "active", "current_period_end": "2026-02-30T00:00:00+00:00"}]}
        with self.assertRaises(ValueError):
            reconcile_state(current, gateway.customer(self.public_id), str(self.public_id), "approved", timezone.now())

    def test_malformed_provider_payloads_are_rejected(self) -> None:
        responses: tuple[object, ...] = (None, [], {"prices": None}, {"prices": [False]})
        for response in responses:
            with self.subTest(response=response), self.assertRaises(ProviderUnavailable):
                PolarGateway(FakeRequester(response), "approved", "https://basis.test").product()

    def test_http_transport_has_bounded_timeout_and_no_retry_or_sensitive_error(self) -> None:
        seen: list[httpx.Request] = []
        def fail(req: httpx.Request) -> httpx.Response:
            seen.append(req)
            return httpx.Response(503, text="private-provider-response")
        client = httpx.Client(transport=httpx.MockTransport(fail), timeout=20)
        with patch("basis.modules.billing.adapters.polar.httpx.Client", return_value=client) as factory:
            with self.assertRaises(ProviderUnavailable) as caught:
                request("GET", "products/approved", token="not-a-credential", product_id="approved", sandbox=True)
        factory.assert_called_once_with(timeout=20)
        self.assertEqual(len(seen), 1)
        self.assertEqual(str(seen[0].url), "https://sandbox-api.polar.sh/v1/products/approved")
        self.assertNotIn("private-provider-response", str(caught.exception))
        self.assertNotIn("not-a-credential", str(caught.exception))

    @override_settings(POLAR_ACCESS_TOKEN="", POLAR_PRODUCT_ID="")
    def test_unconfigured_transport_never_opens_a_connection(self) -> None:
        with patch("basis.modules.billing.adapters.polar.httpx.Client") as factory:
            with self.assertRaises(ProviderUnavailable):
                request("GET", "products/x", token="", product_id="", sandbox=True)
        factory.assert_not_called()
