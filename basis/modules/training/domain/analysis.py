"""Deterministic training analysis for the coach engine.

Every value is computed from recorded data. Unknown stays ``None`` and is reported as
coverage; nothing is inferred, zero-filled or summed across sports or duration protocols.

References (formulas and limits are documented in ``docs/COACH_ENGINE.md``):

- Foster et al. 2001, session-RPE load: minutes x session RPE.
  https://pubmed.ncbi.nlm.nih.gov/11708692/
- Session-RPE review: validity and limits.
  https://pubmed.ncbi.nlm.nih.gov/29163016/
- Impellizzeri et al. 2020, conceptual pitfalls of load ratios (ACWR is descriptive,
  not a injury predictor). https://pubmed.ncbi.nlm.nih.gov/32991699/
- Zourdos et al. 2016, RIR-based RPE for resistance training.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4961270/
- Schoenfeld et al. 2017, dose-response of weekly sets per muscle.
  https://pubmed.ncbi.nlm.nih.gov/27433992/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from .sports import internal_load

ZERO = Decimal(0)
LOAD_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.001")


@dataclass(frozen=True)
class LoadSample:
    """One completed session, already scoped to a single sport and protocol."""

    day: date
    sport: str
    protocol: str
    duration_seconds: int | None
    reported_rpe: Decimal | None

    @property
    def load(self) -> Decimal | None:
        return internal_load(self.duration_seconds, self.reported_rpe)


@dataclass(frozen=True)
class WeeklyLoad:
    week_start: date
    sport: str
    protocol: str
    load: Decimal
    sessions: int
    known: int
    missing: int

    def __post_init__(self) -> None:
        if self.load < ZERO or self.sessions < 1 or self.known < 0 or self.missing < 0:
            raise ValueError("Carga semanal inconsistente.")
        if self.known + self.missing != self.sessions:
            raise ValueError("La cobertura semanal no coincide con las sesiones.")


def week_start(day: date) -> date:
    """ISO week start (Monday)."""
    return day - timedelta(days=day.weekday())


def weekly_loads(samples: Sequence[LoadSample]) -> tuple[WeeklyLoad, ...]:
    """Group by week, sport and protocol. Never merge different sports or protocols."""
    buckets: dict[tuple[date, str, str], list[LoadSample]] = {}
    for sample in samples:
        key = (week_start(sample.day), sample.sport, sample.protocol)
        buckets.setdefault(key, []).append(sample)
    rows: list[WeeklyLoad] = []
    for (start, sport, protocol), group in sorted(buckets.items()):
        loads = [value for value in (item.load for item in group) if value is not None]
        rows.append(
            WeeklyLoad(
                week_start=start,
                sport=sport,
                protocol=protocol,
                load=sum(loads, ZERO).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP),
                sessions=len(group),
                known=len(loads),
                missing=len(group) - len(loads),
            )
        )
    return tuple(rows)


def rolling_mean(
    values: Sequence[Decimal | None], window: int, *, minimum: int | None = None
) -> Decimal | None:
    """Mean of the last ``window`` known values; ``None`` until ``minimum`` exist."""
    if window < 1:
        raise ValueError("La ventana debe ser positiva.")
    known = [value for value in values[-window:] if value is not None]
    required = minimum if minimum is not None else window
    if len(known) < required:
        return None
    return (sum(known, ZERO) / len(known)).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)


def load_ratio(current: Decimal | None, baseline: Decimal | None) -> Decimal | None:
    """Current / baseline. Descriptive only: it does not predict injuries."""
    if current is None or baseline is None or baseline <= ZERO:
        return None
    return (current / baseline).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def consecutive_above(
    ratios: Sequence[Decimal | None], threshold: Decimal, *, weeks: int = 2
) -> int:
    """How many of the last consecutive weeks are above ``threshold``."""
    count = 0
    for ratio in reversed(ratios):
        if ratio is None or ratio <= threshold:
            break
        count += 1
    return count if count >= weeks else 0


def monotony(daily_loads: Sequence[Decimal | None]) -> Decimal | None:
    """Foster monotony: mean daily load / population SD over seven days.

    ``None`` means unknown data or zero dispersion; rest days are real zeros. Callers
    must pass exactly seven entries with ``None`` for a day whose session has no RPE.
    """
    if len(daily_loads) != 7 or any(value is None for value in daily_loads):
        return None
    values = [value for value in daily_loads if value is not None]
    mean = sum(values, ZERO) / len(values)
    variance = sum(((value - mean) ** 2 for value in values), ZERO) / len(values)
    if variance <= ZERO:
        return None
    return (mean / variance.sqrt()).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def strain(weekly_load: Decimal | None, weekly_monotony: Decimal | None) -> Decimal | None:
    """Foster strain: weekly load x monotony."""
    if weekly_load is None or weekly_monotony is None:
        return None
    return (weekly_load * weekly_monotony).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TrendPoint:
    day: date
    value: Decimal


def slope_per_week(points: Sequence[TrendPoint]) -> Decimal | None:
    """Least-squares slope per week; ``None`` with fewer than three points."""
    if len(points) < 3:
        return None
    origin = points[0].day
    xs = [Decimal((point.day - origin).days) for point in points]
    ys = [point.value for point in points]
    count = Decimal(len(points))
    mean_x = sum(xs, ZERO) / count
    mean_y = sum(ys, ZERO) / count
    denominator = sum(((x - mean_x) ** 2 for x in xs), ZERO)
    if denominator <= ZERO:
        return None
    numerator = sum(((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)), ZERO)
    return ((numerator / denominator) * 7).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)


def estimated_1rm_rir(
    weight_kg: Decimal | None, reps: int | None, rir: int | None
) -> Decimal | None:
    """Epley estimate with reps-in-reserve: weight x (1 + (reps + RIR) / 30).

    Requires 1-12 reps and 0-10 RIR. The result inherits the error of the reported RIR
    and of the equation; it is an estimate, never a measured maximum.
    """
    if weight_kg is None or weight_kg <= ZERO or reps is None or rir is None:
        return None
    if not 1 <= reps <= 12 or not 0 <= rir <= 10:
        return None
    effective = Decimal(reps + rir)
    return (weight_kg * (1 + effective / 30)).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SetRecord:
    """One performed set, with the muscle groups attached to its exercise."""

    muscles: tuple[str, ...]
    load_type: str
    weight_kg: Decimal | None
    reps: int | None
    rir: int | None = None


@dataclass(frozen=True)
class MuscleVolume:
    muscle: str
    sets: Decimal
    kg_reps: Decimal | None
    known_sets: int
    missing_sets: int


def volume_by_muscle(sets: Sequence[SetRecord]) -> tuple[MuscleVolume, ...]:
    """Sets and kg x reps per muscle group.

    A set counts once for every listed primary muscle (the catalog records primary
    muscles only). Only ``external`` load with weight and reps contributes kg x reps;
    anything else is reported as a missing set, not as zero.
    """
    counts: dict[str, list[Decimal]] = {}
    volumes: dict[str, list[Decimal]] = {}
    known: dict[str, int] = {}
    missing: dict[str, int] = {}
    for row in sets:
        muscles = {muscle.strip().lower() for muscle in row.muscles if muscle.strip()}
        if not muscles:
            continue
        value: Decimal | None = None
        if row.load_type == "external" and row.weight_kg is not None and row.reps is not None:
            countable = True
            value = (row.weight_kg * row.reps).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)
        else:
            countable = False
        for muscle in muscles:
            counts.setdefault(muscle, []).append(Decimal(1))
            known[muscle] = known.get(muscle, 0) + (1 if countable else 0)
            missing[muscle] = missing.get(muscle, 0) + (0 if countable else 1)
            if value is not None:
                volumes.setdefault(muscle, []).append(value)
    rows = [
        MuscleVolume(
            muscle=muscle,
            sets=sum(counts[muscle], ZERO),
            kg_reps=(
                sum(volumes[muscle], ZERO).quantize(LOAD_QUANTUM, rounding=ROUND_HALF_UP)
                if volumes.get(muscle)
                else None
            ),
            known_sets=known.get(muscle, 0),
            missing_sets=missing.get(muscle, 0),
        )
        for muscle in counts
    ]
    return tuple(sorted(rows, key=lambda row: row.muscle))


@dataclass(frozen=True)
class Adherence:
    eligible: int
    completed: int
    percent: Decimal | None


def adherence(eligible: int, completed: int) -> Adherence:
    """Completed / eligible as a percentage; cancelled and future sessions are excluded."""
    if eligible < 0 or completed < 0 or completed > eligible:
        raise ValueError("Adherencia inconsistente.")
    percent = (
        (Decimal(completed) * 100 / Decimal(eligible)).quantize(
            LOAD_QUANTUM, rounding=ROUND_HALF_UP
        )
        if eligible
        else None
    )
    return Adherence(eligible=eligible, completed=completed, percent=percent)


@dataclass(frozen=True)
class WeeklyMuscleSets:
    week_start: date
    muscle: str
    sets: Decimal


@dataclass(frozen=True)
class MuscleGap:
    muscle: str
    weeks: int


def muscle_gaps(rows: Sequence[WeeklyMuscleSets], muscles: Sequence[str]) -> tuple[MuscleGap, ...]:
    """Muscles with zero recorded sets across every supplied week.

    Callers pass only weeks with data; the gap reports how many weeks were checked.
    A muscle missing from the catalog list is not reported here.
    """
    weeks = {row.week_start for row in rows}
    totals: dict[str, Decimal] = {}
    for row in rows:
        key = row.muscle.strip().lower()
        totals[key] = totals.get(key, ZERO) + row.sets
    return tuple(
        MuscleGap(muscle=muscle.strip().lower(), weeks=len(weeks))
        for muscle in muscles
        if totals.get(muscle.strip().lower(), ZERO) <= ZERO
    )
