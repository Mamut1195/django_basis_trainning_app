"""Public reference projection used by training persistence validation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId


@dataclass(frozen=True)
class RMReference:
    owner: AccountId | None
    exercise: ExerciseId
    measured_on: date


class RMReferences(Protocol):
    def get(self, reference: MeasuredRMId) -> RMReference | None: ...


class RMChoices(Protocol):
    def eligible(self, owner: AccountId, through: date) -> tuple[MeasuredRMId, ...]: ...


@dataclass(frozen=True)
class SportThreshold:
    profile_id: int
    sport: str
    value: Decimal
    unit: str
    measured_on: date
    method: str
    kind: str
    source: str


class SportThresholds(Protocol):
    def current(
        self, owner: AccountId, sport: str, through: date, *, using: str = "default"
    ) -> SportThreshold | None: ...
