"""Provider-neutral projections for the stable account export."""

from dataclasses import dataclass
from typing import Protocol

from .identifiers import AccountId


@dataclass(frozen=True)
class ExportSection:
    key: str
    rows: tuple[dict[str, object], ...]


class ExportReader(Protocol):
    def read(self, owner: AccountId) -> tuple[ExportSection, ...]: ...
