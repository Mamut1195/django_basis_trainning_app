"""Explicit wiring for cross-module model validation projections."""

from basis.modules.athletes.adapters.references import DjangoRMReferences, DjangoSportThresholds
from basis.modules.training.adapters.models import configure_rm_references
from basis.modules.training.adapters.thresholds import configure_thresholds


def configure() -> None:
    configure_rm_references(DjangoRMReferences())
    configure_thresholds(DjangoSportThresholds())
