"""Owner-facing diagnosis built from measured sessions.

The diagnosis is deterministic: it selects one sport and protocol (never mixing them),
computes the weekly load series, and runs the coach rules over the available coverage.
When there are not enough weeks, it says so instead of inventing a baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from basis.modules.training.public import (
    LoadSample,
    load_ratio,
    rolling_mean,
    weekly_loads,
)

from ..domain.decisions import Finding, Thresholds, evaluate

ZERO = Decimal(0)
MIN_BASELINE_WEEKS = 3
BASELINE_WINDOW = 4


@dataclass(frozen=True)
class Diagnosis:
    findings: tuple[Finding, ...]
    sport: str | None
    protocol: str | None
    weeks: int
    average_rpe: Decimal | None
    coverage: Mapping[str, int]
    notes: tuple[str, ...] = ()


def _average_rpe(values: Sequence[Decimal | None]) -> Decimal | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return (sum(known, ZERO) / len(known)).quantize(Decimal("0.01"))


def diagnose(
    samples: Sequence[LoadSample],
    *,
    adherence_percent: Decimal | None,
    recent_rpe: Sequence[Decimal | None],
    excluded_sessions: int = 0,
    thresholds: Thresholds = Thresholds(),
) -> Diagnosis:
    """Select the dominant sport/protocol and evaluate the rules on its weekly series."""
    if not samples:
        return Diagnosis(
            findings=(),
            sport=None,
            protocol=None,
            weeks=0,
            average_rpe=None,
            coverage={"weeks": 0, "known": 0, "missing": 0},
            notes=("Sin sesiones suficientes para diagnosticar.",),
        )
    groups: dict[tuple[str, str], list[LoadSample]] = {}
    for sample in samples:
        groups.setdefault((sample.sport, sample.protocol), []).append(sample)
    (sport, protocol), group = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))[0]
    rows = weekly_loads(tuple(group))
    ratios: list[Decimal | None] = []
    for index, row in enumerate(rows):
        previous = [item.load for item in rows[max(0, index - BASELINE_WINDOW) : index]]
        baseline = rolling_mean(previous, BASELINE_WINDOW, minimum=MIN_BASELINE_WEEKS)
        ratios.append(load_ratio(row.load, baseline))
    average = _average_rpe([sample.reported_rpe for sample in group])
    findings = evaluate(
        load_ratios=ratios,
        adherence_percent=adherence_percent,
        missing_sessions=sum(1 for value in recent_rpe if value is None),
        average_rpe=average,
        thresholds=thresholds,
    )
    notes: list[str] = []
    if len(rows) < BASELINE_WINDOW + 1:
        notes.append("Faltan semanas con dato para comparar contra una base de cuatro semanas.")
    if excluded_sessions:
        notes.append(
            f"{excluded_sessions} sesión(es) de varios deportes no se suman al diagnóstico."
        )
    return Diagnosis(
        findings=findings,
        sport=sport,
        protocol=protocol,
        weeks=len(rows),
        average_rpe=average,
        coverage={
            "weeks": len(rows),
            "known": sum(row.known for row in rows),
            "missing": sum(row.missing for row in rows),
        },
        notes=tuple(notes),
    )
