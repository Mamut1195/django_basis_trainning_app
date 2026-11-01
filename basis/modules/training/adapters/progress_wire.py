"""Existing report dictionaries remain a presentation concern."""

from ..domain.progress import Coverage, ProgressReport, TrekSummary
from ..domain.sports import SPORT_LABELS


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
    }


def encode_trip(result: TrekSummary) -> dict[str, object]:
    return {
        "stages": result.stages,
        "completed": result.completed,
        "totals": {r.name.value: r.value for r in result.totals},
    }
