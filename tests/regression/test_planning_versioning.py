"""622 acceptance: immutable intention, explicit changes and effective history."""

import json
from dataclasses import replace
from datetime import datetime, timedelta
from datetime import timezone as utc
from decimal import Decimal
from unittest import TestCase as UnitTestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase

from basis.bootstrap.planning import planning
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.calendar import calendar_status, effective_sessions
from basis.modules.training.adapters.models import (
    Cycle,
    Goal,
    PlannedSession,
    Session,
    TrainingPlan,
)
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.modules.training.public import (
    BlockData,
    ChangeScheduledSession,
    CreatePlan,
    InvalidPlanning,
    Metric,
    MetricName,
    PlanningConflict,
    RescheduleSession,
    RestorePlan,
    ScheduledState,
    ScheduleStatus,
)
from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId, PlannedSessionId, Revision
from tests.regression.factories import account
from tests_architecture.test_planning import TODAY, definition


class PlanningFixture(UnitTestCase):
    def setUp(self) -> None:
        self.time = patch(
            "django.utils.timezone.now", return_value=datetime(2026, 10, 19, 17, tzinfo=utc.utc)
        )
        self.time.start()
        self.addCleanup(self.time.stop)
        self.user = account("planning-622")
        self.other = account("planning-other-622")
        self.owner = AccountId(self.user.pk)
        self.service = planning()
        goal = Goal.objects.create(owner=self.user, title="Continuidad", sport="running")
        self.data = definition(GoalId(goal.pk))
        self.header = self.service.create(CreatePlan(self.owner, self.data))
        self.future = PlannedSession.objects.get(plan_id=self.header.id, title="future")
        self.client = Client()
        self.client.force_login(self.user)

    def move(self) -> ScheduledState:
        return self.service.reschedule(
            RescheduleSession(
                self.owner,
                PlannedSessionId(self.future.pk),
                TODAY + timedelta(days=2),
                Revision(1),
                "Disponibilidad personal",
            )
        )


