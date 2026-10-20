"""Django registration for sync persistence and adapters."""

from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.sync.adapters"
    label = "basis_sync"
