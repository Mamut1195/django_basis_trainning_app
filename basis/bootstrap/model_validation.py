"""Explicit wiring for cross-module model validation projections."""

from basis.modules.athletes.adapters.references import DjangoRMReferences
from basis.modules.training.adapters.models import configure_rm_references


def configure() -> None:
    configure_rm_references(DjangoRMReferences())
