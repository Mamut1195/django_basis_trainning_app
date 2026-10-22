"""MAM816: real cases and transactions, synthetic Polar responses, never LIVE."""

import base64
import hashlib
import hmac
import json
import threading
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from basis.bootstrap.billing import billing, webhooks
from basis.bootstrap.training import training
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.billing.adapters.models import BillingAccount, WebhookReceipt
from basis.modules.billing.adapters.polar import API_VERSION, PolarGateway, request
from basis.modules.billing.adapters.recovery import process_pending
from basis.modules.billing.adapters.webhook_wire import InvalidWebhook, decode_event
from basis.modules.billing.public import Checkout, OwnerBilling, ProviderUnavailable, WebhookEvent
from basis.modules.training.adapters.models import Session
from basis.modules.training.public import BlockData, RecordSession, SessionChanges
from basis.shared.identifiers import AccountId, Revision, SessionId
from tests.regression.factories import account

ORG = "10000000-0000-4000-8000-000000000001"
PRODUCT = "20000000-0000-4000-8000-000000000001"
SECRET_BYTES = b"synthetic-independent-mam816-signing-key"
SECRET = "whsec_" + base64.b64encode(SECRET_BYTES).decode()


def product(**changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "id": PRODUCT,
        "organization_id": ORG,
        "is_archived": False,
        "recurring_interval": "month",
        "recurring_interval_count": 1,
        "trial_interval": "day",
        "trial_interval_count": 7,
        "prices": [
            {
                "id": "30000000-0000-4000-8000-000000000001",
                "is_archived": False,
                "amount_type": "fixed",
                "price_amount": 500,
                "price_currency": "usd",
                "tax_behavior": "exclusive",
            }
        ],
    }
    result.update(changes)
    return result


def state(
    external: UUID,
    *,
    rows: list[dict[str, object]] | None = None,
    customer: str = "customer-polar",
    **changes: object,
) -> dict[str, object]:
    now = timezone.now()
    row: dict[str, object] = {
        "id": "subscription",
        "product_id": PRODUCT,
        "status": "active",
        "amount": 500,
        "current_period_start": (now - timedelta(days=1)).isoformat(),
        "current_period_end": (now + timedelta(days=29)).isoformat(),
        "trial_start": None,
        "trial_end": (now + timedelta(days=6)).isoformat(),
        "cancel_at_period_end": False,
    }
    row.update(changes)
    return {
        "id": customer,
        "organization_id": ORG,
        "external_id": str(external),
        "active_subscriptions": [row] if rows is None else rows,
    }


def signature(
    body: bytes, event_id: str, *, legacy: bool = False, offset: int = 0
) -> dict[str, str]:
    timestamp = str(int(timezone.now().timestamp()) + offset)
    key = SECRET.encode() if legacy else SECRET_BYTES
    digest = hmac.new(
        key, event_id.encode() + b"." + timestamp.encode() + b"." + body, hashlib.sha256
    ).digest()
    return {
        "webhook-id": event_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": "v1," + base64.b64encode(digest).decode(),
        "webhook-api-version": API_VERSION,
    }


