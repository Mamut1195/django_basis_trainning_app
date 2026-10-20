"""Coach-owned private export read contract."""

from typing import Protocol

from basis.shared.export import ExportReader


class CoachExport(ExportReader, Protocol):
    pass
