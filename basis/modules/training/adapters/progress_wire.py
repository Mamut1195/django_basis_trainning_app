"""Existing report dictionaries remain a presentation concern."""

from ..domain.progress import ProgressReport, TrekSummary
from ..domain.sports import SPORT_LABELS


def encode_progress(result: ProgressReport) -> dict[str, object]:
    return {
        "sports": [
            {
                "sport": s.sport,
                "label": SPORT_LABELS[s.sport],
                "sessions": s.sessions,
                "distance_m": s.distance_m,
                "ascent_m": s.ascent_m,
                "external_volume_kg": s.external_volume_kg,
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
    }


def encode_trip(result: TrekSummary) -> dict[str, object]:
    return {
        "stages": result.stages,
        "completed": result.completed,
        "totals": {r.name.value: r.value for r in result.totals},
    }
