from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q

from basis.modules.billing.adapters.actions import ProviderUnavailable, reconcile
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.billing.adapters.record_actions import mark_pending


class Command(BaseCommand):
    help = "Reconcile current Polar customer state; schedule this for missed webhook recovery."

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--all", action="store_true")
        group.add_argument("--owner-id", type=int)

    def handle(self, *args: object, **options: object) -> None:
        rows = BillingAccount.objects.select_related("owner__athlete")
        owner_id = options["owner_id"]
        if isinstance(owner_id, int) and owner_id:
            rows = rows.filter(owner_id=owner_id)
        else:
            rows = rows.filter(Q(polar_customer_id__isnull=False) | Q(needs_reconciliation=True))
        failed = 0
        for row in rows.iterator():
            try:
                reconcile(row.owner)
            except ProviderUnavailable:
                mark_pending(row.owner_id)
                failed += 1
        if failed:
            raise CommandError(
                f"Conciliaciones pendientes: {failed}. No se registran respuestas ni credenciales del proveedor."
            )
        self.stdout.write("Conciliación completada.")
