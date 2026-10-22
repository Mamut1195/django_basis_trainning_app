"""Durable bounded GET-only recovery; no checkout or payment retries."""

from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from basis.bootstrap.billing import webhooks
from basis.modules.billing.public import WebhookEvent

from . import actions
from .models import WebhookReceipt


def process_pending(*, limit: int = 100, retry_exhausted: bool = False) -> int:
    now = timezone.now()
    query = WebhookReceipt.objects.filter(processed_at__isnull=True)
    if not retry_exhausted:
        query = query.filter(attempts__lt=10).filter(
            Q(retry_at__isnull=True) | Q(retry_at__lte=now)
        )
    pending = list(query.order_by("received_at").values_list("pk", flat=True)[:limit])
    service = webhooks(actions.polar_request)
    for pk in pending:
        row = WebhookReceipt.objects.get(pk=pk)
        event = WebhookEvent(
            row.event_id,
            row.event_type,
            str(row.customer_external_id) if row.customer_external_id else None,
            row.provider_customer_id or None,
            row.organization_id or None,
        )
        outcome = service.process(event).outcome
        if outcome == "processed":
            WebhookReceipt.objects.filter(pk=pk).update(error_code="", retry_at=None)
        else:
            # Counters/error codes only: never persist/log provider payloads or URLs.
            WebhookReceipt.objects.filter(pk=pk).update(
                attempts=F("attempts") + 1,
                retry_at=now + timedelta(seconds=min(3600, 2 ** min(row.attempts + 1, 10))),
                error_code=outcome,
            )
    return len(pending)
