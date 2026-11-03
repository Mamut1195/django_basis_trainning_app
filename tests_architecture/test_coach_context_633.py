"""MAM-633 composition and missingness without Django, HTTP or credentials."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest import TestCase

from basis.modules.athletes.public import (
    AthleteCoachContext,
    PreferencesData,
    SportData,
    WellnessData,
)
from basis.modules.catalog.public import CoachExercise
from basis.modules.coach.application.context import Contexts
from basis.modules.coach.domain.jobs import CoachInvalid, JobKind
from basis.modules.coach.domain.prompts import (
    INSTRUCTIONS_VERSION,
    PLAN_FORMAT,
    SYSTEM,
    instructions_digest,
)
from basis.modules.training.public import (
    CoachBasePlan,
    CoachScope,
    CoachVariables,
    ProgressReport,
    TrainingCoachContext,
)
from basis.shared.identifiers import AccountId, ExerciseId, GoalId, PlanId

TODAY = date(2026, 11, 2)
OWNER = AccountId(633)
OTHER = AccountId(634)


class Clock:
    def today(self) -> date:
        return TODAY

    def now(self) -> datetime:
        return datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


class CapturedClock(Clock):
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def today(self) -> date:
        raise AssertionError("Owner date must not use a global today or another now")

    def now(self) -> datetime:
        self.calls += 1
        return self.instant + timedelta(days=self.calls - 1)


class Athletes:
    def __init__(self) -> None:
        self.data = AthleteCoachContext(None, "", None, (), None)
        self.reads: list[AccountId] = []

    def read(self, owner: AccountId) -> AthleteCoachContext:
        self.reads.append(owner)
        if owner != OWNER:
            raise PermissionError
        return self.data

    def read_for_acceptance(self, owner: AccountId) -> AthleteCoachContext:
        return self.read(owner)


class Training:
    def __init__(self) -> None:
        self.reads: list[AccountId] = []

    def read(self, owner: AccountId, today: date) -> TrainingCoachContext:
        self.reads.append(owner)
        return TrainingCoachContext(
            (),
            (),
            ProgressReport((), (), 0, 0, 0, None),
            CoachScope(today - timedelta(days=13), today, 14, 8),
        )

    def selected(self, owner: AccountId, plan: PlanId) -> CoachBasePlan | None:
        if owner != OWNER or plan != PlanId(1):
            return None
        return CoachBasePlan(plan, "Owned", 1, GoalId(1), TODAY, TODAY)

    def read_for_acceptance(
        self, owner: AccountId, today: date, base_plan: PlanId | None
    ) -> TrainingCoachContext:
        return self.read(owner, today)

    def variables(self) -> tuple[CoachVariables, ...]:
        return (CoachVariables("running", (("distance_m", "m"),)),)


class Exercises:
    def __init__(self) -> None:
        self.calls = 0

    def read(self) -> tuple[CoachExercise, ...]:
        self.calls += 1
        return (CoachExercise(ExerciseId(1), "Synthetic"),)

    def read_for_acceptance(self, referenced: tuple[ExerciseId, ...]) -> tuple[CoachExercise, ...]:
        return self.read()


class CoachContext633Tests(TestCase):
    def setUp(self) -> None:
        self.athletes, self.training, self.catalog = Athletes(), Training(), Exercises()
        self.service = Contexts(self.athletes, self.training, self.catalog, Clock())

    def test_missingness_and_trace_are_explicit_without_sport_inference(self) -> None:
        context = self.service.snapshot(OWNER, "short", None)
        self.assertEqual(context.schema_version, 2)
        self.assertEqual(context.instructions_version, INSTRUCTIONS_VERSION)
        self.assertEqual(context.system_sha256, instructions_digest(SYSTEM))
        self.assertIsNone(context.plan_sha256)
        self.assertEqual(context.tools, ("athletes.coach.read/v1", "training.coach.read/v2"))
        for missing in (
            "objectives",
            "availability",
            "equipment",
            "wellness_in_period",
            "effective_recovery",
            "strength_rm_not_consulted",
            "adherence_not_consulted",
        ):
            self.assertIn(missing, context.missing)
        self.assertIsNone(context.athlete.wellness)
        self.assertEqual(context.training.goals, ())
        self.assertIsNone(context.exercises)
        self.assertEqual(self.catalog.calls, 0)
        self.assertEqual(self.athletes.reads, [OWNER])
        self.assertEqual(self.training.reads, [OWNER])

    def test_acceptance_rejects_absent_preferences_without_silent_defaults(self) -> None:
        with self.assertRaises(CoachInvalid):
            self.service.snapshot_for_acceptance(OWNER, "plan", None)
        self.assertEqual(self.training.reads, [])
        with self.assertRaises(CoachInvalid):
            self.service.snapshot_for_acceptance(OWNER, "short", None)

    def test_owner_dates_use_one_captured_instant_including_dst_boundaries(self) -> None:
        cases = (
            ("Asia/Tokyo", datetime(2026, 11, 2, 2, 30, tzinfo=timezone.utc), date(2026, 11, 2)),
            (
                "Pacific/Honolulu",
                datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc),
                date(2026, 11, 1),
            ),
            (
                "America/New_York",
                datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc),
                date(2026, 3, 7),
            ),
            (
                "America/New_York",
                datetime(2026, 3, 9, 4, 30, tzinfo=timezone.utc),
                date(2026, 3, 9),
            ),
            (
                "America/New_York",
                datetime(2026, 11, 2, 4, 30, tzinfo=timezone.utc),
                date(2026, 11, 1),
            ),
        )
        for zone, instant, expected in cases:
            with self.subTest(zone=zone, instant=instant):
                clock = CapturedClock(instant)
                self.athletes.data = replace(
                    self.athletes.data,
                    preferences=PreferencesData(
                        (1,),
                        30,
                        "Declared",
                        "",
                        zone,
                    ),
                )
                service = Contexts(self.athletes, self.training, self.catalog, clock)
                for locked in (False, True):
                    clock.calls = 0
                    context = (
                        service.snapshot_for_acceptance(OWNER, "plan", None)
                        if locked
                        else service.snapshot(OWNER, "short", None)
                    )
                    self.assertEqual(context.snapshot_at, instant)
                    self.assertEqual(clock.calls, 1)
                    assert context.training.scope is not None
                    self.assertEqual(context.training.scope.end, expected)
                    self.assertNotIn("timezone_missing_utc_fallback", context.missing)

    def test_missing_zone_fallback_is_explicit_utc_and_invalid_zone_is_rejected(self) -> None:
        instant = datetime(2026, 11, 2, 2, 30, tzinfo=timezone.utc)
        for preferences in (None, PreferencesData((1,), 30, "", "", "")):
            clock = CapturedClock(instant)
            self.athletes.data = replace(self.athletes.data, preferences=preferences)
            context = Contexts(self.athletes, self.training, self.catalog, clock).snapshot(
                OWNER, "short", None
            )
            assert context.training.scope is not None
            self.assertEqual(context.training.scope.end, date(2026, 11, 2))
            self.assertIn("timezone_missing_utc_fallback", context.missing)
            self.assertEqual(clock.calls, 1)
        self.athletes.data = replace(
            self.athletes.data, preferences=PreferencesData((1,), 30, "", "", "Invalid/Zone")
        )
        with self.assertRaises(CoachInvalid):
            self.service.snapshot(OWNER, "short", None)
        self.athletes.data = replace(
            self.athletes.data, preferences=PreferencesData((1,), 30, "", "", "Asia/Tokyo")
        )
        with self.assertRaises(CoachInvalid):
            Contexts(
                self.athletes, self.training, self.catalog, CapturedClock(datetime(2026, 11, 2))
            ).snapshot(OWNER, "short", None)

    def test_other_owner_and_foreign_base_are_rejected_before_reading_context(self) -> None:
        cases: tuple[tuple[JobKind, PlanId], ...] = (("plan", PlanId(2)), ("short", PlanId(1)))
        for kind, plan in cases:
            with self.subTest(kind=kind), self.assertRaises(CoachInvalid):
                self.service.snapshot(OWNER, kind, plan)
        self.assertEqual(self.athletes.reads, [])
        with self.assertRaises(PermissionError):
            self.service.snapshot(OTHER, "short", None)
        self.assertEqual(self.training.reads, [])

    def test_plan_catalog_is_read_only_and_trace_identifies_instructions(self) -> None:
        context = self.service.snapshot(OWNER, "plan", PlanId(1))
        self.assertEqual(context.plan_sha256, instructions_digest(PLAN_FORMAT))
        self.assertIsNotNone(context.base_plan)
        self.assertEqual(self.catalog.calls, 1)
        self.assertIn("catalog.coach.read/v1", context.tools)
        self.assertIn("training.coach.variables/v1", context.tools)

    def test_zero_stays_known_and_stale_or_future_recovery_is_not_current(self) -> None:
        wellness = WellnessData(
            TODAY,
            Decimal(0),
            None,
            0,
            None,
            None,
            0,
            "",
            0,
            None,
            None,
            "",
            "private unused narrative",
        )
        self.athletes.data = replace(
            self.athletes.data,
            wellness=wellness,
            preferences=PreferencesData((1,), 30, "none declared", "", "America/Guayaquil"),
        )
        context = self.service.snapshot(OWNER, "short", None)
        self.assertNotIn("wellness:sleep_hours", context.missing)
        self.assertIn("wellness:stress", context.missing)
        self.assertIn("effective_recovery", context.missing)
        for offset in (-14, 1):
            self.athletes.data = replace(
                self.athletes.data, wellness=replace(wellness, date=TODAY + timedelta(days=offset))
            )
            context = self.service.snapshot(OWNER, "short", None)
            self.assertIsNone(context.athlete.wellness)
            self.assertIn("wellness_in_period", context.missing)

    def test_future_threshold_never_becomes_measured_evidence(self) -> None:
        self.athletes.data = replace(
            self.athletes.data,
            sports=(
                SportData(
                    "running",
                    "beginner",
                    Decimal(150),
                    "bpm",
                    TODAY + timedelta(days=1),
                    "synthetic",
                    "measured",
                    "future synthetic source",
                ),
            ),
        )
        context = self.service.snapshot(OWNER, "short", None)
        self.assertIsNone(context.athlete.sports[0].threshold)
        self.assertEqual(context.athlete.sports[0].threshold_source, "")
        self.assertIn("threshold:running", context.missing)
