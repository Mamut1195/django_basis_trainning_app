"""Django registration for catalog persistence and adapters."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "basis.modules.catalog.adapters"
    label = "basis_catalog"
