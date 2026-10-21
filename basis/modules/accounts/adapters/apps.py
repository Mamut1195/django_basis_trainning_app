"""Django registration for accounts persistence and adapters."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.accounts.adapters"
    label = "basis_accounts"

    def ready(self) -> None:
        from . import lifecycle  # noqa: F401
