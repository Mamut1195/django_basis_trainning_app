"""R7/R5-F01: complete real-worker controls of the simulated settlement oracle."""

from collections.abc import Callable
from decimal import Decimal
from typing import cast
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import F
from django.test import TestCase, override_settings

from basis.bootstrap.tests.mam636_harness import FROZEN_NOW, SimulatedHarness
from basis.bootstrap.tests.mam636_report import CaseResult, coverage, require_technical_success
from basis.bootstrap.tests.test_mam636_review_fixes import save
from basis.modules.coach.adapters.actions import process_one as original_process_one
from basis.modules.coach.adapters.management.commands import process_ai_jobs
from basis.modules.coach.adapters.models import AIJob, UsagePeriod
from basis.modules.training.adapters.models import TrainingPlan


@override_settings(
    AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-fix6-only", DEEPSEEK_MODEL="deepseek-flash"
)
class SettlementOracleTests(TestCase):
    def assert_failure(
        self, harness: SimulatedHarness, name: str, observation: str, writes: list[object]
    ) -> None:
        result = next(r for r in harness.results if r.case.id == "EV-017")
        error = None
        try:
            require_technical_success(harness.results)
        except AssertionError as rejected:
            error = str(rejected)
        save(
            name,
            {
                "writes": writes,
                "report": harness.report(name),
                "guard_rejected": error is not None,
                "guard_error": error,
            },
        )
        self.assertEqual(result.export()["status"], "FAIL")
        self.assertTrue(
            any(o.name == observation and o.status == "FAIL" for o in result.observations)
        )
        self.assertIsNotNone(error)
        self.assertIn("EV-017/", str(error))
        self.assertEqual(coverage(harness.results)["case_denominator"], 17)
        self.assertEqual(coverage(harness.results)["expectation_denominator"], 34)

    def test_spent_erased_once_before_first_snapshot_fails(self) -> None:
        original = original_process_one
        writes: list[object] = []

        def erase_once() -> bool:
            worked = original()
            if worked and not writes:
                job = AIJob.objects.filter(
                    owner__username="636-null_content", status="failed", cost__gt=0
                ).first()
                if job is not None:
                    before = SimulatedHarness.state(job)
                    UsagePeriod.objects.filter(pk=job.usage_period_id).update(spent=0)
                    writes.append({"before": before, "after": SimulatedHarness.state(job)})
            return worked

        harness = SimulatedHarness()
        with (
            patch("django.utils.timezone.now", return_value=FROZEN_NOW),
            patch.object(process_ai_jobs, "process_one", side_effect=erase_once),
        ):
            harness.run()
        result = next(r for r in harness.results if r.case.id == "EV-017")
        evidence = cast(dict[str, object], result.artifacts["null_content"])
        after = cast(dict[str, object], evidence["after"])
        self.assertEqual(len(writes), 1)
        self.assertEqual(after, evidence["after_second_worker"])
        self.assertEqual(after["status"], "failed")
        self.assertGreater(Decimal(str(after["cost"])), 0)
        self.assertEqual(after["input_tokens"], 20)
        self.assertEqual(after["output_tokens"], 10)
        self.assertEqual(Decimal(str(after["reserved"])), 0)
        self.assertEqual(Decimal(str(after["spent"])), 0)
        # RED before the fix: the entire report falsely had zero FAIL.
        self.assert_failure(
            harness, "fix6-spent-erased-once", "known_usage_after_spent_delta", writes
        )

    def altered_settlement(
        self, name: str, mutation: Callable[[AIJob], int], observation: str, *, idle: bool = False
    ) -> None:
        original = original_process_one
        writes: list[object] = []

        def alter_once() -> bool:
            worked = original()
            if worked != idle and not writes:
                job = AIJob.objects.filter(
                    owner__username="636-null_content", status="failed", cost__gt=0
                ).first()
                if job is not None:
                    before = SimulatedHarness.state(job)
                    mutation(job)
                    writes.append({"before": before, "after": SimulatedHarness.state(job)})
            return worked

        harness = SimulatedHarness()
        with (
            patch("django.utils.timezone.now", return_value=FROZEN_NOW),
            patch.object(process_ai_jobs, "process_one", side_effect=alter_once),
        ):
            harness.run()
        self.assertEqual(len(writes), 1)
        self.assert_failure(harness, name, observation, writes)

    def test_cost_changed_after_idle_is_rejected(self) -> None:
        self.altered_settlement(
            "fix6-idle-cost",
            lambda job: AIJob.objects.filter(pk=job.pk).update(cost=0),
            "known_usage_after_second_worker_job",
            idle=True,
        )

    def test_ledger_changed_after_idle_is_rejected(self) -> None:
        self.altered_settlement(
            "fix6-idle-ledger",
            lambda job: UsagePeriod.objects.filter(pk=job.usage_period_id).update(
                spent=F("spent") + Decimal("0.000001")
            ),
            "known_usage_after_second_worker_spent_delta",
            idle=True,
        )

    def test_persisted_tokens_differ_from_received_usage_is_rejected(self) -> None:
        self.altered_settlement(
            "fix6-first-tokens",
            lambda job: AIJob.objects.filter(pk=job.pk).update(output_tokens=11),
            "known_usage_after_job",
        )

    def test_first_worker_double_charge_is_rejected(self) -> None:
        self.altered_settlement(
            "fix6-first-double-charge",
            lambda job: UsagePeriod.objects.filter(pk=job.usage_period_id).update(
                spent=F("spent") + job.cost
            ),
            "known_usage_after_spent_delta",
        )

    def test_existing_spend_and_other_reserve_are_preserved(self) -> None:
        original = SimulatedHarness.enqueue

        def seed(
            harness: SimulatedHarness,
            result: CaseResult,
            owner: User,
            kind: str = "short",
            base: TrainingPlan | None = None,
        ) -> AIJob:
            job = original(harness, result, owner, kind, base)
            if owner.username == "636-null_content":
                UsagePeriod.objects.filter(pk=job.usage_period_id).update(
                    spent=Decimal("0.00010000"),
                    reserved=F("reserved") + Decimal("0.00000200"),
                    short_count=2,
                    plan_count=1,
                )
            return job

        harness = SimulatedHarness()
        with (
            patch("django.utils.timezone.now", return_value=FROZEN_NOW),
            patch.object(SimulatedHarness, "enqueue", new=seed),
        ):
            harness.run()
        save("fix6-existing-ledger-baseline", harness.report("fix6-existing-ledger-baseline"))
        require_technical_success(harness.results)
        result = next(r for r in harness.results if r.case.id == "EV-017")
        self.assertEqual(result.export()["status"], "PASS")
        evidence = cast(dict[str, object], result.artifacts["null_content"])
        before = cast(dict[str, object], evidence["before"])
        after = cast(dict[str, object], evidence["after_second_worker"])
        self.assertEqual(Decimal(str(before["spent"])), Decimal("0.00010000"))
        self.assertEqual(
            Decimal(str(after["spent"])),
            Decimal(str(before["spent"])) + Decimal(str(after["cost"])),
        )
        self.assertEqual(Decimal(str(after["reserved"])), Decimal("0.00000200"))
        self.assertEqual(after["short_count"], 2)
        self.assertEqual(after["plan_count"], 1)
