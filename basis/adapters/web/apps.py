"""Presentation-only Django application with no business models."""

from django.apps import AppConfig


class WebConfig(AppConfig):
    name = "basis.adapters.web"
    label = "basis_web"
    verbose_name = "BASIS web"
