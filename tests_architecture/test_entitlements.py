"""MAM817: complementary temporal invariants, without framework or provider IO."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import product
from unittest import TestCase

from basis.modules.billing.domain.records import (
    BillingState,
    CustomerState,
    Subscription,
    entitled,
    reconcile_state,
    state_entitled,
)
from basis.shared.identifiers import AccountId

START = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
END = START + timedelta(days=7)
TICK = timedelta(microseconds=1)


class EntitlementInvariantTests(TestCase):
    def test_full_status_and_boundary_truth_table_including_timezone_equivalence(self) -> None:
        # Independent contract oracle: [start, end), not a second production calculation.
        instants = (START - TICK, START, START + TICK, END - TICK, END, END + TICK)
        allowed = (False, True, True, True, False, False)
        for status, offset in product(
            ("active", "trialing", "inactive", "past_due", "unpaid", "canceled", "revoked", ""),
            (-5, 0, 9),
        ):
            zone = timezone(timedelta(hours=offset))
            for now, inside in zip(instants, allowed, strict=True):
                with self.subTest(status=status, offset=offset, now=now):
                    self.assertEqual(
                        entitled(status, START.astimezone(zone), END.astimezone(zone), False, now),
                        inside and status in ("active", "trialing"),
                    )

    def test_missing_naive_pending_and_nonpositive_intervals_fail_closed(self) -> None:
        for status in ("active", "trialing"):
            for start, end, now, pending in (
                (None, END, START, False),
                (START, None, START, False),
                (START.replace(tzinfo=None), END, START, False),
                (START, END.replace(tzinfo=None), START, False),
                (START, END, START.replace(tzinfo=None), False),
                (START, END, START, True),
                (START, START, START, False),
                (END, START, START, False),
            ):
                with self.subTest(status=status, start=start, end=end, pending=pending):
                    self.assertFalse(entitled(status, start, end, pending, now))

    def test_cancellation_flag_never_extends_or_shortens_the_authoritative_cutoff(self) -> None:
        for status, cancel in product(("active", "trialing"), (False, True)):
            subscription = Subscription(
                id="synthetic-subscription",
                product_id="synthetic-product",
                status=status,
                period_start=START,
                period_end=END + timedelta(days=30),
                period_end_key="unused-ordering-key",
                trial_end=END + timedelta(days=1),
                trial_started=True,
                cancel_at_period_end=cancel,
                ends_at=END,
            )
            customer = CustomerState("synthetic-customer", "synthetic-owner", (subscription,))
            state = reconcile_state(
                BillingState(AccountId(817)),
                customer,
                "synthetic-owner",
                "synthetic-product",
                END - TICK,
            )
            self.assertEqual(state.period_end, END)
            self.assertEqual(state.cancel_at_period_end, cancel)
            self.assertTrue(state_entitled(state, END - TICK))
            self.assertFalse(state_entitled(state, END))
            self.assertFalse(state_entitled(state, END + TICK))
            inactive = reconcile_state(state, customer, "synthetic-owner", "synthetic-product", END)
            self.assertEqual(inactive.status, "inactive")
            self.assertTrue(inactive.trial_used)

    def test_trial_memory_is_monotonic_across_empty_unpaid_and_pending_state(self) -> None:
        previous = BillingState(
            AccountId(817),
            customer_id="synthetic-customer",
            trial_used=True,
            status="trialing",
            period_start=START,
            period_end=END,
        )
        for status in ("active", "trialing", "past_due", "unpaid", "canceled", "inactive"):
            previous = replace(previous, status=status, needs_reconciliation=True)
            result = reconcile_state(
                previous,
                CustomerState("synthetic-customer", "synthetic-owner", ()),
                "synthetic-owner",
                "synthetic-product",
                END,
            )
            self.assertTrue(result.trial_used)
            self.assertFalse(state_entitled(result, END))
            self.assertFalse(result.needs_reconciliation)
            self.assertIsNone(result.period_start)
            self.assertIsNone(result.period_end)
            previous = result
