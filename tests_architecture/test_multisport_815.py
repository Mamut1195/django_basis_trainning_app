"""Descriptive concurrent-session context; no recovery or injury prediction."""

from datetime import date
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from basis.modules.training.domain.execution import DurationProtocol
from basis.modules.training.domain.progress import ProgressBlock, ProgressSession, report
from basis.shared.identifiers import SessionId


def observation(number: int, day: int | None, *, completed: bool = True) -> ProgressSession:
    return ProgressSession(
        SessionId(UUID(int=number)),
        completed,
        DurationProtocol.ELAPSED,
        600,
        Decimal(5),
        (ProgressBlock("running"),),
        date(2026, 10, day) if day is not None else None,
    )


class MultisportContextTests(TestCase):
    def test_unsorted_same_day_and_gap_use_distinct_observed_dates(self) -> None:
        rows = (
            observation(4, 15),
            observation(3, 13),
            observation(1, 12),
            observation(2, 13),
            observation(5, 14, completed=False),
        )
        result = report(rows, (), date(2026, 10, 20))
        context = {row.session.id.int: row for row in result.context}
        self.assertEqual([row.session for row in result.context], list(rows[:4]))
        self.assertEqual((context[1].previous_date, context[1].consecutive_days), (None, 1))
        for number in (2, 3):
            self.assertEqual(context[number].previous_date, date(2026, 10, 12))
            self.assertEqual(context[number].days_since_previous, 1)
            self.assertEqual(context[number].consecutive_days, 2)
            self.assertEqual(context[number].sessions_on_date, 2)
        self.assertEqual(context[4].days_since_previous, 2)
        self.assertEqual(context[4].consecutive_days, 1)
        self.assertEqual(result.sessions, 4)
        self.assertEqual(result.loads[0].value, Decimal(200))

    def test_missing_dates_remain_unknown_and_do_not_extend_observed_sequence(self) -> None:
        result = report((observation(1, None), observation(2, 13)), (), date(2026, 10, 20))
        unknown, known = result.context
        self.assertIsNone(unknown.previous_date)
        self.assertIsNone(unknown.days_since_previous)
        self.assertIsNone(unknown.consecutive_days)
        self.assertIsNone(unknown.sessions_on_date)
        self.assertEqual(known.consecutive_days, 1)
        self.assertEqual(result.sessions, 2)

    def test_empty_selection_has_no_context_or_synthetic_recovery(self) -> None:
        result = report((), (), date(2026, 10, 20))
        self.assertEqual(result.context, ())
        self.assertEqual(result.loads, ())
        self.assertEqual(result.sports, ())

    def test_sequence_is_bounded_by_the_selected_sessions(self) -> None:
        rows = (observation(1, 12), observation(2, 13), observation(3, 14))
        full = report(rows, (), date(2026, 10, 20))
        selected = report(rows[1:], (), date(2026, 10, 20))
        self.assertEqual(full.context[-1].consecutive_days, 3)
        self.assertEqual(selected.context[-1].consecutive_days, 2)
        self.assertIsNone(selected.context[0].previous_date)
