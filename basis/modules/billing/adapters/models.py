from django.conf import settings
from django.db import models
from django.utils import timezone

from basis.modules.billing.public import entitled as billing_entitled
from basis.modules.billing.public import status_label as billing_status_label


class BillingAccount(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="billing"
    )
    polar_customer_id = models.CharField(max_length=100, null=True, unique=True, blank=True)
    subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, default="inactive")
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_used = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    needs_reconciliation = models.BooleanField(default=False)
    checkout_url = models.TextField(blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    checkout_context = models.CharField(max_length=64, blank=True)
    checkout_attempt = models.UUIDField(null=True, blank=True)
    checkout_created_at = models.DateTimeField(null=True, blank=True)

    @property
    def entitled(self) -> bool:
        return billing_entitled(
            self.status,
            self.period_start,
            self.period_end,
            self.needs_reconciliation,
            timezone.now(),
        )

    @property
    def status_label(self) -> str:
        return billing_status_label(self.status)


class WebhookReceipt(models.Model):
    event_id = models.CharField(max_length=200, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    customer_external_id = models.UUIDField(null=True)
    provider_customer_id = models.CharField(max_length=100, blank=True)
    organization_id = models.CharField(max_length=100, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    error_code = models.CharField(max_length=32, blank=True)
