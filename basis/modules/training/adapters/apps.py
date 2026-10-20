"""Django registration for training persistence and adapters."""

from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.training.adapters"
    label = "basis_training"

    def ready(self) -> None:
        from basis.bootstrap.model_validation import configure

        configure()
