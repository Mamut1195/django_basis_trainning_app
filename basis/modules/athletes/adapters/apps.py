"""Django registration for athletes persistence and adapters."""

from django.apps import AppConfig


class AthletesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.athletes.adapters"
    label = "basis_athletes"
