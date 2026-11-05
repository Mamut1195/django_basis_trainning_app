"""Owner-facing diagnosis: dominant sport, honest coverage, rule findings."""

from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase

from basis.modules.coach.application.diagnosis import diagnose
from basis.modules.training.public import LoadSample

START = date(2026, 9, 21)


def sample(
    week: int, load: Decimal, *, sport: str = "running", rpe: Decimal | None = Decimal(5)
) -> LoadSample:
    seconds = int(load * 60 / 5)
    day = START + timedelta(days=week * 7)
    return LoadSample(day, sport, "elapsed", seconds, rpe)


class DiagnosisTests(TestCase):
    def test_two_high_weeks_after_a_stable_base_fire_the_spike(self) -> None:
        diagnosis = diagnose(
            [sample(index, Decimal("500")) for index in range(4)]
            + [sample(4, Decimal("720")), sample(5, Decimal("720"))],
            adherence_percent=Decimal("80.00"),
            recent_rpe=[Decimal(5)] * 6,
        )
        self.assertEqual(diagnosis.sport, "running")
        self.assertEqual(diagnosis.weeks, 6)
        self.assertIn("load_spike", [finding.rule for finding in diagnosis.findings])
        spike = next(finding for finding in diagnosis.findings if finding.rule == "load_spike")
        self.assertIn("20 %", spike.proposal or "")

    def test_insufficient_weeks_are_reported_not_invented(self) -> None:
        diagnosis = diagnose(
            [sample(0, Decimal("500")), sample(1, Decimal("720"))],
            adherence_percent=None,
            recent_rpe=[Decimal(5), Decimal(5)],
        )
        self.assertEqual(diagnosis.weeks, 2)
        self.assertNotIn("load_spike", [finding.rule for finding in diagnosis.findings])
        self.assertTrue(diagnosis.notes)
        self.assertIn("Faltan semanas", diagnosis.notes[0])

    def test_dominant_sport_is_selected_without_mixing(self) -> None:
        diagnosis = diagnose(
            [sample(index, Decimal("300"), sport="cycling") for index in range(4)]
            + [sample(index, Decimal("500"), sport="running") for index in range(2)],
            adherence_percent=None,
            recent_rpe=[Decimal(5)],
        )
        self.assertEqual(diagnosis.sport, "cycling")
        self.assertEqual(diagnosis.coverage["weeks"], 4)

    def test_low_adherence_and_missing_rpe_are_reported(self) -> None:
        diagnosis = diagnose(
            [sample(index, Decimal("500")) for index in range(4)],
            adherence_percent=Decimal("40.00"),
            recent_rpe=[Decimal(5), None],
        )
        rules = [finding.rule for finding in diagnosis.findings]
        self.assertIn("adherence_low", rules)
        self.assertIn("missing_rpe", rules)

    def test_excluded_multi_sport_sessions_are_explained(self) -> None:
        diagnosis = diagnose(
            [sample(index, Decimal("500")) for index in range(4)],
            adherence_percent=None,
            recent_rpe=[],
            excluded_sessions=3,
        )
        self.assertTrue(any("varios deportes" in note for note in diagnosis.notes))

    def test_empty_history_says_so(self) -> None:
        diagnosis = diagnose([], adherence_percent=None, recent_rpe=[])
        self.assertEqual(diagnosis.findings, ())
        self.assertIsNone(diagnosis.sport)
        self.assertTrue(diagnosis.notes)

    def test_average_rpe_ignores_unknown(self) -> None:
        diagnosis = diagnose(
            [sample(0, Decimal("500"), rpe=Decimal(6)), sample(1, Decimal("500"), rpe=None)],
            adherence_percent=None,
            recent_rpe=[Decimal(6), None],
        )
        self.assertEqual(diagnosis.average_rpe, Decimal("6.00"))
