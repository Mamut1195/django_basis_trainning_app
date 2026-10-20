"""Athletes-owned private export read contract."""

from typing import Protocol

from basis.shared.export import ExportReader


class AthleteExport(ExportReader, Protocol):
    pass
