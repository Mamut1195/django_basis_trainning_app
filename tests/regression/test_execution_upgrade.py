"""Additive upgrade from the actual PR8 schema; never infer historical sources."""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExecutionUpgradeTests(TransactionTestCase):
    def test_upgrade_keeps_existing_ids_actuals_and_unknown_sources(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("basis_training", "0002_planning_version_history")])
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM django_migrations WHERE app = 'basis_training'"
                )
                self.assertEqual(cursor.fetchone()[0], 2)
            apps = executor.loader.project_state(
                [("basis_training", "0002_planning_version_history")]
            ).apps
            owner = apps.get_model("auth", "User").objects.create(username="upgrade623")
            classification = apps.get_model("basis_catalog", "Classification").objects.create(
                nombre="Fuerza"
            )
            exercise = apps.get_model("basis_catalog", "Exercise").objects.create(
                nombre="Legado", classification_id=classification.pk
            )
            session = apps.get_model("basis_training", "Session").objects.create(
                owner_id=owner.pk, title="Histórico", date=date(2026, 10, 19), status="completed"
            )
            block = apps.get_model("basis_training", "Block").objects.create(
                session_id=session.pk, title="Real", sport="strength", order=7
            )
            row = apps.get_model("basis_training", "StrengthSet").objects.create(
                block_id=block.pk,
                exercise_id=exercise.pk,
                target_reps=5,
                target_kg="80",
                actual_reps=4,
                actual_kg="75",
                order=9,
            )
            before = session.pk, block.pk, row.pk
        finally:
            upgrade = MigrationExecutor(connection)
            upgrade.migrate(upgrade.loader.graph.leaf_nodes())
        from basis.modules.training.adapters.models import Block, Session, StrengthSet

        self.assertEqual(Session.objects.get(pk=before[0]).status, "completed")
        self.assertEqual(Block.objects.get(pk=before[1]).order, 7)
        restored = StrengthSet.objects.get(pk=before[2])
        self.assertEqual((restored.target_reps, restored.actual_reps, restored.order), (5, 4, 9))
        self.assertEqual(str(restored.actual_kg), "75.00")
        self.assertIsNone(restored.source_id)
        self.assertIsNone(restored.actual_exercise_id)
        self.assertEqual(restored.adaptation_reason, "")
