"""Explicit JSON boundary for frozen contexts; no free JSON crosses the core."""

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
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
    CoachScope,
    CoachSessionEvidence,
    CoachVariables,
    Coverage,
    DurationProtocol,
    ProgressReport,
    ProtocolLoad,
    SportProgress,
    StageRecovery,
    TrainingCoachContext,
)
from basis.shared.identifiers import ExerciseId, GoalId, PlanId, TrekStageId, TrekTripId

from ..domain.context import CoachContext
from ..domain.decisions import Finding

CONTEXT_UNITS = {
    "duration_seconds": "s",
    "distance_m": "m",
    "ascent_m": "m",
    "external_volume_kg": "kg·rep",
    "internal_load": "UA",
    "reported_rpe": "0–10",
    "sleep_hours": "h",
    "overnight_altitude_m": "m",
}
CONTEXT_METHODS = {
    "progress": "training.domain.progress.report",
    "load": "training.domain.sports.internal_load",
    "context": "training.domain.progress.session_context",
    "recovery": "declarada; fechas observadas no acreditan descanso ni recuperación efectiva",
}
COVERAGE_ORDER = ("known", "missing", "not_applicable", "unknown_applicability")


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
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Expected decimal")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Expected decimal") from error
    if not result.is_finite():
        raise ValueError("Expected finite decimal")
    return result


def boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("Expected boolean")
    return value


def required_decimal(value: object) -> Decimal:
    result = decimal(value)
    if result is None:
        raise ValueError("Expected non-null decimal")
    return result


def coverage(value: object) -> Coverage:
    values = rows(value)
    if len(values) != 4:
        raise ValueError("Expected four coverage counts")
    return Coverage(integer(values[0]), integer(values[1]), integer(values[2]), integer(values[3]))


def decode_findings(value: object) -> tuple[Finding, ...]:
    if value is None:
        return ()
    result: list[Finding] = []
    for item in rows(value):
        d = mapping(item)
        proposal = d.get("proposal")
        result.append(
            Finding(
                rule=text(d["rule"]),
                severity=text(d["severity"]),
                title=text(d["title"]),
                reason=text(d["reason"]),
                evidence=tuple(text(s) for s in rows(d["evidence"])),
                proposal=text(proposal) if proposal is not None else None,
            )
        )
    return tuple(result)


def decode_evidence(value: object, recent: tuple[CoachRecentSession, ...]) -> CoachSessionEvidence:
    d = mapping(value)
    source = next((s for s in recent if s.id == text(d["id"])), None)
    if source is None or source.status != "completed":
        raise ValueError("Evidence must reference a captured completed session")
    stage = mapping(d["stage_recovery"]) if d["stage_recovery"] is not None else None
    return CoachSessionEvidence(
        text(d["id"]),
        source.date,
        source.sports,
        source.duration_protocol,
        source.duration_seconds,
        source.rpe,
        decimal(d["internal_load"]),
        optional_day(d["previous_date"]),
        optional_int(d["days_since_previous"]),
        optional_int(d["consecutive_days"]),
        optional_int(d["sessions_on_date"]),
        StageRecovery(
            TrekTripId(integer(stage["trip"])),
            TrekStageId(integer(stage["stage"])),
            integer(stage["order"]),
            decimal(stage["overnight_altitude_m"]),
            text(stage["recovery_notes"]),
        )
        if stage
        else None,
    )


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
            "moment": w.moment,
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
            "method": context.progress_method,
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
    if context.schema_version == 2:
        data["schema_version"] = 2
        data["missing"] = list(context.missing)
        data["provenance"] = {
            "instructions": context.instructions_version,
            "system_sha256": context.system_sha256,
            "plan_sha256": context.plan_sha256,
            "tools": list(context.tools),
        }
        data["diagnosis"] = [
            {
                "rule": finding.rule,
                "severity": finding.severity,
                "title": finding.title,
                "reason": finding.reason,
                "evidence": list(finding.evidence[:2]),
                "proposal": finding.proposal,
            }
            for finding in context.diagnosis[:4]
        ]
        data["scope"] = asdict(t.scope) if t.scope else None
        data["session_evidence"] = [
            {
                "id": e.id,
                "internal_load": e.internal_load,
                "previous_date": e.previous_date,
                "days_since_previous": e.days_since_previous,
                "consecutive_days": e.consecutive_days,
                "sessions_on_date": e.sessions_on_date,
                "stage_recovery": asdict(e.stage_recovery) if e.stage_recovery else None,
            }
            for e in t.evidence
        ]
        data["missing_data_policy"] = (
            "null=desconocido; completed=registro cerrado, no metas cumplidas; sin sensores/GPS"
        )
        data["units"] = dict(CONTEXT_UNITS)
        data["methods"] = dict(CONTEXT_METHODS)
        data["coverage_order"] = list(COVERAGE_ORDER)
        wire_progress = mapping(data["progress"])
        for item, source in zip(rows(wire_progress["sports"]), r.sports, strict=True):
            dest = mapping(item)
            for name, counts in (
                ("distance_coverage", source.distance_coverage),
                ("ascent_coverage", source.ascent_coverage),
                ("volume_coverage", source.volume_coverage),
            ):
                dest[name] = [
                    counts.known,
                    counts.missing,
                    counts.not_applicable,
                    counts.unknown_applicability,
                ]
            dest.update(
                rpe_min=source.rpe_min,
                rpe_max=source.rpe_max,
                rpe_known=source.rpe_known,
                rpe_missing=source.rpe_missing,
            )
        if t.scope is not None and not t.scope.adherence_included:
            for key in ("scheduled_past", "completed_scheduled", "adherence_percent"):
                wire_progress.pop(key)
    elif context.schema_version == 1:
        data["schema_version"] = 1
    else:
        raise ValueError("Unsupported context version")
    # An unversioned saved snapshot must not gain evidence it never captured.
    for path in context.legacy_omissions:
        parts = path.split("/")
        parent: object = data
        for part in parts[:-1]:
            parent = rows(parent)[int(part)] if isinstance(parent, list) else mapping(parent)[part]
        mapping(parent).pop(parts[-1], None)
    return mapping(json.loads(json.dumps(data, default=str)))


