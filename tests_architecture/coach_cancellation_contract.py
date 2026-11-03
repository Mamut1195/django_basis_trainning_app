"""One cancellation contract executed against fake and PostgreSQL repositories."""

from dataclasses import replace
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from basis.modules.coach.application.jobs import Enqueue, Jobs
from basis.modules.coach.domain.jobs import (
    CancellationConflict,
    CoachInvalid,
    Job,
    JobKind,
    JobNotFound,
)
from basis.shared.identifiers import AccountId, AIRequestKey, JobId


class CancellationContract:
    service: Jobs
    owner: AccountId
    other: AccountId

    def pending(self, trial: bool = False, kind: JobKind = "short") -> Job:
        state = self.service.billing.get(self.owner)
        assert state is not None
        with patch.object(
            self.service.billing,
            "lock",
            return_value=replace(state, status="trialing" if trial else "active"),
        ):
            return self.service.enqueue(
                Enqueue(self.owner, kind, "question", AIRequestKey(uuid4()))
            )

    def test_cancel_paid_trial_short_plan_twice_and_enqueue_replay_without_dispatch(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            for kind in ("short", "plan"):
                with self.subTest(trial=trial, kind=kind):
                    job = self.pending(trial, kind)
                    before = self.service.repo.usage(job.usage_period)
                    fund = self.service.repo.fund(job.trial_fund) if job.trial_fund else None
                    with (
                        patch.object(self.service.provider, "call") as call,
                        patch.object(self.service.proposals, "complete") as proposal,
                    ):
                        result = self.service.cancel(self.owner, job.id)
                        self.assertEqual((result.status, result.cost), ("cancelled", 0))
                        self.assertEqual(result.completed_at, self.service.clock.now())
                        self.assertEqual(self.service.cancel(self.owner, job.id), result)
                        replay = self.service.enqueue(
                            Enqueue(self.owner, kind, "question", job.request_key)
                        )
                        self.assertEqual(replay, result)
                        self.assertFalse(self.service.process_one())
                        call.assert_not_called()
                        proposal.assert_not_called()
                    after = self.service.repo.usage(job.usage_period)
                    self.assertEqual(after.reserved, before.reserved - job.reservation)
                    self.assertEqual(after.spent, before.spent)
                    self.assertEqual(after.short_count, before.short_count - (kind == "short"))
                    self.assertEqual(after.plan_count, before.plan_count - (kind == "plan"))
                    if fund:
                        self.assertEqual(
                            self.service.repo.fund(fund.id),
                            replace(fund, reserved=fund.reserved - job.reservation),
                        )

    def test_cancel_original_ledgers_with_later_periods_funds_and_nonzero_spent(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self.pending(trial)
            with self.service.uow() as work:
                old = self.service.repo.lock_usage(job.usage_period)
                old.spent, old.plan_count = Decimal("0.001"), 1
                self.service.repo.save_usage(old)
                if job.trial_fund:
                    original_fund = self.service.repo.lock_fund(job.trial_fund)
                    original_fund.spent = Decimal("0.01")
                    self.service.repo.save_fund(original_fund)
                later = self.service.repo.lock_period(self.owner, "later-period", False)
                later.spent, later.reserved, later.short_count = Decimal("0.02"), Decimal("0.04"), 3
                self.service.repo.save_usage(later)
                later_fund = self.service.repo.lock_month("2099-01")
                later_fund.spent, later_fund.reserved = Decimal("0.1"), Decimal("0.2")
                self.service.repo.save_fund(later_fund)
                work.commit()
            self.service.cancel(self.owner, job.id)
            self.assertEqual(self.service.repo.usage(later.id), later)
            self.assertEqual(self.service.repo.fund(later_fund.id), later_fund)
            self.assertEqual(
                self.service.repo.usage(old.id), replace(old, reserved=Decimal(0), short_count=0)
            )
            if job.trial_fund:
                self.assertEqual(
                    self.service.repo.fund(job.trial_fund),
                    replace(original_fund, reserved=Decimal(0)),
                )

    def test_foreign_and_absent_do_not_reveal_or_adjust_job(self) -> None:
        assert isinstance(self, TestCase)
        job = self.pending(True)
        with self.assertRaises(JobNotFound):
            self.service.cancel(self.other, job.id)
        with self.assertRaises(JobNotFound):
            self.service.cancel(self.owner, JobId(uuid4()))
        self.assertEqual(self.service.repo.job(job.id), job)
        self.assertEqual(self.service.repo.usage(job.usage_period).reserved, job.reservation)

    def test_all_nonpending_states_and_any_open_attempt_conflict_without_mutation(self) -> None:
        assert isinstance(self, TestCase)
        job = self.pending(True)
        for status in (
            "running",
            "uncertain",
            "succeeded",
            "failed",
            "unknown",
            "pending",
            "cancelled",
        ):
            for attempt in (None, uuid4()):
                if status in ("pending", "cancelled") and attempt is None:
                    continue
                changed = replace(job, status=status, attempt_id=attempt)
                with self.service.uow() as work:
                    self.service.repo.save_job(changed)
                    work.commit()
                before = self.service.repo.usage(job.usage_period)
                fund = self.service.repo.fund(job.trial_fund) if job.trial_fund else None
                with self.assertRaises(CancellationConflict):
                    self.service.cancel(self.owner, job.id)
                self.assertEqual(self.service.repo.job(job.id), changed)
                self.assertEqual(self.service.repo.usage(before.id), before)
                if fund:
                    self.assertEqual(self.service.repo.fund(fund.id), fund)

    def test_release_invariants_and_final_write_rollback_all_ledgers(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self.pending(trial)
            usage = self.service.repo.usage(job.usage_period)
            fund = self.service.repo.fund(job.trial_fund) if job.trial_fund else None
            for bad in (
                replace(usage, reserved=Decimal(0)),
                replace(usage, short_count=0),
                replace(usage, plan_count=-1),
                replace(usage, spent=Decimal("2")),
                replace(usage, owner=self.other),
                replace(usage, is_trial=not trial),
            ):
                with patch.object(self.service.repo, "lock_usage", return_value=bad):
                    with self.assertRaises(CoachInvalid):
                        self.service.cancel(self.owner, job.id)
                self.assertEqual(self.service.repo.job(job.id), job)
                self.assertEqual(self.service.repo.usage(usage.id), usage)
                if fund:
                    self.assertEqual(self.service.repo.fund(fund.id), fund)
            if fund:
                for bad_fund in (replace(fund, reserved=Decimal(0)), replace(fund, spent=fund.cap)):
                    with patch.object(self.service.repo, "lock_fund", return_value=bad_fund):
                        with self.assertRaises(CoachInvalid):
                            self.service.cancel(self.owner, job.id)
                    self.assertEqual(self.service.repo.usage(usage.id), usage)
            save = self.service.repo.save_job

            def fail_after_save(changed: Job) -> None:
                save(changed)
                raise RuntimeError("synthetic cancellation rollback")

            with patch.object(self.service.repo, "save_job", side_effect=fail_after_save):
                with self.assertRaisesRegex(RuntimeError, "cancellation rollback"):
                    self.service.cancel(self.owner, job.id)
            self.assertEqual(self.service.repo.job(job.id), job)
            self.assertEqual(self.service.repo.usage(usage.id), usage)
            if fund:
                self.assertEqual(self.service.repo.fund(fund.id), fund)

    def test_expired_disabled_and_blocked_can_cancel_without_commercial_or_sport_gate(self) -> None:
        assert isinstance(self, TestCase)
        job = self.pending(True)
        self.service.config = replace(
            self.service.config, enabled=False, credential_configured=False
        )
        with (
            patch.object(self.service.billing, "get", side_effect=AssertionError("billing read")),
            patch.object(self.service.billing, "lock", side_effect=AssertionError("billing gate")),
            patch.object(
                self.service.contexts, "snapshot", side_effect=AssertionError("sport gate")
            ),
        ):
            self.assertEqual(self.service.cancel(self.owner, job.id).status, "cancelled")

    def test_lock_order_and_cancelled_settlement_never_releases_again(self) -> None:
        assert isinstance(self, TestCase)
        for trial in (False, True):
            job = self.pending(trial)
            recorder = Mock()
            with (
                patch.object(
                    self.service.repo, "lock_fund", wraps=self.service.repo.lock_fund
                ) as fund,
                patch.object(
                    self.service.accounts, "lock", wraps=self.service.accounts.lock
                ) as account,
                patch.object(
                    self.service.repo, "lock_job", wraps=self.service.repo.lock_job
                ) as locked_job,
                patch.object(
                    self.service.repo, "lock_usage", wraps=self.service.repo.lock_usage
                ) as usage,
            ):
                for label, wrapped in (
                    ("fund", fund),
                    ("account", account),
                    ("job", locked_job),
                    ("usage", usage),
                ):
                    recorder.attach_mock(wrapped, label)
                cancelled = self.service.cancel(self.owner, job.id)
                order = [call[0] for call in recorder.mock_calls]
            self.assertEqual(order, (["fund"] if trial else []) + ["account", "job", "usage"])
            before = self.service.repo.usage(job.usage_period)
            for token in (None, uuid4()):
                self.assertEqual(
                    self.service.settle(job.id, definitive=True, attempt_id=token), cancelled
                )
            self.assertEqual(self.service.repo.usage(before.id), before)
