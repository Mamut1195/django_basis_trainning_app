"""Public reference projection used by training persistence validation."""

from dataclasses import dataclass
from datetime import date
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
