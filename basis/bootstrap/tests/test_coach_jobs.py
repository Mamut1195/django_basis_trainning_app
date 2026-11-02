"""Shared persistence and PostgreSQL claim contracts on temporary databases."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.bootstrap.tests.test_coach_edges import account
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.coach.adapters.actions import enqueue
from basis.modules.coach.adapters.jobs import DjangoJobsRepository
from basis.modules.coach.adapters.models import AIJob, TrialFund, UsagePeriod
from basis.modules.coach.application.jobs import CoachConfiguration, Jobs
from basis.modules.coach.domain.jobs import Job, ProviderReply, TokenUsage, reservation_for
from basis.shared.identifiers import AccountId, AIRequestKey, JobId, TrialFundId, UsagePeriodId
from tests_architecture.coach_jobs_contract import JobsContract, JobsSettlementContract
from tests_architecture.test_coach_jobs import CONTEXT, NOW, Locks, Ports, Profiles


class DjangoJobsTests(JobsContract, JobsSettlementContract, TestCase):
    def setUp(self) -> None:
        self.owner = AccountId(get_user_model().objects.create_user(username="jobs").pk)
        self.other = AccountId(get_user_model().objects.create_user(username="other-jobs").pk)
        self.repository = DjangoJobsRepository()
        self.uow_factory = DjangoUnitOfWork
        usage = UsagePeriod.objects.create(owner_id=self.owner, key="period")
        self.sample = Job(
            JobId(UUID(int=1)),
            self.owner,
            AIRequestKey(UUID(int=2)),
            "short",
            "question",
            CONTEXT,
            UsagePeriodId(usage.pk),
            None,
            reservation_for("short"),
            "deepseek-v4-flash",
        )

        self.ports = Ports()
        self.service = Jobs(
            self.repository,
            Locks(),
            self.ports,
            Profiles(),
            self.ports,
            self.ports,
            self.ports,
            self.ports,
            DjangoUnitOfWork,
            CoachConfiguration(True, True, "deepseek-v4-flash"),
        )

    def test_quarantine_preserves_budget_and_does_not_complete(self) -> None:
        self.repository.create(self.sample)
        self.repository.save_job(
            replace(self.sample, status="running", started_at=NOW - timedelta(minutes=11))
        )
        UsagePeriod.objects.filter(pk=self.sample.usage_period).update(
            reserved=self.sample.reservation
        )
        with DjangoUnitOfWork() as work:
            self.repository.quarantine(NOW - timedelta(minutes=10))
            work.commit()
        row = self.repository.job(self.sample.id)
        self.assertEqual(row.status, "uncertain")
        self.assertIsNone(row.completed_at)
        self.assertEqual(self.repository.usage(row.usage_period).reserved, row.reservation)


@override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-a-credential")
class DjangoSelectionTests(TestCase):
    def test_string_zero_is_selected_but_numeric_zero_is_absent(self) -> None:
        owner = account("selected-zero")
        with self.assertRaisesRegex(ValidationError, "no est.*disponible"):
            enqueue(owner, "short", "question", UUID(int=10), base_plan_id="0")
        self.assertFalse(AIJob.objects.exists())
        job = enqueue(owner, "short", "question", UUID(int=11), base_plan_id=0)
        self.assertIsNone(job.base_plan_id)


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class DjangoClaimConcurrencyTests(TransactionTestCase):
    def test_concurrent_null_settlement_never_debits_or_releases_twice(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                owner = AccountId(
                    get_user_model().objects.create_user(username=f"settle-{trial}").pk
                )
                reservation = reservation_for("short")
                usage = UsagePeriod.objects.create(
                    owner_id=owner, key="settle", reserved=reservation, is_trial=trial
                )
                fund = (
                    TrialFund.objects.create(month="2026-10", reserved=reservation)
                    if trial
                    else None
                )
                repo = DjangoJobsRepository()
                job = Job(
                    JobId(UUID(int=10 + int(trial))),
                    owner,
                    AIRequestKey(UUID(int=10)),
                    "short",
                    "q",
                    CONTEXT,
                    UsagePeriodId(usage.pk),
                    None,
                    reservation,
                    "deepseek-v4-flash",
                    status="running",
                )
                if fund is not None:
                    job = replace(job, trial_fund=TrialFundId(fund.pk))
                repo.create(job)
                repo.save_job(job)
                barrier = Barrier(2)

                def settle() -> Job:
                    close_old_connections()
                    try:
                        ports = Ports()
                        service = Jobs(
                            DjangoJobsRepository(),
                            DjangoAccountLocks(),
                            ports,
                            Profiles(),
                            ports,
                            ports,
                            ports,
                            ports,
                            DjangoUnitOfWork,
                            CoachConfiguration(True, True, "deepseek-v4-flash"),
                        )
                        barrier.wait(timeout=10)
                        return service.settle(
                            job.id,
                            ProviderReply(
                                TokenUsage(1000, 100), "reported", True, None, False, "stop"
                            ),
                        )
                    finally:
                        connections.close_all()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(settle) for _ in range(2)]
                    results = [future.result(timeout=20) for future in futures]
                self.assertEqual([result.status for result in results], ["failed", "failed"])
                self.assertEqual(results[0], results[1])
                usage.refresh_from_db()
                self.assertEqual(usage.spent, Decimal("0.00042000"))
                self.assertEqual(usage.reserved, 0)
                if fund is not None:
                    fund.refresh_from_db()
                    self.assertEqual(fund.spent, Decimal("0.00042000"))
                    self.assertEqual(fund.reserved, 0)

    def test_two_workers_claim_different_jobs_without_partial_writes(self) -> None:
        owner = AccountId(get_user_model().objects.create_user(username="claim").pk)
        usage = UsagePeriod.objects.create(owner_id=owner, key="claim")
        repo = DjangoJobsRepository()
        for number in (1, 2):
            repo.create(
                Job(
                    JobId(UUID(int=number)),
                    owner,
                    AIRequestKey(UUID(int=number)),
                    "short",
                    "q",
                    CONTEXT,
                    UsagePeriodId(usage.pk),
                    None,
                    reservation_for("short"),
                    "model",
                )
            )
        barrier = Barrier(2)

        def claim() -> JobId:
            close_old_connections()
            try:
                with DjangoUnitOfWork() as work:
                    job = DjangoJobsRepository().claim(NOW)
                    assert job is not None
                    barrier.wait(timeout=10)
                    work.commit()
                return job.id
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(claim) for _ in range(2)]
            ids = [future.result(timeout=20) for future in futures]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(AIJob.objects.filter(status="running").count(), 2)
        self.assertEqual(AIJob.objects.filter(status="pending").count(), 0)
