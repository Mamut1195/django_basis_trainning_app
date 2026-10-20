"""Training-owned private export read contract."""

from typing import Protocol

from basis.shared.export import ExportReader


class TrainingExport(ExportReader, Protocol):
    pass
