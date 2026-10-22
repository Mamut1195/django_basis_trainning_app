import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q
from django.utils import timezone

from basis.modules.billing.adapters.actions import ProviderUnavailable, reconcile
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.billing.adapters.record_actions import mark_pending
from basis.modules.billing.adapters.recovery import process_pending


class Command(BaseCommand):
    help = "Reconcile current Polar customer state; schedule this for missed webhook recovery."

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--all", action="store_true")
        group.add_argument("--owner-id", type=int)
        parser.add_argument("--watch", action="store_true")
        parser.add_argument(
            "--retry-events",
            action="store_true",
            help="Explicitly retry exhausted/unlinked receipts (bounded batch).",
        )

    def handle(self, *args: object, **options: object) -> None:
        self.last_pk = 0
        while True:
            process_pending(limit=25, retry_exhausted=bool(options["retry_events"]))
            failed = self.reconcile_accounts(options)
            if not options["watch"]:
                if failed:
                    raise CommandError(
                        f"Conciliaciones pendientes: {failed}. No se registran respuestas ni credenciales del proveedor."
                    )
                self.stdout.write("Conciliación completada.")
                return
            self.stdout.write(f"billing_recovery pending_accounts={failed}")
            time.sleep(60)

    def reconcile_accounts(self, options: dict[str, object]) -> int:
        rows = BillingAccount.objects.select_related("owner__athlete")
        owner_id = options["owner_id"]
        if isinstance(owner_id, int) and owner_id:
            rows = rows.filter(owner_id=owner_id)
        else:
            rows = rows.filter(
                Q(polar_customer_id__isnull=False)
                | Q(needs_reconciliation=True)
                | Q(checkout_attempt__isnull=False)
            )
            if options["watch"]:
                rows = rows.filter(
                    Q(needs_reconciliation=True)
                    | Q(reconciled_at__isnull=True)
                    | Q(reconciled_at__lt=timezone.now() - timedelta(minutes=5))
                )
                batch = rows.filter(pk__gt=self.last_pk).order_by("pk")[:25]
                if not batch.exists():
                    self.last_pk = 0
                    batch = rows.order_by("pk")[:25]
                rows = batch
        failed = 0
        for row in rows.iterator():
            self.last_pk = row.pk
            try:
                reconcile(row.owner)
            except ProviderUnavailable:
                mark_pending(row.owner_id)
                failed += 1
        return failed
