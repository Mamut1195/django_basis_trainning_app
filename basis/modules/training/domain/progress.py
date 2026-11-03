"""Measured progress and historical adherence; unknown is distinct from zero."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal

from basis.shared.identifiers import SessionId, TrekStageId, TrekTripId

from .execution import DurationProtocol, Metric, MetricName
from .sports import VARIABLES, internal_load


@dataclass(frozen=True)
class ProgressBlock:
    sport: str
    actual: tuple[Metric, ...] = ()
    set_volumes: tuple[Decimal | None, ...] = ()
    set_applicable: tuple[bool, ...] = ()


@dataclass(frozen=True)
class StageRecovery:
    trip: TrekTripId
    stage: TrekStageId
    order: int
    overnight_altitude_m: Decimal | None
    recovery_notes: str


@dataclass(frozen=True)
class ProgressSession:
    id: SessionId
    completed: bool
    protocol: DurationProtocol
    duration_seconds: int | None = None
    reported_rpe: Decimal | None = None
    blocks: tuple[ProgressBlock, ...] = ()
    date: Date | None = None
    stage_recovery: StageRecovery | None = None


@dataclass(frozen=True)
class SessionContext:
    session: ProgressSession
    previous_date: Date | None
    days_since_previous: int | None
    consecutive_days: int | None
    sessions_on_date: int | None


@dataclass(frozen=True)
class ScheduledProgress:
    date: Date
    completed: bool
    replaced_on: Date | None


@dataclass(frozen=True)
class Coverage:
    known: int = 0
    missing: int = 0
    not_applicable: int = 0
    unknown_applicability: int = 0


@dataclass(frozen=True)
class SportProgress:
    sport: str
    sessions: int
    distance_m: Decimal | None
    ascent_m: Decimal | None
    external_volume_kg: Decimal | None
    distance_coverage: Coverage = Coverage()
    ascent_coverage: Coverage = Coverage()
    volume_coverage: Coverage = Coverage()
    rpe_min: Decimal | None = None
    rpe_max: Decimal | None = None
    rpe_known: int = 0
    rpe_missing: int = 0


@dataclass(frozen=True)
class ProtocolLoad:
    protocol: DurationProtocol
    value: Decimal
    known: int
    missing: int


@dataclass(frozen=True)
class ProgressReport:
    sports: tuple[SportProgress, ...]
    loads: tuple[ProtocolLoad, ...]
    sessions: int
    scheduled_past: int
    completed_scheduled: int
    adherence_percent: float | None
    context: tuple[SessionContext, ...] = ()


@dataclass(frozen=True)
class MetricTotal:
    name: MetricName
    value: Decimal | None


@dataclass(frozen=True)
class TrekSummary:
    stages: int
    completed: int
    totals: tuple[MetricTotal, ...]


def metric_value(block: ProgressBlock, name: MetricName) -> Decimal | None:
    for metric in block.actual:
        if metric.name == name:
            return Decimal(metric.value)
    return None


def measured_sum(values: tuple[Decimal | None, ...]) -> Decimal | None:
    known = tuple(v for v in values if v is not None)
    return sum(known, Decimal(0)) if known else None


def metric_coverage(blocks: list[ProgressBlock], name: MetricName) -> Coverage:
    known = missing = not_applicable = 0
    for block in blocks:
        if name.value not in VARIABLES[block.sport]:
            not_applicable += 1
        elif metric_value(block, name) is None:
            missing += 1
        else:
            known += 1
    return Coverage(known, missing, not_applicable)


def volume_coverage(blocks: list[ProgressBlock]) -> Coverage:
    known = missing = not_applicable = unknown = 0
    for block in blocks:
        if block.sport != "strength":
            continue
        if block.set_applicable and len(block.set_applicable) != len(block.set_volumes):
            raise ValueError("Set volume applicability length mismatch")
        for index, value in enumerate(block.set_volumes):
            if not block.set_applicable:
                if value is None:
                    unknown += 1
                else:
                    known += 1
                continue
            applicable = block.set_applicable[index]
            if not applicable:
                not_applicable += 1
            elif value is None:
                missing += 1
            else:
                known += 1
    return Coverage(known, missing, not_applicable, unknown)


def intensity_summary(
    values: tuple[Decimal | None, ...],
) -> tuple[Decimal | None, Decimal | None, int, int]:
    known = tuple(value for value in values if value is not None)
    return (
        min(known) if known else None,
        max(known) if known else None,
        len(known),
        len(values) - len(known),
    )


def session_context(sessions: tuple[ProgressSession, ...]) -> tuple[SessionContext, ...]:
    """Observed dates in this selection; gaps do not establish rest or recovery.

    Same-day sessions share a day count: dates alone cannot order them or
    establish hours between sessions. Missing dates never imply a streak.
    """
    counts: dict[Date, int] = {}
    for session in sessions:
        if session.date is not None:
            counts[session.date] = counts.get(session.date, 0) + 1
    days: dict[Date, tuple[Date | None, int | None, int]] = {}
    previous: Date | None = None
    streak = 0
    for day in sorted(counts):
        gap = (day - previous).days if previous is not None else None
        streak = streak + 1 if gap == 1 else 1
        days[day] = (previous, gap, streak)
        previous = day
    return tuple(
        SessionContext(
            session,
            *days[session.date],
            counts[session.date],
        )
        if session.date is not None
        else SessionContext(session, None, None, None, None)
        for session in sessions
    )


def report(
    sessions: tuple[ProgressSession, ...],
    scheduled: tuple[ScheduledProgress, ...],
    today: Date,
) -> ProgressReport:
    completed = tuple(s for s in sessions if s.completed)
    # Dict insertion order retains the order of first observation in the source.
    sport_sessions: dict[str, set[SessionId]] = {}
    sport_blocks: dict[str, list[ProgressBlock]] = {}
    protocol_sessions: dict[DurationProtocol, list[ProgressSession]] = {}
    sport_efforts: dict[str, dict[SessionId, Decimal | None]] = {}
    for session in completed:
        protocol_sessions.setdefault(session.protocol, []).append(session)
        for block in session.blocks:
            sport_sessions.setdefault(block.sport, set()).add(session.id)
            sport_efforts.setdefault(block.sport, {}).setdefault(session.id, session.reported_rpe)
            sport_blocks.setdefault(block.sport, []).append(block)
    sports = tuple(
        SportProgress(
            sport,
            len(sport_sessions[sport]),
            measured_sum(tuple(metric_value(b, MetricName.DISTANCE_M) for b in blocks)),
            measured_sum(tuple(metric_value(b, MetricName.ASCENT_M) for b in blocks)),
            measured_sum(tuple(v for b in blocks for v in b.set_volumes)),
            metric_coverage(blocks, MetricName.DISTANCE_M),
            metric_coverage(blocks, MetricName.ASCENT_M),
            volume_coverage(blocks),
            *intensity_summary(tuple(sport_efforts[sport].values())),
        )
        for sport, blocks in sport_blocks.items()
    )
    loads: list[ProtocolLoad] = []
    for protocol, rows in protocol_sessions.items():
        values = tuple(internal_load(s.duration_seconds, s.reported_rpe) for s in rows)
        known = tuple(v for v in values if v is not None)
        loads.append(
            ProtocolLoad(protocol, sum(known, Decimal(0)), len(known), len(rows) - len(known))
        )
    eligible = tuple(
        s
        for s in scheduled
        if s.date <= today and (s.completed or s.replaced_on is None or s.date < s.replaced_on)
    )
    expected = len(eligible)
    done = sum(s.completed for s in eligible)
    return ProgressReport(
        sports,
        tuple(loads),
        len(completed),
        expected,
        done,
        round(done / expected * 100, 1) if expected else None,
        session_context(completed),
    )


def summarize_trip(stages: tuple[ProgressSession, ...]) -> TrekSummary:
    names = (
        MetricName.DISTANCE_M,
        MetricName.ASCENT_M,
        MetricName.DESCENT_M,
        MetricName.DURATION_SECONDS,
        MetricName.MOVING_SECONDS,
    )
    blocks = tuple(b for s in stages if s.completed for b in s.blocks if b.sport == "hiking")
    return TrekSummary(
        len(stages),
        sum(s.completed for s in stages),
        tuple(
            MetricTotal(n, measured_sum(tuple(metric_value(b, n) for b in blocks))) for n in names
        ),
    )