class PlanningVersioningTests(PlanningFixture, TestCase):
    def test_change_action_is_discriminant_and_inconsistent_fields_do_not_publish(self) -> None:
        for action, reference in (
            ("cancelled", self.future.pk),
            ("skipped", self.future.pk),
            ("replace", ""),
        ):
            with self.subTest(action=action):
                response = self.client.post(
                    f"/scheduled/{self.future.pk}/change/",
                    {
                        "action": action,
                        "replacement": reference,
                        "revision": 1,
                        "reason": "No debe reinterpretarse",
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(TrainingPlan.objects.count(), 1)
                self.future.refresh_from_db()
                self.assertEqual((self.future.status, self.future.revision), ("scheduled", 1))
                print(
                    "R622_ACTION_STATE "
                    + json.dumps(
                        {
                            "action": action,
                            "replacement": reference,
                            "http": response.status_code,
                            "version_count": TrainingPlan.objects.count(),
                            "status": self.future.status,
                            "revision": self.future.revision,
                        }
                    ),
                    flush=True,
                )
        with self.assertRaises(InvalidPlanning):
            self.service.change_session(
                ChangeScheduledSession(
                    self.owner,
                    PlannedSessionId(self.future.pk),
                    Revision(1),
                    "Inválido también por puerto",
                    ScheduleStatus.CANCELLED,
                    self.data.sessions[1],
                )
            )

    def test_change_actions_work_without_silently_switching_status(self) -> None:
        for action in ("cancelled", "skipped", "replace"):
            head = self.service.create(CreatePlan(self.owner, self.data))
            row = PlannedSession.objects.get(plan_id=head.id, title="future")
            reference = PlannedSession.objects.get(plan_id=head.id, title="past")
            response = self.client.post(
                f"/scheduled/{row.pk}/change/",
                {
                    "action": action,
                    "replacement": reference.pk if action == "replace" else "",
                    "revision": 1,
                    "reason": "Acción explícita " + action,
                },
            )
            self.assertEqual(response.status_code, 302)
            result = PlannedSession.objects.get(
                pk=int(response["Location"].strip("/").split("/")[-1])
            )
            self.assertEqual(result.status, "scheduled" if action == "replace" else action)
            self.assertEqual(result.plan.change_kind, action)
            self.assertEqual(result.plan.change_reason, "Acción explícita " + action)
            row.refresh_from_db()
            self.assertEqual(row.status, "scheduled")

    def test_web_creates_and_consults_goal_to_full_prescription(self) -> None:
        response = self.client.post(
            "/records/goal/new/",
            {
                "title": "Meta estructurada",
                "sport": "running",
                "priority": "primary",
                "target_value": "5000",
                "target_unit": "m",
                "baseline_value": "3000",
                "baseline_date": TODAY.isoformat(),
                "target_date": self.data.end_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        goal = Goal.objects.get(owner=self.user, title="Meta estructurada")
        response = self.client.post(
            "/plans/new/",
            {
                "title": "Plan web completo",
                "goal": goal.pk,
                "start_date": TODAY.isoformat(),
                "end_date": self.data.end_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        plan = TrainingPlan.objects.get(title="Plan web completo")
        parent = None
        for kind in ("macro", "meso", "micro"):
            response = self.client.post(
                f"/plans/{plan.pk}/cycles/new/",
                {
                    "kind": kind,
                    "title": kind,
                    "parent": parent or "",
                    "start_date": TODAY.isoformat(),
                    "end_date": self.data.end_date.isoformat(),
                },
            )
            self.assertEqual(response.status_code, 302)
            parent = plan.cycles.get(kind=kind).pk
        response = self.client.post(
            "/scheduled/new/",
            {"plan": plan.pk, "cycle": parent, "title": "Sesión web", "date": TODAY.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        scheduled = plan.sessions.get()
        response = self.client.post(
            f"/blocks/parent/planned/{scheduled.pk}/new/",
            {"sport": "running", "title": "Rodaje", "revision": 1},
        )
        self.assertEqual(response.status_code, 302)
        block = scheduled.blocks.get()
        response = self.client.post(
            f"/blocks/{block.pk}/metrics/", {"distance_m": "5000", "revision": 2}
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(f"/plans/{plan.pk}/"), "Sesión web")
        self.assertContains(self.client.get(f"/scheduled/{scheduled.pk}/"), "Programada")
        block.refresh_from_db()
        self.assertEqual((block.target, block.actual), ({"distance_m": "5000"}, {}))
        self.assertFalse(Session.objects.exists())

    def test_move_between_explicit_microcycles_retains_temporal_bounds(self) -> None:
        cycle = Cycle.objects.create(
            plan_id=self.header.id,
            parent=self.future.cycle.parent,
            kind="micro",
            title="Destino",
            start_date=TODAY + timedelta(days=2),
            end_date=TODAY + timedelta(days=3),
        )
        result = self.service.reschedule(
            RescheduleSession(
                self.owner,
                PlannedSessionId(self.future.pk),
                cycle.start_date,
                Revision(1),
                "Cambio de microciclo",
                CycleId(cycle.pk),
            )
        )
        copy = PlannedSession.objects.get(pk=result.id)
        self.assertEqual(copy.cycle.title, "Destino")
        self.assertEqual(copy.date, cycle.start_date)
        self.assertNotEqual(copy.cycle_id, self.future.cycle_id)

    def test_move_retains_original_and_records_protected_origin_reason_and_actor(self) -> None:
        old_date = self.future.date
        before = self.future.blocks.get().target.copy()
        changed = self.move()
        copy = PlannedSession.objects.get(pk=changed.id)
        self.future.refresh_from_db()
        self.assertEqual(self.future.date, old_date)
        self.assertEqual((copy.origin_id, copy.supersedes_id), (self.future.pk, self.future.pk))
        self.assertEqual(copy.blocks.get().target, before)
        self.assertEqual(copy.plan.change_reason, "Disponibilidad personal")
        self.assertEqual(copy.plan.changed_by_id, self.user.pk)
        self.assertEqual(copy.plan.effective_on, TODAY)
        self.assertIsNotNone(copy.plan.created_at)
        exported = self.client.get("/export/").json()
        exported_copy = next(
            item["fields"] for item in exported["plannedsession"] if item["pk"] == copy.pk
        )
        exported_plan = next(
            item["fields"] for item in exported["trainingplan"] if item["pk"] == copy.plan_id
        )
        self.assertEqual(
            (exported_copy["origin"], exported_copy["supersedes"]), (self.future.pk, self.future.pk)
        )
        self.assertEqual(
            (exported_plan["change_reason"], exported_plan["changed_by"]),
            ("Disponibilidad personal", self.user.pk),
        )
        with self.assertRaises(ProtectedError):
            self.future.delete()
        with self.assertRaises(PlanningConflict):
            self.move()
        self.assertEqual(
            self.client.post(
                f"/plans/{self.header.id}/revise/", {"reason": "Petición obsoleta"}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                f"/scheduled/{self.future.pk}/change/",
                {"reason": "Obsoleta", "revision": 1, "action": "cancelled"},
            ).status_code,
            409,
        )
        self.assertEqual(TrainingPlan.objects.count(), 2)

    def test_missing_reason_and_invalid_dates_leave_no_new_version(self) -> None:
        for reason, day in (
            (" ", TODAY),
            ("Fuera del ciclo", self.data.end_date + timedelta(days=1)),
        ):
            with self.assertRaises(InvalidPlanning):
                self.service.reschedule(
                    RescheduleSession(
                        self.owner, PlannedSessionId(self.future.pk), day, Revision(1), reason
                    )
                )
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_cancel_skip_and_restore_are_versions_not_results(self) -> None:
        cancelled = self.service.change_session(
            ChangeScheduledSession(
                self.owner,
                PlannedSessionId(self.future.pk),
                Revision(1),
                "Viaje",
                ScheduleStatus.CANCELLED,
            )
        )
        row = PlannedSession.objects.get(pk=cancelled.id)
        self.assertEqual(calendar_status(row, TODAY), "Cancelada")
        self.assertFalse(Session.objects.exists())
        restored = self.service.restore(
            RestorePlan(
                self.owner, PlanId(row.plan_id), self.header.id, "Retomo la intención original"
            )
        )
        current = PlannedSession.objects.get(plan_id=restored.id, origin=self.future)
        self.assertEqual((current.status, current.date), ("scheduled", self.future.date))
        skipped = self.service.change_session(
            ChangeScheduledSession(
                self.owner,
                PlannedSessionId(current.pk),
                Revision(current.revision),
                "No realizada",
                ScheduleStatus.SKIPPED,
            )
        )
        self.assertEqual(
            calendar_status(PlannedSession.objects.get(pk=skipped.id), TODAY), "Omitida"
        )
        self.assertEqual(TrainingPlan.objects.get(pk=restored.id).restored_from_id, self.header.id)
        self.assertEqual(TrainingPlan.objects.count(), 4)

    def test_replace_deep_copies_intention_with_reason(self) -> None:
        candidate = replace(
            self.data.sessions[1],
            title="Alternativa",
            blocks=(
                BlockData(
                    "cycling",
                    "Rodillo",
                    target=(Metric(MetricName.DURATION_SECONDS, Decimal(900)),),
                ),
            ),
        )
        changed = self.service.change_session(
            ChangeScheduledSession(
                self.owner,
                PlannedSessionId(self.future.pk),
                Revision(1),
                "Cambio de equipo",
                replacement=candidate,
            )
        )
        row = PlannedSession.objects.get(pk=changed.id)
        self.assertEqual(row.title, "Alternativa")
        self.assertEqual(row.blocks.get().sport, "cycling")
        self.assertEqual(self.future.blocks.get().sport, "running")
        self.assertFalse(Session.objects.exists())

    def test_effective_calendar_retains_past_and_completed_but_not_superseded_copies(self) -> None:
        today = PlannedSession.objects.get(plan_id=self.header.id, title="executed")
        execution = start_session(self.user, today)
        execution.status = "completed"
        execution.save(update_fields=["status"])
        changed = self.move()
        rows = effective_sessions(self.owner)
        self.assertEqual(len(rows), 3)
        self.assertEqual({r.title for r in rows}, {"executed", "future", "past"})
        self.assertNotIn(self.future.pk, [r.pk for r in rows])
        self.assertIn(today.pk, [r.pk for r in rows])
        self.assertIn(changed.id, [r.pk for r in rows])
        self.assertEqual(len(DjangoProgressRepository().scheduled(self.owner, TODAY)), 2)
        self.assertEqual(calendar_status(today, TODAY), "Completada")
        self.assertContains(self.client.get("/"), "Completada")

    def test_restore_never_rewinds_completed_or_partial_execution(self) -> None:
        changed = self.move()
        row = PlannedSession.objects.get(pk=changed.id)
        execution = start_session(self.user, row)
        block = execution.blocks.get()
        block.actual = {"distance_m": "2500"}
        block.save()
        restored = self.service.restore(
            RestorePlan(self.owner, PlanId(row.plan_id), self.header.id, "Recuperar programación")
        )
        self.assertEqual(restored.version, 3)
        self.assertFalse(
            PlannedSession.objects.filter(plan_id=restored.id, origin=self.future).exists()
        )
        execution.refresh_from_db()
        self.assertEqual(execution.planned_id, row.pk)
        self.assertEqual(execution.blocks.get().actual, {"distance_m": "2500"})
        self.assertIn(row.pk, [r.pk for r in effective_sessions(self.owner)])

    def test_superseded_starts_rejected_and_completed_intent_not_restarted(self) -> None:
        changed = self.move()
        self.assertEqual(self.client.post(f"/scheduled/{self.future.pk}/start/").status_code, 400)
        row = PlannedSession.objects.get(pk=changed.id)
        first = start_session(self.user, row)
        self.assertEqual(start_session(self.user, row).pk, first.pk)
        first.status = "completed"
        first.save(update_fields=["status"])
        self.assertEqual(self.client.post(f"/scheduled/{row.pk}/start/").status_code, 400)
        self.assertEqual(Session.objects.count(), 1)

    def test_old_prescription_models_and_blocks_are_immutable(self) -> None:
        self.move()
        self.future.notes = "Overwrite"
        with self.assertRaises(ValidationError):
            self.future.save()
        block = self.future.blocks.get()
        block.title = "Overwrite"
        with self.assertRaises(ValidationError):
            block.save()

    def test_incremental_editor_cannot_bypass_original_prescription_versioning(self) -> None:
        block = self.future.blocks.get()
        response = self.client.post(
            f"/blocks/{block.pk}/metrics/", {"revision": 1, "distance_m": "1000"}
        )
        self.assertEqual(response.status_code, 400)
        block.refresh_from_db()
        self.assertEqual(block.target, {"distance_m": "0"})
        self.assertEqual(TrainingPlan.objects.count(), 1)
        changed = self.move()
        copy_block = PlannedSession.objects.get(pk=changed.id).blocks.get()
        response = self.client.post(
            f"/blocks/{copy_block.pk}/metrics/",
            {"revision": changed.revision, "distance_m": "1000"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(block.target, {"distance_m": "0"})

    def test_web_reason_comparison_restoration_and_privacy(self) -> None:
        self.assertEqual(
            self.client.post(
                f"/scheduled/{self.future.pk}/reschedule/",
                {"date": TODAY.isoformat(), "revision": 1},
            ).status_code,
            200,
        )
        self.assertEqual(TrainingPlan.objects.count(), 1)
        changed = self.move()
        self.assertContains(
            self.client.get(f"/plans/{changed.plan}/?compare={self.header.id}"),
            "Disponibilidad personal",
        )
        response = self.client.post(
            f"/plans/{changed.plan}/restore/{self.header.id}/",
            {"reason": "Restauración consciente"},
        )
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/plans/{changed.plan}/").status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/plans/{changed.plan}/restore/{self.header.id}/", {"reason": "Ajeno"}
            ).status_code,
            404,
        )

    def test_paid_planning_guard_and_readable_history(self) -> None:
        billing = self.user.billing
        billing.status = "expired"
        billing.save()
        for path in (
            f"/plans/{self.header.id}/revise/",
            f"/scheduled/{self.future.pk}/change/",
            "/records/goal/new/",
        ):
            self.assertEqual(self.client.post(path, {"reason": "Bloqueado"}).status_code, 403)
        self.assertEqual(self.client.get(f"/plans/{self.header.id}/").status_code, 200)

    def test_owner_timezone_does_not_impose_hard_availability(self) -> None:
        preferences = self.user.training_settings
        preferences.timezone_name = "Pacific/Kiritimati"
        preferences.availability = [7]
        preferences.save()
        self.assertEqual(self.client.get("/").context["today"], TODAY + timedelta(days=1))
        self.move()
        self.assertEqual(TrainingPlan.objects.count(), 2)

    def test_cancelled_not_in_adherence_and_skipped_not_completed(self) -> None:
        today = PlannedSession.objects.get(plan_id=self.header.id, title="executed")
        cancelled = self.service.change_session(
            ChangeScheduledSession(
                self.owner,
                PlannedSessionId(today.pk),
                Revision(1),
                "Descanso declarado",
                ScheduleStatus.CANCELLED,
            )
        )
        self.assertEqual(len(DjangoProgressRepository().scheduled(self.owner, TODAY)), 1)
        copy = PlannedSession.objects.get(pk=cancelled.id)
        skipped = self.service.change_session(
            ChangeScheduledSession(
                self.owner,
                PlannedSessionId(copy.pk),
                Revision(copy.revision),
                "No realizada",
                ScheduleStatus.SKIPPED,
            )
        )
        self.assertFalse(Session.objects.exists())
        self.assertEqual(len(DjangoProgressRepository().scheduled(self.owner, TODAY)), 2)
        self.assertEqual(PlannedSession.objects.get(pk=skipped.id).status, "skipped")
