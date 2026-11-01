"""Coverage semantics without Django or a database."""

from datetime import date
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.domain.execution import DurationProtocol, Metric, MetricName
from basis.modules.training.domain.progress import Coverage, ProgressBlock, ProgressSession, report
from basis.shared.identifiers import SessionId


class ProgressCoverageTests(TestCase):
    def test_known_zero_missing_and_not_applicable_have_distinct_counts(self) -> None:
        blocks = (
            ProgressBlock("running", (Metric(MetricName.DISTANCE_M, Decimal(0)),)),
            ProgressBlock("running"),
            ProgressBlock("cardio"),
            ProgressBlock(
                "strength", set_volumes=(Decimal(0), None, None), set_applicable=(True, True, False)
            ),
        )
        result = report(
            (
                ProgressSession(
                    SessionId(UUID(int=1)), True, DurationProtocol.ELAPSED, blocks=blocks
                ),
            ),
            (),
            date(2026, 1, 1),
        )
        sport = {row.sport: row for row in result.sports}
        self.assertEqual(sport["running"].distance_m, Decimal(0))
        self.assertEqual(sport["running"].distance_coverage, Coverage(1, 1, 0))
        self.assertEqual(sport["running"].ascent_coverage, Coverage(0, 2, 0))
        self.assertEqual(sport["cardio"].ascent_coverage, Coverage(0, 0, 1))
        self.assertEqual(sport["strength"].volume_coverage, Coverage(1, 1, 1))
        self.assertEqual(sport["strength"].external_volume_kg, Decimal(0))

    def test_legacy_unknown_applicability_and_mismatched_lengths(self) -> None:
        legacy = ProgressBlock("strength", set_volumes=(None, Decimal(2)))
        result = report(
            (
                ProgressSession(
                    SessionId(UUID(int=2)), True, DurationProtocol.ELAPSED, blocks=(legacy,)
                ),
            ),
            (),
            date(2026, 1, 1),
        )
        self.assertEqual(result.sports[0].volume_coverage, Coverage(1, 0, 0, 1))
        invalid = ProgressBlock("strength", set_volumes=(None, None), set_applicable=(True,))
        with self.assertRaisesRegex(ValueError, "length mismatch"):
            report(
                (
                    ProgressSession(
                        SessionId(UUID(int=3)), True, DurationProtocol.ELAPSED, blocks=(invalid,)
                    ),
                ),
                (),
                date(2026, 1, 1),
            )
