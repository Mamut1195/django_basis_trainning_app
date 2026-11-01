"""Read-only measured strength marks owned by one account."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId


@dataclass(frozen=True)
class MeasuredMark:
    id: MeasuredRMId
    exercise_id: ExerciseId
    exercise_name: str
    date: date
    kg: Decimal


@dataclass(frozen=True)
class MeasuredMarkPage:
    rows: tuple[MeasuredMark, ...]
    number: int
    pages: int
    total: int
    previous: int | None
    next: int | None


class MeasuredMarks(Protocol):
    def read(
        self,
        owner: AccountId,
        exercise: ExerciseId | None,
        start: date | None,
        end: date | None,
        page: int,
    ) -> MeasuredMarkPage: ...
