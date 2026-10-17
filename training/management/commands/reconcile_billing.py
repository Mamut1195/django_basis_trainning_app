from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from training.billing import ProviderUnavailable, reconcile
from training.models import BillingAccount


class Command(BaseCommand):
    help = "Reconcile current Polar customer state; schedule this for missed webhook recovery."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--all", action="store_true")
        group.add_argument("--owner-id", type=int)

    def handle(self, *args, **options):
        rows = BillingAccount.objects.select_related("owner__athlete")
        if options["owner_id"]:
            rows = rows.filter(owner_id=options["owner_id"])
        else:
            rows = rows.filter(Q(polar_customer_id__isnull=False) | Q(needs_reconciliation=True))
        failed = 0
        for row in rows.iterator():
            try:
                reconcile(row.owner)
            except ProviderUnavailable:
                BillingAccount.objects.filter(pk=row.pk).update(needs_reconciliation=True)
                failed += 1
        if failed:
            raise CommandError(
                f"Conciliaciones pendientes: {failed}. No se registran respuestas ni credenciales del proveedor."
            )
        self.stdout.write("Conciliación completada.")
