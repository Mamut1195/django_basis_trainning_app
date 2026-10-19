"""AI proposal JSON validation and conversion into source-independent plan definitions."""

from datetime import date

from django.core.exceptions import ValidationError

from basis.shared.identifiers import GoalId

from ..domain.planning import CycleDefinition, CycleKind, PlanDefinition, ScheduledDefinition
from .wire import blocks, integer, object_map, sequence, text

INVALID = "Propuesta incompleta, objetivo ajeno o estructura inv\u00e1lida."


def proposal_definition(value: object) -> PlanDefinition:
    if not isinstance(value, dict) or set(value) - {
        "title",
        "goal_id",
        "start_date",
        "end_date",
        "notes",
        "cycles",
        "sessions",
    }:
        raise ValidationError("Formato de propuesta inv\u00e1lido.")
    try:
        data = object_map(value)
        start, end = (
            date.fromisoformat(text(data["start_date"])),
            date.fromisoformat(text(data["end_date"])),
        )
        raw_cycles, raw_sessions = sequence(data["cycles"]), sequence(data["sessions"])
        if (
            end < start
            or (end - start).days > 366
            or not 3 <= len(raw_cycles) <= 100
            or not 1 <= len(raw_sessions) <= 14
        ):
            raise ValueError
        cycles: list[CycleDefinition] = []
        for raw in raw_cycles:
            cycle = object_map(raw)
            if set(cycle) - {"key", "parent", "kind", "title", "start_date", "end_date", "focus"}:
                raise ValueError
            cycles.append(
                CycleDefinition(
                    text(cycle["key"]),
                    text(cycle["parent"]) if cycle.get("parent") is not None else None,
                    CycleKind(text(cycle["kind"])),
                    text(cycle["title"]),
                    date.fromisoformat(text(cycle["start_date"])),
                    date.fromisoformat(text(cycle["end_date"])),
                    text(cycle.get("focus", "")),
                )
            )
        sessions: list[ScheduledDefinition] = []
        for raw in raw_sessions:
            session = object_map(raw)
            if set(session) - {"title", "date", "cycle_key", "blocks"}:
                raise ValueError
            sessions.append(
                ScheduledDefinition(
                    text(session["cycle_key"]),
                    text(session["title"]),
                    date.fromisoformat(text(session["date"])),
                    blocks(session["blocks"]),
                )
            )
        return PlanDefinition(
            GoalId(integer(data["goal_id"])),
            text(data["title"]),
            start,
            end,
            text(data.get("notes", "")),
            tuple(cycles),
            tuple(sessions),
        )
    except (KeyError, TypeError, ValueError):
        raise ValidationError(INVALID) from None
