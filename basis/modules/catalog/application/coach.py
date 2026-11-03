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
    def read_for_acceptance(self, referenced: tuple[ExerciseId, ...]) -> tuple[CoachExercise, ...]:
        """Require caller UoW; lock referenced existing rows in stable ID order.

        Return the same bounded catalog as read(). Unreferenced rows and new
        inserts are not protected; caller compares only referenced exercises.
        """
        ...