@override_settings(
    POLAR_PRODUCT_ID=PRODUCT,
    POLAR_ORGANIZATION_ID=ORG,
    POLAR_ACCESS_TOKEN="synthetic-not-a-credential",
    POLAR_WEBHOOK_SECRET=SECRET,
)
class PolarAcceptanceTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("polar", status="inactive")
        self.other = account("foreign-polar", status="inactive")
        self.public = self.owner.athlete.public_id
        self.client.force_login(self.owner)

    def send(self, event_id: str, kind: str, data: dict[str, object], *, bad: bool = False) -> int:
        body = json.dumps({"api_version": API_VERSION, "type": kind, "data": data}).encode()
        headers = signature(body, event_id)
        if bad:
            headers["webhook-signature"] = "v1," + base64.b64encode(b"x" * 32).decode()
        return self.client.post(
            "/webhooks/polar/",
            data=body,
            content_type="application/json",
            HTTP_WEBHOOK_ID=headers["webhook-id"],
            HTTP_WEBHOOK_TIMESTAMP=headers["webhook-timestamp"],
            HTTP_WEBHOOK_SIGNATURE=headers["webhook-signature"],
            HTTP_WEBHOOK_API_VERSION=headers["webhook-api-version"],
        ).status_code

    def test_native_product_policy_rejects_month_count_zero_missing_and_bad_prices(self) -> None:
        from basis.modules.billing.domain.records import validate_product

        valid = product()
        cases = [
            product(recurring_interval_count=3),
            product(recurring_interval_count=None),
            product(recurring_interval_count=True),
            product(trial_interval_count=0),
        ]
        for amount in (0, None, "500", True):
            cases.append(
                product(
                    prices=[
                        {
                            "amount_type": "fixed",
                            "price_amount": amount,
                            "price_currency": "usd",
                            "tax_behavior": "exclusive",
                        }
                    ]
                )
            )
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ProviderUnavailable):
                validate_product(
                    PolarGateway(
                        lambda *a, **kw: raw, PRODUCT, "https://basis.test", True, ORG
                    ).product(),
                    False,
                )
        validate_product(
            PolarGateway(
                lambda *a, **kw: valid, PRODUCT, "https://basis.test", True, ORG
            ).product(),
            False,
        )

    def test_current_eligible_selection_cannot_be_shadowed_or_reset_by_timezone(self) -> None:
        service = billing()
        base = state(self.public, customer="customer-polar")
        row = dict(
            id="eligible",
            product_id=PRODUCT,
            status="active",
            current_period_start=(timezone.now() - timedelta(days=1)).isoformat(),
            current_period_end=(timezone.now() + timedelta(days=10)).isoformat(),
        )
        future = dict(
            row,
            id="future",
            current_period_start=(timezone.now() + timedelta(days=20)).isoformat(),
            current_period_end=(timezone.now() + timedelta(days=40)).isoformat(),
        )
        expired = dict(
            row, id="expired", current_period_end=(timezone.now() - timedelta(days=1)).isoformat()
        )
        base["active_subscriptions"] = [future, expired, row]
        with patch.object(service.gateway, "requester", return_value=base):
            current = service.reconcile(OwnerBilling(AccountId(self.owner.pk)))
        self.assertEqual(current.subscription_id, "eligible")
        self.assertEqual(
            current.period_start.utcoffset() if current.period_start else None, timedelta()
        )
        for invalid in ("2026-02-30T00:00:00Z", "2026-11-01T00:00:00", "garbage"):
            with patch.object(
                service.gateway,
                "requester",
                return_value=state(self.public, current_period_end=invalid),
            ):
                with self.assertRaises(ProviderUnavailable):
                    service.reconcile(OwnerBilling(AccountId(self.owner.pk)))

        for missing in (None, 0, "", "x" * 101):
            with patch.object(
                service.gateway, "requester", return_value=state(self.public, id=missing)
            ):
                with self.assertRaises(ProviderUnavailable):
                    service.reconcile(OwnerBilling(AccountId(self.owner.pk)))

    def test_authoritative_ends_at_bounds_active_and_trial_before_selection(self) -> None:
        service = billing()
        now = timezone.now()
        owner = OwnerBilling(AccountId(self.owner.pk))
        for status in ("active", "trialing"):
            for end in (now - timedelta(seconds=1), now, now + timedelta(hours=1)):
                with patch.object(
                    service.gateway,
                    "requester",
                    return_value=state(self.public, status=status, ends_at=end.isoformat()),
                ):
                    result = service.reconcile(owner)
                self.assertEqual(service.can_write(owner.owner), end > now)
                self.assertEqual(result.period_end, end if end > now else None)
            for invalid in ("bad", "2026-10-21T12:00:00", "2026-02-30T00:00:00Z"):
                with patch.object(
                    service.gateway,
                    "requester",
                    return_value=state(self.public, status=status, ends_at=invalid),
                ):
                    with self.assertRaises(ProviderUnavailable):
                        service.reconcile(owner)
        valid: dict[str, object] = {
            "id": "subscription",
            "product_id": PRODUCT,
            "status": "active",
            "current_period_start": (now - timedelta(days=1)).isoformat(),
            "current_period_end": (now + timedelta(days=29)).isoformat(),
        }
        ended = dict(valid, id="ended", ends_at=(now - timedelta(seconds=1)).isoformat())
        with patch.object(
            service.gateway, "requester", return_value=state(self.public, rows=[ended, valid])
        ):
            self.assertEqual(service.reconcile(owner).subscription_id, "subscription")

    def test_checkout_intent_cache_context_and_ambiguous_post(self) -> None:
        fixed = product()
        calls: list[tuple[str, str, Mapping[str, object] | None]] = []

        def provider(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
            calls.append((method, path, json))
            if method == "GET":
                return fixed
            return {
                "url": "https://sandbox.polar.sh/checkout/opaque",
                "expires_at": (timezone.now() + timedelta(minutes=45)).isoformat(),
            }

        service = billing(provider)
        command = Checkout(AccountId(self.owner.pk), self.owner.email)
        self.assertEqual(service.checkout(command), service.checkout(command))
        self.assertEqual(sum(m == "POST" for m, _, _ in calls), 1)
        row = BillingAccount.objects.get(owner=self.owner)
        self.assertIsNotNone(row.checkout_attempt)
        assert row.checkout_expires_at is not None
        self.assertLessEqual(row.checkout_expires_at, timezone.now() + timedelta(minutes=30))
        row.trial_used = True
        row.save()
        service.checkout(command)
        self.assertEqual(sum(m == "POST" for m, _, _ in calls), 2)
        self.assertFalse(calls[-1][2]["allow_trial"] if calls[-1][2] else True)
        BillingAccount.objects.filter(owner=self.owner).update(
            checkout_url="", checkout_attempt=None
        )

        def timeout(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
            if method == "GET":
                return fixed
            raise ProviderUnavailable("no provider content exposed")

        with self.assertRaises(ProviderUnavailable):
            billing(timeout).checkout(command)
        row.refresh_from_db()
        self.assertTrue(row.needs_reconciliation)
        self.assertIsNotNone(row.checkout_attempt)
        with patch.object(service.gateway, "checkout") as post:
            with self.assertRaises(ProviderUnavailable):
                service.checkout(command)
        post.assert_not_called()

    def test_refund_customer_id_only_uses_bound_identity_and_current_state(self) -> None:
        row = BillingAccount.objects.get(owner=self.owner)
        row.polar_customer_id = "bound-customer"
        row.save()
        refund: dict[str, object] = {
            "id": "refund",
            "organization_id": ORG,
            "customer_id": "bound-customer",
            "order_id": "order",
            "status": "succeeded",
            "amount": 500,
        }
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            return_value=state(self.public, customer="bound-customer"),
        ) as provider:
            for amount in (100, 500):
                refund["amount"] = amount
                self.assertEqual(self.send("refund-" + str(amount), "refund.updated", refund), 202)
                self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
                process_pending()
                self.assertTrue(BillingAccount.objects.get(owner=self.owner).entitled)
            self.assertEqual(provider.call_count, 2)
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            return_value=state(self.public, rows=[], customer="bound-customer"),
        ):
            self.send(
                "cancel",
                "subscription.revoked",
                {"customer_id": "bound-customer", "organization_id": ORG},
            )
            process_pending()
            self.send("old-refund", "refund.updated", refund)
            process_pending()
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)

    def test_wrong_org_customer_and_external_id_never_grant(self) -> None:
        row = BillingAccount.objects.get(owner=self.owner)
        row.polar_customer_id = "bound-customer"
        row.save()
        with patch("basis.modules.billing.adapters.actions.polar_request") as provider:
            cases: list[dict[str, object]] = [
                {"customer_id": "bound-customer", "organization_id": "foreign"},
                {
                    "customer_id": "bound-customer",
                    "organization_id": ORG,
                    "customer": {"external_id": str(self.other.athlete.public_id)},
                },
                {"customer_id": "unknown", "organization_id": ORG},
            ]
            for i, data in enumerate(cases):
                self.assertEqual(self.send("unlinked-" + str(i), "refund.updated", data), 202)
            process_pending()
        provider.assert_not_called()
        self.assertFalse(BillingAccount.objects.get(owner=self.other).entitled)
        self.assertTrue(WebhookReceipt.objects.filter(processed_at__isnull=True).exists())

    def test_raw_signature_full_headers_timestamp_rotation_and_secret_modes(self) -> None:
        body = b'{ "api_version":"2026-10", "type":"customer.state_changed", "data":{} }'
        headers = signature(body, "independent")
        self.assertEqual(
            decode_event(SECRET, body, headers, expected_version=API_VERSION).id, "independent"
        )
        for offset in (-360, 360):
            with self.assertRaises(InvalidWebhook):
                decode_event(SECRET, body, signature(body, "independent", offset=offset))
        with self.assertRaises(InvalidWebhook):
            decode_event(SECRET, body.replace(b"{ ", b"{", 1), headers)
        wrong = "v1," + base64.b64encode(b"x" * 32).decode()
        rotated = dict(headers, **{"webhook-signature": wrong + " " + headers["webhook-signature"]})
        decode_event(SECRET, body, rotated)
        with self.assertRaises(InvalidWebhook):
            decode_event(SECRET, body, signature(body, "legacy", legacy=True))
        decode_event(SECRET, body, signature(body, "legacy", legacy=True), secret_format="legacy")
        with self.assertRaises(InvalidWebhook):
            decode_event(SECRET, body, headers, secret_format="legacy")
        with self.assertRaises(InvalidWebhook):
            decode_event(
                SECRET,
                body,
                dict(headers, **{"webhook-api-version": "2027-01"}),
                expected_version=API_VERSION,
            )
        with patch("basis.modules.billing.adapters.actions.polar_request") as provider:
            self.assertEqual(
                self.send(
                    "bad", "customer.state_changed", {"external_id": str(self.public)}, bad=True
                ),
                400,
            )
        self.assertFalse(WebhookReceipt.objects.exists())
        provider.assert_not_called()

    def test_past_due_replay_order_recovery_and_generic_retry_metrics(self) -> None:
        data: dict[str, object] = {
            "external_id": str(self.public),
            "organization_id": ORG,
            "id": "customer-polar",
        }
        row = BillingAccount.objects.get(owner=self.owner)
        row.polar_customer_id = "customer-polar"
        row.save()
        responses = [
            state(self.public),
            state(self.public, rows=[]),
            state(self.public, rows=[]),
            state(self.public),
        ]
        with patch(
            "basis.modules.billing.adapters.actions.polar_request", side_effect=responses
        ) as provider:
            for i in range(4):
                self.send(str(i), "customer.state_changed", data)
                process_pending()
            self.assertEqual(self.send("1", "customer.state_changed", data), 200)
            self.assertEqual(provider.call_count, 4)
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            side_effect=ProviderUnavailable("sensitive-body"),
        ):
            self.send(
                "past-due",
                "subscription.past_due",
                {"customer_id": "customer-polar", "organization_id": ORG},
            )
            process_pending()
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)
        receipt = WebhookReceipt.objects.get(event_id="past-due")
        self.assertEqual(receipt.error_code, "reconciliation_pending")
        self.assertNotIn("sensitive", receipt.error_code)
        self.assertIsNotNone(receipt.retry_at)

    def test_portal_verified_owner_csrf_return_and_redirect_never_grants(self) -> None:
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            return_value={"customer_portal_url": "https://sandbox.polar.sh/portal"},
        ) as provider:
            response = self.client.post(
                "/billing/portal/",
                {
                    "external_customer_id": str(self.other.athlete.public_id),
                    "return_url": "https://attacker.test",
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                provider.call_args.kwargs["json"]["external_customer_id"], str(self.public)
            )
        Athlete.objects.filter(account=self.owner).update(email_verified=False)
        with patch("basis.modules.billing.adapters.actions.polar_request") as provider:
            self.assertEqual(self.client.post("/billing/portal/").status_code, 302)
            self.assertEqual(self.client.post("/billing/checkout/").status_code, 302)
            self.assertEqual(
                self.client.get("/billing/?checkout=returned&status=paid").status_code, 200
            )
        provider.assert_not_called()
        self.assertFalse(BillingAccount.objects.get(owner=self.owner).entitled)

    def test_mocktransport_requests_match_public_schema_projection_and_version(self) -> None:
        contract = json.loads(
            (Path(__file__).parents[1] / "fixtures/polar_2026_10_contract.json").read_text()
        )
        captured: list[httpx.Request] = []

        def respond(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            if req.url.path.endswith("checkouts/"):
                payload = {
                    "url": "https://sandbox.polar.sh/checkout",
                    "expires_at": (timezone.now() + timedelta(minutes=30)).isoformat(),
                }
            else:
                payload = {"customer_portal_url": "https://sandbox.polar.sh/portal"}
            return httpx.Response(201, headers={"Polar-Version": API_VERSION}, json=payload)

        original = httpx.Client
        with patch(
            "basis.modules.billing.adapters.polar.httpx.Client",
            side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
        ):
            gateway = PolarGateway(
                lambda method, path, **kw: request(
                    method, path, token="synthetic", product_id=PRODUCT, sandbox=True, **kw
                ),
                PRODUCT,
                "https://basis.test",
                True,
                ORG,
            )
            gateway.checkout(self.public, self.owner.email, True, uuid4())
            gateway.portal(self.public)
        types = {"array": list, "string": str, "boolean": bool, "object": dict}
        for req, key in zip(captured, ("checkout", "portal"), strict=True):
            payload = json.loads(req.content)
            spec = contract[key]
            self.assertTrue(set(spec["required"]) <= payload.keys())
            self.assertTrue(payload.keys() <= spec["types"].keys())
            for name, value in payload.items():
                self.assertIsInstance(value, types[spec["types"][name]])
            self.assertEqual(req.headers["Polar-Version"], API_VERSION)
            self.assertEqual(req.url.host, "sandbox-api.polar.sh")

    def test_cache_revalidates_environment_product_origin_and_period(self) -> None:
        fixed = product()

        def provider(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
            if method == "GET":
                return fixed
            return {
                "url": "https://sandbox.polar.sh/checkout",
                "expires_at": (timezone.now() + timedelta(minutes=20)).isoformat(),
            }

        command = Checkout(AccountId(self.owner.pk), self.owner.email)
        original = billing(provider).checkout(command)
        for changes in ({"POLAR_SANDBOX": False}, {"PUBLIC_URL": "https://other.test"}):
            with (
                override_settings(**changes),
                patch(
                    "basis.modules.billing.adapters.actions.polar_request",
                    side_effect=ProviderUnavailable("configuration switch"),
                ),
            ):
                with self.assertRaises(ProviderUnavailable):
                    billing().checkout(command)
        with patch(
            "basis.modules.billing.adapters.actions.polar_request",
            return_value=product(id="wrong-product"),
        ):
            with self.assertRaises(ProviderUnavailable):
                billing().checkout(command)
        self.assertEqual(billing(provider).checkout(command), original)

    def test_strict_redirect_origins_and_legacy_price_periods(self) -> None:
        from basis.modules.billing.adapters.polar import safe_provider_url

        for url in (
            "https://user@polar.sh/x",
            "https://polar.sh:444/x",
            "https://api.polar.sh/x",
            "https://polar.sh.attacker.test/x",
            "https://[broken",
            "https://polar.sh:bad/x",
        ):
            with self.subTest(url=url), self.assertRaises(ProviderUnavailable):
                safe_provider_url(url, False)
        with self.assertRaises(ProviderUnavailable):
            safe_provider_url("https://polar.sh/checkout", True)
        with self.assertRaises(ProviderUnavailable):
            safe_provider_url("https://sandbox.polar.sh/checkout", False)
        bad = product(
            prices=[
                {
                    "amount_type": "fixed",
                    "price_amount": 500,
                    "price_currency": "usd",
                    "tax_behavior": "exclusive",
                    "recurring_interval": "year",
                }
            ]
        )
        with self.assertRaises(ProviderUnavailable):
            PolarGateway(lambda *a, **kw: bad, PRODUCT, "https://basis.test", True, ORG).product()
        with patch("basis.modules.billing.adapters.actions.polar_request") as provider:
            with override_settings(PUBLIC_URL="https://user@basis.test/"):
                with self.assertRaises(ProviderUnavailable):
                    billing().portal(OwnerBilling(AccountId(self.owner.pk)))
        provider.assert_not_called()

    def test_get_state_lifecycle_and_monotonic_trial_history(self) -> None:
        service = billing()
        owner = OwnerBilling(AccountId(self.owner.pk))
        cases: list[tuple[dict[str, object], bool]] = [
            (state(self.public, status="trialing"), True),
            (
                state(self.public, trial_start=(timezone.now() - timedelta(days=8)).isoformat()),
                True,
            ),
            (state(self.public, cancel_at_period_end=True), True),
            (state(self.public, status="trialing", trial_end=timezone.now().isoformat()), False),
            (state(self.public, status="unpaid"), False),
            (state(self.public, status=None), False),
            (state(self.public, status=0), False),
            (state(self.public, product_id="foreign-sku"), False),
            (state(self.public, rows=[]), False),
        ]
        for raw, expected in cases:
            with patch.object(service.gateway, "requester", return_value=raw):
                current = service.reconcile(owner)
            self.assertEqual(billing().can_write(owner.owner), expected)
            self.assertTrue(current.trial_used)


class PolarUpgradeTests(TransactionTestCase):
    def test_billing_upgrade_preserves_identity_period_history_and_receipts(self) -> None:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([("basis_billing", "0001_initial")])
        try:
            old = executor.loader.project_state([("basis_billing", "0001_initial")]).apps
            owner = old.get_model("auth", "User").objects.create(username="billing-upgrade")
            start = timezone.now() - timedelta(days=1)
            end = timezone.now() + timedelta(days=6)
            row = old.get_model("basis_billing", "BillingAccount").objects.create(
                owner_id=owner.pk,
                polar_customer_id="upgrade-customer",
                subscription_id="upgrade-sub",
                trial_used=True,
                status="trialing",
                period_start=start,
                period_end=end,
                needs_reconciliation=True,
                checkout_url="https://sandbox.polar.sh/legacy-cache",
                checkout_expires_at=end,
            )
            receipt = old.get_model("basis_billing", "WebhookReceipt").objects.create(
                event_id="upgrade-event", event_type="refund.updated"
            )
            keys = (row.pk, owner.pk, receipt.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
        restored = BillingAccount.objects.get(pk=keys[0])
        self.assertEqual(
            (restored.owner_id, restored.polar_customer_id, restored.subscription_id),
            (keys[1], "upgrade-customer", "upgrade-sub"),
        )
        self.assertEqual((restored.period_start, restored.period_end), (start, end))
        self.assertTrue(restored.trial_used and restored.needs_reconciliation)
        self.assertEqual(restored.checkout_context, "")
        self.assertIsNone(restored.checkout_attempt)
        pending = WebhookReceipt.objects.get(pk=keys[2])
        self.assertEqual((pending.event_id, pending.attempts), ("upgrade-event", 0))
        self.assertIsNone(pending.processed_at)


@override_settings(POLAR_PRODUCT_ID=PRODUCT, POLAR_ORGANIZATION_ID=ORG)
class PolarSerializationTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_checkout_has_one_committed_intent_and_one_post(self) -> None:
        user = account("checkout-race", status="inactive")
        owner = AccountId(user.pk)
        entered, release, done = (threading.Event() for _ in range(3))
        fixed = product()
        results: list[str] = []
        failures: list[BaseException] = []
        posts: list[object] = []

        def provider(method: str, path: str, *, json: Mapping[str, object] | None = None) -> object:
            if method == "GET":
                return fixed
            posts.append(json)
            entered.set()
            if not release.wait(10):
                raise RuntimeError("checkout release timeout")
            return {
                "url": "https://sandbox.polar.sh/checkout/race",
                "expires_at": (timezone.now() + timedelta(minutes=30)).isoformat(),
            }

        def checkout(second: bool) -> None:
            try:
                results.append(billing(provider).checkout(Checkout(owner, user.email)))
            except BaseException as exc:
                failures.append(exc)
            finally:
                connections.close_all()
                if second:
                    done.set()

        first = threading.Thread(target=checkout, args=(False,))
        second = threading.Thread(target=checkout, args=(True,))
        first.start()
        try:
            self.assertTrue(entered.wait(10))
            second.start()
            self.assertFalse(done.wait(0.25))
        finally:
            release.set()
            first.join(15)
            if second.ident is not None:
                second.join(15)
        self.assertEqual(failures, [])
        self.assertEqual(len(posts), 1)
        self.assertEqual(results, ["https://sandbox.polar.sh/checkout/race"] * 2)

    @skipUnlessDBFeature("has_select_for_update")
    def test_protected_write_commits_before_revocation_waiting_on_same_account(self) -> None:
        self.run_race(revoke_first=False)

    @skipUnlessDBFeature("has_select_for_update")
    def test_revocation_commits_before_waiting_guard_and_write_is_denied(self) -> None:
        self.run_race(revoke_first=True)

    def run_race(self, *, revoke_first: bool) -> None:
        user = account("polar-race")
        owner = AccountId(user.pk)
        entered, release, second_started, second_finished = (threading.Event() for _ in range(4))
        errors: list[BaseException] = []
        denied: list[bool] = []
        session = SessionId(uuid4())
        public = user.athlete.public_id

        def writer() -> None:
            try:
                service = training()

                def changes() -> SessionChanges:
                    if not revoke_first:
                        entered.set()
                        if not release.wait(10):
                            raise RuntimeError("writer release timeout")
                    return SessionChanges((BlockData("running", title="Actual guarded write"),))

                if revoke_first:
                    second_started.set()
                service.record_from(
                    RecordSession(owner, session, Revision(0), SessionChanges(())), changes
                )
            except PermissionDenied:
                denied.append(True)
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()
                if revoke_first:
                    second_finished.set()

        def revoke() -> None:
            try:

                def provider(
                    method: str, path: str, *, json: Mapping[str, object] | None = None
                ) -> object:
                    if revoke_first:
                        entered.set()
                        if not release.wait(10):
                            raise RuntimeError("revoker release timeout")
                    return state(public, rows=[], customer="customer-polar-race")

                if not revoke_first:
                    second_started.set()
                result = webhooks(provider).process(
                    WebhookEvent("race", "customer.state_changed", str(public))
                )
                if result.outcome != "processed":
                    raise RuntimeError(result.outcome)
            except BaseException as exc:
                errors.append(exc)
            finally:
                connections.close_all()
                if not revoke_first:
                    second_finished.set()

        first = threading.Thread(target=revoke if revoke_first else writer)
        second = threading.Thread(target=writer if revoke_first else revoke)
        first.start()
        try:
            self.assertTrue(entered.wait(10))
            second.start()
            self.assertTrue(second_started.wait(5))
            self.assertFalse(
                second_finished.wait(0.25), "second operation bypassed shared account lock"
            )
        finally:
            release.set()
            first.join(15)
            if second.ident is not None:
                second.join(15)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(denied, [True] if revoke_first else [])
        self.assertEqual(Session.objects.filter(pk=session).exists(), not revoke_first)
        self.assertFalse(BillingAccount.objects.get(owner=user).entitled)
