"""Shared durable-job repository contract for fake and Django adapters."""

from dataclasses import replace
from decimal import Decimal
from typing import Callable
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from basis.modules.coach.application.jobs import CoachConfiguration, Enqueue, Jobs, JobsRepository
from basis.modules.coach.domain.jobs import (
    HISTORICAL_PRICING,
    CoachInvalid,
    Job,
    ProviderReply,
    Reconcile,
    Reconciliation,
    TokenUsage,
)
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
                request_key=AIRequestKey(uuid4()),
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
        reply = ProviderReply(
            TokenUsage(1000, 100, 200), "deepseek-v4-flash", True, None, False, "stop"
        )
        result = self.service.settle(job.id, reply)
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.error)
        self.assertEqual(result.answer, "")
        self.assertEqual(result.cost, Decimal("0.00036120"))
        self.assertEqual(
            (result.input_tokens, result.output_tokens, result.cache_hit_tokens), (1000, 100, 200)
        )
        self.assertEqual(result.reported_model, "deepseek-v4-flash")
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
            job.id, ProviderReply(TokenUsage(10, 2), "deepseek-v4-flash", True, None, True, "stop")
        )
        self.assertEqual((result.status, result.answer), ("failed", ""))

    def test_contract_unknown_cost_retains_trial_reservations(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(True)
        reply = ProviderReply(None, "deepseek-v4-flash", True, None, False, "stop")
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
        reply = ProviderReply(TokenUsage(1000, 100), "deepseek-v4-flash", True, None, False, "stop")
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
        valid = ProviderReply(TokenUsage(10, 2), "deepseek-v4-flash", True, "answer", True, "stop")
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
            ProviderReply(TokenUsage(10, 2), "deepseek-v4-flash", True, None, False, "stop"),
            "failed",
        )

    def _uncertain_job(self, trial: bool = False) -> Job:
        job = self._running_reserved_job(trial)
        return self.service.settle(job.id)

    def _decision(self, job: Job, *, charged: bool = False) -> Reconcile:
        return Reconcile(
            job.id,
            "decision-1",
            "admin:test",
            "fixture:provider-ledger/1",
            "Synthetic external ledger evidence, never a live reconciliation.",
            "usage" if charged else "no_charge",
            not charged,
            "deepseek-v4-flash" if charged else "",
            TokenUsage(1000, 100, 200) if charged else None,
        )

    def test_contract_freezes_effective_rates_limits_and_models_across_enqueue_settle(self) -> None:
        assert isinstance(self, TestCase)
        original = self.service.config
        first = self.service.enqueue(
            Enqueue(self.owner, "short", "question", AIRequestKey(uuid4()))
        )
        changed = replace(
            HISTORICAL_PRICING,
            version="synthetic-rate-change",
            input_rate=Decimal("0.60") / 1000000,
            allowed_models=("synthetic-next-model",),
            short_limits=(5000, 2000),
        )
        self.service.config = CoachConfiguration(True, True, "synthetic-next-model", changed)
        second = self.service.enqueue(
            Enqueue(self.owner, "short", "question", AIRequestKey(uuid4()))
        )
        self.assertEqual(self.repository.job(first.id).pricing, original.pricing.freeze("short"))
        self.assertEqual(first.reservation, Decimal("0.003"))
        self.assertEqual(second.reservation, Decimal("0.0054"))
        with self.uow_factory() as work:
            self.repository.save_job(replace(first, status="running"))
            self.repository.save_job(replace(second, status="running"))
            work.commit()
        for job, model, expected in (
            (first, first.requested_model, Decimal("0.00036120")),
            (second, second.requested_model, Decimal("0.00060120")),
        ):
            result = self.service.settle(
                job.id, ProviderReply(TokenUsage(1000, 100, 200), model, True, "ok", True, "stop")
            )
            self.assertEqual(result.cost, expected)
        self.assertEqual(self.repository.usage(first.usage_period).reserved, 0)

    def test_contract_unexpected_model_is_not_success_and_never_invents_cost(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(True)
        result = self.service.settle(
            job.id, ProviderReply(TokenUsage(1000, 100), "reported", True, "ok", True, "stop")
        )
        self.assertEqual(
            (result.status, result.cost, result.reported_model), ("uncertain", None, "reported")
        )
        self.assertEqual(result.input_tokens, 1000)
        self.assertEqual(self.repository.usage(job.usage_period).reserved, job.reservation)
        self.assertEqual(self.repository.usage(job.usage_period).spent, 0)
        self.assertTrue(self.repository.blocked())
        record = self.service.reconcile(self._decision(result, charged=True), apply=True)
        self.assertEqual(record.outcome, "retained")
        self.assertEqual(self.repository.job(job.id).status, "uncertain")
        self.assertEqual(
            self.service.reconcile(
                replace(self._decision(result), key="no-charge-mismatch"), apply=True
            ).outcome,
            "retained",
        )

    def test_contract_missing_snapshot_is_held_before_provider_dispatch(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(False)
        # Construct unverifiable historical data at creation; never overwrite snapshots.
        unknown = replace(
            job,
            id=JobId(uuid4()),
            request_key=AIRequestKey(uuid4()),
            pricing=None,
            pricing_version="unknown",
            status="pending",
        )
        with self.uow_factory() as work:
            self.repository.save_job(replace(job, status="failed"))
            self.repository.create(unknown)
            work.commit()
        with patch.object(self.service.provider, "call") as call:
            self.assertTrue(self.service.process_one())
            call.assert_not_called()
        self.assertEqual(self.repository.job(unknown.id).status, "uncertain")
        self.assertTrue(self.repository.blocked())
        held = self.service.reconcile(self._decision(unknown, charged=True), apply=True)
        self.assertEqual(held.outcome, "retained")
        # Explicit verified no-charge evidence can release without inventing a tariff.
        released = self.service.reconcile(
            replace(self._decision(unknown), key="verified-no-charge"), apply=True
        )
        self.assertEqual((released.outcome, released.cost), ("released", 0))

    def _assert_reconciliation(self, trial: bool, charged: bool) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job(trial)
        command = self._decision(job, charged=charged)
        before = self.repository.usage(job.usage_period)
        self.service.config = replace(
            self.service.config,
            enabled=False,
            pricing=replace(
                HISTORICAL_PRICING,
                version="synthetic-new-policy",
                input_rate=Decimal("0.60") / 1000000,
                allowed_models=("synthetic-new-model",),
            ),
        )
        with self.uow_factory() as work:
            self.repository.block()
            work.commit()
        with patch.object(self.service.provider, "call") as call:
            preview = self.service.reconcile(command)
            self.assertEqual(self.repository.job(job.id), job)
            self.assertEqual(self.repository.usage(before.id), before)
            self.assertIsNone(self.repository.reconciliation(job.id, command.key))
            record = self.service.reconcile(command, apply=True)
            self.assertEqual(record, preview)
            self.assertEqual(self.service.reconcile(command, apply=True), record)
            call.assert_not_called()
        cost = Decimal("0.00036120") if charged else Decimal(0)
        self.assertEqual(record.cost, cost)
        self.assertEqual(record.outcome, "charged" if charged else "released")
        self.assertEqual(self.repository.reconciliation(job.id, command.key), record)
        usage = self.repository.usage(job.usage_period)
        self.assertEqual((usage.reserved, usage.spent), (0, cost))
        self.assertEqual(
            (usage.short_count, usage.plan_count), (before.short_count, before.plan_count)
        )
        if job.trial_fund is not None:
            fund = self.repository.fund(job.trial_fund)
            self.assertEqual((fund.reserved, fund.spent), (0, cost))
        self.assertEqual(self.repository.job(job.id).status, "failed")
        self.assertTrue(self.repository.blocked())
        # New decision cannot release or charge the same reservation again.
        again = self.service.reconcile(replace(command, key="decision-2"), apply=True)
        self.assertEqual(again.outcome, "retained")
        self.assertEqual(self.repository.usage(usage.id), usage)
        with self.assertRaisesRegex(CoachInvalid, "otra decisión"):
            self.service.reconcile(replace(command, evidence="changed evidence"), apply=True)

    def test_contract_reconcile_paid_known_usage(self) -> None:
        self._assert_reconciliation(False, True)

    def test_contract_reconcile_trial_known_usage(self) -> None:
        self._assert_reconciliation(True, True)

    def test_contract_reconcile_paid_no_charge(self) -> None:
        self._assert_reconciliation(False, False)

    def test_contract_reconcile_trial_no_charge(self) -> None:
        self._assert_reconciliation(True, False)

    def test_contract_reconcile_requires_explicit_no_charge_evidence(self) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job()
        command = self._decision(job)
        for invalid in (
            replace(command, actor=""),
            replace(command, reference=""),
            replace(command, evidence=" "),
            replace(command, key=""),
            replace(command, confirmed_no_charge=False),
            replace(command, usage=TokenUsage(0, 0)),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(CoachInvalid):
                self.service.reconcile(invalid, apply=True)
        self.assertEqual(self.repository.job(job.id), job)
        self.assertIsNone(self.repository.reconciliation(job.id, command.key))

    def test_contract_out_of_limits_and_discrepant_usage_remain_held_and_audited(self) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job(True)
        before = self.repository.usage(job.usage_period)
        for number, usage in enumerate(
            (
                TokenUsage(-1, 0),
                TokenUsage(1, 0, 2),
                TokenUsage(4001, 0),
                TokenUsage(1, 1501),
                TokenUsage(True, 0),
                TokenUsage(10**40, 0),
                TokenUsage(0, 10**40),
                TokenUsage(1, 0, 10**40),
            )
        ):
            command = replace(
                self._decision(job, charged=True), key=f"invalid-{number}", usage=usage
            )
            record = self.service.reconcile(command, apply=True)
            self.assertEqual((record.outcome, record.cost), ("retained", None))
            self.assertEqual(self.repository.reconciliation(job.id, command.key), record)
            self.assertEqual(self.service.reconcile(command, apply=True), record)
        self.assertEqual(self.repository.job(job.id), job)
        self.assertEqual(self.repository.usage(before.id), before)

    def test_contract_reconciliation_uses_original_period_after_renewal(self) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job(True)
        with self.uow_factory() as work:
            newer = self.repository.lock_period(self.owner, "renewed-paid-period", False)
            month = self.repository.lock_month("2027-01")
            work.commit()
        with patch.object(
            self.service.billing, "get", side_effect=AssertionError("must use original ledger")
        ):
            self.service.reconcile(self._decision(job, charged=True), apply=True)
        self.assertEqual(self.repository.usage(newer.id), newer)
        self.assertEqual(self.repository.fund(month.id), month)
        self.assertEqual(self.repository.usage(job.usage_period).spent, Decimal("0.00036120"))

    def test_contract_audit_failure_rolls_back_job_usage_and_trial_fund(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self._uncertain_job(trial)
            before = self.repository.usage(job.usage_period)
            fund = self.repository.fund(job.trial_fund) if job.trial_fund else None
            command = self._decision(job, charged=True)
            append = self.repository.add_reconciliation

            def append_then_fail(record: Reconciliation) -> None:
                append(record)
                raise RuntimeError("audit failed")

            with patch.object(self.repository, "add_reconciliation", side_effect=append_then_fail):
                with self.assertRaisesRegex(RuntimeError, "audit failed"):
                    self.service.reconcile(command, apply=True)
            self.assertEqual(self.repository.job(job.id), job)
            self.assertEqual(self.repository.usage(before.id), before)
            self.assertIsNone(self.repository.reconciliation(job.id, command.key))
            if fund is not None:
                self.assertEqual(self.repository.fund(fund.id), fund)

    def test_contract_observed_usage_cannot_be_overridden_to_invent_cost(self) -> None:
        assert isinstance(self, TestCase)
        job = self._running_reserved_job(False)
        result = self.service.settle(
            job.id, ProviderReply(TokenUsage(500, 20), "deepseek-v4-flash", False)
        )
        command = self._decision(result, charged=True)
        self.assertEqual(self.service.reconcile(command, apply=True).outcome, "retained")
        corrected = replace(command, key="matching-ledger", usage=TokenUsage(500, 20))
        record = self.service.reconcile(corrected, apply=True)
        self.assertEqual(record.cost, Decimal("0.00017400"))

    def test_contract_reconciliation_cannot_overdraw_incomplete_reserves(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self._uncertain_job(trial)
            with self.uow_factory() as work:
                usage = self.repository.lock_usage(job.usage_period)
                usage.reserved = Decimal(0)
                self.repository.save_usage(usage)
                work.commit()
            record = self.service.reconcile(self._decision(job, charged=True), apply=True)
            self.assertEqual((record.outcome, record.cost), ("retained", None))
            self.assertEqual(self.repository.usage(job.usage_period).reserved, 0)
            self.assertEqual(self.repository.usage(job.usage_period).spent, 0)
            self.assertEqual(self.repository.job(job.id), job)
            if job.trial_fund:
                self.assertEqual(self.repository.fund(job.trial_fund).reserved, job.reservation)

    def test_contract_no_charge_cannot_override_out_of_bounds_partial_observations(self) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job()
        with self.uow_factory() as work:
            job = replace(job, input_tokens=4001)
            self.repository.save_job(job)
            work.commit()
        record = self.service.reconcile(self._decision(job), apply=True)
        self.assertEqual((record.outcome, record.cost), ("retained", None))
        self.assertEqual(self.repository.usage(job.usage_period).reserved, job.reservation)

    def test_contract_reconciliation_keeps_consumed_action_quota(self) -> None:
        from basis.modules.coach.domain.jobs import require_budget

        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self._uncertain_job(trial)
            with self.uow_factory() as work:
                usage = self.repository.lock_usage(job.usage_period)
                usage.short_count = 5 if trial else 200
                self.repository.save_usage(usage)
                fund = self.repository.lock_month("2026-11")
                work.commit()
            self.service.reconcile(self._decision(job), apply=True)
            usage = self.repository.usage(job.usage_period)
            self.assertEqual(usage.short_count, 5 if trial else 200)
            with self.assertRaisesRegex(CoachInvalid, "acciones IA"):
                require_budget("short", usage, fund, trial)

    def test_contract_uncertain_with_preexisting_cost_is_not_charged_or_released_again(
        self,
    ) -> None:
        assert isinstance(self, TestCase)
        job = self._uncertain_job()
        with self.uow_factory() as work:
            job = replace(job, cost=Decimal("0.0001"))
            self.repository.save_job(job)
            work.commit()
        before = self.repository.usage(job.usage_period)
        record = self.service.reconcile(self._decision(job, charged=True), apply=True)
        self.assertEqual((record.outcome, record.cost), ("retained", None))
        self.assertEqual(self.repository.usage(before.id), before)
        self.assertEqual(self.repository.job(job.id), job)
