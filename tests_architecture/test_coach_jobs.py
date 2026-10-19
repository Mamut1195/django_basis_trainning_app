"""Budget and orchestration tests require no Django, database or provider."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import TracebackType
from unittest import TestCase
from uuid import UUID

from basis.modules.athletes.public import AthleteCoachContext, BillingProfile
from basis.modules.billing.public import BillingState
from basis.modules.coach.application.jobs import CoachConfiguration, Enqueue, Jobs
from basis.modules.coach.domain.context import CoachContext
from basis.modules.coach.domain.jobs import (
    CoachInvalid,
    Fund,
    Job,
    JobKind,
    ProviderAmbiguous,
    ProviderReply,
    TokenUsage,
    Usage,
    require_budget,
    reservation_for,
    usage_cost,
)
from basis.modules.training.public import ProgressReport, TrainingCoachContext
from basis.shared.identifiers import (
    AccountId,
    AIRequestKey,
    JobId,
    PlanId,
    TrialFundId,
    UsagePeriodId,
)
from tests_architecture.coach_jobs_contract import JobsContract

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
OWNER, OTHER = AccountId(1), AccountId(2)
CONTEXT = CoachContext(
    NOW,
    AthleteCoachContext(None, "", None, (), None),
    TrainingCoachContext((), (), ProgressReport((), (), 0, 0, 0, None)),
)


class Memory:
    def __init__(self) -> None:
        self.jobs: dict[JobId, Job] = {}
        self.usages: dict[UsagePeriodId, Usage] = {}
        self.funds: dict[TrialFundId, Fund] = {}
        self.is_blocked = False
        self.committed = False

    def __enter__(self) -> "Memory":
        self.before = deepcopy((self.jobs, self.usages, self.funds, self.is_blocked))
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self.committed or exc_type is not None:
            self.jobs, self.usages, self.funds, self.is_blocked = self.before

    def commit(self) -> None:
        self.committed = True

    def blocked(self) -> bool:
        return self.is_blocked

    def block(self) -> None:
        self.is_blocked = True

    def lock_month(self, month: str) -> Fund:
        for fund in self.funds.values():
            if fund.month == month:
                return replace(fund)
        fund = Fund(TrialFundId(len(self.funds) + 1), month)
        self.funds[fund.id] = fund
        return replace(fund)

    def lock_fund(self, fund: TrialFundId) -> Fund:
        return self.fund(fund)

    def fund(self, fund: TrialFundId) -> Fund:
        return replace(self.funds[fund])

    def save_fund(self, fund: Fund) -> None:
        self.funds[fund.id] = replace(fund)

    def existing(self, owner: AccountId, key: AIRequestKey) -> Job | None:
        return next(
            (replace(j) for j in self.jobs.values() if j.owner == owner and j.request_key == key),
            None,
        )

    def lock_period(self, owner: AccountId, key: str, trial: bool) -> Usage:
        for usage in self.usages.values():
            if usage.owner == owner and usage.key == key:
                return replace(usage)
        usage = Usage(UsagePeriodId(len(self.usages) + 1), owner, key, trial)
        self.usages[usage.id] = usage
        return replace(usage)

    def lock_usage(self, usage: UsagePeriodId) -> Usage:
        return self.usage(usage)

    def usage(self, usage: UsagePeriodId) -> Usage:
        return replace(self.usages[usage])

    def save_usage(self, usage: Usage) -> None:
        self.usages[usage.id] = replace(usage)

    def job(self, job: JobId) -> Job:
        return replace(self.jobs[job])

    def lock_job(self, job: JobId) -> Job:
        return self.job(job)

    def create(self, job: Job) -> None:
        self.jobs[job.id] = replace(job)

    def save_job(self, job: Job) -> None:
        self.jobs[job.id] = replace(job)

    def claim(self, now: datetime) -> Job | None:
        for job in self.jobs.values():
            if job.status == "pending":
                job.status, job.started_at = "running", now
                return replace(job)
        return None

    def quarantine(self, before: datetime) -> None:
        for job in self.jobs.values():
            if job.status == "running" and job.started_at is not None and job.started_at < before:
                job.status = "uncertain"


class Ports:
    def __init__(self) -> None:
        self.state = BillingState(
            OWNER,
            "polar",
            status="active",
            period_start=NOW - timedelta(days=1),
            period_end=NOW + timedelta(days=29),
        )
        self.calls = 0
        self.ambiguous = False

    def lock(self, owner: AccountId) -> BillingState:
        return self.state

    def get(self, owner: AccountId) -> BillingState:
        return self.state

    def snapshot(
        self, owner: AccountId, kind: JobKind, base_plan_id: PlanId | None
    ) -> CoachContext:
        return CONTEXT

    def prepare(self, kind: JobKind, prompt: str, context: CoachContext, model: str) -> None:
        pass

    def call(self, kind: JobKind, prompt: str, context: CoachContext, model: str) -> ProviderReply:
        self.calls += 1
        if self.ambiguous:
            raise ProviderAmbiguous
        return ProviderReply(TokenUsage(1000, 100, 200), "reported", True, "answer", True, "stop")

    def complete(self, job: Job) -> bool:
        return True

    def now(self) -> datetime:
        return NOW

    def today(self) -> date:
        return NOW.date()


class Profiles:
    def get(self, owner: AccountId) -> BillingProfile:
        return BillingProfile(owner, UUID(int=owner), True)

    def owner_for(self, public_id: UUID) -> AccountId | None:
        return OWNER


class Locks:
    def lock(self, owner: AccountId) -> None:
        pass


class JobsTests(JobsContract, TestCase):
    def setUp(self) -> None:
        self.memory = Memory()
        self.repository = self.memory
        self.uow_factory = lambda: self.memory
        self.owner, self.other = OWNER, OTHER
        self.ports = Ports()
        self.service = Jobs(
            self.memory,
            Locks(),
            self.ports,
            Profiles(),
            self.ports,
            self.ports,
            self.ports,
            self.ports,
            self.uow_factory,
            CoachConfiguration(True, True, "deepseek-v4-flash"),
        )
        self.sample = Job(
            JobId(UUID(int=1)),
            OWNER,
            AIRequestKey(UUID(int=2)),
            "short",
            "question",
            CONTEXT,
            UsagePeriodId(1),
            None,
            reservation_for("short"),
            "deepseek-v4-flash",
        )

    def command(self, key: int = 3) -> Enqueue:
        return Enqueue(OWNER, "short", "question", AIRequestKey(UUID(int=key)))

    def test_ambiguous_is_held_and_never_retried(self) -> None:
        job = self.service.enqueue(self.command())
        self.ports.ambiguous = True
        self.assertTrue(self.service.process_one())
        self.assertFalse(self.service.process_one())
        self.assertEqual(self.ports.calls, 1)
        self.assertEqual(self.memory.job(job.id).status, "uncertain")
        self.assertEqual(self.memory.usage(job.usage_period).reserved, job.reservation)
        self.assertEqual(self.service.settle(job.id, definitive=True).status, "uncertain")

    def test_partial_usage_retained_on_bad_choice_and_circuit_blocked(self) -> None:
        job = self.service.enqueue(self.command())
        self.memory.save_job(replace(job, status="running"))
        result = self.service.settle(job.id, ProviderReply(TokenUsage(1000, 100)))
        self.assertEqual(result.input_tokens, 1000)
        self.assertEqual(result.status, "uncertain")
        self.assertTrue(self.memory.blocked())
        self.assertEqual(self.memory.usage(job.usage_period).reserved, job.reservation)

    def test_settlement_rounds_up_and_is_idempotent(self) -> None:
        job = self.service.enqueue(self.command())
        self.assertTrue(self.service.process_one())
        self.assertEqual(self.memory.job(job.id).cost, Decimal("0.00036120"))
        before = self.memory.usage(job.usage_period)
        self.service.settle(job.id, definitive=True)
        self.assertEqual(self.memory.usage(job.usage_period), before)

    def test_period_change_releases_without_provider_call(self) -> None:
        job = self.service.enqueue(self.command())
        self.ports.state = replace(self.ports.state, period_start=NOW)
        self.service.process_one()
        self.assertEqual(self.ports.calls, 0)
        self.assertEqual(self.memory.job(job.id).status, "failed")
        self.assertEqual(self.memory.usage(job.usage_period).reserved, 0)

    def test_trial_month_rollover_releases_both_reservations_without_call(self) -> None:
        self.ports.state = replace(self.ports.state, status="trialing")
        job = self.service.enqueue(self.command())
        assert job.trial_fund is not None
        self.memory.funds[job.trial_fund].month = "2026-09"
        self.assertTrue(self.service.process_one())
        self.assertEqual(self.ports.calls, 0)
        self.assertEqual(self.memory.job(job.id).status, "failed")
        self.assertEqual(self.memory.usage(job.usage_period).reserved, 0)
        self.assertEqual(self.memory.fund(job.trial_fund).reserved, 0)

    def test_trial_to_paid_change_invalidates_pending_trial_job(self) -> None:
        self.ports.state = replace(self.ports.state, status="trialing")
        job = self.service.enqueue(self.command())
        self.ports.state = replace(self.ports.state, status="active")
        self.service.process_one()
        self.assertEqual(self.ports.calls, 0)
        self.assertEqual(self.memory.job(job.id).status, "failed")

    def test_stale_quarantine_retains_reservation_without_completion_or_retry(self) -> None:
        job = self.service.enqueue(self.command())
        self.memory.save_job(replace(job, status="running", started_at=NOW - timedelta(minutes=11)))
        self.service.quarantine_stale_jobs()
        self.assertEqual(self.memory.job(job.id).status, "uncertain")
        self.assertIsNone(self.memory.job(job.id).completed_at)
        self.assertEqual(self.memory.usage(job.usage_period).reserved, job.reservation)
        self.assertFalse(self.service.process_one())
        self.assertEqual(self.ports.calls, 0)

    def test_selected_raw_key_conflicts_and_quota_precedes_invalid_selection(self) -> None:
        command = replace(self.command(), kind="plan", base_plan=PlanId(1), base_plan_key="1")
        job = self.service.enqueue(command)
        with self.assertRaises(CoachInvalid):
            self.service.enqueue(replace(command, base_plan_key="001"))
        self.memory.usages[job.usage_period].plan_count = 8
        with self.assertRaisesRegex(CoachInvalid, "acciones IA"):
            self.service.enqueue(
                replace(command, request_key=AIRequestKey(UUID(int=4)), invalid_base_plan=True)
            )

    def test_context_budget_failure_rolls_back_all_reservations_and_counters(self) -> None:
        self.service.provider = RejectingProvider()
        with self.assertRaises(CoachInvalid):
            self.service.enqueue(self.command())
        self.assertEqual(self.memory.funds, {})
        self.assertEqual(self.memory.usages, {})
        self.assertEqual(self.memory.jobs, {})

    def test_trial_global_and_personal_boundaries(self) -> None:
        usage = Usage(UsagePeriodId(1), OWNER, "trial-lifetime", True)
        fund = Fund(TrialFundId(1), "2026-10", spent=Decimal("4.999"))
        with self.assertRaises(CoachInvalid):
            require_budget("short", usage, fund, True)
        fund.spent = Decimal(0)
        usage.spent = Decimal("0.029")
        with self.assertRaises(CoachInvalid):
            require_budget("short", usage, fund, True)

    def test_invalid_token_values_cannot_be_billed(self) -> None:
        for usage in (TokenUsage(-1, 0), TokenUsage(1, 0, 2), TokenUsage(4001, 0)):
            with self.assertRaises(CoachInvalid):
                usage_cost(usage, "short", reservation_for("short"))


class RejectingProvider(Ports):
    def prepare(self, kind: JobKind, prompt: str, context: CoachContext, model: str) -> None:
        raise CoachInvalid("request too large")
