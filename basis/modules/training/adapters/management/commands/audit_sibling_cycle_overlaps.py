"""Read-only inventory of legacy H1 violations without personal or free-text data."""

from itertools import combinations, groupby

from django.core.management.base import BaseCommand

from basis.modules.training.adapters.models import Cycle
from basis.modules.training.domain.planning import (
    CycleDefinition,
    CycleKind,
    sibling_cycles_overlap,
)


class Command(BaseCommand):
    help = "Cuenta planes con ciclos hermanos solapados; solo lectura, sin datos personales."

    def handle(self, *args: object, **options: object) -> None:
        rows = Cycle.objects.only(
            "id", "plan_id", "parent_id", "kind", "start_date", "end_date"
        ).order_by("plan_id", "parent_id", "start_date", "pk")
        plans: set[int] = set()
        pairs = 0
        for (plan_id, parent_id), siblings in groupby(
            rows, key=lambda row: (row.plan_id, row.parent_id)
        ):
            cycles = tuple(
                CycleDefinition(
                    str(row.pk),
                    str(parent_id) if parent_id is not None else None,
                    CycleKind(row.kind),
                    "",
                    row.start_date,
                    row.end_date,
                )
                for row in siblings
            )
            for first, second in combinations(cycles, 2):
                if sibling_cycles_overlap(first, second):
                    plans.add(plan_id)
                    pairs += 1
                    self.stdout.write(
                        f"plan_id={plan_id} parent_id={parent_id} "
                        f"cycle_id={first.key} kind={first.kind.value} "
                        f"[{first.start_date.isoformat()}, {first.end_date.isoformat()}] "
                        f"cycle_id={second.key} kind={second.kind.value} "
                        f"[{second.start_date.isoformat()}, {second.end_date.isoformat()}]"
                    )
        self.stdout.write(f"Planes con solapes: {len(plans)}")
        self.stdout.write(f"Pares de ciclos hermanos solapados: {pairs}")
