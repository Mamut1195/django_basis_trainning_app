"""Distinct opaque IDs. Persistence representations remain unchanged."""

from typing import NewType
from uuid import UUID

JobId = NewType("JobId", UUID)
UsagePeriodId = NewType("UsagePeriodId", int)
TrialFundId = NewType("TrialFundId", int)
AIRequestKey = NewType("AIRequestKey", UUID)
ProposalId = NewType("ProposalId", int)

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

GoalId = NewType("GoalId", int)
CycleId = NewType("CycleId", int)
LineageId = NewType("LineageId", UUID)

TrekTripId = NewType("TrekTripId", int)

TrekStageId = NewType("TrekStageId", int)
