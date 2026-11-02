"""Effective prescriptions, statuses and paginated private source links."""

from datetime import date, datetime, timedelta
from datetime import timezone as utc_timezone
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from basis.bootstrap.tests.test_execution import account
from basis.modules.training.adapters.models import (
    Cycle,
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)


@override_settings(DEVELOPMENT_ACCESS=True)
class ProgressAgendaTests(TestCase):
    def setUp(self) -> None:
        self.user = account("agenda-owner")
        self.other = account("agenda-other")
        self.client.force_login(self.user)
        self.today = date(2026, 1, 5)
        goal = Goal.objects.create(owner=self.user, title="Agenda", sport="running")
        self.plan = TrainingPlan.objects.create(
            owner=self.user,
            goal=goal,
            title="Plan",
            start_date=self.today - timedelta(days=2),
            end_date=self.today + timedelta(days=2),
        )
        macro = Cycle.objects.create(
            plan=self.plan,
            title="macro",
            kind="macro",
            start_date=self.plan.start_date,
            end_date=self.plan.end_date,
        )
        meso = Cycle.objects.create(
            plan=self.plan,
            parent=macro,
            title="meso",
            kind="meso",
            start_date=self.plan.start_date,
            end_date=self.plan.end_date,
        )
        self.cycle = Cycle.objects.create(
            plan=self.plan,
            parent=meso,
            title="micro",
            kind="micro",
            start_date=self.plan.start_date,
            end_date=self.plan.end_date,
        )

    def row(self, name: str, day: date, status: str = "scheduled") -> PlannedSession:
        return PlannedSession.objects.create(
            owner=self.user, plan=self.plan, cycle=self.cycle, title=name, date=day, status=status
        )

    def test_statuses_links_exclusions_and_private_batch(self) -> None:
        past = self.row("Pendiente propia", self.today - timedelta(days=1))
        skipped = self.row("Omitida propia", self.today, "skipped")
        active = self.row("Activa propia", self.today)
        completed = self.row("Completada propia", self.today)
        cancelled = self.row("Cancelada propia", self.today, "cancelled")
        future = self.row("Futura propia", self.today + timedelta(days=1))
        started = Session.objects.create(
            owner=self.user,
            planned=active,
            title="Ejecución propia",
            date=self.today,
            status="in_progress",
        )
        done = Session.objects.create(
            owner=self.user,
            planned=completed,
            title="Terminada propia",
            date=self.today,
            status="completed",
        )
        Session.objects.bulk_create(
            [
                Session(
                    owner=self.other,
                    planned=active,
                    title="Ejecución ajena privada",
                    date=self.today,
                    status="in_progress",
                )
            ]
        )
        Session.objects.bulk_create(
            [
                Session(
                    owner=self.other,
                    planned=past,
                    title="Completada ajena inválida",
                    date=self.today,
                    status="completed",
                )
            ]
        )
        before_export = self.client.get(reverse("export")).json()
        with patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 1, 5, 17, tzinfo=utc_timezone.utc),
        ):
            response = self.client.get(
                "/progress/", {"period": "range", "start": "2026-01-04", "end": "2026-01-06"}
            )
        self.assertEqual(response.status_code, 200)
        entries = {item["planned"].pk: item for item in response.context["agenda_entries"]}
        self.assertEqual(entries[past.pk]["state"], "Pendiente pasada")
        self.assertEqual(entries[skipped.pk]["state"], "Omitida")
        self.assertEqual(entries[active.pk]["state"], "En curso")
        self.assertEqual(entries[completed.pk]["state"], "Completada")
        self.assertEqual(entries[cancelled.pk]["exclusion_reason"], "Cancelada")
        self.assertEqual(entries[future.pk]["exclusion_reason"], "Fecha futura")
        self.assertEqual([s.pk for s in entries[active.pk]["executions"]], [started.pk])
        self.assertContains(response, reverse("scheduled-detail", args=[active.pk]))
        self.assertContains(response, reverse("session-detail", args=[started.pk]))
        self.assertContains(response, reverse("session-detail", args=[done.pk]))
        self.assertNotContains(response, "Ejecución ajena privada")
        eligible = [item for item in entries.values() if not item["exclusion_reason"]]
        self.assertEqual(len(eligible), response.context["report"]["scheduled_past"])
        self.assertEqual(
            sum(item["state"] == "Completada" for item in eligible),
            response.context["report"]["completed_scheduled"],
        )
        after_export = self.client.get(reverse("export")).json()
        before_export.pop("exported_at")
        after_export.pop("exported_at")
        self.assertEqual(before_export, after_export)
        self.client.force_login(self.other)
        foreign_view = self.client.get(
            "/progress/", {"period": "range", "start": "2026-01-04", "end": "2026-01-06"}
        )
        self.assertNotContains(foreign_view, "Pendiente propia")
        self.assertNotContains(foreign_view, reverse("scheduled-detail", args=[active.pk]))
        self.assertEqual(
            self.client.get(reverse("scheduled-detail", args=[active.pk])).status_code, 404
        )
        self.assertEqual(
            (
                response.context["report"]["scheduled_past"],
                response.context["report"]["completed_scheduled"],
            ),
            (4, 1),
        )

    def test_pagination_preserves_range_and_queries_do_not_grow_per_row(self) -> None:
        self.row("first", self.today)
        params = {"period": "range", "start": "2026-01-05", "end": "2026-01-05"}
        with CaptureQueriesContext(connection) as small:
            self.client.get("/progress/", params)
        PlannedSession.objects.bulk_create(
            [
                PlannedSession(
                    owner=self.user,
                    plan=self.plan,
                    cycle=self.cycle,
                    title=f"item {n}",
                    date=self.today,
                )
                for n in range(25)
            ]
        )
        with CaptureQueriesContext(connection) as large:
            first = self.client.get("/progress/", params)
        self.assertEqual(len(first.context["agenda_entries"]), 20)
        self.assertLessEqual(len(large), len(small) + 1)
        self.assertContains(first, "agenda_page=2")
        second = self.client.get("/progress/", {**params, "agenda_page": "2"})
        self.assertEqual(len(second.context["agenda_entries"]), 6)
        self.assertEqual(second.context["agenda_page"].paginator.count, 26)
        both = self.client.get("/progress/", {**params, "page": "2", "agenda_page": "2"})
        self.assertIn("page=2", both.context["agenda_query"])
        self.assertIn("agenda_page=2", both.context["detail_query"])
        self.assertIn("start=2026-01-05", both.context["agenda_query"])
        self.assertNotEqual(
            first.context["agenda_entries"][0]["planned"].pk,
            second.context["agenda_entries"][0]["planned"].pk,
        )
