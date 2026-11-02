"""Shared durable-job repository contract for fake and Django adapters."""

from dataclasses import replace
from decimal import Decimal
from typing import Callable
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from basis.modules.coach.application.jobs import Enqueue, Jobs, JobsRepository
from basis.modules.coach.domain.jobs import Job, ProviderReply, TokenUsage
from basis.shared.identifiers import AccountId, AIRequestKey, JobId
from basis.shared.ports import UnitOfWork


class JobsContract:
    repository: JobsRepository
    owner: AccountId
    other: AccountId
    uow_factory: Callable[[], UnitOfWork]
    sample: Job

    def test_contract_commit_ids_owner_and_rollback(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory() as work:
            self.repository.create(self.sample)
            work.commit()
        found = self.repository.existing(self.owner, self.sample.request_key)
        assert found is not None
        self.assertEqual(found.id, self.sample.id)
        self.assertEqual(found.context, self.sample.context)
        self.assertIsNone(self.repository.existing(self.other, self.sample.request_key))
        with self.uow_factory():
            self.repository.save_job(replace(found, status="failed"))
        self.assertEqual(self.repository.job(found.id).status, "pending")
        with self.assertRaises(ValueError), self.uow_factory() as work:
            self.repository.save_job(replace(found, status="failed"))
            work.commit()
            raise ValueError("rollback even after commit request")
        self.assertEqual(self.repository.job(found.id).status, "pending")

    def test_contract_claim_once_and_stale_never_retries(self) -> None:
        assert isinstance(self, TestCase)
        with self.uow_factory() as work:
            self.repository.create(self.sample)
            work.commit()
        now = self.sample.context.snapshot_at
        with self.uow_factory() as work:
            claimed = self.repository.claim(now)
            work.commit()
        assert claimed is not None
        self.assertEqual(claimed.id, self.sample.id)
        with self.uow_factory() as work:
            self.assertIsNone(self.repository.claim(now))
            self.repository.quarantine(now.replace(year=now.year + 1))
            work.commit()
        self.assertEqual(self.repository.job(self.sample.id).status, "uncertain")
        with self.uow_factory() as work:
            self.assertIsNone(self.repository.claim(now))
            work.commit()


class JobsSettlementContract:
    """Identical accounting, worker continuity and rollback on fake/ORM UoWs."""

    service: Jobs
    repository: JobsRepository
    owner: AccountId
    sample: Job
    uow_factory: Callable[[], UnitOfWork]

    def _running_reserved_job(self, trial: bool) -> Job:
        with self.uow_factory() as work:
            usage = self.repository.lock_period(self.owner, str(uuid4()), trial)
            usage.reserved += self.sample.reservation
            self.repository.save_usage(usage)
            fund = self.repository.lock_month(self.sample.context.snapshot_at.strftime("%Y-%m"))
            if trial:
                fund.reserved += self.sample.reservation
                self.repository.save_fund(fund)
            job = replace(
                self.sample,
                id=JobId(uuid4()),
                usage_period=usage.id,
                trial_fund=fund.id if trial else None,
                status="running",
            )
            self.repository.create(job)
            # Explicitly save running state after the repository's creation step.
            self.repository.save_job(job)
            work.commit()
        return job

    def _assert_null_settlement(self, trial: bool) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(trial)
        reply = ProviderReply(TokenUsage(1000, 100, 200), "reported", True, None, False, "stop")
        result = self.service.settle(job.id, reply)
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.error)
        self.assertEqual(result.answer, "")
        self.assertEqual(result.cost, Decimal("0.00036120"))
        self.assertEqual(
            (result.input_tokens, result.output_tokens, result.cache_hit_tokens), (1000, 100, 200)
        )
        self.assertEqual(result.reported_model, "reported")
        self.assertEqual(result.completed_at, self.service.clock.now())
        self.assertEqual(self.repository.job(job.id), result)
        usage = self.repository.usage(job.usage_period)
        self.assertEqual((usage.reserved, usage.spent), (0, result.cost))
        fund = self.repository.fund(job.trial_fund) if job.trial_fund is not None else None
        if fund is not None:
            self.assertEqual((fund.reserved, fund.spent), (0, result.cost))
        for data, definitive in ((reply, False), (None, False), (None, True)):
            self.assertEqual(self.service.settle(job.id, data, definitive=definitive), result)
        self.assertEqual(self.repository.usage(job.usage_period), usage)
        if fund is not None:
            self.assertEqual(self.repository.fund(fund.id), fund)
        self.assertFalse(self.repository.blocked())

    def test_contract_null_paid_settles_once(self) -> None:
        self._assert_null_settlement(False)

    def test_contract_null_trial_settles_usage_and_fund_once(self) -> None:
        self._assert_null_settlement(True)

    def test_contract_null_cannot_succeed_with_inconsistent_text_flag(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(False)
        result = self.service.settle(
            job.id, ProviderReply(TokenUsage(10, 2), "reported", True, None, True, "stop")
        )
        self.assertEqual((result.status, result.answer), ("failed", ""))

    def test_contract_unknown_cost_retains_trial_reservations(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(True)
        reply = ProviderReply(None, "reported", True, None, False, "stop")
        result = self.service.settle(job.id, reply)
        self.assertEqual(result.status, "uncertain")
        self.assertIsNone(result.cost)
        self.assertEqual(result.answer, "")
        usage = self.repository.usage(job.usage_period)
        self.assertEqual((usage.spent, usage.reserved), (0, job.reservation))
        assert job.trial_fund is not None
        fund = self.repository.fund(job.trial_fund)
        self.assertEqual((fund.spent, fund.reserved), (0, job.reservation))
        self.service.settle(job.id, definitive=True)
        self.assertEqual(self.repository.usage(usage.id), usage)
        self.assertEqual(self.repository.fund(fund.id), fund)

    def _assert_settlement_rollback(self, trial: bool) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(trial)
        usage = self.repository.usage(job.usage_period)
        fund = self.repository.fund(job.trial_fund) if job.trial_fund is not None else None
        reply = ProviderReply(TokenUsage(1000, 100), "reported", True, None, False, "stop")
        with patch.object(
            self.repository, "save_job", side_effect=RuntimeError("final write failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "final write failed"):
                self.service.settle(job.id, reply)
        self.assertEqual(self.repository.job(job.id), job)
        self.assertEqual(self.repository.usage(usage.id), usage)
        if fund is not None:
            self.assertEqual(self.repository.fund(fund.id), fund)
        # Persist the already received response; never call the provider again.
        result = self.service.settle(job.id, reply)
        self.assertEqual(result.status, "failed")
        self.assertEqual(self.repository.usage(usage.id).spent, result.cost)
        self.assertEqual(self.repository.usage(usage.id).reserved, 0)
        self.service.settle(job.id, reply)
        self.assertEqual(self.repository.usage(usage.id).spent, result.cost)
        if fund is not None:
            self.assertEqual(self.repository.fund(fund.id).spent, result.cost)
            self.assertEqual(self.repository.fund(fund.id).reserved, 0)

    def test_contract_paid_settlement_rolls_back_all_writes(self) -> None:
        self._assert_settlement_rollback(False)

    def test_contract_trial_settlement_rolls_back_all_writes(self) -> None:
        self._assert_settlement_rollback(True)

    def _assert_worker_continues(self, first_reply: ProviderReply | None, status: str) -> None:
        assert isinstance(self, TestCase)
        first, second = (
            self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))
            for _ in range(2)
        )
        valid = ProviderReply(TokenUsage(10, 2), "reported", True, "answer", True, "stop")
        with patch.object(self.service.provider, "call", side_effect=[first_reply, valid]) as call:
            self.assertTrue(self.service.process_one())
            self.assertTrue(self.service.process_one())
            self.assertFalse(self.service.process_one())
            self.assertEqual(call.call_count, 2)
        failed, succeeded = self.repository.job(first.id), self.repository.job(second.id)
        self.assertEqual((failed.status, succeeded.status), (status, "succeeded"))
        self.assertEqual(succeeded.answer, "answer")
        self.assertEqual(failed.answer, "")
        self.assertIsNotNone(failed.completed_at)
        self.assertFalse(self.repository.blocked())
        usage = self.repository.usage(first.usage_period)
        self.assertEqual(usage.reserved, first.reservation if status == "uncertain" else 0)
        self.assertEqual(usage.spent, (failed.cost or Decimal(0)) + (succeeded.cost or Decimal(0)))
        self.service.settle(first.id, valid)
        self.assertEqual(self.repository.usage(usage.id), usage)

    def test_contract_ambiguous_response_does_not_stop_next_job_or_retry(self) -> None:
        self._assert_worker_continues(None, "uncertain")

    def test_contract_null_response_does_not_stop_next_job_or_retry(self) -> None:
        self._assert_worker_continues(
            ProviderReply(TokenUsage(10, 2), "reported", True, None, False, "stop"), "failed"
        )
