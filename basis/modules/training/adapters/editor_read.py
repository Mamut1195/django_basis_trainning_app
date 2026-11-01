"""Owner-scoped projections for the weekly calendar, tree and version comparison."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from basis.shared.identifiers import AccountId

from .calendar import calendar_status, effective_sessions
from .locking import intent_executions
from .models import Cycle, PlannedSession, TrainingPlan
from .planning import scheduled_definition


@dataclass
class CycleNode:
    cycle: Cycle
    children: list["CycleNode"] = field(default_factory=list)
    sessions: list[PlannedSession] = field(default_factory=list)


@dataclass(frozen=True)
class CalendarDay:
    date: date
    sessions: tuple[tuple[PlannedSession, str], ...]


@dataclass(frozen=True)
class Difference:
    label: str
    before: str
    after: str


def plan_rows(
    plan: TrainingPlan, local_date: Callable[[AccountId, datetime], date]
) -> tuple[PlannedSession, ...]:
    if TrainingPlan.objects.filter(previous=plan).exists():
        return tuple(plan.sessions.select_related("cycle").order_by("date", "pk"))
    return tuple(
        s
        for s in effective_sessions(AccountId(plan.owner_id), local_date)
        if s.plan.lineage == plan.lineage
    )


def week_days(
    rows: tuple[PlannedSession, ...], start: date, today: date
) -> tuple[CalendarDay, ...]:
    return tuple(
        CalendarDay(day, tuple((s, calendar_status(s, today)) for s in rows if s.date == day))
        for day in (start + timedelta(days=i) for i in range(7))
    )


def cycle_tree(plan: TrainingPlan, rows: tuple[PlannedSession, ...]) -> list[CycleNode]:
    nodes = {c.pk: CycleNode(c) for c in plan.cycles.order_by("start_date", "pk")}
    roots = []
    for node in nodes.values():
        if node.cycle.parent_id in nodes:
            nodes[node.cycle.parent_id].children.append(node)
        else:
            roots.append(node)
    for session in rows:
        if session.cycle_id in nodes:
            nodes[session.cycle_id].sessions.append(session)
    return roots


def impact(plan: TrainingPlan, today: date) -> tuple[int, int, int]:
    rows = list(plan.sessions.all())
    executed = sum(intent_executions(s).exists() for s in rows)
    copied = sum(s.date >= today and not intent_executions(s).exists() for s in rows)
    return copied, executed, len(rows) - copied - executed


def differences(before: TrainingPlan, after: TrainingPlan) -> list[Difference]:
    result = []

    def add(label: str, old: object, new: object) -> None:
        if old != new:
            result.append(
                Difference(
                    label,
                    str(old) if old != "" else "Sin notas",
                    str(new) if new != "" else "Sin notas",
                )
            )

    for key, label in (
        ("title", "Plan"),
        ("start_date", "Inicio"),
        ("end_date", "Final"),
        ("notes", "Notas del plan"),
    ):
        add(label, getattr(before, key), getattr(after, key))
    # Cycle PKs change across versions; hierarchy order provides presentation only.
    old_cycles = list(before.cycles.order_by("kind", "start_date", "pk"))
    new_cycles = list(after.cycles.order_by("kind", "start_date", "pk"))
    for index in range(max(len(old_cycles), len(new_cycles))):
        old = old_cycles[index] if index < len(old_cycles) else None
        new = new_cycles[index] if index < len(new_cycles) else None

        def describe(cycle: Cycle | None) -> str:
            return (
                f"{cycle.get_kind_display()}: {cycle.title} · {cycle.start_date} → {cycle.end_date} · {cycle.focus}"
                if cycle
                else "Ausente"
            )

        add("Ciclo", describe(old), describe(new))
    left = {s.origin_id or s.pk: s for s in before.sessions.all()}
    right = {s.origin_id or s.pk: s for s in after.sessions.all()}
    for root in sorted(left.keys() | right.keys()):
        a, b = left.get(root), right.get(root)
        if a is None or b is None:
            row = a or b
            assert row is not None
            add(
                row.title,
                f"{a.date} · {a.get_status_display()}" if a else "Ausente",
                f"{b.date} · {b.get_status_display()}"
                if b
                else "Conservada solo en su versión histórica",
            )
            continue
        for key, label in (
            ("title", "Nombre"),
            ("date", "Fecha"),
            ("status", "Estado"),
            ("notes", "Notas"),
        ):
            old_value = a.get_status_display() if key == "status" else getattr(a, key)
            new_value = b.get_status_display() if key == "status" else getattr(b, key)
            add(f"{a.title} · {label}", old_value, new_value)
        if scheduled_definition(a).blocks != scheduled_definition(b).blocks:
            # IDs differ after copying; use prescribed values without persistent IDs.
            from dataclasses import replace

            def prescription(row: PlannedSession) -> object:
                return tuple(
                    replace(
                        block,
                        id=None,
                        sets=tuple(replace(s, id=None) for s in block.sets),
                        intervals=tuple(replace(i, id=None) for i in block.intervals),
                    )
                    for block in scheduled_definition(row).blocks
                )

            if prescription(a) != prescription(b):
                result.append(
                    Difference(
                        f"{a.title} · Prescripción",
                        "Consultar bloques en versión anterior",
                        "Prescripción modificada; consultar sesión de esta versión",
                    )
                )
    return result
