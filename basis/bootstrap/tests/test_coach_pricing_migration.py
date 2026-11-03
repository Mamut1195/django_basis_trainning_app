"""Historical local policy migration on synthetic rows only."""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class HistoricalPricingMigrationTests(TransactionTestCase):
    def test_schema_downgrade_cannot_remove_existing_reconciliation_history(self) -> None:
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(
            [("basis_coach", "0002_frozen_pricing_reconciliation")]
        ).apps
        owner = get_user_model().objects.create_user(username="migration-audit")
        usage = apps.get_model("basis_coach", "UsagePeriod").objects.create(
            owner_id=owner.pk, key="audit", reserved="0.003"
        )
        job = apps.get_model("basis_coach", "AIJob").objects.create(
            id=uuid4(),
            owner_id=owner.pk,
            request_key=uuid4(),
            kind="short",
            prompt="fixture",
            context={},
            usage_period_id=usage.pk,
            reservation="0.003",
            requested_model="deepseek-flash",
            status="uncertain",
        )
        Audit = apps.get_model("basis_coach", "AIReconciliation")
        record = Audit.objects.create(
            job_id=job.pk,
            key="audit-1",
            actor="admin:test",
            reference="fixture:migration",
            evidence="Synthetic decision",
            decision="usage",
            outcome="retained",
            job_status="uncertain",
            created_at=timezone.now(),
        )
        with self.assertRaisesRegex(IrreversibleError, "durable ledger"):
            executor.migrate([("basis_coach", "0001_initial")])
        self.assertTrue(Audit.objects.filter(pk=record.pk).exists())

    def test_identified_history_is_preserved_and_unknown_policy_is_not_invented(self) -> None:
        target = [("basis_coach", "0002_frozen_pricing_reconciliation")]
        executor = MigrationExecutor(connection)
        executor.migrate([("basis_coach", "0001_initial")])
        try:
            apps = executor.loader.project_state([("basis_coach", "0001_initial")]).apps
            owner = get_user_model().objects.create_user(username="migration-pricing")
            usage = apps.get_model("basis_coach", "UsagePeriod").objects.create(
                owner_id=owner.pk, key="historic", reserved="0.006", spent="0.00042"
            )
            Job = apps.get_model("basis_coach", "AIJob")
            ids = []
            for version, model, reserve, cost in (
                ("flash-peak-2026-10-17", "deepseek-v4-flash", "0.003", "0.00042"),
                ("unidentified-policy", "deepseek-v4-flash", "0.003", None),
                ("flash-peak-2026-10-17", "unidentified-model", "0.003", None),
                ("flash-peak-2026-10-17", "deepseek-flash", "0.002", None),
            ):
                row = Job.objects.create(
                    id=uuid4(),
                    owner_id=owner.pk,
                    request_key=uuid4(),
                    kind="short",
                    prompt="fixture",
                    context={},
                    usage_period_id=usage.pk,
                    reservation=reserve,
                    cost=cost,
                    requested_model=model,
                    pricing_version=version,
                    status="succeeded" if cost else "uncertain",
                )
                ids.append(row.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            apps = executor.loader.project_state(target).apps
            Job = apps.get_model("basis_coach", "AIJob")
            known = Job.objects.get(pk=ids[0])
            self.assertEqual(known.pricing_snapshot["input_rate"], "0.00000030")
            self.assertEqual(known.pricing_snapshot["input_limit"], 4000)
            self.assertEqual(
                (known.cost, known.status, known.pricing_version),
                (Decimal("0.00042"), "succeeded", "flash-peak-2026-10-17"),
            )
            for pk in ids[1:]:
                self.assertIsNone(Job.objects.get(pk=pk).pricing_snapshot)
            # A reversible schema rollout preserves pre-existing amounts/versions.
            executor = MigrationExecutor(connection)
            executor.migrate([("basis_coach", "0001_initial")])
            apps = executor.loader.project_state([("basis_coach", "0001_initial")]).apps
            old = apps.get_model("basis_coach", "AIJob").objects.get(pk=ids[0])
            self.assertEqual(
                (old.cost, old.pricing_version), (Decimal("0.00042"), "flash-peak-2026-10-17")
            )
        finally:
            MigrationExecutor(connection).migrate(target)
