"""Upgrade the actual preceding schema with historical FK rows intact."""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PlanningUpgradeTests(TransactionTestCase):
    def test_upgrade_preserves_rows_fk_and_unknown_legacy_provenance(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("basis_training", "0001_initial")])
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_migrations")
                self.assertEqual(cursor.fetchone()[0], 28)
            old = executor.loader.project_state([("basis_training", "0001_initial")]).apps
            user = old.get_model("auth", "User").objects.create(username="upgrade-622")
            goal = old.get_model("basis_training", "Goal").objects.create(
                owner_id=user.pk, title="Legado", sport="running"
            )
            plan = old.get_model("basis_training", "TrainingPlan").objects.create(
                owner_id=user.pk,
                goal_id=goal.pk,
                title="Histórico",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 31),
            )
            parent = None
            for kind in ("macro", "meso", "micro"):
                parent = old.get_model("basis_training", "Cycle").objects.create(
                    plan_id=plan.pk,
                    parent_id=parent.pk if parent else None,
                    kind=kind,
                    title=kind,
                    start_date=plan.start_date,
                    end_date=plan.end_date,
                )
            assert parent is not None
            scheduled = old.get_model("basis_training", "PlannedSession").objects.create(
                owner_id=user.pk,
                plan_id=plan.pk,
                cycle_id=parent.pk,
                title="Original",
                date=date(2026, 10, 19),
            )
            execution = old.get_model("basis_training", "Session").objects.create(
                owner_id=user.pk,
                planned_id=scheduled.pk,
                title="Resultado histórico",
                date=scheduled.date,
                status="completed",
            )
            block = old.get_model("basis_training", "Block").objects.create(
                session_id=execution.pk,
                sport="running",
                title="Real",
                actual={"distance_m": "2500"},
            )
            before = (plan.pk, scheduled.pk, execution.pk, block.pk)
        finally:
            MigrationExecutor(connection).migrate(
                [("basis_training", "0002_planning_version_history")]
            )
        from basis.modules.training.adapters.models import (
            Block,
            PlannedSession,
            Session,
            TrainingPlan,
        )

        current = TrainingPlan.objects.get(pk=before[0])
        self.assertEqual(
            (current.change_reason, current.changed_by_id, current.effective_on), ("", None, None)
        )
        restored = PlannedSession.objects.get(pk=before[1])
        self.assertEqual((restored.origin_id, restored.supersedes_id), (None, None))
        self.assertEqual(Session.objects.get(pk=before[2]).planned_id, restored.pk)
        self.assertEqual(Block.objects.get(pk=before[3]).actual, {"distance_m": "2500"})
