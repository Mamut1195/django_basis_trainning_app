"""MAM-629 private templates, accessible calendar and immutable editor acceptance."""

from dataclasses import replace
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from basis.bootstrap.plan_editor import plan_editor
from basis.modules.training.adapters.actions import session_snapshot, start_session
from basis.modules.training.adapters.editor_read import differences
from basis.modules.training.adapters.models import Goal, PlannedSession, TrainingPlan
from basis.modules.training.application.plan_editor import CopyTemplate, EditPlan
from basis.modules.training.domain.plan_editor import edit_definition, template_definition
from basis.modules.training.public import InvalidPlanning, PlanningConflict, PlanningUnavailable
from basis.shared.identifiers import AccountId, GoalId
from tests.regression.test_planning_versioning import PlanningFixture
from tests_architecture.test_planning import TODAY


class PlanEditorTests(PlanningFixture, TestCase):
    def plan(self) -> TrainingPlan:
        return TrainingPlan.objects.get(pk=self.header.id)

    def edit(
        self, *, owner: AccountId | None = None, reason: str = "Ajustar disponibilidad"
    ) -> EditPlan:
        return EditPlan(
            owner or self.owner,
            self.header.id,
            "Plan editado",
            self.data.start_date,
            self.data.end_date,
            "Notas nuevas",
            reason,
        )

    def test_pure_edit_validates_descendants_and_keeps_drafts(self) -> None:
        snapshot = self.service.repository.snapshot(self.owner, self.header.id, lock=False)
        with self.assertRaises(InvalidPlanning):
            edit_definition(snapshot, TODAY, "Plan", TODAY, TODAY, "")
        draft = replace(
            snapshot,
            definition=replace(
                snapshot.definition,
                sessions=tuple(replace(s, blocks=()) for s in snapshot.definition.sessions),
            ),
        )
        result = edit_definition(
            draft, TODAY, "Borrador", self.data.start_date, self.data.end_date, ""
        )
        self.assertEqual(len(result.sessions), 2)
        self.assertTrue(all(not s.blocks for s in result.sessions))

    def test_edit_creates_version_without_touching_executed_snapshot(self) -> None:
        execution = start_session(self.user, self.plan().sessions.get(title="executed"))
        block = execution.blocks.get()
        block.actual = {"distance_m": "1234"}
        block.save()
        before = session_snapshot(execution)
        result = plan_editor().edit(self.edit())
        head = TrainingPlan.objects.get(pk=result.id)
        self.assertEqual(
            (head.version, head.previous_id, head.change_reason, head.changed_by_id),
            (2, self.header.id, "Ajustar disponibilidad", self.user.pk),
        )
        self.assertEqual(list(head.sessions.values_list("title", flat=True)), ["future"])
        execution.refresh_from_db()
        self.assertEqual(before, session_snapshot(execution))
        response = self.client.get(reverse("plan-calendar", args=[head.pk]))
        self.assertContains(response, "Conservada en v1")
        self.assertContains(response, "executed")
        with self.assertRaises(PlanningConflict):
            plan_editor().edit(self.edit())

    def test_template_shifts_dates_with_new_lineage_and_no_execution_identity(self) -> None:
        start_session(self.user, self.plan().sessions.get(title="executed"))
        start = TODAY + timedelta(days=30)
        goal = Goal.objects.create(owner=self.user, title="Meta nueva", sport="running")
        result = plan_editor().copy(
            CopyTemplate(
                self.owner,
                self.header.id,
                GoalId(goal.pk),
                "Plantilla adaptada",
                start,
                "Nuevo bloque",
            )
        )
        copied = TrainingPlan.objects.get(pk=result.id)
        self.assertNotEqual(copied.lineage, self.header.lineage)
        self.assertEqual((copied.version, copied.previous_id, copied.start_date), (1, None, start))
        self.assertEqual(copied.cycles.count(), 3)
        self.assertEqual(copied.sessions.count(), 3)
        self.assertTrue(
            all(
                s.origin_id is None and s.supersedes_id is None and not s.executions.exists()
                for s in copied.sessions.all()
            )
        )
        self.assertTrue(all(not b.actual for s in copied.sessions.all() for b in s.blocks.all()))
        snapshot = self.service.repository.snapshot(self.owner, self.header.id, lock=False)
        pure = template_definition(snapshot, GoalId(goal.pk), "Copia", start)
        self.assertEqual(
            pure.sessions[0].date, self.data.sessions[0].date + (start - self.data.start_date)
        )

    def test_copy_and_edit_are_owner_scoped_and_reason_required(self) -> None:
        foreign = Goal.objects.create(owner=self.other, title="Privado", sport="running")
        with self.assertRaises(InvalidPlanning):
            plan_editor().copy(
                CopyTemplate(self.owner, self.header.id, GoalId(foreign.pk), "No", TODAY, "Motivo")
            )
        with self.assertRaises(PlanningUnavailable):
            plan_editor().edit(self.edit(owner=AccountId(self.other.pk)))
        with self.assertRaises(InvalidPlanning):
            plan_editor().edit(self.edit(reason="   "))
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_week_has_seven_days_htmx_fragment_and_full_fallback(self) -> None:
        url = reverse("plan-calendar", args=[self.header.id])
        full = self.client.get(url, {"week": TODAY.isoformat()})
        self.assertEqual(len(full.context["days"]), 7)
        self.assertContains(full, "Macrociclo")
        self.assertContains(full, "Microciclo")
        self.assertContains(full, "future")
        fragment = self.client.get(url, {"week": TODAY.isoformat()}, HTTP_HX_REQUEST="true")
        self.assertContains(fragment, 'id="plan-board"')
        self.assertNotContains(fragment, "<html")
        self.assertIn("no-store", fragment["Cache-Control"])
        self.assertEqual(self.client.get(url, {"week": "mal"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"compare": "mal"}).status_code, 400)

    def test_web_cycle_edit_versions_and_invalid_dates_stay_local(self) -> None:
        cycle = self.plan().cycles.get(kind="micro")
        url = reverse("editor-cycle", args=[self.header.id, cycle.pk])
        payload = {
            "kind": cycle.kind,
            "parent": cycle.parent_id,
            "title": "Semana editada",
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "focus": "Constancia",
            "reason": "Cambiar enfoque",
        }
        bad = self.client.post(url, {**payload, "end_date": TODAY - timedelta(days=10)})
        self.assertEqual(bad.status_code, 200)
        self.assertTrue(bad.context["form"].errors)
        self.assertEqual(TrainingPlan.objects.count(), 1)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        cycle.refresh_from_db()
        self.assertEqual(cycle.title, "Micro")
        head = TrainingPlan.objects.get(previous_id=self.header.id)
        self.assertEqual(head.cycles.get(kind="micro").title, "Semana editada")

    def test_web_create_hierarchy_and_session_without_dragging(self) -> None:
        plan = TrainingPlan.objects.create(
            owner=self.user,
            goal=self.plan().goal,
            title="Nuevo bloque",
            start_date=self.data.start_date,
            end_date=self.data.end_date,
        )
        parent = ""
        for kind in ("macro", "meso", "micro"):
            response = self.client.post(
                reverse("editor-cycle-new", args=[plan.pk]),
                {
                    "kind": kind,
                    "parent": parent,
                    "title": kind,
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                },
            )
            self.assertEqual(response.status_code, 302)
            parent = str(plan.cycles.get(kind=kind).pk)
        response = self.client.post(
            reverse("editor-session-new", args=[plan.pk]),
            {"plan": plan.pk, "cycle": parent, "title": "Sesión concreta", "date": TODAY},
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(
            self.client.get(reverse("plan-calendar", args=[plan.pk])), "Sesión concreta"
        )

    def test_web_move_skip_replace_and_compare_preserve_intent(self) -> None:
        old = self.future
        move = self.client.post(
            reverse("editor-session", args=[old.pk, "move"]),
            {
                "date": TODAY + timedelta(days=2),
                "cycle": old.cycle_id,
                "revision": old.revision,
                "reason": "Viaje",
            },
        )
        self.assertEqual(move.status_code, 302)
        moved = PlannedSession.objects.get(supersedes=old)
        skip = self.client.post(
            reverse("editor-session", args=[moved.pk, "change"]),
            {
                "action": "skipped",
                "replacement": "",
                "revision": moved.revision,
                "reason": "Descanso",
            },
        )
        self.assertEqual(skip.status_code, 302)
        skipped = PlannedSession.objects.get(supersedes=moved)
        replace_response = self.client.post(
            reverse("editor-session", args=[skipped.pk, "change"]),
            {
                "action": "replace",
                "replacement": self.plan().sessions.get(title="past").pk,
                "revision": skipped.revision,
                "reason": "Otra prescripción",
            },
        )
        self.assertEqual(replace_response.status_code, 302)
        replaced = PlannedSession.objects.get(supersedes=skipped)
        self.assertEqual(
            (replaced.status, replaced.origin_id, replaced.date), ("scheduled", old.pk, moved.date)
        )
        old.refresh_from_db()
        self.assertEqual((old.date, old.status), (TODAY + timedelta(days=1), "scheduled"))
        comparison = self.client.get(
            reverse("plan-calendar", args=[replaced.plan_id]), {"compare": self.header.id}
        )
        self.assertContains(comparison, "Antes:")
        self.assertContains(comparison, "Después:")
        self.assertTrue(differences(self.plan(), replaced.plan))

    def test_web_conflict_and_execution_guard_show_errors_next_to_form(self) -> None:
        start_session(self.user, self.future)
        response = self.client.post(
            reverse("editor-session", args=[self.future.pk, "edit"]),
            {"title": "No", "notes": "", "revision": 1, "reason": "No sobrescribir"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "ya tiene ejecuciones", status_code=409)
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_web_template_and_foreign_get_post_guards(self) -> None:
        template_url = reverse("plan-template")
        response = self.client.post(
            template_url,
            {
                "source": self.header.id,
                "goal": self.plan().goal_id,
                "title": "Nuevo desde plantilla",
                "start_date": TODAY,
                "reason": "Nuevo periodo",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.other)
        for name, args in (
            ("plan-calendar", [self.header.id]),
            ("plan-edit", [self.header.id]),
            ("editor-cycle", [self.header.id, self.plan().cycles.get(kind="macro").pk]),
            ("editor-session-new", [self.header.id]),
            ("editor-session", [self.future.pk, "move"]),
        ):
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(reverse(name, args=args)).status_code, 404)
        foreign = self.client.post(
            template_url,
            {
                "source": self.header.id,
                "goal": self.plan().goal_id,
                "title": "No",
                "start_date": TODAY,
                "reason": "No",
            },
        )
        self.assertTrue(foreign.context["form"].errors)
        own_goal = Goal.objects.create(owner=self.other, title="Propio", sport="running")
        own_plan = TrainingPlan.objects.create(
            owner=self.other, goal=own_goal, title="Propio", start_date=TODAY, end_date=TODAY
        )
        self.assertEqual(
            self.client.get(
                reverse("plan-calendar", args=[own_plan.pk]), {"compare": self.header.id}
            ).status_code,
            404,
        )

    def test_plan_edit_dates_render_as_iso_for_native_inputs(self) -> None:
        response = self.client.get(reverse("plan-edit", args=[self.header.id]))
        self.assertContains(response, f'value="{self.data.start_date.isoformat()}"')
        self.assertContains(response, f'value="{self.data.end_date.isoformat()}"')

    def test_readonly_account_cannot_edit(self) -> None:
        self.user.billing.status = "inactive"
        self.user.billing.save()
        self.assertEqual(
            self.client.post(reverse("plan-edit", args=[self.header.id]), {}).status_code, 403
        )
