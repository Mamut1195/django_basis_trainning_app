"""Shared repository contract and durable webhook failure against real transactions."""

from dataclasses import replace
from unittest.mock import patch
from uuid import UUID

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase

from basis.bootstrap.transactions import DjangoUnitOfWork
from basis.modules.athletes.public import BillingProfile
from basis.modules.billing.adapters.models import BillingAccount, WebhookReceipt
from basis.shared.identifiers import AccountId
from tests_architecture.billing_contract import BillingContract
from tests_architecture.test_billing import PUBLIC, Clock, Gateway

from ..application.service import Billing, Checkout, WebhookEvent, Webhooks
from ..domain.records import ProviderUnavailable
from .django import DjangoBillingRepository, DjangoReceipts


class Profiles:
    def __init__(self, owner: AccountId) -> None:
        self.owner = owner

    def get(self, owner: AccountId) -> BillingProfile | None:
        return BillingProfile(owner, PUBLIC, True) if owner == self.owner else None

    def owner_for(self, public_id: UUID) -> AccountId | None:
        return self.owner if public_id == PUBLIC else None


class DjangoBillingTests(BillingContract, TestCase):
    def setUp(self) -> None:
        self.owner = AccountId(User.objects.create_user(username="billing").pk)
        self.other = AccountId(User.objects.create_user(username="other-billing").pk)
        self.repository = DjangoBillingRepository()
        self.uow_factory = DjangoUnitOfWork
        self.gateway = Gateway()
        self.billing = Billing(
            self.repository,
            Profiles(self.owner),
            self.gateway,
            DjangoUnitOfWork,
            Clock(),
            "product",
        )
        self.receipts = DjangoReceipts()

    def test_pending_failure_retry_and_duplicate_receipt_persist(self) -> None:
        with DjangoUnitOfWork() as uow:
            self.repository.lock(self.owner)
            uow.commit()
        event = WebhookEvent("delivery", "customer.state_changed", str(PUBLIC))
        webhooks = Webhooks(self.billing, self.receipts)
        self.gateway.fail = True
        self.assertEqual(webhooks.process(event).outcome, "reconciliation_pending")
        self.assertTrue(BillingAccount.objects.get(owner_id=self.owner).needs_reconciliation)
        self.assertIsNone(WebhookReceipt.objects.get(event_id=event.id).processed_at)
        self.gateway.fail = False
        self.assertEqual(webhooks.process(event).outcome, "processed")
        self.assertFalse(BillingAccount.objects.get(owner_id=self.owner).needs_reconciliation)
        receipt = WebhookReceipt.objects.get(event_id=event.id)
        self.assertIsNotNone(receipt.processed_at)
        self.assertEqual(receipt.customer_external_id, PUBLIC)
        self.gateway.fail = True
        self.assertEqual(webhooks.process(event).outcome, "processed")
        self.assertEqual(WebhookReceipt.objects.count(), 1)

    def test_partial_checkout_save_failure_rolls_back_created_account(self) -> None:
        original = self.repository.save

        def save_then_fail(state: object) -> None:
            # Failure is injected after the actual adapter save, not before persistence.
            from ..domain.records import BillingState

            assert isinstance(state, BillingState)
            original(state)
            raise ProviderUnavailable("injected failure")

        with patch.object(self.repository, "save", side_effect=save_then_fail):
            with self.assertRaises(ProviderUnavailable):
                self.billing.checkout(Checkout(self.owner, "owner@example.test"))
        self.assertFalse(BillingAccount.objects.filter(owner_id=self.owner).exists())

    def test_unknown_event_and_unlinked_identity_leave_expected_receipts(self) -> None:
        webhooks = Webhooks(self.billing, self.receipts)
        self.assertEqual(
            webhooks.process(WebhookEvent("ignored", "unknown", None)).outcome, "processed"
        )
        self.assertIsNotNone(WebhookReceipt.objects.get(event_id="ignored").processed_at)
        self.assertEqual(
            webhooks.process(WebhookEvent("unlinked", "subscription.updated", "invalid")).outcome,
            "unlinked",
        )
        self.assertIsNone(WebhookReceipt.objects.get(event_id="unlinked").processed_at)

    def test_model_entitlement_delegates_policy_without_changing_labels(self) -> None:
        with DjangoUnitOfWork() as uow:
            self.repository.save(replace(self.repository.lock(self.owner), status="past_due"))
            uow.commit()
        row = BillingAccount.objects.get(owner_id=self.owner)
        self.assertFalse(row.entitled)
        self.assertEqual(row.status_label, "Pago pendiente")


class DurableWebhookTests(TransactionTestCase):
    def test_pending_is_committed_before_failed_reconciliation_without_outer_test_atomic(
        self,
    ) -> None:
        self.assertTrue(transaction.get_autocommit())
        owner = AccountId(User.objects.create_user(username="durable-billing").pk)
        repository = DjangoBillingRepository()
        with DjangoUnitOfWork() as uow:
            repository.lock(owner)
            uow.commit()
        gateway = Gateway()
        billing = Billing(
            repository, Profiles(owner), gateway, DjangoUnitOfWork, Clock(), "product"
        )
        event = WebhookEvent("durable-delivery", "customer.state_changed", str(PUBLIC))

        def unavailable(public_id: UUID) -> None:
            self.assertTrue(connection.in_atomic_block)
            self.assertTrue(BillingAccount.objects.get(owner_id=owner).needs_reconciliation)
            self.assertIsNone(WebhookReceipt.objects.get(event_id=event.id).processed_at)
            raise ProviderUnavailable("injected bounded provider failure")

        with patch.object(gateway, "customer", side_effect=unavailable):
            result = Webhooks(billing, DjangoReceipts()).process(event)
        self.assertEqual(result.outcome, "reconciliation_pending")
        self.assertTrue(transaction.get_autocommit())
        self.assertFalse(connection.in_atomic_block)
        # These reads happen after the failing reconciliation transaction has rolled back.
        # With no TestCase wrapper, receipt/pending writes survived actual commit boundaries.
        self.assertTrue(BillingAccount.objects.get(owner_id=owner).needs_reconciliation)
        self.assertIsNone(WebhookReceipt.objects.get(event_id=event.id).processed_at)
