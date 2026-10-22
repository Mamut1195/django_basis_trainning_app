"""Persistence of billing and webhook receipts in the existing Django tables."""

from datetime import datetime
from uuid import UUID

from basis.adapters.django.account_locks import lock_account
from basis.modules.billing.adapters.models import BillingAccount, WebhookReceipt
from basis.shared.identifiers import AccountId

from ..application.service import WebhookEvent
from ..domain.records import BillingState


def billing_state(row: BillingAccount) -> BillingState:
    return BillingState(
        AccountId(row.owner_id),
        row.polar_customer_id,
        row.subscription_id,
        row.status,
        row.period_start,
        row.period_end,
        row.cancel_at_period_end,
        row.trial_used,
        row.reconciled_at,
        row.needs_reconciliation,
        row.checkout_url,
        row.checkout_expires_at,
        row.checkout_context,
        row.checkout_attempt,
        row.checkout_created_at,
    )


class DjangoBillingRepository:
    def lock(self, owner: AccountId) -> BillingState:
        lock_account(owner, BillingAccount.objects.db)
        row, _ = BillingAccount.objects.get_or_create(owner_id=owner)
        return billing_state(BillingAccount.objects.select_for_update().get(pk=row.pk))

    def get(self, owner: AccountId) -> BillingState | None:
        row = BillingAccount.objects.filter(owner_id=owner).first()
        return billing_state(row) if row else None

    def save(self, state: BillingState) -> None:
        row = BillingAccount.objects.get(owner_id=state.owner)
        row.polar_customer_id = state.customer_id
        row.subscription_id = state.subscription_id
        row.status = state.status
        row.period_start = state.period_start
        row.period_end = state.period_end
        row.cancel_at_period_end = state.cancel_at_period_end
        row.trial_used = state.trial_used
        row.reconciled_at = state.reconciled_at
        row.needs_reconciliation = state.needs_reconciliation
        row.checkout_url = state.checkout_url
        row.checkout_expires_at = state.checkout_expires_at
        row.checkout_context = state.checkout_context
        row.checkout_attempt = state.checkout_attempt
        row.checkout_created_at = state.checkout_created_at
        row.save()

    def mark_pending(self, owner: AccountId) -> None:
        lock_account(owner, BillingAccount.objects.db)
        BillingAccount.objects.filter(owner_id=owner).update(needs_reconciliation=True)

    def owner_for_customer(self, customer_id: str) -> AccountId | None:
        value = (
            BillingAccount.objects.filter(polar_customer_id=customer_id)
            .values_list("owner_id", flat=True)
            .first()
        )
        return AccountId(value) if value is not None else None


class DjangoReceipts:
    def received(self, event: WebhookEvent) -> bool:
        row, _ = WebhookReceipt.objects.get_or_create(
            event_id=event.id,
            defaults={
                "event_type": event.kind,
                "customer_external_id": self._uuid(event.external_id),
                "provider_customer_id": event.customer_id or "",
                "organization_id": event.organization_id or "",
            },
        )
        return row.processed_at is not None

    @staticmethod
    def _uuid(value: str | None) -> UUID | None:
        try:
            return UUID(value) if value else None
        except ValueError:
            return None

    def complete(self, event_id: str, now: datetime, public_id: UUID | None = None) -> None:
        fields: dict[str, object] = {"processed_at": now}
        if public_id is not None:
            fields["customer_external_id"] = public_id
        WebhookReceipt.objects.filter(event_id=event_id).update(**fields)
