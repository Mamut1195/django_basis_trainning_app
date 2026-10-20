"""Django registration for billing persistence and adapters."""

from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.billing.adapters"
    label = "basis_billing"
