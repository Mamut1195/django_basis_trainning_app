"""Administrative accounting and immutable storage on disposable test databases."""

import json
from dataclasses import replace
from io import StringIO
from typing import cast
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.db.models import Sum
from django.test import TestCase

from basis.bootstrap.coach import jobs
from basis.bootstrap.tests.test_coach_edges import account
from basis.modules.coach.adapters.jobs import decode_pricing, encode_pricing
from basis.modules.coach.adapters.models import (
    AIJob,
    AIReconciliation,
    AIServiceState,
    TrialFund,
    UsagePeriod,
)
from basis.modules.coach.domain.jobs import (
    HISTORICAL_PRICING,
    Job,
    ProviderReply,
    Reconcile,
    TokenUsage,
    reservation_for,
)
from basis.shared.identifiers import AccountId, AIRequestKey, JobId, TrialFundId, UsagePeriodId
from tests_architecture.test_coach_jobs import CONTEXT


class ReconciliationCommandTests(TestCase):
    def setUp(self) -> None:
        owner = account("reconcile-command")
        usage = UsagePeriod.objects.create(
            owner=owner, key="original", reserved="0.003", short_count=1
        )
        self.service = jobs()
        self.job = Job(
            JobId(uuid4()),
            AccountId(owner.pk),
            AIRequestKey(uuid4()),
            "short",
            "private prompt",
            CONTEXT,
            UsagePeriodId(usage.pk),
            None,
            reservation_for("short"),
            "deepseek-v4-flash",
            status="uncertain",
            pricing=HISTORICAL_PRICING.freeze("short"),
        )
        self.service.repo.create(self.job)
        self.service.repo.save_job(self.job)
        AIServiceState.objects.create(blocked=True)

    def command(self, *extra: str) -> dict[str, object]:
        output = StringIO()
        call_command("reconcile_ai_job", str(self.job.id), *extra, stdout=output)
        return cast(dict[str, object], json.loads(output.getvalue()))

    def arguments(self) -> tuple[str, ...]:
        return (
            "--key",
            "ledger-1",
            "--actor",
            "admin:test",
            "--reference",
            "fixture:ledger",
            "--evidence",
            "Synthetic confirmed no-charge record",
            "--decision",
            "no_charge",
            "--confirmed-no-charge",
        )

    def test_query_and_default_dry_run_do_not_apply_or_contact_provider(self) -> None:
        with patch(
            "basis.modules.coach.adapters.provider.DeepSeekProvider.call",
            side_effect=AssertionError("forbidden"),
        ):
            query = self.command()
            self.assertEqual(query["mode"], "query")
            self.assertNotIn("private prompt", str(query))
            self.assertEqual(self.command(*self.arguments())["mode"], "dry-run")
            self.assertEqual(self.command(*self.arguments(), "--dry-run")["outcome"], "released")
        self.assertEqual(self.service.repo.job(self.job.id), self.job)
        self.assertEqual(
            self.service.repo.usage(self.job.usage_period).reserved, self.job.reservation
        )
        self.assertFalse(AIReconciliation.objects.exists())

    def test_apply_is_explicit_audited_idempotent_and_never_unblocks(self) -> None:
        with self.assertRaises(CommandError):
            self.command("--apply")
        with self.assertRaises(CommandError):
            self.command("--decision", "no_charge", "--apply")
        result = self.command(*self.arguments(), "--apply")
        self.assertEqual(result["outcome"], "released")
        self.assertEqual(self.command(*self.arguments(), "--apply"), result)
        self.assertEqual(AIReconciliation.objects.count(), 1)
        record = AIReconciliation.objects.get()
        self.assertEqual((record.actor, record.reference), ("admin:test", "fixture:ledger"))
        self.assertEqual(self.service.repo.usage(self.job.usage_period).reserved, 0)
        self.assertTrue(self.service.repo.blocked())
        query = self.command("--key", "ledger-1")
        record_data = query["reconciliation"]
        assert isinstance(record_data, dict)
        self.assertEqual((record_data["actor"], record_data["outcome"]), ("admin:test", "released"))

    def test_known_usage_requires_all_counts_and_valid_model_and_retains_bad_usage(self) -> None:
        base = (
            "--key",
            "usage-1",
            "--actor",
            "admin:test",
            "--reference",
            "fixture:usage",
            "--evidence",
            "Synthetic usage record",
            "--decision",
            "usage",
        )
        with self.assertRaises(CommandError):
            self.command(*base, "--input-tokens", "1", "--output-tokens", "1", "--apply")
        counts = ("--input-tokens", "1000", "--output-tokens", "100", "--cache-hits", "200")
        held = self.command(*base, *counts, "--reported-model", "reported", "--apply")
        self.assertEqual((held["outcome"], held["cost"]), ("retained", None))
        with self.assertRaises(CommandError):
            self.command(*base, *counts, "--reported-model", "deepseek-v4-flash", "--apply")
        corrected = tuple("usage-2" if arg == "usage-1" else arg for arg in base)
        charged = self.command(
            *corrected, *counts, "--reported-model", "deepseek-v4-flash", "--apply"
        )
        self.assertEqual((charged["outcome"], charged["cost"]), ("charged", "0.00036120"))

    def test_audit_and_accounting_anchors_are_immutable_in_database(self) -> None:
        self.command(*self.arguments(), "--apply")
        audit = AIReconciliation.objects.get()
        for mutation in (
            lambda: AIReconciliation.objects.filter(pk=audit.pk).update(actor="replacement"),
            lambda: AIReconciliation.objects.filter(pk=audit.pk).delete(),
            lambda: AIJob.objects.filter(pk=self.job.id).update(pricing_version="replacement"),
            lambda: AIJob.objects.filter(pk=self.job.id).update(pricing_snapshot={}),
            lambda: AIJob.objects.filter(pk=self.job.id).update(reservation=0),
            lambda: AIJob.objects.filter(pk=self.job.id).update(requested_model="replacement"),
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                mutation()
        audit.refresh_from_db()
        self.assertEqual(audit.actor, "admin:test")
        self.assertEqual(self.service.repo.job(self.job.id).pricing, self.job.pricing)

    def test_database_rejects_negative_overspent_and_overquota_aggregates(self) -> None:
        for changes in ({"reserved": -1}, {"spent": 1}, {"short_count": 201}, {"plan_count": 9}):
            with self.assertRaises(DatabaseError), transaction.atomic():
                UsagePeriod.objects.filter(pk=self.job.usage_period).update(**changes)
        fund = TrialFund.objects.create(month="2026-11")
        with self.assertRaises(DatabaseError), transaction.atomic():
            TrialFund.objects.filter(pk=fund.pk).update(spent=5, reserved="0.01")
        with self.assertRaises(DatabaseError), transaction.atomic():
            AIJob.objects.filter(pk=self.job.id).update(cost="0.004")

    def test_snapshot_roundtrip_rejects_corrupt_data_without_fallback(self) -> None:
        pricing = HISTORICAL_PRICING.freeze("short")
        self.assertEqual(decode_pricing(encode_pricing(pricing)), pricing)
        data = encode_pricing(pricing)
        assert data is not None
        for field, value in (
            ("input_rate", "NaN"),
            ("input_rate", "1e999999"),
            ("input_rate", "1e-999999"),
            ("output_rate", "-1"),
            ("hit_rate", "0.1"),
            ("input_limit", True),
            ("allowed_models", []),
            ("version", 123),
        ):
            self.assertIsNone(decode_pricing({**data, field: value}))
        self.assertIsNone(decode_pricing({}))

    def test_aggregate_ledger_matches_pending_uncertain_and_effective_settlements(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                usage = UsagePeriod.objects.create(
                    owner_id=self.job.owner,
                    key=f"aggregates-{trial}",
                    is_trial=trial,
                    reserved="0.009",
                    short_count=3,
                )
                fund = (
                    TrialFund.objects.create(month="2027-02", reserved="0.009") if trial else None
                )
                samples = []
                for status in ("pending", "running", "uncertain"):
                    job = replace(
                        self.job,
                        id=JobId(uuid4()),
                        request_key=AIRequestKey(uuid4()),
                        usage_period=UsagePeriodId(usage.pk),
                        trial_fund=TrialFundId(fund.pk) if fund else None,
                        status=status,
                    )
                    self.service.repo.create(job)
                    self.service.repo.save_job(job)
                    samples.append(job)

                def assert_ledger() -> None:
                    rows = AIJob.objects.filter(usage_period=usage)
                    reserved = (
                        rows.filter(status__in=("pending", "running", "uncertain")).aggregate(
                            total=Sum("reservation")
                        )["total"]
                        or 0
                    )
                    spent = (
                        rows.filter(cost__isnull=False).aggregate(total=Sum("cost"))["total"] or 0
                    )
                    usage.refresh_from_db()
                    self.assertEqual((usage.reserved, usage.spent), (reserved, spent))
                    if fund:
                        fund.refresh_from_db()
                        self.assertEqual((fund.reserved, fund.spent), (reserved, spent))

                assert_ledger()
                self.service.settle(
                    samples[1].id,
                    ProviderReply(
                        TokenUsage(100, 10), "deepseek-v4-flash", True, "ok", True, "stop"
                    ),
                )
                assert_ledger()
                command = Reconcile(
                    samples[2].id,
                    "aggregate-release",
                    "admin:test",
                    "fixture:aggregate",
                    "Synthetic no-charge evidence",
                    "no_charge",
                    True,
                )
                self.service.reconcile(command)
                assert_ledger()
                self.service.reconcile(command, apply=True)
                assert_ledger()
                self.service.reconcile(command, apply=True)
                assert_ledger()
                self.assertEqual(usage.short_count, 3)
