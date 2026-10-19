"""Bounded public exercise catalog projection for planning context."""

from dataclasses import dataclass
from typing import Protocol

from basis.shared.identifiers import ExerciseId


@dataclass(frozen=True)
class CoachExercise:
    id: ExerciseId
    name: str


class CoachExercises(Protocol):
    def read(self) -> tuple[CoachExercise, ...]: ...
