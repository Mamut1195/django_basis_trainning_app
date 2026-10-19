"""Narrow authorized athlete context exported to the coach."""

from dataclasses import dataclass
from typing import Protocol

from basis.shared.identifiers import AccountId

from ..domain.records import PreferencesData, SportData, WellnessData


@dataclass(frozen=True)
class AthleteCoachContext:
    age: int | None
    objectives: str
    preferences: PreferencesData | None
    sports: tuple[SportData, ...]
    wellness: WellnessData | None


class AthleteCoachContexts(Protocol):
    def read(self, owner: AccountId) -> AthleteCoachContext: ...
