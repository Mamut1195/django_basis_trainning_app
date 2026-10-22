"""Billing rules and orchestration run without Django, a database or a network."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import TracebackType
from unittest import TestCase
from uuid import UUID

from basis.modules.athletes.public import BillingProfile
from basis.modules.billing.application.service import (
    Billing,
    Checkout,
    OwnerBilling,
    WebhookEvent,
    Webhooks,
)
from basis.modules.billing.domain.records import (
    BillingState,
    CheckoutLink,
    CustomerState,
    Price,
    Product,
    ProviderUnavailable,
    Subscription,
    VerificationRequired,
    entitled,
    reconcile_state,
    validate_product,
)
from basis.shared.identifiers import AccountId
from tests_architecture.billing_contract import BillingContract

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
OWNER = AccountId(1)
PUBLIC = UUID(int=1)


class Clock:
    def now(self) -> datetime:
        return NOW

    def today(self) -> date:
        return NOW.date()


class Memory:
    def __init__(self) -> None:
        self.rows: dict[AccountId, BillingState] = {}
        self.receipts: dict[str, bool] = {}
        self.committed = False

    def __enter__(self) -> "Memory":
        self.before = self.rows.copy(), self.receipts.copy()
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.committed or exc_type is not None:
            self.rows, self.receipts = self.before

    def commit(self) -> None:
        self.committed = True

    def lock(self, owner: AccountId) -> BillingState:
        self.rows.setdefault(owner, BillingState(owner))
        return self.rows[owner]

    def get(self, owner: AccountId) -> BillingState | None:
        return self.rows.get(owner)

    def save(self, state: BillingState) -> None:
        self.rows[state.owner] = state

    def mark_pending(self, owner: AccountId) -> None:
        if owner in self.rows:
            self.rows[owner] = replace(self.rows[owner], needs_reconciliation=True)

    def owner_for_customer(self, customer_id: str) -> AccountId | None:
        return next(
            (owner for owner, state in self.rows.items() if state.customer_id == customer_id), None
        )

    def received(self, event: WebhookEvent) -> bool:
        self.receipts.setdefault(event.id, False)
        return self.receipts[event.id]

    def complete(self, event_id: str, now: datetime, public_id: UUID | None = None) -> None:
        self.receipts[event_id] = True


class Profiles:
    verified = True

    def get(self, owner: AccountId) -> BillingProfile | None:
        return BillingProfile(owner, PUBLIC, self.verified) if owner == OWNER else None

    def owner_for(self, public_id: UUID) -> AccountId | None:
        return OWNER if public_id == PUBLIC else None


class Gateway:
    fail = False
    calls = 0

    def product(self) -> Product:
        return Product(
            False,
            "month",
            (Price(False, Decimal(500), "usd", "exclusive", id="price"),),
            "day",
            Decimal(7),
            1,
        )

    def checkout(
        self, public_id: UUID, email: str, allow_trial: bool, attempt: UUID | None = None
    ) -> CheckoutLink:
        self.calls += 1
        return CheckoutLink("https://polar.sh/checkout", NOW + timedelta(minutes=30))

    def validate_link(self, url: str) -> str:
        return url

    def portal(self, public_id: UUID) -> str:
        return "https://polar.sh/portal"

    def customer(self, public_id: UUID) -> CustomerState:
        if self.fail:
            raise ProviderUnavailable("unavailable")
        return CustomerState("customer", str(public_id), (subscription(),))


def subscription() -> Subscription:
    return Subscription(
        "sub",
        "product",
        "active",
        NOW - timedelta(days=1),
        NOW + timedelta(days=1),
        "z",
        None,
        True,
        True,
    )


class MemoryBillingTests(BillingContract, TestCase):
    def test_read_provisioning_commits_without_verification_or_gateway(self) -> None:
        self.profiles.verified = False
        result = self.service.ensure(OwnerBilling(self.owner))
        self.assertEqual(result.owner, self.owner)
        self.assertEqual(self.gateway.calls, 0)
        self.assertTrue(self.memory.committed)

    def test_failure_mark_commits_without_provider_and_does_not_create_missing_account(
        self,
    ) -> None:
        self.service.mark_pending(OwnerBilling(OWNER))
        self.assertEqual(self.memory.rows, {})
        self.service.ensure(OwnerBilling(OWNER))
        self.service.mark_pending(OwnerBilling(OWNER))
        self.assertTrue(self.memory.rows[OWNER].needs_reconciliation)
        self.assertTrue(self.memory.committed)
        self.assertEqual(self.gateway.calls, 0)

    def setUp(self) -> None:
        self.memory = Memory()
        self.repository = self.memory
        self.owner, self.other = OWNER, AccountId(2)
        self.uow_factory = lambda: self.memory
        self.gateway = Gateway()
        self.profiles = Profiles()
        self.service = Billing(
            self.memory, self.profiles, self.gateway, self.uow_factory, Clock(), "product"
        )

    def test_access_inclusive_start_exclusive_end_and_pending(self) -> None:
        self.assertTrue(entitled("active", NOW, NOW + timedelta(seconds=1), False, NOW))
        self.assertFalse(entitled("trialing", NOW - timedelta(days=1), NOW, False, NOW))
        self.assertFalse(entitled("active", NOW, NOW + timedelta(days=1), True, NOW))
        self.assertFalse(entitled("active", None, NOW + timedelta(days=1), False, NOW))

    def test_checkout_cached_and_unverified_does_not_create_account(self) -> None:
        self.profiles.verified = False
        with self.assertRaises(VerificationRequired):
            self.service.checkout(Checkout(OWNER, "a@example.test"))
        self.assertEqual(self.memory.rows, {})
        self.profiles.verified = True
        self.assertEqual(
            self.service.checkout(Checkout(OWNER, "a@example.test")), "https://polar.sh/checkout"
        )
        self.service.checkout(Checkout(OWNER, "a@example.test"))
        self.assertEqual(self.gateway.calls, 1)
        self.assertFalse(self.memory.rows[OWNER].trial_used)

    def test_product_policy_and_trial_used_exception(self) -> None:
        valid = self.gateway.product()
        for product in (
            replace(valid, archived=True),
            replace(valid, recurring_interval="year"),
            replace(valid, prices=()),
            replace(valid, trial_days=Decimal(8)),
            replace(valid, prices=(Price(False, Decimal(500), "usd", "inclusive"),)),
        ):
            with self.assertRaises(ProviderUnavailable):
                validate_product(product, False)
        validate_product(replace(valid, trial_days=None), True)

    def test_reconcile_raw_order_product_scope_and_trial_history(self) -> None:
        chosen = subscription()
        earlier = replace(
            chosen, id="earlier", period_end_key="a", period_end=NOW + timedelta(days=100)
        )
        foreign = replace(chosen, id="foreign", product_id="foreign", period_end_key="zz")
        result = reconcile_state(
            BillingState(OWNER),
            CustomerState("customer", str(PUBLIC), (earlier, foreign, chosen)),
            str(PUBLIC),
            "product",
            NOW,
        )
        self.assertEqual(result.subscription_id, "earlier")
        self.assertTrue(result.trial_used)
        inactive = reconcile_state(
            result, CustomerState("customer", str(PUBLIC), ()), str(PUBLIC), "product", NOW
        )
        self.assertEqual(inactive.status, "inactive")
        self.assertTrue(inactive.trial_used)

    def test_identity_mismatch_rolls_back_new_account(self) -> None:
        with self.assertRaises(ProviderUnavailable):
            reconcile_state(
                BillingState(OWNER),
                CustomerState("customer", "wrong", ()),
                str(PUBLIC),
                "product",
                NOW,
            )
        self.gateway.fail = True
        with self.assertRaises(ProviderUnavailable):
            self.service.reconcile(OwnerBilling(OWNER))
        self.assertEqual(self.memory.rows, {})

    def test_invalid_dates_raise_only_for_selected_relevant_subscription(self) -> None:
        selected = subscription()
        ignored = replace(
            selected,
            id="older",
            product_id="foreign",
            period_end_key="a",
            invalid_period_start=True,
        )
        state = BillingState(OWNER)
        customer = CustomerState("customer", str(PUBLIC), (ignored, selected))
        self.assertEqual(
            reconcile_state(state, customer, str(PUBLIC), "product", NOW).subscription_id, "sub"
        )
        invalid = replace(selected, invalid_period_end=True)
        with self.assertRaises(ProviderUnavailable):
            reconcile_state(
                state, replace(customer, subscriptions=(invalid,)), str(PUBLIC), "product", NOW
            )
        # A trial uses trial_end, so an invalid unused regular period end is ignored.
        trial = replace(invalid, status="trialing", trial_end=NOW)
        self.assertEqual(
            reconcile_state(
                state, replace(customer, subscriptions=(trial,)), str(PUBLIC), "product", NOW
            ).period_end,
            None,
        )

    def test_webhook_failure_preserves_pending_receipt_and_retry_completes(self) -> None:
        self.memory.lock(OWNER)
        self.gateway.fail = True
        webhook = Webhooks(self.service, self.memory)
        event = WebhookEvent("event", "customer.state_changed", str(PUBLIC))
        self.assertEqual(webhook.process(event).outcome, "reconciliation_pending")
        self.assertTrue(self.memory.rows[OWNER].needs_reconciliation)
        self.assertFalse(self.memory.receipts["event"])
        self.gateway.fail = False
        self.assertEqual(webhook.process(event).outcome, "processed")
        self.assertFalse(self.memory.rows[OWNER].needs_reconciliation)
        self.assertTrue(self.memory.receipts["event"])
        self.gateway.fail = True
        self.assertEqual(webhook.process(event).outcome, "processed")

    def test_unknown_event_and_unlinked_identity(self) -> None:
        webhook = Webhooks(self.service, self.memory)
        self.assertEqual(
            webhook.process(WebhookEvent("unknown", "unknown", None)).outcome, "processed"
        )
        self.assertTrue(self.memory.receipts["unknown"])
        self.assertEqual(
            webhook.process(WebhookEvent("unlinked", "subscription.created", "bad")).outcome,
            "unlinked",
        )
        self.assertFalse(self.memory.receipts["unlinked"])

    def test_development_access_still_requires_verified_profile(self) -> None:
        self.service.development_access = True
        self.assertTrue(self.service.can_write(OWNER))
        self.assertFalse(self.service.can_write(self.other))
        self.profiles.verified = False
        self.assertFalse(self.service.can_write(OWNER))
