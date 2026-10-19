"""Private planning definitions, independent of source, persistence and actual execution."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum

from basis.shared.identifiers import (
    AccountId,
    GoalId,
    LineageId,
    PlanId,
    PlannedSessionId,
    Revision,
)

from .execution import BlockData


class InvalidPlanning(Exception):
    pass


class PlanningUnavailable(Exception):
    pass


class CycleKind(StrEnum):
    MACRO = "macro"
    MESO = "meso"
    MICRO = "micro"


@dataclass(frozen=True)
class GoalData:
    title: str
    sport: str
    priority: str
    baseline_value: Decimal | None
    baseline_date: date | None
    target_date: date | None
    description: str
    target_value: Decimal | None
    target_unit: str


@dataclass(frozen=True)
class CycleDefinition:
    key: str
    parent: str | None
    kind: CycleKind
    title: str
    start_date: date
    end_date: date
    focus: str = ""


@dataclass(frozen=True)
class ScheduledDefinition:
    cycle_key: str
    title: str
    date: date
    blocks: tuple[BlockData, ...] = ()
    notes: str = ""
    source_id: PlannedSessionId | None = None


@dataclass(frozen=True)
class PlanDefinition:
    goal: GoalId
    title: str
    start_date: date
    end_date: date
    notes: str = ""
    cycles: tuple[CycleDefinition, ...] = ()
    sessions: tuple[ScheduledDefinition, ...] = ()


@dataclass(frozen=True)
class PlanHeader:
    id: PlanId
    owner: AccountId
    lineage: LineageId
    version: int
    previous: PlanId | None


@dataclass(frozen=True)
class PlanSnapshot:
    header: PlanHeader
    definition: PlanDefinition
    executed: frozenset[PlannedSessionId]
    has_successor: bool


@dataclass(frozen=True)
class ScheduledState:
    id: PlannedSessionId
    owner: AccountId
    plan: PlanId
    revision: Revision
    definition: ScheduledDefinition
    cycle: CycleDefinition
    has_executions: bool


def validate_goal(data: GoalData) -> None:
    if data.target_value is not None and not data.target_unit:
        raise InvalidPlanning("Indica la unidad del objetivo.")
    if data.baseline_value is not None and (not data.baseline_date or not data.target_unit):
        raise InvalidPlanning("La l\u00ednea base necesita fecha y unidad.")


def validate_dates(start: date, end: date) -> None:
    if end < start:
        raise InvalidPlanning("El final debe ser posterior al inicio.")


def validate_cycle(
    data: CycleDefinition,
    plan_start: date,
    plan_end: date,
    parent: CycleDefinition | None,
    *,
    same_plan: bool = True,
) -> None:
    if data.end_date < data.start_date or data.start_date < plan_start or data.end_date > plan_end:
        raise InvalidPlanning("El ciclo debe estar dentro de las fechas del plan.")
    if data.kind == CycleKind.MACRO and data.parent is not None:
        raise InvalidPlanning("Un macrociclo no tiene padre.")
    expected = {CycleKind.MESO: CycleKind.MACRO, CycleKind.MICRO: CycleKind.MESO}
    if data.kind != CycleKind.MACRO and (parent is None or parent.kind != expected[data.kind]):
        raise InvalidPlanning("Jerarqu\u00eda requerida: macro \u2192 meso \u2192 micro.")
    if parent is not None and (
        not same_plan or data.start_date < parent.start_date or data.end_date > parent.end_date
    ):
        raise InvalidPlanning("El ciclo debe estar dentro de su padre y plan.")


def validate_schedule(
    data: ScheduledDefinition, cycle: CycleDefinition, *, same_plan: bool = True
) -> None:
    if (
        not same_plan
        or cycle.kind != CycleKind.MICRO
        or not cycle.start_date <= data.date <= cycle.end_date
    ):
        raise InvalidPlanning("La sesi\u00f3n debe pertenecer a un microciclo y sus fechas.")


def validate_prescription(blocks: tuple[BlockData, ...]) -> None:
    if not 1 <= len(blocks) <= 30:
        raise InvalidPlanning("Una sesi\u00f3n necesita entre 1 y 30 bloques.")
    for block in blocks:
        if block.actual:
            raise InvalidPlanning("Una prescripci\u00f3n no contiene resultados reales.")
        for row in block.sets:
            if any(
                value is not None
                for value in (
                    row.actual_kg,
                    row.actual_reps,
                    row.actual_rpe,
                    row.actual_rir,
                    row.actual_rest_seconds,
                    row.isometric_seconds,
                )
            ):
                raise InvalidPlanning("La prescripci\u00f3n no contiene resultados reales.")
        for interval in block.intervals:
            if (
                interval.actual
                or interval.actual_rpe is not None
                or interval.actual_rest_seconds is not None
            ):
                raise InvalidPlanning("La prescripci\u00f3n no contiene resultados reales.")


def validate_definition(data: PlanDefinition) -> None:
    validate_dates(data.start_date, data.end_date)
    cycles: dict[str, CycleDefinition] = {}
    for kind in CycleKind:
        for cycle in data.cycles:
            if cycle.kind != kind:
                continue
            if cycle.key in cycles or (cycle.parent and cycle.parent not in cycles):
                raise InvalidPlanning(
                    "Propuesta incompleta, objetivo ajeno o estructura inv\u00e1lida."
                )
            validate_cycle(
                cycle,
                data.start_date,
                data.end_date,
                cycles.get(cycle.parent) if cycle.parent is not None else None,
            )
            cycles[cycle.key] = cycle
    for session in data.sessions:
        if session.cycle_key not in cycles:
            raise InvalidPlanning(
                "Propuesta incompleta, objetivo ajeno o estructura inv\u00e1lida."
            )
        validate_schedule(session, cycles[session.cycle_key])
        validate_prescription(session.blocks)


def revision_definition(current: PlanSnapshot, today: date) -> PlanDefinition:
    if current.has_successor:
        raise InvalidPlanning("Ya existe una versi\u00f3n posterior.")
    return replace(
        current.definition,
        sessions=tuple(
            replace(session, source_id=None)
            for session in current.definition.sessions
            if session.date >= today and session.source_id not in current.executed
        ),
    )


def require_reschedulable(current: ScheduledState, expected: Revision) -> None:
    if current.has_executions or current.revision != expected:
        raise InvalidPlanning(
            "La sesi\u00f3n cambi\u00f3 o ya tiene ejecuciones. Crea otra versi\u00f3n del plan."
        )
