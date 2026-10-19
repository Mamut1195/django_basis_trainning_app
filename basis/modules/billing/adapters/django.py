"""Persistence of billing and webhook receipts in the existing Django tables."""

from datetime import datetime
from uuid import UUID

from basis.shared.identifiers import AccountId
from training.models import BillingAccount, WebhookReceipt

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
    )


class DjangoBillingRepository:
    def lock(self, owner: AccountId) -> BillingState:
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
        row.save()

    def mark_pending(self, owner: AccountId) -> None:
        BillingAccount.objects.filter(owner_id=owner).update(needs_reconciliation=True)


class DjangoReceipts:
    def received(self, event: WebhookEvent) -> bool:
        row, _ = WebhookReceipt.objects.get_or_create(
            event_id=event.id, defaults={"event_type": event.kind}
        )
        return row.processed_at is not None

    def complete(self, event_id: str, now: datetime, public_id: UUID | None = None) -> None:
        fields: dict[str, object] = {"processed_at": now}
        if public_id is not None:
            fields["customer_external_id"] = public_id
        WebhookReceipt.objects.filter(event_id=event_id).update(**fields)
