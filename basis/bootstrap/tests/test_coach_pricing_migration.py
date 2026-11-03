"""Historical local policy migration on synthetic rows only."""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from basis.modules.coach.adapters.jobs import encode_pricing
from basis.modules.coach.domain.jobs import HISTORICAL_PRICING


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class HistoricalPricingMigrationTests(TransactionTestCase):
    def test_downgrade_preserves_unreconstructible_snapshot_even_without_audit(self) -> None:
        snapshot = {
            "version": "synthetic-new-policy",
            "input_rate": "0.00000060",
            "hit_rate": "0.000000006",
            "output_rate": "0.00000120",
            "input_limit": 4000,
            "output_limit": 100,
            "allowed_models": ["deepseek-v4-flash"],
        }
        self._assert_snapshot_is_preserved(snapshot, "synthetic-new-policy", "0.00252")

    def test_downgrade_preserves_exact_json_even_for_equivalent_historical_rates(self) -> None:
        snapshot = encode_pricing(HISTORICAL_PRICING.freeze("short"))
        assert snapshot is not None
        self._assert_snapshot_is_preserved(snapshot, "flash-peak-2026-10-17", "0.003")

    def test_downgrade_cannot_turn_missing_snapshot_into_identified_policy(self) -> None:
        self._assert_snapshot_is_preserved(None, "flash-peak-2026-10-17", "0.003")

    def _assert_snapshot_is_preserved(
        self, snapshot: dict[str, object] | None, version: str, reservation: str
    ) -> None:
        target = [("basis_coach", "0002_frozen_pricing_reconciliation")]
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(target).apps
        owner = get_user_model().objects.create_user(username="migration-new-snapshot")
        usage = apps.get_model("basis_coach", "UsagePeriod").objects.create(
            owner_id=owner.pk, key="new", reserved=reservation
        )
        Job = apps.get_model("basis_coach", "AIJob")
        job = Job.objects.create(
            id=uuid4(),
            owner_id=owner.pk,
            request_key=uuid4(),
            kind="short",
            prompt="fixture",
            context={},
            usage_period_id=usage.pk,
            reservation=reservation,
            requested_model="deepseek-v4-flash",
            pricing_version=version,
            pricing_snapshot=snapshot,
        )
        self.assertFalse(apps.get_model("basis_coach", "AIReconciliation").objects.exists())
        try:
            with self.assertRaisesRegex(IrreversibleError, "snapshot"):
                executor.migrate([("basis_coach", "0001_initial")])
            job.refresh_from_db()
            self.assertEqual(job.pricing_snapshot, snapshot)
        finally:
            MigrationExecutor(connection).migrate(target)

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
            before = list(
                Job.objects.order_by("pk").values_list(
                    "pk", "pricing_snapshot", "pricing_version", "cost", "reservation", "status"
                )
            )
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
        apps = MigrationExecutor(connection).loader.project_state(target).apps
        after = list(
            apps.get_model("basis_coach", "AIJob")
            .objects.order_by("pk")
            .values_list(
                "pk", "pricing_snapshot", "pricing_version", "cost", "reservation", "status"
            )
        )
        self.assertEqual(after, before)
