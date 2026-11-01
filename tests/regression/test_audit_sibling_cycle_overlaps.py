"""Read-only legacy inventory: inclusive H1 pairs, without free-text fields."""

from dataclasses import replace
from datetime import timedelta
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from basis.modules.training.adapters.models import Cycle, TrainingPlan
from basis.modules.training.public import CreatePlan, CycleKind
from tests.regression.test_planning_versioning import PlanningFixture
from tests_architecture.test_planning import TODAY
from tests_architecture.test_planning_siblings import sibling_plan


class AuditSiblingCycleOverlapsTests(PlanningFixture, TestCase):
    def audit(self) -> str:
        output = StringIO()
        call_command("audit_sibling_cycle_overlaps", stdout=output)
        return output.getvalue()

    def plan_with_siblings(self, kind: CycleKind) -> TrainingPlan:
        data, following = sibling_plan(kind)
        header = self.service.create(
            CreatePlan(
                self.owner,
                replace(data, goal=self.data.goal, cycles=(*data.cycles, following)),
            )
        )
        return TrainingPlan.objects.get(pk=header.id)

    def pair_line(self, first: Cycle, second: Cycle) -> str:
        return (
            f"plan_id={first.plan_id} parent_id={first.parent_id} "
            f"cycle_id={first.pk} kind={first.kind} [{first.start_date}, {first.end_date}] "
            f"cycle_id={second.pk} kind={second.kind} [{second.start_date}, {second.end_date}]"
        )

    def test_zero_overlaps_with_adjacent_siblings_and_parent_child_containment(self) -> None:
        for kind in CycleKind:
            self.plan_with_siblings(kind)
        self.assertEqual(
            self.audit(), "Planes con solapes: 0\nPares de ciclos hermanos solapados: 0\n"
        )

    def test_counts_distinct_plans_and_every_legacy_pair_at_all_levels(self) -> None:
        expected: list[str] = []
        for kind in CycleKind:
            plan = self.plan_with_siblings(kind)
            first = plan.cycles.get(title="Primero")
            second = plan.cycles.get(title="Siguiente")
            # Simulate pre-H1 rows; current save validation must remain enabled.
            Cycle.objects.filter(pk=second.pk).update(start_date=first.end_date)
            second.refresh_from_db()
            third = Cycle(
                plan=plan,
                parent_id=first.parent_id,
                kind=kind.value,
                title="Private cycle text",
                start_date=first.end_date,
                end_date=first.end_date,
            )
            Cycle.objects.bulk_create([third])
            expected.extend(
                (
                    self.pair_line(first, second),
                    self.pair_line(first, third),
                    self.pair_line(second, third),
                )
            )
        self.assertEqual(
            self.audit().splitlines(),
            [*expected, "Planes con solapes: 3", "Pares de ciclos hermanos solapados: 9"],
        )

    def test_different_plans_and_different_parents_are_not_siblings(self) -> None:
        plan = self.plan_with_siblings(CycleKind.MACRO)
        other = self.plan_with_siblings(CycleKind.MACRO)
        first = plan.cycles.get(title="Primero")
        second = plan.cycles.get(title="Siguiente")
        Cycle.objects.filter(pk=second.pk).update(start_date=first.start_date)
        second.refresh_from_db()
        # Children share dates but have different parents; roots in other plans also share dates.
        Cycle.objects.bulk_create(
            [
                Cycle(
                    plan=plan,
                    parent=parent,
                    kind="meso",
                    title="Private child",
                    start_date=TODAY,
                    end_date=TODAY + timedelta(days=9),
                )
                for parent in (first, second)
            ]
        )
        self.assertNotEqual(plan.pk, other.pk)
        self.assertEqual(
            self.audit().splitlines(),
            [
                self.pair_line(first, second),
                "Planes con solapes: 1",
                "Pares de ciclos hermanos solapados: 1",
            ],
        )

    def test_only_selects_safe_columns_and_leaves_all_database_rows_unchanged(self) -> None:
        plan = self.plan_with_siblings(CycleKind.MICRO)
        second = plan.cycles.get(title="Siguiente")
        Cycle.objects.filter(pk=second.pk).update(start_date=TODAY + timedelta(days=9))

        def state() -> dict[str, list[dict[str, object]]]:
            return {
                model._meta.label: list(model._base_manager.order_by("pk").values())
                for model in apps.get_models(include_auto_created=True)
                if model._meta.managed and not model._meta.proxy
            }

        before = state()
        with CaptureQueriesContext(connection) as queries:
            output = self.audit()
        self.assertEqual(state(), before)
        self.assertEqual(len(queries), 1)
        sql = queries[0]["sql"]
        self.assertTrue(sql.lstrip().upper().startswith("SELECT "))
        for field in ("title", "focus", "owner", "email", "username", "notes"):
            self.assertNotIn(field, sql.lower())
        for private in (self.user.username, self.user.email, plan.title, "Primero", "Siguiente"):
            if private:
                self.assertNotIn(private, output)
        self.assertIn("Planes con solapes: 1\n", output)
