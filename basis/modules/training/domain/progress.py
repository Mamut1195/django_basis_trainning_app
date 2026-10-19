"""Measured progress and historical adherence; unknown is distinct from zero."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal

from basis.shared.identifiers import SessionId

from .execution import DurationProtocol, Metric, MetricName
from .sports import internal_load


@dataclass(frozen=True)
class ProgressBlock:
    sport: str
    actual: tuple[Metric, ...] = ()
    set_volumes: tuple[Decimal | None, ...] = ()


@dataclass(frozen=True)
class ProgressSession:
    id: SessionId
    completed: bool
    protocol: DurationProtocol
    duration_seconds: int | None = None
    reported_rpe: Decimal | None = None
    blocks: tuple[ProgressBlock, ...] = ()


@dataclass(frozen=True)
class ScheduledProgress:
    date: Date
    completed: bool
    replaced_on: Date | None


@dataclass(frozen=True)
class SportProgress:
    sport: str
    sessions: int
    distance_m: Decimal | None
    ascent_m: Decimal | None
    external_volume_kg: Decimal | None


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
    for session in completed:
        protocol_sessions.setdefault(session.protocol, []).append(session)
        for block in session.blocks:
            sport_sessions.setdefault(block.sport, set()).add(session.id)
            sport_blocks.setdefault(block.sport, []).append(block)
    sports = tuple(
        SportProgress(
            sport,
            len(sport_sessions[sport]),
            measured_sum(tuple(metric_value(b, MetricName.DISTANCE_M) for b in blocks)),
            measured_sum(tuple(metric_value(b, MetricName.ASCENT_M) for b in blocks)),
            measured_sum(tuple(v for b in blocks for v in b.set_volumes)),
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
