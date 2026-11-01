"""Progress periods, owner dates, source pagination and isolated reads."""

from datetime import date, datetime
from datetime import timezone as utc_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings

from basis.bootstrap.progress import progress
from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.models import AthleteSettings
from basis.modules.training.adapters.models import Session
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.modules.training.application.progress import ReadProgress
from basis.shared.identifiers import AccountId


@override_settings(DEVELOPMENT_ACCESS=True)
class ProgressPeriodTests(TestCase):
    def setUp(self) -> None:
        self.user = account("period-owner")
        self.other = account("period-other")
        self.client.force_login(self.user)
        self.sunday = Session.objects.create(
            owner=self.user, title="Sunday", date=date(2026, 1, 4), status="completed"
        )
        self.monday = Session.objects.create(
            owner=self.user, title="Monday", date=date(2026, 1, 5), status="completed"
        )
        Session.objects.create(
            owner=self.user, title="Partial", date=date(2026, 1, 5), status="in_progress"
        )
        Session.objects.create(
            owner=self.other, title="Foreign private", date=date(2026, 1, 5), status="completed"
        )
        AthleteSettings.objects.create(owner=self.user, timezone_name="America/New_York")

    def test_local_day_and_iso_week_at_midnight(self) -> None:
        instant = datetime(2026, 1, 5, 1, tzinfo=utc_timezone.utc)
        with patch(
            "basis.modules.training.adapters.web.progress.timezone.now", return_value=instant
        ):
            sunday = self.client.get("/progress/", {"period": "day"})
            self.assertContains(sunday, "Sunday")
            self.assertNotContains(sunday, "Monday")
            self.assertEqual(sunday.context["report"]["sessions"], 1)
            AthleteSettings.objects.filter(owner=self.user).update(timezone_name="Asia/Tokyo")
            monday = self.client.get("/progress/", {"period": "week"})
            self.assertContains(monday, "2026-01-05")
            self.assertContains(monday, "2026-01-11")
            self.assertContains(monday, "Monday")
            self.assertContains(monday, "Partial")
            self.assertNotContains(monday, "Sunday")
            self.assertNotContains(monday, "Foreign private")
            self.assertEqual(monday.context["report"]["sessions"], 1)

    def test_inclusive_range_default_and_invalid_inputs(self) -> None:
        owner = AccountId(self.user.pk)
        self.assertEqual(progress().read(ReadProgress(owner)).sessions, 2)
        self.assertEqual(
            progress().read(ReadProgress(owner, date(2026, 1, 4), date(2026, 1, 5))).sessions, 2
        )
        response = self.client.get(
            "/progress/", {"period": "range", "start": "2026-01-04", "end": "2026-01-04"}
        )
        self.assertContains(response, "Sunday")
        self.assertNotContains(response, "Monday")
        for params in (
            {"period": "range", "start": "2026-01-05", "end": "2026-01-04"},
            {"period": "range", "start": "bad", "end": "2026-01-04"},
            {"period": "range", "start": "2026-01-04"},
        ):
            self.assertEqual(self.client.get("/progress/", params).status_code, 400)
        with self.assertRaises(ValueError):
            progress().read(ReadProgress(owner, date(2026, 1, 5), date(2026, 1, 4)))

    def test_repository_excludes_other_dates_before_projection(self) -> None:
        with patch(
            "basis.modules.training.adapters.progress.progress_session",
            wraps=__import__(
                "basis.modules.training.adapters.progress", fromlist=["progress_session"]
            ).progress_session,
        ) as projection:
            rows = DjangoProgressRepository().sessions(
                AccountId(self.user.pk), date(2026, 1, 5), date(2026, 1, 5)
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(projection.call_count, 1)
        self.assertEqual(rows[0].id, self.monday.pk)

    def test_source_detail_is_paginated_and_preserves_filters(self) -> None:
        Session.objects.bulk_create(
            [
                Session(
                    owner=self.user,
                    title=f"Item {index}",
                    date=date(2026, 1, 5),
                    status="in_progress",
                )
                for index in range(22)
            ]
        )
        params = {"period": "range", "start": "2026-01-05", "end": "2026-01-05"}
        response = self.client.get("/progress/", params)
        self.assertEqual(len(response.context["source_sessions"]), 20)
        self.assertContains(response, "page=2")
        self.assertNotContains(response, "Foreign private")
        second = self.client.get("/progress/", {**params, "page": "2"})
        self.assertEqual(second.context["source_sessions"].paginator.count, 24)
        self.assertEqual(len(second.context["source_sessions"]), 4)

    def test_week_overflow_rejected_and_default_reference_stays_in_page_links(self) -> None:
        self.assertEqual(
            self.client.get(
                "/progress/", {"period": "week", "reference": "9999-12-31"}
            ).status_code,
            400,
        )
        Session.objects.bulk_create(
            [
                Session(
                    owner=self.user, title=f"extra {i}", date=date(2026, 1, 4), status="in_progress"
                )
                for i in range(21)
            ]
        )
        before = datetime(2026, 1, 5, 1, tzinfo=utc_timezone.utc)
        after = datetime(2026, 1, 5, 6, tzinfo=utc_timezone.utc)
        with patch(
            "basis.modules.training.adapters.web.progress.timezone.now", return_value=before
        ):
            first = self.client.get("/progress/", {"period": "day"})
        self.assertEqual(first.context["period_start"], date(2026, 1, 4))
        query = first.context["detail_query"]
        self.assertIn("reference=2026-01-04", query)
        with patch("basis.modules.training.adapters.web.progress.timezone.now", return_value=after):
            second = self.client.get("/progress/?" + query + "&page=2")
        self.assertEqual(second.context["period_start"], date(2026, 1, 4))
        self.assertEqual(second.context["source_sessions"].paginator.count, 22)

    def test_coverage_display_separates_no_data_from_not_applicable(self) -> None:
        from basis.modules.catalog.adapters.models import Classification, Exercise
        from basis.modules.training.adapters.models import Block, StrengthSet

        classification = Classification.objects.create(nombre="Coverage")
        exercise = Exercise.objects.create(nombre="Coverage", classification=classification)
        strength = Block.objects.bulk_create(
            [Block(session=self.monday, order=1, sport="strength", title="Strength")]
        )[0]
        Block.objects.bulk_create(
            [Block(session=self.monday, order=2, sport="swimming", title="Swimming")]
        )
        params = {"period": "day", "reference": "2026-01-05"}
        empty = self.client.get("/progress/", params)
        sports = {row["sport"]: row for row in empty.context["report"]["sports"]}
        self.assertFalse(sports["strength"]["volume_not_applicable"])
        self.assertIsNone(sports["strength"]["external_volume_kg"])
        self.assertTrue(sports["strength"]["distance_not_applicable"])
        self.assertTrue(sports["swimming"]["ascent_not_applicable"])
        self.assertEqual(sports["swimming"]["volume_coverage"]["not_applicable"], 0)
        self.assertTrue(sports["swimming"]["volume_not_applicable"])
        StrengthSet.objects.bulk_create(
            [StrengthSet(block=strength, exercise=exercise, load_type="bodyweight", order=1)]
        )
        response = self.client.get("/progress/", params)
        sports = {row["sport"]: row for row in response.context["report"]["sports"]}
        self.assertTrue(sports["strength"]["volume_not_applicable"])
        self.assertEqual(sports["strength"]["volume_coverage"]["not_applicable"], 1)
        self.assertContains(response, "No aplica")
        self.assertNotContains(response, "sin tipo de carga conocido")

    def test_range_adherence_excludes_cancelled_and_future_preserves_completed(self) -> None:
        from datetime import timedelta

        from basis.modules.training.adapters.models import Cycle, Goal, PlannedSession, TrainingPlan

        today = date(2026, 1, 5)
        goal = Goal.objects.create(owner=self.user, title="Goal", sport="running")
        plan = TrainingPlan.objects.create(
            owner=self.user,
            goal=goal,
            title="Plan",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )
        macro = Cycle.objects.create(
            plan=plan,
            title="macro",
            kind="macro",
            start_date=plan.start_date,
            end_date=plan.end_date,
        )
        meso = Cycle.objects.create(
            plan=plan,
            parent=macro,
            title="meso",
            kind="meso",
            start_date=plan.start_date,
            end_date=plan.end_date,
        )
        micro = Cycle.objects.create(
            plan=plan,
            parent=meso,
            title="micro",
            kind="micro",
            start_date=plan.start_date,
            end_date=plan.end_date,
        )
        done = PlannedSession.objects.create(
            owner=self.user, plan=plan, cycle=micro, title="done", date=today - timedelta(days=1)
        )
        PlannedSession.objects.create(
            owner=self.user,
            plan=plan,
            cycle=micro,
            title="cancelled",
            date=today,
            status="cancelled",
        )
        PlannedSession.objects.create(
            owner=self.user, plan=plan, cycle=micro, title="future", date=today + timedelta(days=1)
        )
        Session.objects.create(
            owner=self.user, planned=done, title="done", date=done.date, status="completed"
        )
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 1, 5, 17, tzinfo=utc_timezone.utc),
        ):
            result = progress().read(
                ReadProgress(
                    AccountId(self.user.pk), today - timedelta(days=1), today + timedelta(days=1)
                )
            )
        self.assertEqual(
            (result.scheduled_past, result.completed_scheduled, result.adherence_percent),
            (1, 1, 100.0),
        )

    def test_load_ui_distinguishes_missing_from_observed_zero(self) -> None:
        params = {"period": "day", "reference": "2026-01-05"}
        missing = self.client.get("/progress/", params)
        self.assertEqual(
            (
                missing.context["report"]["loads"][0]["known"],
                missing.context["report"]["loads"][0]["missing"],
            ),
            (0, 1),
        )
        self.assertRegex(missing.content.decode(), r"Sin datos\s*·\s*1 sin datos")
        Session.objects.filter(pk=self.monday.pk).update(duration_seconds=60, reported_rpe=0)
        zero = self.client.get("/progress/", params)
        self.assertEqual(
            (
                zero.context["report"]["loads"][0]["known"],
                zero.context["report"]["loads"][0]["missing"],
            ),
            (1, 0),
        )
        self.assertRegex(zero.content.decode(), r"0,00 UA\s*·\s*0 sin datos")

    def test_rpe_summary_ui_preserves_zero_and_missing(self) -> None:
        from basis.modules.training.adapters.models import Block

        Block.objects.bulk_create([Block(session=self.monday, title="Run", sport="running")])
        params = {"period": "day", "reference": "2026-01-05"}
        missing = self.client.get("/progress/", params)
        sport = missing.context["report"]["sports"][0]
        self.assertEqual((sport["rpe_min"], sport["rpe_known"], sport["rpe_missing"]), (None, 0, 1))
        self.assertContains(missing, "RPE real de sesión completa")
        Session.objects.filter(pk=self.monday.pk).update(reported_rpe=0)
        zero = self.client.get("/progress/", params)
        sport = zero.context["report"]["sports"][0]
        self.assertEqual((sport["rpe_min"], sport["rpe_max"], sport["rpe_known"]), (0, 0, 1))
        self.assertContains(zero, "mínimo 0,0")
