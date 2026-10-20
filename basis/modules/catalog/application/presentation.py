"""Public read contract for historical exercise display."""

from collections.abc import Mapping
from typing import Protocol

from basis.shared.identifiers import ExerciseId


class ExerciseNames(Protocol):
    def names(self, exercises: tuple[ExerciseId, ...]) -> Mapping[ExerciseId, str]: ...

    def fatigue(self, exercise: ExerciseId) -> str | None: ...
