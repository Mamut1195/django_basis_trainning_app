"""Coach decision rules: deterministic, evidence-carrying, no diagnosis."""

from decimal import Decimal
from unittest import TestCase

from basis.modules.coach.domain.decisions import (
    Finding,
    Thresholds,
    adherence_rule,
    evaluate,
    high_rpe_low_load,
    load_drop,
    load_spike,
    missing_rpe,
    muscle_gap_rule,
    pain_rule,
    plateau,
)


class LoadRuleTests(TestCase):
    def test_two_high_weeks_propose_less_volume(self) -> None:
        finding = load_spike((Decimal("1.000"), Decimal("1.300"), Decimal("1.440")))
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "load_spike")
        self.assertEqual(finding.severity, "warn")
        self.assertIn("20 %", finding.proposal or "")
        self.assertTrue(any("1.440" in item for item in finding.evidence))

    def test_one_high_week_is_not_enough(self) -> None:
        self.assertIsNone(load_spike((Decimal("1.000"), Decimal("1.440"))))

    def test_two_low_weeks_do_not_add_load(self) -> None:
        finding = load_drop((Decimal("1.000"), Decimal("0.700"), Decimal("0.600")))
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "load_drop")
        self.assertIn("No subir", finding.proposal or "")
        self.assertIsNone(load_drop((Decimal("1.000"), Decimal("0.600"))))


class AdherenceRuleTests(TestCase):
    def test_low_adherence_simplifies(self) -> None:
        finding = adherence_rule(Decimal("50.00"))
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "adherence_low")
        self.assertIn("Simplificar", finding.proposal or "")

    def test_enough_adherence_or_missing_data_do_nothing(self) -> None:
        self.assertIsNone(adherence_rule(Decimal("75.00")))
        self.assertIsNone(adherence_rule(None))


class PlateauRuleTests(TestCase):
    def test_flat_weight_with_moderate_effort_suggests_progressing(self) -> None:
        finding = plateau(
            (Decimal("100.00"), Decimal("100.20"), Decimal("100.40")),
            (Decimal("6"), Decimal("6"), Decimal("6")),
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "plateau_low_effort")
        self.assertIn("2,5 %", finding.proposal or "")

    def test_flat_weight_with_high_effort_reviews_recovery(self) -> None:
        finding = plateau(
            (Decimal("100.00"), Decimal("100.10"), Decimal("100.20")),
            (Decimal("9"), Decimal("9"), Decimal("9")),
        )
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "plateau_high_effort")
        self.assertIn("recuperación", (finding.proposal or "").lower())

    def test_clear_progress_or_too_few_sessions_do_nothing(self) -> None:
        self.assertIsNone(
            plateau(
                (Decimal("100"), Decimal("105"), Decimal("110")),
                (Decimal("6"), Decimal("6"), Decimal("6")),
            )
        )
        self.assertIsNone(plateau((Decimal("100"), Decimal("100")), (Decimal("6"), Decimal("6"))))


class CoverageRuleTests(TestCase):
    def test_muscle_gap_needs_two_weeks(self) -> None:
        finding = muscle_gap_rule(("back", "calves"), 2)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "muscle_gap")
        self.assertIn("back, calves", finding.evidence[0])
        self.assertIsNone(muscle_gap_rule(("back",), 1))

    def test_missing_rpe_is_a_question(self) -> None:
        finding = missing_rpe(2)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertIn("Preguntar", finding.proposal or "")
        self.assertIsNone(missing_rpe(0))


class RecoveryAndSafetyTests(TestCase):
    def test_high_effort_low_load_reviews_recovery(self) -> None:
        finding = high_rpe_low_load(Decimal("8.5"), Decimal("0.700"))
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.rule, "high_rpe_low_load")
        self.assertIn("no añadir carga", (finding.proposal or "").lower())
        self.assertIsNone(high_rpe_low_load(Decimal("8.5"), Decimal("0.900")))
        self.assertIsNone(high_rpe_low_load(Decimal("7.0"), Decimal("0.700")))

    def test_pain_stops_and_refers(self) -> None:
        finding = pain_rule(True)
        self.assertIsNotNone(finding)
        assert finding is not None
        self.assertEqual(finding.severity, "stop")
        self.assertIn("valoración profesional", finding.proposal or "")
        self.assertIsNone(pain_rule(False))

    def test_finding_requires_known_severity_and_evidence(self) -> None:
        with self.assertRaises(ValueError):
            Finding("x", "critical", "t", "r", ("e",))
        with self.assertRaises(ValueError):
            Finding("x", "info", "t", "r", ())


class AggregateTests(TestCase):
    def test_empty_inputs_produce_no_findings(self) -> None:
        self.assertEqual(evaluate(), ())

    def test_pain_is_reported_first(self) -> None:
        findings = evaluate(
            load_ratios=(Decimal("1.0"), Decimal("1.4"), Decimal("1.5")),
            has_pain=True,
        )
        self.assertTrue(findings)
        self.assertEqual(findings[0].rule, "pain_stop")
        self.assertIn("load_spike", [finding.rule for finding in findings])

    def test_thresholds_are_configurable_in_one_place(self) -> None:
        custom = Thresholds(load_spike_ratio=Decimal("1.50"))
        self.assertIsNone(load_spike((Decimal("1.0"), Decimal("1.4"), Decimal("1.4")), custom))
        self.assertIsNotNone(load_spike((Decimal("1.0"), Decimal("1.6"), Decimal("1.6")), custom))
