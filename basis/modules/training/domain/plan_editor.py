"""Pure transformations for private templates and versioned plan editing."""

from dataclasses import replace
from datetime import date

from basis.shared.identifiers import GoalId

from .planning import (
    CycleDefinition,
    InvalidPlanning,
    PlanDefinition,
    PlanSnapshot,
    revision_definition,
    validate_definition,
)


def edit_definition(
    snapshot: PlanSnapshot,
    today: date,
    title: str,
    start: date,
    end: date,
    notes: str,
    cycle: CycleDefinition | None = None,
) -> PlanDefinition:
    definition = revision_definition(snapshot, today)
    if cycle is not None and cycle.key not in {c.key for c in definition.cycles}:
        raise InvalidPlanning("El ciclo no pertenece a esta versión.")
    result = replace(
        definition,
        title=title.strip(),
        start_date=start,
        end_date=end,
        notes=notes,
        cycles=tuple(
            cycle if cycle is not None and c.key == cycle.key else c for c in definition.cycles
        ),
    )
    if not result.title or any(not c.title.strip() for c in result.cycles):
        raise InvalidPlanning("Indica el nombre del plan y de cada ciclo.")
    validate_definition(result, allow_drafts=True)
    return result


def template_definition(
    snapshot: PlanSnapshot, goal: GoalId, title: str, start: date
) -> PlanDefinition:
    """Copy intent only into a new lineage; no execution/origin identity is reused."""
    delta = start - snapshot.definition.start_date
    try:
        end = snapshot.definition.end_date + delta
    except OverflowError as error:
        raise InvalidPlanning("El calendario copiado supera las fechas admitidas.") from error
    result = replace(
        snapshot.definition,
        goal=goal,
        title=title.strip(),
        start_date=start,
        end_date=end,
        cycles=tuple(
            replace(c, start_date=c.start_date + delta, end_date=c.end_date + delta)
            for c in snapshot.definition.cycles
        ),
        sessions=tuple(
            replace(s, date=s.date + delta, source_id=None, origin_id=None)
            for s in snapshot.definition.sessions
            if s.status == "scheduled"
        ),
    )
    if not result.title:
        raise InvalidPlanning("Indica el nombre del plan.")
    validate_definition(result, allow_drafts=True)
    return result
