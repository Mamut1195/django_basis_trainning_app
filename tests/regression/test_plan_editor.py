"""MAM-629 private templates, accessible calendar and immutable editor acceptance."""

from dataclasses import replace
from datetime import timedelta
from typing import cast

from django.apps import apps
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from basis.bootstrap.plan_editor import plan_editor
from basis.modules.training.adapters.actions import session_snapshot, start_session
from basis.modules.training.adapters.editor_read import differences
from basis.modules.training.adapters.models import Cycle, Goal, PlannedSession, TrainingPlan
from basis.modules.training.application.plan_editor import CopyTemplate, EditPlan
from basis.modules.training.domain.plan_editor import edit_definition, template_definition
from basis.modules.training.public import (
    AddCycle,
    CreatePlan,
    CycleDefinition,
    CycleKind,
    InvalidPlanning,
    PlanningConflict,
    PlanningUnavailable,
)
from basis.shared.identifiers import AccountId, CycleId, GoalId, PlanId
from tests.regression.test_planning_versioning import PlanningFixture
from tests_architecture.test_planning import TODAY, definition
from tests_architecture.test_planning_siblings import OVERLAP, sibling_plan


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


class PlanEditorSiblingTests(PlanningFixture, TestCase):
    def database_state(self) -> dict[str, list[dict[str, object]]]:
        return {
            model._meta.label: list(model._base_manager.order_by("pk").values())
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        }

    def sibling_fixture(
        self, kind: CycleKind, *, with_following: bool = False
    ) -> tuple[TrainingPlan, CycleDefinition]:
        data, following = sibling_plan(kind)
        data = replace(data, goal=self.data.goal)
        if with_following:
            data = replace(data, cycles=(*data.cycles, following))
        header = self.service.create(CreatePlan(self.owner, data))
        return TrainingPlan.objects.get(pk=header.id), following

    def cycle_payload(self, cycle: CycleDefinition, parent: int | None) -> dict[str, object]:
        return {
            "kind": cycle.kind.value,
            "parent": parent or "",
            "title": cycle.title,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "focus": cycle.focus,
            "reason": "Ajustar calendario H1",
        }

    def assert_overlap_without_writes(self, url: str, payload: dict[str, object]) -> None:
        before = self.database_state()
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(OVERLAP, response.context["form"].non_field_errors())
        self.assertContains(response, OVERLAP)
        self.assertEqual(self.database_state(), before)

    def test_web_create_rejects_overlap_and_accepts_adjacency_at_all_levels(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, following = self.sibling_fixture(kind)
                first = plan.cycles.get(title="Primero")
                payload = self.cycle_payload(following, first.parent_id)
                url = reverse("editor-cycle-new", args=[plan.pk])
                self.assert_overlap_without_writes(url, {**payload, "start_date": first.end_date})
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    plan.cycles.get(title="Siguiente").start_date, following.start_date
                )

    def test_web_edit_rejects_overlap_and_versions_adjacent_siblings(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, following = self.sibling_fixture(kind, with_following=True)
                cycle = plan.cycles.get(title="Siguiente")
                payload = self.cycle_payload(replace(following, title="Editado"), cycle.parent_id)
                url = reverse("editor-cycle", args=[plan.pk, cycle.pk])
                self.assert_overlap_without_writes(
                    url, {**payload, "start_date": TODAY + timedelta(days=9)}
                )
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 302)
                head = TrainingPlan.objects.get(previous=plan)
                self.assertEqual(head.cycles.get(title="Editado").start_date, following.start_date)
                cycle.refresh_from_db()
                self.assertEqual(cycle.title, "Siguiente")

    def test_web_move_validates_destination_and_preserves_source(self) -> None:
        plan, _ = self.sibling_fixture(CycleKind.MESO, with_following=True)
        parents = (plan.cycles.get(title="Primero"), plan.cycles.get(title="Siguiente"))
        source = Cycle.objects.create(
            plan=plan,
            parent=parents[0],
            kind="micro",
            title="Origen",
            start_date=TODAY,
            end_date=TODAY + timedelta(days=4),
        )
        Cycle.objects.create(
            plan=plan,
            parent=parents[1],
            kind="micro",
            title="Destino",
            start_date=TODAY + timedelta(days=10),
            end_date=TODAY + timedelta(days=14),
        )
        url = reverse("editor-cycle", args=[plan.pk, source.pk])
        payload = {
            "kind": "micro",
            "parent": parents[1].pk,
            "title": "Movido",
            "start_date": TODAY + timedelta(days=15),
            "end_date": TODAY + timedelta(days=19),
            "reason": "Cambiar de padre",
        }
        self.assert_overlap_without_writes(
            url, {**payload, "start_date": TODAY + timedelta(days=14)}
        )
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        head = TrainingPlan.objects.get(previous=plan)
        moved = head.cycles.get(title="Movido")
        self.assertEqual(moved.parent_id, head.cycles.get(title="Siguiente").pk)
        self.assertEqual(moved.start_date, TODAY + timedelta(days=15))
        source.refresh_from_db()
        self.assertEqual((source.parent_id, source.start_date), (parents[0].pk, TODAY))

    def test_web_template_accepts_adjacency_and_rejects_legacy_overlap(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, _ = self.sibling_fixture(kind, with_following=True)
                payload = {
                    "source": plan.pk,
                    "goal": plan.goal_id,
                    "title": "Plantilla H1",
                    "start_date": TODAY + timedelta(days=60),
                    "reason": "Nuevo periodo",
                }
                url = reverse("plan-template")
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 302)
                copied = TrainingPlan.objects.get(
                    pk=response["Location"].rstrip("/").split("/")[-2]
                )
                self.assertEqual(
                    copied.cycles.get(title="Siguiente").start_date, TODAY + timedelta(days=70)
                )
                # Simulate pre-H1 persisted data, bypassing current model validation only here.
                plan.cycles.filter(title="Siguiente").update(start_date=TODAY + timedelta(days=9))
                self.assert_overlap_without_writes(url, payload)

    def test_application_create_overlap_fails_before_writing_any_rows(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                data, following = sibling_plan(kind)
                following = replace(following, start_date=TODAY + timedelta(days=9))
                before = self.database_state()
                with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                    self.service.create(
                        CreatePlan(
                            self.owner,
                            replace(data, goal=self.data.goal, cycles=(*data.cycles, following)),
                        )
                    )
                self.assertEqual(self.database_state(), before)

    def test_application_add_cycle_rejects_overlap_under_aggregate_lock(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, following = self.sibling_fixture(kind)
                first = plan.cycles.get(title="Primero")
                command = AddCycle(
                    self.owner,
                    PlanId(plan.pk),
                    following,
                    CycleId(first.parent_id) if first.parent_id else None,
                )
                before = self.database_state()
                with self.assertRaisesRegex(InvalidPlanning, OVERLAP):
                    self.service.add_cycle(
                        replace(command, data=replace(following, start_date=first.end_date))
                    )
                self.assertEqual(self.database_state(), before)
                added = self.service.add_cycle(command)
                self.assertEqual(plan.cycles.get(pk=added).start_date, following.start_date)

    def legacy_siblings(self, kind: CycleKind) -> tuple[TrainingPlan, Cycle, Cycle]:
        plan, _ = self.sibling_fixture(kind, with_following=True)
        first = plan.cycles.get(title="Primero")
        second = plan.cycles.get(title="Siguiente")
        # Persisted pre-H1 overlap, bypassing validation only in this fixture.
        plan.cycles.filter(pk=second.pk).update(start_date=first.end_date)
        second.refresh_from_db()
        return plan, first, second

    def assert_detailed_overlap_without_writes(
        self,
        url: str,
        payload: dict[str, object],
        first: Cycle,
        second: Cycle,
        *,
        offset: int = 0,
    ) -> None:
        before = self.database_state()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(OVERLAP, response.context["form"].non_field_errors())
        self.assertContains(response, OVERLAP)
        for cycle in (first, second):
            fragment = (
                f'"{cycle.title}" ({cycle.kind}, '
                f"{cycle.start_date + timedelta(days=offset)} a "
                f"{cycle.end_date + timedelta(days=offset)})"
            )
            self.assertContains(response, escape(fragment))
        self.assertContains(
            response, "Ajusta las fechas para que uno termine antes de que empiece el otro"
        )
        self.assertContains(response, "inicio y final están incluidas")
        self.assertEqual(self.database_state(), before)
        for query in queries:
            self.assertNotIn(
                query["sql"].lstrip().split()[0].upper(),
                {"INSERT", "UPDATE", "DELETE", "REPLACE"},
            )

    def test_legacy_template_shows_both_cycles_and_shifted_dates_without_writes(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, first, second = self.legacy_siblings(kind)
                self.assert_detailed_overlap_without_writes(
                    reverse("plan-template"),
                    {
                        "source": plan.pk,
                        "goal": plan.goal_id,
                        "title": "Copia",
                        "start_date": plan.start_date + timedelta(days=60),
                        "reason": "Nuevo periodo",
                    },
                    first,
                    second,
                    offset=60,
                )

    def test_legacy_plan_edit_shows_both_cycles_dates_and_remedy_without_writes(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, first, second = self.legacy_siblings(kind)
                self.assert_detailed_overlap_without_writes(
                    reverse("plan-edit", args=[plan.pk]),
                    {
                        "title": plan.title,
                        "start_date": plan.start_date,
                        "end_date": plan.end_date,
                        "reason": "Ajustar plan",
                    },
                    first,
                    second,
                )

    def test_legacy_cycle_edit_shows_both_cycles_dates_and_remedy_without_writes(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, first, second = self.legacy_siblings(kind)
                candidate = CycleDefinition(
                    str(second.pk),
                    str(second.parent_id) if second.parent_id else None,
                    kind,
                    second.title,
                    second.start_date,
                    second.end_date,
                )
                self.assert_detailed_overlap_without_writes(
                    reverse("editor-cycle", args=[plan.pk, second.pk]),
                    self.cycle_payload(candidate, second.parent_id),
                    first,
                    second,
                )

    def test_legacy_session_move_shows_inherited_overlap_without_writes(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, first, second = self.legacy_siblings(kind)
                micro = first
                for child_kind in (CycleKind.MESO, CycleKind.MICRO):
                    if child_kind == kind or (kind == CycleKind.MICRO):
                        continue
                    micro = Cycle.objects.create(
                        plan=plan,
                        parent=micro,
                        kind=child_kind.value,
                        title=child_kind.value,
                        start_date=first.start_date,
                        end_date=first.end_date,
                    )
                session = PlannedSession.objects.create(
                    owner=self.user,
                    plan=plan,
                    cycle=micro,
                    title="Sesión futura",
                    date=TODAY + timedelta(days=1),
                )
                self.assert_detailed_overlap_without_writes(
                    reverse("editor-session", args=[session.pk, "move"]),
                    {
                        "date": TODAY + timedelta(days=2),
                        "cycle": micro.pk,
                        "revision": session.revision,
                        "reason": "Mover sesión",
                    },
                    first,
                    second,
                )

    def test_cycle_create_shows_conflicting_titles_types_dates_and_remedy(self) -> None:
        for kind in CycleKind:
            with self.subTest(kind=kind):
                plan, first, _ = self.legacy_siblings(kind)
                candidate = Cycle(
                    plan=plan,
                    parent_id=first.parent_id,
                    kind=kind.value,
                    title='Nuevo <ciclo> "privado"',
                    start_date=first.start_date,
                    end_date=first.end_date,
                )
                self.assert_detailed_overlap_without_writes(
                    reverse("editor-cycle-new", args=[plan.pk]),
                    {
                        "kind": kind.value,
                        "parent": first.parent_id or "",
                        "title": candidate.title,
                        "start_date": candidate.start_date,
                        "end_date": candidate.end_date,
                    },
                    first,
                    candidate,
                )


class PlanEditorSecurityTests(PlanningFixture, TestCase):
    def database_state(self) -> dict[str, list[dict[str, object]]]:
        """Compare rows, fields and relations, including versions and audit records."""
        return {
            model._meta.label: list(model._base_manager.order_by("pk").values())
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and not model._meta.proxy
        }

    def editor_cases(self) -> dict[str, tuple[str, dict[str, object]]]:
        plan = TrainingPlan.objects.get(pk=self.header.id)
        cycle = plan.cycles.get(kind="micro")
        cycle_data: dict[str, object] = {
            "kind": cycle.kind,
            "parent": cycle.parent_id,
            "title": "Ciclo editado",
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "focus": "Constancia",
            "reason": "Ajustar ciclo",
        }
        revision = {"revision": self.future.revision, "reason": "Ajustar sesión"}
        cases: dict[str, tuple[str, dict[str, object]]] = {
            "template": (
                reverse("plan-template"),
                {
                    "source": plan.pk,
                    "goal": plan.goal_id,
                    "title": "Copia privada",
                    "start_date": TODAY,
                    "reason": "Nuevo periodo",
                },
            ),
            "plan-edit": (
                reverse("plan-edit", args=[plan.pk]),
                {
                    "title": "Plan editado",
                    "start_date": plan.start_date,
                    "end_date": plan.end_date,
                    "notes": "Notas nuevas",
                    "reason": "Ajustar plan",
                },
            ),
            "cycle-new": (reverse("editor-cycle-new", args=[plan.pk]), cycle_data),
            "cycle-edit": (reverse("editor-cycle", args=[plan.pk, cycle.pk]), cycle_data),
            "session-new": (
                reverse("editor-session-new", args=[plan.pk]),
                {"plan": plan.pk, "cycle": cycle.pk, "title": "Nueva sesión", "date": TODAY},
            ),
            "edit": (
                reverse("editor-session", args=[self.future.pk, "edit"]),
                {**revision, "title": "Sesión editada", "notes": "Notas nuevas"},
            ),
            "move": (
                reverse("editor-session", args=[self.future.pk, "move"]),
                {**revision, "date": TODAY + timedelta(days=2), "cycle": cycle.pk},
            ),
        }
        for action in ("skipped", "cancelled", "replace"):
            cases[action] = (
                reverse("editor-session", args=[self.future.pk, "change"]),
                {
                    **revision,
                    "action": action,
                    "replacement": plan.sessions.get(title="past").pk
                    if action == "replace"
                    else "",
                },
            )
        return cases

    def additional_plan(self, *, foreign: bool = False) -> TrainingPlan:
        user = self.other if foreign else self.user
        goal = Goal.objects.create(owner=user, title="Otro objetivo", sport="running")
        header = self.service.create(CreatePlan(AccountId(user.pk), definition(GoalId(goal.pk))))
        return TrainingPlan.objects.get(pk=header.id)

    def assert_foreign_case_rejected(self, case: str) -> None:
        url, payload = self.editor_cases()[case]
        self.client.force_login(self.other)
        for method in (self.client.get, self.client.post):
            with self.subTest(case=case, method=method.__name__):
                before = self.database_state()
                response = method(url, cast("dict[str, str]", payload))
                self.assertEqual(self.database_state(), before)
                self.assertEqual(response.status_code, 404)

    def assert_invalid_reference_without_write(
        self, url: str, payload: dict[str, object], field: str
    ) -> None:
        before = self.database_state()
        response = self.client.post(url, payload)
        self.assertEqual(self.database_state(), before)
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors)

    def test_template_rejects_foreign_source_and_goal_without_writes(self) -> None:
        foreign = self.additional_plan(foreign=True)
        url, payload = self.editor_cases()["template"]
        for field, value in (("source", foreign.pk), ("goal", foreign.goal_id)):
            with self.subTest(field=field):
                self.assert_invalid_reference_without_write(url, {**payload, field: value}, field)

    def test_foreign_plan_edit_get_post_are_404_without_writes(self) -> None:
        self.assert_foreign_case_rejected("plan-edit")

    def test_foreign_cycle_new_get_post_are_404_without_writes(self) -> None:
        self.assert_foreign_case_rejected("cycle-new")

    def test_foreign_cycle_edit_get_post_are_404_without_writes(self) -> None:
        self.assert_foreign_case_rejected("cycle-edit")

    def test_foreign_cycle_id_in_own_plan_is_404_without_writes(self) -> None:
        own = self.additional_plan(foreign=True)
        foreign_cycle = self.future.cycle_id
        _, payload = self.editor_cases()["cycle-edit"]
        self.client.force_login(self.other)
        url = reverse("editor-cycle", args=[own.pk, foreign_cycle])
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                before = self.database_state()
                response = method(url, cast("dict[str, str]", payload))
                self.assertEqual(self.database_state(), before)
                self.assertEqual(response.status_code, 404)

    def test_foreign_session_new_get_post_are_404_without_writes(self) -> None:
        self.assert_foreign_case_rejected("session-new")

    def test_foreign_session_actions_get_post_are_404_without_writes(self) -> None:
        for action in ("edit", "move", "skipped", "cancelled", "replace"):
            self.assert_foreign_case_rejected(action)

    def test_cycle_new_rejects_parent_from_another_own_plan_without_writes(self) -> None:
        other_plan = self.additional_plan()
        url, payload = self.editor_cases()["cycle-new"]
        self.assert_invalid_reference_without_write(
            url, {**payload, "parent": other_plan.cycles.get(kind="meso").pk}, "parent"
        )

    def test_cycle_edit_rejects_parent_from_another_own_plan_without_writes(self) -> None:
        other_plan = self.additional_plan()
        url, payload = self.editor_cases()["cycle-edit"]
        self.assert_invalid_reference_without_write(
            url, {**payload, "parent": other_plan.cycles.get(kind="meso").pk}, "parent"
        )

    def test_session_move_rejects_cycle_from_another_own_plan_without_writes(self) -> None:
        other_plan = self.additional_plan()
        url, payload = self.editor_cases()["move"]
        self.assert_invalid_reference_without_write(
            url, {**payload, "cycle": other_plan.cycles.get(kind="micro").pk}, "cycle"
        )

    def test_session_new_rejects_cycle_from_another_own_plan_without_writes(self) -> None:
        other_plan = self.additional_plan()
        url, payload = self.editor_cases()["session-new"]
        self.assert_invalid_reference_without_write(
            url, {**payload, "cycle": other_plan.cycles.get(kind="micro").pk}, "cycle"
        )

    def test_replacement_rejects_foreign_session_without_writes(self) -> None:
        foreign = self.additional_plan(foreign=True)
        url, payload = self.editor_cases()["replace"]
        self.assert_invalid_reference_without_write(
            url, {**payload, "replacement": foreign.sessions.get(title="past").pk}, "replacement"
        )

    def test_all_editor_posts_require_csrf_token_without_writes(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for case, (url, payload) in self.editor_cases().items():
            # Both a missing cookie and a cookie without the submitted token must fail.
            for cookie in (False, True):
                with self.subTest(case=case, csrf_cookie=cookie):
                    if cookie:
                        before = self.database_state()
                        self.assertEqual(client.get(url).status_code, 200)
                        self.assertEqual(self.database_state(), before)
                        self.assertIn("csrftoken", client.cookies)
                    else:
                        client.cookies.pop("csrftoken", None)
                    before = self.database_state()
                    response = client.post(url, payload)
                    self.assertEqual(self.database_state(), before)
                    self.assertEqual(response.status_code, 403)

    def test_all_editor_gets_with_mutation_fields_do_not_write(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for case, (url, payload) in self.editor_cases().items():
            with self.subTest(case=case):
                before = self.database_state()
                response = client.get(url, cast("dict[str, str]", payload))
                self.assertEqual(self.database_state(), before)
                self.assertEqual(response.status_code, 200)
