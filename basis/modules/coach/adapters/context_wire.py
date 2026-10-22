"""Explicit JSON boundary for frozen contexts; no free JSON crosses the core."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import cast

from basis.modules.athletes.public import (
    AthleteCoachContext,
    PreferencesData,
    SportData,
    WellnessData,
)
from basis.modules.catalog.public import CoachExercise
from basis.modules.training.public import (
    SPORT_LABELS,
    CoachBasePlan,
    CoachGoal,
    CoachRecentSession,
    CoachVariables,
    DurationProtocol,
    ProgressReport,
    ProtocolLoad,
    SportProgress,
    TrainingCoachContext,
)
from basis.shared.identifiers import ExerciseId, GoalId, PlanId

from ..domain.context import CoachContext


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError("Expected object")
    return cast(dict[str, object], value)


def rows(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected list")
    return list(value)


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected text")
    return value


def integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("Expected integer")
    return value


def optional_int(value: object) -> int | None:
    return integer(value) if value is not None else None


def decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def day(value: object) -> date:
    return date.fromisoformat(text(value))


def optional_day(value: object) -> date | None:
    return day(value) if value is not None else None


def encode_context(context: CoachContext) -> dict[str, object]:
    a, t = context.athlete, context.training
    p, w, r = a.preferences, a.wellness, t.progress
    data: dict[str, object] = {
        "snapshot_at": context.snapshot_at.isoformat(),
        "age": a.age,
        "objectives": a.objectives,
        "preferences": {
            "availability": list(p.availability),
            "minutes_per_session": p.minutes_per_session,
            "equipment": p.equipment[:500],
            "limitations": p.limitations[:500],
        }
        if p
        else None,
        "sport_profiles": [
            {
                "sport": s.sport,
                "experience": s.experience,
                "threshold": s.threshold,
                "threshold_unit": s.threshold_unit,
                "measured_on": s.measured_on,
                "method": s.method,
                "threshold_kind": s.threshold_kind,
                "threshold_source": s.threshold_source,
            }
            for s in a.sports
        ],
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "sport": g.sport,
                "target_date": g.target_date,
                "target_value": g.target_value,
                "target_unit": g.target_unit,
                "baseline_value": g.baseline_value,
                "baseline_date": g.baseline_date,
                "priority": g.priority,
            }
            for g in t.goals
        ],
        "wellness_latest": {
            "date": w.date,
            "sleep_hours": w.sleep_hours,
            "fatigue": w.fatigue,
            "stress": w.stress,
            "soreness": w.soreness,
            "pain_regions": w.pain_regions,
            "pain_score": w.pain_score,
            "readiness": w.readiness,
        }
        if w
        else None,
        "progress": {
            "sports": [
                {
                    "sport": s.sport,
                    "label": SPORT_LABELS[s.sport],
                    "sessions": s.sessions,
                    "distance_m": s.distance_m,
                    "ascent_m": s.ascent_m,
                    "external_volume_kg": s.external_volume_kg,
                }
                for s in r.sports
            ],
            "loads": [
                {
                    "protocol": load.protocol.value,
                    "label": "Tiempo total" if load.protocol == "elapsed" else "Tiempo activo",
                    "value": load.value,
                    "known": load.known,
                    "missing": load.missing,
                }
                for load in r.loads
            ],
            "sessions": r.sessions,
            "scheduled_past": r.scheduled_past,
            "completed_scheduled": r.completed_scheduled,
            "adherence_percent": r.adherence_percent,
            "method": "session-rpe-v1; total de bloque; sin suma entre deportes",
        },
        "recent_sessions": [
            {
                "id": s.id,
                "status": s.status,
                "planned": s.planned,
                "date": s.date.isoformat(),
                "duration_seconds": s.duration_seconds,
                "duration_protocol": s.duration_protocol,
                "rpe": s.rpe,
                "sports": list(s.sports),
            }
            for s in t.recent
        ],
    }
    if context.exercises is not None:
        data["exercises"] = [{"id": e.id, "nombre": e.name} for e in context.exercises]
    if context.variables is not None:
        data["variables"] = {s.sport: dict(s.variables) for s in context.variables}
    data["missing_data_policy"] = (
        "null significa desconocido, nunca cero; completed significa registro cerrado, no cumplimiento completo de objetivos; no hay datos de sensores ni GPS"
    )
    if context.base_plan:
        b = context.base_plan
        data["base_plan"] = {
            "id": b.id,
            "title": b.title,
            "version": b.version,
            "goal_id": b.goal_id,
            "start_date": b.start_date.isoformat(),
            "end_date": b.end_date.isoformat(),
        }
    return mapping(json.loads(json.dumps(data, default=str)))


def decode_context(value: object) -> CoachContext:
    d = mapping(value)
    raw_p, raw_w = d.get("preferences"), d.get("wellness_latest")
    p, w = (
        mapping(raw_p) if raw_p is not None else None,
        mapping(raw_w) if raw_w is not None else None,
    )
    preferences = (
        PreferencesData(
            tuple(integer(n) for n in rows(p["availability"])),
            integer(p["minutes_per_session"]),
            text(p["equipment"]),
            text(p["limitations"]),
            "",
        )
        if p
        else None
    )
    wellness = (
        WellnessData(
            day(w["date"]),
            decimal(w["sleep_hours"]),
            None,
            optional_int(w["fatigue"]),
            optional_int(w["stress"]),
            optional_int(w["soreness"]),
            optional_int(w["readiness"]),
            text(w["pain_regions"]),
            optional_int(w["pain_score"]),
            None,
            None,
            "",
            "",
        )
        if w
        else None
    )
    sports = tuple(
        SportData(
            text(s["sport"]),
            text(s["experience"]),
            decimal(s["threshold"]),
            text(s["threshold_unit"]),
            optional_day(s["measured_on"]),
            text(s["method"]),
            text(s.get("threshold_kind", "")),
            text(s.get("threshold_source", "")),
        )
        for s in (mapping(raw) for raw in rows(d["sport_profiles"]))
    )
    goals = tuple(
        CoachGoal(
            GoalId(integer(g["id"])),
            text(g["title"]),
            text(g["sport"]),
            optional_day(g["target_date"]),
            decimal(g["target_value"]),
            text(g["target_unit"]),
            decimal(g["baseline_value"]),
            optional_day(g["baseline_date"]),
            text(g["priority"]),
        )
        for g in (mapping(raw) for raw in rows(d["goals"]))
    )
    recent = tuple(
        CoachRecentSession(
            day(s["date"]),
            optional_int(s["duration_seconds"]),
            text(s["duration_protocol"]),
            decimal(s["rpe"]),
            tuple(text(x) for x in rows(s["sports"])),
            text(s["id"]) if s.get("id") is not None else None,
            text(s["status"]) if s.get("status") is not None else None,
            optional_int(s.get("planned")),
        )
        for s in (mapping(raw) for raw in rows(d["recent_sessions"]))
    )
    r = mapping(d["progress"])
    adherence = r["adherence_percent"]
    if adherence is not None and not isinstance(adherence, (int, float)):
        raise ValueError("Invalid adherence")
    progress = ProgressReport(
        tuple(
            SportProgress(
                text(s["sport"]),
                integer(s["sessions"]),
                decimal(s["distance_m"]),
                decimal(s["ascent_m"]),
                decimal(s["external_volume_kg"]),
            )
            for s in (mapping(raw) for raw in rows(r["sports"]))
        ),
        tuple(
            ProtocolLoad(
                DurationProtocol(text(load["protocol"])),
                Decimal(str(load["value"])),
                integer(load["known"]),
                integer(load["missing"]),
            )
            for load in (mapping(raw) for raw in rows(r["loads"]))
        ),
        integer(r["sessions"]),
        integer(r["scheduled_past"]),
        integer(r["completed_scheduled"]),
        float(adherence) if adherence is not None else None,
    )
    exercises = (
        tuple(
            CoachExercise(ExerciseId(integer(e["id"])), text(e["nombre"]))
            for e in (mapping(raw) for raw in rows(d["exercises"]))
        )
        if "exercises" in d
        else None
    )
    variables = (
        tuple(
            CoachVariables(sport, tuple((key, text(unit)) for key, unit in mapping(spec).items()))
            for sport, spec in mapping(d["variables"]).items()
        )
        if "variables" in d
        else None
    )
    b = mapping(d["base_plan"]) if "base_plan" in d else None
    base = (
        CoachBasePlan(
            PlanId(integer(b["id"])),
            text(b["title"]),
            integer(b["version"]),
            GoalId(integer(b["goal_id"])),
            day(b["start_date"]),
            day(b["end_date"]),
        )
        if b
        else None
    )
    return CoachContext(
        datetime.fromisoformat(text(d["snapshot_at"])),
        AthleteCoachContext(
            optional_int(d["age"]), text(d["objectives"]), preferences, sports, wellness
        ),
        TrainingCoachContext(goals, recent, progress),
        exercises,
        variables,
        base,
    )
