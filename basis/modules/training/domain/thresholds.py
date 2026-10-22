"""Frozen context only: a threshold never generates targets, zones or observations."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ThresholdSnapshot:
    profile_id: int
    sport: str
    value: Decimal
    unit: str
    measured_on: date
    method: str
    kind: str
    source: str
