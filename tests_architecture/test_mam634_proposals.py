"""MAM-634 declared constraints and proposal decisions without Django/network."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from basis.modules.athletes.public import AthleteCoachContext, PreferencesData
from basis.modules.coach.application.proposals import AcceptProposal, Proposals
from basis.modules.coach.domain.context import CoachContext
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import validate_context
from basis.modules.training.public import (
    BlockData,
    CoachGoal,
    IntervalData,
    Metric,
    MetricName,
    PlanDefinition,
    ProgressReport,
    ScheduledDefinition,
    TrainingCoachContext,
)
from basis.shared.identifiers import AccountId, GoalId, JobId, PlanId, ProposalId
from tests_architecture.test_coach_proposals import (
    Authorization,
    MemoryPlanning,
    MemoryProposals,
    Work,
)


def context() -> CoachContext:
    return CoachContext(
        datetime(2026, 11, 2, tzinfo=timezone.utc),
        AthleteCoachContext(
            30, "Constancia", PreferencesData((1, 3, 5), 30, "Zapatillas", "", ""), (), None
        ),
        TrainingCoachContext(
            (CoachGoal(GoalId(1), "Constancia", "running", None, None, "", None, None, "primary"),),
            (),
            ProgressReport((), (), 0, 0, 0, None),
        ),
        (),
    )


def definition() -> PlanDefinition:
    return PlanDefinition(
        GoalId(1),
        "Semana",
        date(2027, 1, 4),
        date(2027, 1, 10),
        sessions=(
            ScheduledDefinition(
                "micro",
                "Práctica",
                date(2027, 1, 4),
                (
                    BlockData(
                        "running", target=(Metric(MetricName.DURATION_SECONDS, Decimal(1800)),)
                    ),
                ),
            ),
        ),
    )


class DeclaredConstraints634Tests(TestCase):
    def test_clocks_progress_and_new_observations_are_not_restriction_equality(self) -> None:
        frozen = context()
        current = replace(
            frozen,
            snapshot_at=frozen.snapshot_at + timedelta(days=1),
            training=replace(frozen.training, progress=ProgressReport((), (), 4, 4, 2, 50.0)),
        )
        validate_context(definition(), frozen, current)

    def test_block_total_does_not_double_count_interval_duration(self) -> None:
        frozen = context()
        data = definition()
        block = replace(
            data.sessions[0].blocks[0],
            intervals=(
                IntervalData(
                    repetitions=3, target=(Metric(MetricName.DURATION_SECONDS, Decimal(600)),)
                ),
            ),
        )
        data = replace(data, sessions=(replace(data.sessions[0], blocks=(block,)),))
        validate_context(data, frozen, frozen)

    def test_unknown_duration_remains_unknown_instead_of_estimation_from_distance(self) -> None:
        frozen = context()
        data = definition()
        block = BlockData("running", target=(Metric(MetricName.DISTANCE_M, Decimal(1000)),))
        validate_context(
            replace(data, sessions=(replace(data.sessions[0], blocks=(block,)),)), frozen, frozen
        )

    def test_declared_total_above_minutes_and_unavailable_weekday_are_rejected(self) -> None:
        frozen = context()
        data = definition()
        second = replace(
            data.sessions[0].blocks[0], target=(Metric(MetricName.DURATION_SECONDS, Decimal(1)),)
        )
        with self.assertRaisesRegex(CoachInvalid, "minutos"):
            validate_context(
                replace(
                    data,
                    sessions=(
                        replace(data.sessions[0], blocks=data.sessions[0].blocks + (second,)),
                    ),
                ),
                frozen,
                frozen,
            )
        with self.assertRaisesRegex(CoachInvalid, "días"):
            validate_context(
                replace(data, sessions=(replace(data.sessions[0], date=date(2027, 1, 5)),)),
                frozen,
                frozen,
            )

    def test_free_text_is_only_compared_for_change_without_inferred_equipment_rules(self) -> None:
        frozen = context()
        assert frozen.athlete.preferences is not None
        current = replace(
            frozen,
            athlete=replace(
                frozen.athlete,
                preferences=replace(frozen.athlete.preferences, equipment="Solo bandas"),
            ),
        )
        with self.assertRaisesRegex(CoachInvalid, "cambiaron"):
            validate_context(definition(), frozen, current)
        validate_context(definition(), current, current)

    def test_accepted_replay_and_rejection_never_call_context_guard(self) -> None:
        class FailChecks:
            def validate(
                self, owner: AccountId, job: JobId, definition: PlanDefinition, base: PlanId | None
            ) -> None:
                raise AssertionError("Resolved proposals must not revalidate context")

        repo, planning = MemoryProposals(), MemoryPlanning()
        repo.row = replace(repo.row, status="accepted", accepted_plan=PlanId(4))
        service = Proposals(repo, planning, Authorization(), Work, FailChecks())
        self.assertEqual(service.accept(AcceptProposal(AccountId(1), ProposalId(1))), PlanId(4))
        service.reject(AcceptProposal(AccountId(1), ProposalId(1)))
        repo.row = replace(repo.row, status="pending")
        service.reject(AcceptProposal(AccountId(1), ProposalId(1)))
        self.assertEqual(repo.row.status, "rejected")
