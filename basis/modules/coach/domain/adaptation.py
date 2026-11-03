"""Deterministic week decision from recorded session-RPE. No provider and no invented load."""

from dataclasses import dataclass
from decimal import Decimal

from basis.modules.training.public import SPORT_LABELS, internal_load

PROTOCOLS = ("elapsed", "moving")


@dataclass(frozen=True)
class ObservedSession:
    sport: str
    protocol: str
    duration_seconds: int
    reported_rpe: Decimal | None


@dataclass(frozen=True)
class SportLoad:
    sport: str
    protocol: str
    load: Decimal | None
    sessions: int
    missing_rpe: int


@dataclass(frozen=True)
class Adaptation:
    action: str
    message: str
    loads: tuple[SportLoad, ...]
    protects: tuple[str, ...]
    progression: str | None


def adapt(
    sessions: tuple[ObservedSession, ...],
    *,
    goal: str | None,
    progress_sport: str | None,
    availability: tuple[int, ...] | None,
    pain: bool,
) -> Adaptation:
    """One next-week decision. Distinct sports and protocols stay on separate rows."""
    loads = _loads(sessions)
    if pain:
        return Adaptation(
            "stop",
            "Hay dolor registrado. No propongo un plan. Detén la actividad que duele y pide "
            "valoración profesional.",
            loads,
            (),
            None,
        )
    if not goal:
        return Adaptation(
            "ask", "Dime cómo quieres progresar antes de armar la semana.", loads, (), None
        )
    if not availability:
        return Adaptation("ask", "Registra los días que puedes entrenar.", loads, (), None)
    missing = next((row for row in loads if row.missing_rpe), None)
    if missing is not None:
        return Adaptation(
            "ask",
            f"Falta el RPE de {_label(missing.sport)} ({missing.protocol}). No lo tomo como cero. "
            "Dime ese RPE antes de cambiar el plan.",
            loads,
            (),
            None,
        )
    if progress_sport is None:
        return Adaptation("ask", "Dime en qué deporte quieres progresar.", loads, (), None)
    progress_rows = [row for row in loads if row.sport == progress_sport and row.load is not None]
    if not progress_rows:
        return Adaptation(
            "ask",
            f"No tengo carga registrada de {_label(progress_sport)}. No invento una semana.",
            loads,
            (),
            None,
        )
    progress_peak = max(row.load for row in progress_rows if row.load is not None)
    protects = tuple(
        sorted(
            {
                row.sport
                for row in loads
                if row.sport != progress_sport
                and row.load is not None
                and row.load >= progress_peak
            }
        )
    )
    listed = "; ".join(
        f"{_label(row.sport)}, protocolo {row.protocol}: {row.load} UA"
        for row in loads
        if row.load is not None
    )
    protected = ""
    if protects:
        protected = " Protejo " + " y ".join(_label(sport) for sport in protects) + "."
    several = len({row.sport for row in loads if row.load is not None}) > 1 or len(loads) > 1
    separate = " No las sumo." if several else ""
    return Adaptation(
        "propose",
        f"Puedo proponerte la próxima semana para progresar en {_label(progress_sport)}. "
        f"{listed}.{separate}{protected} Cambio una sola sesión.",
        loads,
        protects,
        f"una sola subida en {_label(progress_sport)}",
    )


def _loads(sessions: tuple[ObservedSession, ...]) -> tuple[SportLoad, ...]:
    grouped: dict[tuple[str, str], list[ObservedSession]] = {}
    for session in sessions:
        if session.protocol not in PROTOCOLS:
            raise ValueError("El protocolo de carga tiene que ser elapsed o moving.")
        if session.duration_seconds < 0:
            raise ValueError("La duración no puede ser negativa.")
        if session.reported_rpe is not None and not Decimal(0) <= session.reported_rpe <= Decimal(
            10
        ):
            raise ValueError("El RPE de sesión va de 0 a 10.")
        grouped.setdefault((session.sport, session.protocol), []).append(session)
    rows: list[SportLoad] = []
    for sport, protocol in sorted(grouped):
        bucket = grouped[sport, protocol]
        missing = sum(1 for session in bucket if session.reported_rpe is None)
        if missing:
            load = None
        else:
            parts: list[Decimal] = []
            for session in bucket:
                if session.reported_rpe is None:
                    continue
                value = internal_load(session.duration_seconds, session.reported_rpe)
                if value is None:
                    raise ValueError("La carga de sesión no se pudo calcular.")
                parts.append(value)
            load = sum(parts, Decimal(0))
        rows.append(SportLoad(sport, protocol, load, len(bucket), missing))
    return tuple(rows)


def _label(sport: str) -> str:
    return SPORT_LABELS.get(sport, sport)
