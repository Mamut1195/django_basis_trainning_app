"""Existing report dictionaries remain a presentation concern."""

from ..domain.progress import Coverage, ProgressReport, TrekSummary
from ..domain.sports import SPORT_LABELS, internal_load


def coverage(value: Coverage) -> dict[str, int]:
    return {
        "known": value.known,
        "missing": value.missing,
        "not_applicable": value.not_applicable,
        "unknown_applicability": value.unknown_applicability,
    }


def encode_progress(result: ProgressReport) -> dict[str, object]:
    return {
        "sports": [
            {
                "sport": s.sport,
                "label": SPORT_LABELS[s.sport],
                "sessions": s.sessions,
                "rpe_min": s.rpe_min,
                "rpe_max": s.rpe_max,
                "rpe_known": s.rpe_known,
                "rpe_missing": s.rpe_missing,
                "distance_m": s.distance_m,
                "ascent_m": s.ascent_m,
                "external_volume_kg": s.external_volume_kg,
                "distance_not_applicable": s.distance_coverage.known == 0
                and s.distance_coverage.missing == 0
                and s.distance_coverage.not_applicable > 0,
                "ascent_not_applicable": s.ascent_coverage.known == 0
                and s.ascent_coverage.missing == 0
                and s.ascent_coverage.not_applicable > 0,
                "volume_not_applicable": s.sport != "strength"
                or (
                    s.volume_coverage.known == 0
                    and s.volume_coverage.missing == 0
                    and s.volume_coverage.unknown_applicability == 0
                    and s.volume_coverage.not_applicable > 0
                ),
                "distance_coverage": coverage(s.distance_coverage),
                "ascent_coverage": coverage(s.ascent_coverage),
                "volume_coverage": coverage(s.volume_coverage),
            }
            for s in result.sports
        ],
        "loads": [
            {
                "protocol": r.protocol.value,
                "label": "Tiempo total" if r.protocol == "elapsed" else "Tiempo activo",
                "value": r.value,
                "known": r.known,
                "missing": r.missing,
            }
            for r in result.loads
        ],
        "sessions": result.sessions,
        "scheduled_past": result.scheduled_past,
        "completed_scheduled": result.completed_scheduled,
        "adherence_percent": result.adherence_percent,
        "method": "session-rpe-v1; total de bloque; sin suma entre deportes",
        "load_method": "session-rpe-v1: minutos de sesión × RPE de sesión; separado por protocolo",
        "load_unit": "UA",
        "context_method": (
            "Fechas de sesiones completadas dentro del período seleccionado; "
            "días consecutivos observados, sin inferir descanso, horas de recuperación "
            "ni riesgo de lesión. Notas de recuperación declaradas de etapas de trekking; "
            "no son una evaluación de recuperación."
        ),
        "context": [
            {
                "session_id": str(c.session.id),
                "date": c.session.date,
                "sports": list(dict.fromkeys(b.sport for b in c.session.blocks)),
                "protocol": c.session.protocol.value,
                "duration_seconds": c.session.duration_seconds,
                "reported_rpe": c.session.reported_rpe,
                "internal_load": internal_load(c.session.duration_seconds, c.session.reported_rpe),
                "previous_date": c.previous_date,
                "days_since_previous": c.days_since_previous,
                "consecutive_days": c.consecutive_days,
                "sessions_on_date": c.sessions_on_date,
                "stage_recovery": (
                    {
                        "trip_id": c.session.stage_recovery.trip,
                        "stage_id": c.session.stage_recovery.stage,
                        "order": c.session.stage_recovery.order,
                        "overnight_altitude_m": c.session.stage_recovery.overnight_altitude_m,
                        "recovery_notes": c.session.stage_recovery.recovery_notes,
                    }
                    if c.session.stage_recovery is not None
                    else None
                ),
            }
            for c in result.context
        ],
    }


def encode_trip(result: TrekSummary) -> dict[str, object]:
    return {
        "stages": result.stages,
        "completed": result.completed,
        "totals": {r.name.value: r.value for r in result.totals},
    }
