"""Wellness scales and moment are validated without persistence or Django."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase

from basis.modules.athletes.application.records import Athletes, RecordWellness
from basis.modules.athletes.domain.records import (
    InvalidAthleteData,
    WellnessData,
    validate_wellness,
)
from tests_architecture.test_athlete_records import OWNER, PermissiveAthleteRecords
from tests_architecture.test_billing import Memory
from tests_architecture.test_planning import Authorization

TODAY = date(2026, 10, 31)
EMPTY = WellnessData(TODAY, None, None, None, None, None, None, "", None, None, None, "", "")


class WellnessPolicyTests(TestCase):
    def test_empty_and_partial_checkins_and_all_moments(self) -> None:
        for moment in ("day", "before", "after"):
            validate_wellness(replace(EMPTY, moment=moment))
            validate_wellness(replace(EMPTY, moment=moment, sleep_hours=Decimal(0), fatigue=5))
        self.assertEqual(EMPTY.moment, "day")

    def test_historical_hrv_method_and_positive_pain_regions_contract(self) -> None:
        for value in (Decimal(0), Decimal(42)):
            with self.subTest(hrv_ms=value):
                with self.assertRaisesRegex(InvalidAthleteData, "Indica el método de medición HRV"):
                    validate_wellness(replace(EMPTY, hrv_ms=value))
                validate_wellness(replace(EMPTY, hrv_ms=value, hrv_method="reloj"))
        for pain_score in (1, 10):
            with self.subTest(pain_score=pain_score):
                with self.assertRaisesRegex(InvalidAthleteData, "Indica dónde sientes dolor"):
                    validate_wellness(replace(EMPTY, pain_score=pain_score))
                validate_wellness(replace(EMPTY, pain_score=pain_score, pain_regions="pierna"))
        validate_wellness(replace(EMPTY, pain_score=0))
        validate_wellness(replace(EMPTY, hrv_method="reloj", pain_regions="pierna"))

    def test_scale_boundaries_and_invalid_values(self) -> None:
        for value in (1, 5, 0, 6, -1):
            for data in (
                replace(EMPTY, sleep_quality=value),
                replace(EMPTY, fatigue=value),
                replace(EMPTY, stress=value),
                replace(EMPTY, soreness=value),
                replace(EMPTY, readiness=value),
            ):
                if value in (1, 5):
                    validate_wellness(data)
                else:
                    with self.subTest(data=data), self.assertRaises(InvalidAthleteData):
                        validate_wellness(data)
        for value in (0, 10):
            validate_wellness(replace(EMPTY, pain_score=value, pain_regions="pierna"))
        for value in (-1, 11):
            with self.assertRaises(InvalidAthleteData):
                validate_wellness(replace(EMPTY, pain_score=value))

    def test_units_invalid_moment_and_future_date(self) -> None:
        for data in (
            replace(EMPTY, moment="invalid"),
            replace(EMPTY, sleep_hours=Decimal(25)),
            replace(EMPTY, sleep_hours=Decimal("NaN")),
            replace(EMPTY, resting_hr_bpm=19),
            replace(EMPTY, resting_hr_bpm=251),
            replace(EMPTY, hrv_ms=Decimal(-1), hrv_method="reloj"),
            replace(EMPTY, date=TODAY + timedelta(days=1)),
        ):
            with self.subTest(data=data), self.assertRaises(InvalidAthleteData):
                validate_wellness(data, TODAY)


class WellnessApplicationTests(TestCase):
    def test_invalid_checkins_do_not_reach_permissive_writer(self) -> None:
        records = PermissiveAthleteRecords()
        service = Athletes(records, Authorization(), Memory)
        for data in (
            replace(EMPTY, moment="invalid"),
            replace(EMPTY, fatigue=6),
            replace(EMPTY, hrv_ms=Decimal(0)),
            replace(EMPTY, pain_score=1),
        ):
            with self.assertRaises(InvalidAthleteData):
                service.record_wellness(RecordWellness(OWNER, data))
        self.assertEqual(records.writes, [])
