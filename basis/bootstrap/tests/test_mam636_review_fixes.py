"""Regression controls for the evaluator; mutations are never product findings."""

import json
import os
from pathlib import Path
from typing import cast
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from basis.bootstrap.tests.mam636_harness import FROZEN_NOW, PRIVATE_B, SimulatedHarness
from basis.bootstrap.tests.mam636_report import (
    CaseResult,
    CorpusCase,
    Dimension,
    Observation,
    Status,
    aggregate,
    coverage,
    require_technical_success,
)
from basis.modules.coach.adapters import provider
from basis.modules.coach.adapters.actions import process_one as original_process_one
from basis.modules.coach.adapters.management.commands import process_ai_jobs
from basis.modules.coach.adapters.models import AIJob, UsagePeriod
from basis.modules.coach.adapters.proposals import DjangoProposalSink
from basis.modules.coach.domain.context import CoachContext
from basis.modules.coach.domain.jobs import Job, JobKind, PricingSnapshot
from basis.modules.training.adapters.models import Cycle


def save(name: str, value: object) -> None:
    destination = os.environ.get("MAM636_FIX_EVIDENCE")
    if destination:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        with (path / (name + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, default=str)


def sample() -> CaseResult:
    return CaseResult(CorpusCase("EV-X", "system", "probe", "probe", ("one",)))


class RuntimeEvidenceTests(SimpleTestCase):
    def test_invalid_status_is_rejected_at_entry_and_aggregation(self) -> None:
        attempts: list[object] = []
        invalid_values: tuple[object, ...] = (None, "BROKEN", "", 0, True, [], {})
        for value in invalid_values:
            with self.subTest(value=value):
                result = sample()
                status = cast(Status, value)
                attempts.append({"invalid": value, "coverage_before": coverage([result])})
                with self.assertRaises(ValueError):
                    result.observe(1, "operation", "invalid", status)
                with self.assertRaises(ValueError):
                    aggregate([status])
                # A FAIL must not mask another invalid status either.
                with self.assertRaises(ValueError):
                    aggregate(["FAIL", status])
                self.assertEqual(len(result.observations), 0)
                self.assertEqual(coverage([result])["expectation_denominator"], 1)
        save("runtime-invalid-status", attempts)

    def test_invalid_dimension_and_expectation_are_rejected(self) -> None:
        invalid_dimensions: tuple[object, ...] = (None, "invalid", [], {})
        for dimension in invalid_dimensions:
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                sample().observe(1, cast(Dimension, dimension), "invalid", "FAIL")
        for index in (None, True, False, 1.0, "1", 0, 2, -1):
            with self.subTest(index=index), self.assertRaises(ValueError):
                sample().observe(cast(int, index), "operation", "invalid", "FAIL")

    def test_direct_observations_are_validated_by_export_coverage_and_guard(self) -> None:
        for observation in (
            Observation(1, "operation", "invalid", cast(Status, None), None, None, ""),
            Observation(1, cast(Dimension, "invalid"), "invalid", "FAIL", 1, 0, "probe"),
            Observation(2, "operation", "invalid", "FAIL", 1, 0, "probe"),
            Observation(1, "operation", "missing_evidence", "PASS", None, None, ""),
        ):
            result = sample()
            result.observations.append(observation)
            with self.subTest(observation=observation):
                with self.assertRaises(ValueError):
                    result.export()
                with self.assertRaises(ValueError):
                    coverage([result])
                with self.assertRaises(ValueError):
                    require_technical_success([result])

    def test_boolean_numeric_mismatches_including_nested_values_fail(self) -> None:
        pairs: tuple[tuple[object, object], ...] = (
            (True, 1),
            (False, 0),
            ({"count": True, "cost": False}, {"count": 1, "cost": 0}),
            ({"rows": [{"values": [True, False]}]}, {"rows": [{"values": [1, 0]}]}),
            (({"count": [True]},), ({"count": [1]},)),
            ({True: "key"}, {1: "key"}),
            (1, 1.0),
        )
        reports = []
        for actual, expected in pairs:
            result = sample()
            result.check(1, "structure", "typed_structure", actual, expected)
            reports.append(result.export())
            with self.subTest(actual=actual, expected=expected):
                self.assertEqual(result.export()["status"], "FAIL")
                with self.assertRaises(AssertionError):
                    require_technical_success([result])
        save("typed-structure-mismatches", reports)
        for value in (True, False, 1, 1.0, {"rows": [{"value": [True, 1, None]}]}):
            result = sample()
            result.check(1, "structure", "same_types", value, value)
            self.assertEqual(result.export()["status"], "PASS")


@override_settings(
    AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-fix3-only", DEEPSEEK_MODEL="deepseek-flash"
)
class FullMutationDetectionTests(TestCase):
    def run_harness(self) -> SimulatedHarness:
        harness = SimulatedHarness()
        with patch("django.utils.timezone.now", return_value=FROZEN_NOW):
            harness.run()
        return harness

    def assert_detected(self, harness: SimulatedHarness, case: str, name: str) -> None:
        result = next(r for r in harness.results if r.case.id == case)
        self.assertEqual(result.export()["status"], "FAIL")
        self.assertTrue(any(o.name == name and o.status == "FAIL" for o in result.observations))
        with self.assertRaisesRegex(AssertionError, case + "/" + name) as rejected:
            require_technical_success(harness.results)
        save(
            "guard-" + case + "-" + name,
            {
                "guard_rejected": True,
                "error": str(rejected.exception),
                "contradictions": [o.__dict__ for o in result.observations if o.status == "FAIL"],
            },
        )

    def test_full_request_only_leak_fails_and_rejects_guard(self) -> None:
        original = provider.request_body

        def leaking(
            kind: JobKind, prompt: str, context: CoachContext, model: str, pricing: PricingSnapshot
        ) -> dict[str, object]:
            body = original(kind, prompt, context, model, pricing)
            if kind == "short":
                messages = cast(list[dict[str, str]], body["messages"])
                content = json.loads(messages[1]["content"])
                content["context"]["private_B"] = PRIVATE_B
                messages[1]["content"] = json.dumps(content)
            return body

        with patch.object(provider, "request_body", side_effect=leaking):
            harness = self.run_harness()
        report = harness.report("fix3-mutant-request-leak")
        save("full-request-leak", report)
        job = AIJob.objects.get(owner__username="636-A")
        self.assertNotIn(PRIVATE_B, json.dumps(job.context))
        self.assertNotIn(PRIVATE_B, job.answer)
        self.assert_detected(harness, "EV-014", "dispatched_payload_excludes_B")
        privacy = next(r for r in harness.results if r.case.id == "EV-014")
        dispatch = cast(dict[str, object], privacy.artifacts["A_dispatch"])
        self.assertEqual(dispatch["job_id"], str(job.pk))
        self.assertEqual(dispatch["owner_id"], job.owner_id)
        self.assertIn(PRIVATE_B, json.dumps(dispatch["body"]))

    def test_full_idle_worker_release_fails_both_cases_and_rejects_guard(self) -> None:
        original = original_process_one

        def unsafe() -> bool:
            worked = original()
            if not worked:
                for job in AIJob.objects.filter(status="uncertain"):
                    UsagePeriod.objects.filter(pk=job.usage_period_id).update(reserved=0)
                    AIJob.objects.filter(pk=job.pk).update(status="failed", cost=0)
            return worked

        with patch.object(process_ai_jobs, "process_one", side_effect=unsafe):
            harness = self.run_harness()
        save("full-idle-release", harness.report("fix3-mutant-idle-release"))
        self.assert_detected(harness, "EV-016", "second_worker_preserves_state")
        self.assert_detected(harness, "EV-017", "invalid_json_second_worker_preserves_state")
        self.assert_detected(harness, "EV-017", "missing_usage_second_worker_preserves_state")

    def test_full_cycle_corruption_fails_and_rejects_guard(self) -> None:
        original = DjangoProposalSink.complete
        writes: list[object] = []

        def corrupt(sink: DjangoProposalSink, job: Job) -> bool:
            accepted = original(sink, job)
            if not accepted and job.base_plan is not None:
                before = list(Cycle.objects.filter(plan_id=job.base_plan).values())
                Cycle.objects.filter(plan_id=job.base_plan).update(title="CORRUPTED-FIX3-CONTROL")
                writes.append(
                    {
                        "before": before,
                        "after": list(Cycle.objects.filter(plan_id=job.base_plan).values()),
                    }
                )
            return accepted

        with patch.object(DjangoProposalSink, "complete", corrupt):
            harness = self.run_harness()
        save(
            "full-cycle-corruption",
            {"writes": writes, "report": harness.report("fix3-mutant-cycles")},
        )
        self.assertTrue(writes)
        self.assert_detected(harness, "EV-015", "invalid_preserves_all_history")
        result = next(r for r in harness.results if r.case.id == "EV-015")
        observation = next(
            o for o in result.observations if o.name == "invalid_preserves_all_history"
        )
        self.assertNotEqual(observation.actual, observation.expected)
        self.assertIn("cycles", cast(dict[str, object], observation.actual))

    def test_full_no_a_dispatch_does_not_credit_b_response(self) -> None:
        original = original_process_one

        def skip_a() -> bool:
            if AIJob.objects.filter(owner__username="636-A", status="pending").exists():
                return False
            return original()

        with patch.object(process_ai_jobs, "process_one", side_effect=skip_a):
            harness = self.run_harness()
        save("full-no-a-response", harness.report("fix3-mutant-no-response"))
        job = AIJob.objects.get(owner__username="636-A")
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.answer, "")
        result = next(r for r in harness.results if r.case.id == "EV-014")
        check = next(o for o in result.observations if o.name == "controlled_response_excludes_B")
        self.assertEqual(check.status, "INCONCLUSIVE")
        self.assert_detected(harness, "EV-014", "A_dispatch_count")

    def test_full_runtime_error_remains_failure_with_other_cases_retained(self) -> None:
        with patch.object(SimulatedHarness, "injection", side_effect=RuntimeError("fix3-sentinel")):
            harness = self.run_harness()
        save("full-runtime-error", harness.report("fix3-mutant-runtime-error"))
        self.assert_detected(harness, "EV-013", "scenario_execution")
        result = next(r for r in harness.results if r.case.id == "EV-013")
        self.assertEqual(result.artifacts["exception"], "fix3-sentinel")
        self.assertEqual(coverage(harness.results)["cases_executed"], 5)
        self.assertEqual(harness.results[14].export()["status"], "PASS")
