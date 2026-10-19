"""Distinct opaque IDs. Persistence representations remain unchanged."""

from typing import NewType
from uuid import UUID

AccountId = NewType("AccountId", int)
AthleteId = NewType("AthleteId", int)
SessionId = NewType("SessionId", UUID)
PlannedSessionId = NewType("PlannedSessionId", int)
PlanId = NewType("PlanId", int)
Revision = NewType("Revision", int)