def decode_context(value: object) -> CoachContext:
    d = mapping(value)
    version = integer(d.get("schema_version", 1))
    if version not in (1, 2):
        raise ValueError("Unsupported context version")
    if version == 2 and (
        mapping(d["units"]) != CONTEXT_UNITS
        or mapping(d["methods"]) != CONTEXT_METHODS
        or tuple(rows(d["coverage_order"])) != COVERAGE_ORDER
    ):
        raise ValueError("Unsupported context units or methods")
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
            text(w.get("moment", "day")),
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
    raw_scope = d.get("scope") if version == 2 else None
    scope_data = mapping(raw_scope) if raw_scope is not None else None
    scope = (
        CoachScope(
            day(scope_data["start"]),
            day(scope_data["end"]),
            integer(scope_data["session_limit"]),
            integer(scope_data["goal_limit"]),
            boolean(scope_data["sessions_truncated"]),
            boolean(scope_data["goals_truncated"]),
            boolean(scope_data["adherence_included"]),
        )
        if scope_data is not None
        else None
    )
    adherence_included = scope is None or scope.adherence_included
    adherence = r["adherence_percent"] if adherence_included else None
    if adherence is not None and (
        isinstance(adherence, bool) or not isinstance(adherence, (int, float))
    ):
        raise ValueError("Invalid adherence")
    if adherence is not None:
        required_decimal(adherence)
    progress = ProgressReport(
        tuple(
            SportProgress(
                text(s["sport"]),
                integer(s["sessions"]),
                decimal(s["distance_m"]),
                decimal(s["ascent_m"]),
                decimal(s["external_volume_kg"]),
                coverage(s["distance_coverage"]) if version == 2 else Coverage(),
                coverage(s["ascent_coverage"]) if version == 2 else Coverage(),
                coverage(s["volume_coverage"]) if version == 2 else Coverage(),
                decimal(s["rpe_min"]) if version == 2 else None,
                decimal(s["rpe_max"]) if version == 2 else None,
                integer(s["rpe_known"]) if version == 2 else 0,
                integer(s["rpe_missing"]) if version == 2 else 0,
            )
            for s in (mapping(raw) for raw in rows(r["sports"]))
        ),
        tuple(
            ProtocolLoad(
                DurationProtocol(text(load["protocol"])),
                required_decimal(load["value"]),
                integer(load["known"]),
                integer(load["missing"]),
            )
            for load in (mapping(raw) for raw in rows(r["loads"]))
        ),
        integer(r["sessions"]),
        integer(r["scheduled_past"]) if adherence_included else 0,
        integer(r["completed_scheduled"]) if adherence_included else 0,
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
    omissions: list[str] = []
    if version == 1:
        omissions.extend(
            k for k in ("schema_version", "preferences", "wellness_latest") if k not in d
        )
        for collection, keys in (
            ("sport_profiles", ("threshold_kind", "threshold_source")),
            ("recent_sessions", ("id", "status", "planned")),
        ):
            for i, raw in enumerate(rows(d[collection])):
                omissions.extend(f"{collection}/{i}/{k}" for k in keys if k not in mapping(raw))
        if w is not None and "moment" not in w:
            omissions.append("wellness_latest/moment")
        if "method" not in r:
            omissions.append("progress/method")
    provenance = mapping(d["provenance"]) if version == 2 else {}
    return CoachContext(
        datetime.fromisoformat(text(d["snapshot_at"])),
        AthleteCoachContext(
            optional_int(d["age"]), text(d["objectives"]), preferences, sports, wellness
        ),
        TrainingCoachContext(
            goals,
            recent,
            progress,
            scope,
            tuple(decode_evidence(e, recent) for e in rows(d["session_evidence"]))
            if version == 2
            else (),
        ),
        exercises,
        variables,
        base,
        schema_version=version,
        missing=tuple(text(s) for s in rows(d["missing"])) if version == 2 else (),
        instructions_version=text(provenance["instructions"])
        if provenance.get("instructions") is not None
        else None,
        system_sha256=text(provenance["system_sha256"])
        if provenance.get("system_sha256") is not None
        else None,
        plan_sha256=text(provenance["plan_sha256"])
        if provenance.get("plan_sha256") is not None
        else None,
        tools=tuple(text(s) for s in rows(provenance["tools"])) if version == 2 else (),
        legacy_omissions=tuple(omissions),
        progress_method=text(r["method"]) if "method" in r else "",
        diagnosis=decode_findings(d.get("diagnosis")) if version == 2 else (),
    )
