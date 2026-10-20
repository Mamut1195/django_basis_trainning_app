"""Django registration for coach persistence and adapters."""

from django.apps import AppConfig


class CoachConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.coach.adapters"
    label = "basis_coach"
