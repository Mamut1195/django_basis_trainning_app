"""Immutable, authorized context: observations remain typed and optional."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from basis.modules.athletes.public import AthleteCoachContext
from basis.modules.catalog.public import CoachExercise
from basis.modules.training.public import CoachBasePlan, CoachVariables, TrainingCoachContext

from .decisions import Finding


def owner_snapshot_date(instant: datetime, timezone_name: str | None) -> date:
    """One captured, aware instant; missing owner zone explicitly falls back to UTC."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("La captura requiere un instante con zona horaria.")
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("La zona horaria del perfil no está disponible.") from error
    return instant.astimezone(zone).date()


@dataclass(frozen=True)
class CoachContext:
    snapshot_at: datetime
    athlete: AthleteCoachContext
    training: TrainingCoachContext
    exercises: tuple[CoachExercise, ...] | None = None
    variables: tuple[CoachVariables, ...] | None = None
    base_plan: CoachBasePlan | None = None
    # Defaults preserve old constructors and saved, unversioned snapshots.
    schema_version: int = 1
    missing: tuple[str, ...] = ()
    instructions_version: str | None = None
    system_sha256: str | None = None
    plan_sha256: str | None = None
    tools: tuple[str, ...] = ()
    legacy_omissions: tuple[str, ...] = ()
    progress_method: str = "session-rpe-v1; total de bloque; sin suma entre deportes"
    diagnosis: tuple[Finding, ...] = ()
