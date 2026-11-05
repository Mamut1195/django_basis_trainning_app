"""Deterministic coach decisions over already-computed metrics.

The rules never calculate load or estimate a maximum; they receive numbers and return
findings with evidence. Thresholds are explicit product policy, not universal truths, and
live in ``Thresholds`` so they can be reviewed in one place.

The load ratio is descriptive (Impellizzeri et al. 2020): it is never used to predict an
injury. Progression and volume guidance follows the ACSM progression models and the
dose-response of weekly sets (Schoenfeld et al. 2017). See ``docs/COACH_ENGINE.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

ZERO = Decimal(0)


@dataclass(frozen=True)
class Thresholds:
    load_spike_ratio: Decimal = Decimal("1.20")
    load_drop_ratio: Decimal = Decimal("0.80")
    consecutive_weeks: int = 2
    plateau_sessions: int = 3
    plateau_tolerance_kg: Decimal = Decimal("0.50")
    plateau_rpe_max: Decimal = Decimal("7")
    adherence_min_percent: Decimal = Decimal("60")
    high_rpe: Decimal = Decimal("8")
    muscle_gap_weeks: int = 2


@dataclass(frozen=True)
class Finding:
    """One rule outcome. ``severity`` is ``info``, ``warn`` or ``stop``."""

    rule: str
    severity: str
    title: str
    reason: str
    evidence: tuple[str, ...]
    proposal: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warn", "stop"):
            raise ValueError("Severidad desconocida.")
        if not self.evidence:
            raise ValueError("Un hallazgo necesita evidencia.")


def _last(values: Sequence[Decimal | None]) -> Decimal | None:
    return values[-1] if values else None


def _trailing_above(values: Sequence[Decimal | None], threshold: Decimal) -> int:
    count = 0
    for value in reversed(values):
        if value is None or value <= threshold:
            break
        count += 1
    return count


def _trailing_below(values: Sequence[Decimal | None], threshold: Decimal) -> int:
    count = 0
    for value in reversed(values):
        if value is None or value >= threshold:
            break
        count += 1
    return count


def load_spike(
    ratios: Sequence[Decimal | None], thresholds: Thresholds = Thresholds()
) -> Finding | None:
    """Two or more consecutive weeks above the spike ratio."""
    weeks = _trailing_above(ratios, thresholds.load_spike_ratio)
    if weeks < thresholds.consecutive_weeks:
        return None
    current = _last(ratios)
    evidence = tuple(
        ("Hace 1 semana: " if offset == 1 else f"Hace {offset} semanas: ") + f"{value:.3f}x"
        for offset, value in enumerate(reversed(ratios[-weeks:]), start=1)
        if value is not None
    )
    return Finding(
        rule="load_spike",
        severity="warn",
        title="Carga por encima de tu base",
        reason=(
            f"Llevas {weeks} semanas por encima del {thresholds.load_spike_ratio:.0%} "
            "de tu media reciente."
        ),
        evidence=(
            evidence
            if evidence
            else (
                (f"Última semana: {current:.3f}x",)
                if current is not None
                else ("Sin datos recientes",)
            )
        ),
        proposal="Bajar un 20 % del volumen en accesorios y mantener los ejercicios principales.",
    )


def load_drop(
    ratios: Sequence[Decimal | None], thresholds: Thresholds = Thresholds()
) -> Finding | None:
    """Two or more consecutive weeks below the drop ratio."""
    weeks = _trailing_below(ratios, thresholds.load_drop_ratio)
    if weeks < thresholds.consecutive_weeks:
        return None
    current = _last(ratios)
    return Finding(
        rule="load_drop",
        severity="info",
        title="Carga por debajo de tu base",
        reason=f"Llevas {weeks} semanas por debajo del {thresholds.load_drop_ratio:.0%}.",
        evidence=(
            f"Última semana: {current:.3f}x" if current is not None else "Sin dato reciente",
        ),
        proposal="No subir todavía: primero recupera la continuidad y confirma que los datos están completos.",
    )


def adherence_rule(
    percent: Decimal | None, thresholds: Thresholds = Thresholds()
) -> Finding | None:
    """Low adherence suggests simplifying the plan instead of adding load."""
    if percent is None or percent >= thresholds.adherence_min_percent:
        return None
    return Finding(
        rule="adherence_low",
        severity="warn",
        title="Poca continuidad",
        reason=f"Adherencia del {percent:.2f} % en el período.",
        evidence=(f"Umbral: {thresholds.adherence_min_percent:.0f} %",),
        proposal="Simplificar el plan: menos sesiones o menos duración antes de subir intensidad.",
    )


def plateau(
    one_rep_max: Sequence[Decimal],
    rpe: Sequence[Decimal],
    thresholds: Thresholds = Thresholds(),
) -> Finding | None:
    """No 1RM progress across the last sessions, split by reported effort."""
    if len(one_rep_max) < thresholds.plateau_sessions:
        return None
    window = one_rep_max[-thresholds.plateau_sessions :]
    first, last = window[0], window[-1]
    if last - first > thresholds.plateau_tolerance_kg:
        return None
    effort = rpe[-thresholds.plateau_sessions :]
    average = sum(effort, ZERO) / len(effort) if effort else None
    evidence = (
        f"1RM estimado: {first:.2f} kg → {last:.2f} kg en {len(window)} sesiones",
        f"RPE medio: {average:.2f}" if average is not None else "RPE sin datos",
    )
    if average is not None and average > thresholds.plateau_rpe_max:
        return Finding(
            rule="plateau_high_effort",
            severity="info",
            title="Estancado con esfuerzo alto",
            reason="El peso no sube y el RPE ya es alto.",
            evidence=evidence,
            proposal="Revisar recuperación y sueño antes de añadir carga.",
        )
    return Finding(
        rule="plateau_low_effort",
        severity="info",
        title="Margen para progresar",
        reason="El peso no sube y el esfuerzo reportado todavía es moderado.",
        evidence=evidence,
        proposal="Añadir una serie o subir un 2,5 % de carga en el ejercicio.",
    )


def muscle_gap_rule(
    missing_muscles: Sequence[str], weeks: int, thresholds: Thresholds = Thresholds()
) -> Finding | None:
    """Muscle groups with zero recorded sets for enough weeks."""
    if weeks < thresholds.muscle_gap_weeks or not missing_muscles:
        return None
    muscles = ", ".join(sorted(missing_muscles))
    return Finding(
        rule="muscle_gap",
        severity="info",
        title="Grupos sin volumen registrado",
        reason=f"Sin series registradas en {weeks} semanas.",
        evidence=(f"Grupos: {muscles}",),
        proposal=f"Elegir un ejercicio de la biblioteca para: {muscles}.",
    )


def missing_rpe(missing_sessions: int) -> Finding | None:
    """Missing effort is a question, never zero."""
    if missing_sessions <= 0:
        return None
    return Finding(
        rule="missing_rpe",
        severity="info",
        title="Falta el esfuerzo percibido",
        reason=f"{missing_sessions} sesión(es) sin RPE.",
        evidence=(f"Sesiones sin dato: {missing_sessions}",),
        proposal="Preguntar el RPE antes de proponer cualquier cambio de carga.",
    )


def high_rpe_low_load(
    average_rpe: Decimal | None,
    load_ratio: Decimal | None,
    thresholds: Thresholds = Thresholds(),
) -> Finding | None:
    """High effort while load is below baseline: review recovery, never diagnose."""
    if average_rpe is None or load_ratio is None:
        return None
    if average_rpe < thresholds.high_rpe or load_ratio >= thresholds.load_drop_ratio:
        return None
    return Finding(
        rule="high_rpe_low_load",
        severity="warn",
        title="Esfuerzo alto con carga baja",
        reason="El RPE sube mientras la carga está por debajo de tu base.",
        evidence=(f"RPE medio: {average_rpe:.2f}", f"Carga: {load_ratio:.3f}x"),
        proposal="Revisar sueño, fatiga y disposición; no añadir carga esta semana.",
    )


def pain_rule(has_pain: bool) -> Finding | None:
    """Pain stops programming and refers to a professional."""
    if not has_pain:
        return None
    return Finding(
        rule="pain_stop",
        severity="stop",
        title="Dolor reportado",
        reason="Hay dolor agudo o síntomas reportados.",
        evidence=("Dolor o síntomas marcados en el registro",),
        proposal="Detener la actividad y pedir valoración profesional. No programar rehabilitación.",
    )


def evaluate(
    *,
    load_ratios: Sequence[Decimal | None] = (),
    adherence_percent: Decimal | None = None,
    one_rep_max: Sequence[Decimal] = (),
    rpe: Sequence[Decimal] = (),
    missing_muscles: Sequence[str] = (),
    muscle_weeks: int = 0,
    missing_sessions: int = 0,
    average_rpe: Decimal | None = None,
    has_pain: bool = False,
    thresholds: Thresholds = Thresholds(),
) -> tuple[Finding, ...]:
    """Run every rule that has enough inputs and return findings in a stable order."""
    findings = [
        pain_rule(has_pain),
        load_spike(load_ratios, thresholds),
        high_rpe_low_load(average_rpe, _last(load_ratios), thresholds),
        load_drop(load_ratios, thresholds),
        adherence_rule(adherence_percent, thresholds),
        plateau(one_rep_max, rpe, thresholds),
        muscle_gap_rule(missing_muscles, muscle_weeks, thresholds),
        missing_rpe(missing_sessions),
    ]
    return tuple(finding for finding in findings if finding is not None)
