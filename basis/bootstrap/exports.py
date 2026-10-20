"""Compose private export readers without querying persistence."""

from basis.modules.athletes.adapters.export import DjangoAthleteExport
from basis.modules.coach.adapters.export import DjangoCoachExport
from basis.modules.training.adapters.export import DjangoTrainingExport
from basis.shared.export import ExportReader


def export_readers() -> tuple[ExportReader, ...]:
    return DjangoAthleteExport(), DjangoTrainingExport(), DjangoCoachExport()
