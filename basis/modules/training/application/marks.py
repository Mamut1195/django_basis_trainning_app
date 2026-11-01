"""Read-only estimated marks, never measured-reference values."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from basis.shared.identifiers import AccountId, ExerciseId, SessionId, StrengthSetId


@dataclass(frozen=True)
class EstimatedMark:
    set_id: StrengthSetId
    exercise_id: ExerciseId
    exercise_name: str
    date: date
    session_id: SessionId
    session_title: str
    block_title: str
    set_order: int
    kg: Decimal
    observed_kg: Decimal
    reps: int
    rpe: Decimal


@dataclass(frozen=True)
class EstimatedMarkPage:
    rows: tuple[EstimatedMark, ...]
    number: int
    pages: int
    total: int
    previous: int | None
    next: int | None


class EstimatedMarks(Protocol):
    def read(
        self,
        owner: AccountId,
        exercise: ExerciseId | None,
        start: date | None,
        end: date | None,
        page: int,
    ) -> EstimatedMarkPage: ...
