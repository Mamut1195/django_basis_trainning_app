"""Behavioral evaluation tests; mocks establish transport contracts, never sports quality."""

import json
import os
from pathlib import Path
from time import perf_counter_ns
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from basis.bootstrap.tests.mam636_harness import FROZEN_NOW, SimulatedHarness
from basis.bootstrap.tests.mam636_report import (
    CaseResult,
    CorpusCase,
    aggregate,
    coverage,
    digest,
    require_technical_success,
)


class EvaluationAccountingTests(SimpleTestCase):
    def sample(self) -> CaseResult:
        return CaseResult(CorpusCase("EV-X", "system", "synthetic", "request", ("one", "two")))

    def test_partial_evidence_never_becomes_case_pass(self) -> None:
        result = self.sample()
        result.check(1, "operation", "service_effect", True, True)
        self.assertEqual(result.export()["status"], "INCONCLUSIVE")
        self.assertEqual(coverage([result])["expectations_pass"], 1)
        self.assertEqual(coverage([result])["case_denominator"], 1)
        self.assertEqual(coverage([result])["cases_all_expectations_pass"], 0)

    def test_defect_is_retained_and_causes_failure_even_with_other_passes(self) -> None:
        result = self.sample()
        result.check(1, "structure", "auto_applied_plan_count", 1, 0)
        result.check(2, "structure", "other_contract", True, True)
        self.assertEqual(result.export()["status"], "FAIL")
        self.assertEqual(
            coverage([result])["observations"],
            {"PASS": 1, "FAIL": 1, "INCONCLUSIVE": 0, "NOT_RUN": 0},
        )
        with self.assertRaisesRegex(AssertionError, "auto_applied_plan_count"):
            require_technical_success([result])

    def test_ambiguity_and_missing_fixture_are_not_promoted_by_simulated_text(self) -> None:
        result = self.sample()
        result.observe(1, "operation", "unknown_usage", "INCONCLUSIVE", reason="Not observable")
        self.assertEqual(result.export()["status"], "INCONCLUSIVE")
        self.assertEqual(aggregate(["PASS", "NOT_RUN"]), "INCONCLUSIVE")
        self.assertEqual(aggregate([]), "NOT_RUN")
        self.assertEqual(aggregate(["FAIL", "NOT_RUN"]), "FAIL")
        require_technical_success([result])  # Technical checks do not grant final acceptance.

    def test_pass_requires_evidence_and_unknown_expectations_are_rejected(self) -> None:
        result = self.sample()
        with self.assertRaises(ValueError):
            result.observe(1, "operation", "unsupported_pass", "PASS")
        with self.assertRaises(ValueError):
            result.check(3, "operation", "outside_corpus", True, True)


@override_settings(
    AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-636-only", DEEPSEEK_MODEL="deepseek-flash"
)
class DeterministicEvaluationTests(TestCase):
    def test_full_corpus_simulated_system_slice(self) -> None:
        harness = SimulatedHarness()
        with patch("django.utils.timezone.now", return_value=FROZEN_NOW):
            results = harness.run()
        report = harness.report(os.environ.get("MAM636_ATTEMPT", "unrecorded-test"))
        destination = os.environ.get("MAM636_REPORT")
        if destination:
            # Exclusive creation preserves all previous attempts, including failures.
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        require_technical_success(results)
        self.assertEqual(len(results), 17)
        self.assertEqual(coverage(results)["cases_executed"], 5)
        self.assertEqual([r.export()["status"] for r in results[:12]], ["NOT_RUN"] * 12)
        self.assertEqual(
            [r.export()["status"] for r in results[12:]],
            ["INCONCLUSIVE", "INCONCLUSIVE", "PASS", "PASS", "PASS"],
        )
        self.assertEqual(report["final_acceptance"], "NOT_RUN")
        self.assertEqual(report["sport_review"], "PENDING")
        # Source/corpus/artifact identities are present without conflating execution modes.
        self.assertEqual(len(str(report["corpus_sha256"])), 64)
        self.assertEqual(digest(report["cases"]), digest([r.export() for r in results]))

    def test_observed_private_response_leak_is_reported_and_fails(self) -> None:
        harness = SimulatedHarness(leak_response=True)
        result = next(r for r in harness.results if r.case.id == "EV-014")
        start = perf_counter_ns()
        with patch("django.utils.timezone.now", return_value=FROZEN_NOW):
            harness.privacy(result)
        result.duration_ns = perf_counter_ns() - start
        evidence = [o for o in result.observations if o.name == "controlled_response_excludes_B"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].status, "FAIL")
        self.assertEqual(result.export()["status"], "FAIL")
        destination = os.environ.get("MAM636_REPORT")
        if destination:
            path = Path(destination).with_suffix(".negative-leak.json")
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                report = harness.report(os.environ.get("MAM636_ATTEMPT", "test") + "/negative-leak")
                stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        with self.assertRaisesRegex(AssertionError, "EV-014/controlled_response_excludes_B"):
            require_technical_success([result])
