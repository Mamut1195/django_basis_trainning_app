"""Distinct opaque IDs. Persistence representations remain unchanged."""

from typing import NewType
from uuid import UUID

AccountId = NewType("AccountId", int)
AthleteId = NewType("AthleteId", int)
SessionId = NewType("SessionId", UUID)
PlannedSessionId = NewType("PlannedSessionId", int)
PlanId = NewType("PlanId", int)
Revision = NewType("Revision", int)

ExerciseId = NewType("ExerciseId", int)
ClassificationId = NewType("ClassificationId", int)
MeasurementId = NewType("MeasurementId", int)
WellnessId = NewType("WellnessId", int)
SportProfileId = NewType("SportProfileId", int)
MeasuredRMId = NewType("MeasuredRMId", int)
WorkoutId = NewType("WorkoutId", int)
