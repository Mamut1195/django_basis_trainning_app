"""Exercise proposal fixtures against real constraints on every weekday."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase

from basis.bootstrap.coach import contexts, proposal_definition
from basis.bootstrap.tests.test_coach_edges import account, proposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import validate_context
from basis.shared.identifiers import AccountId


class ProposalFixtureCalendarTests(TestCase):
    def test_valid_fixture_preserves_availability_on_every_weekday(self) -> None:
        monday = datetime(2027, 1, 4, 12, tzinfo=datetime_timezone.utc)
        expected_dates = (4, 6, 6, 8, 8, 11, 11)
        for offset, expected_day in enumerate(expected_dates):
            frozen = monday + timedelta(days=offset)
            with (
                self.subTest(weekday=offset + 1),
                patch("django.utils.timezone.now", return_value=frozen),
            ):
                owner = account(f"calendar-{offset}")
                definition = proposal_definition(proposal(owner))
                context = contexts().snapshot(AccountId(owner.pk), "plan", None)
                preferences = context.athlete.preferences
                assert preferences is not None
                self.assertEqual(preferences.availability, (1, 3, 5))
                validate_context(definition, context, context)
                self.assertEqual(definition.sessions[0].date, date(2027, 1, expected_day))

    def test_unavailable_weekday_is_still_rejected_by_real_validator(self) -> None:
        tuesday = datetime(2027, 1, 5, 12, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.now", return_value=tuesday):
            owner = account("calendar-rejection")
            definition = proposal_definition(proposal(owner))
            context = contexts().snapshot(AccountId(owner.pk), "plan", None)
            invalid = replace(
                definition,
                sessions=(replace(definition.sessions[0], date=tuesday.date()),),
            )
            with self.assertRaisesRegex(CoachInvalid, "días disponibles"):
                validate_context(invalid, context, context)
