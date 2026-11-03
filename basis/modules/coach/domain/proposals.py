"""Proposal state is separate from its private athlete plan instance."""

from dataclasses import dataclass
from decimal import Decimal

from basis.modules.training.public import MetricName, PlanDefinition
from basis.shared.identifiers import AccountId, JobId, PlanId, ProposalId

from .context import CoachContext
from .jobs import CoachInvalid


@dataclass(frozen=True)
class Proposal:
    id: ProposalId
    owner: AccountId
    job: JobId
    definition: PlanDefinition | None
    base_plan: PlanId | None
    status: str
    accepted_plan: PlanId | None
    review_key: str = ""


class ProposalUnavailable(Exception):
    pass


def require_review(proposal: Proposal, expected: str | None) -> None:
    if expected is not None and proposal.review_key != expected:
        raise CoachInvalid("La propuesta cambió desde tu revisión. Recarga antes de decidir.")


def validate_context(
    definition: PlanDefinition, source: CoachContext, current: CoachContext
) -> None:
    """Check declared constraints; free text is never an equipment/safety ontology."""
    goal = next((g for g in source.training.goals if g.id == definition.goal), None)
    current_goal = next((g for g in current.training.goals if g.id == definition.goal), None)
    if goal is None or goal != current_goal:
        raise CoachInvalid(
            "El objetivo no pertenece al contexto autorizado o cambió. Pide otra propuesta."
        )
    if source.base_plan != current.base_plan:
        raise CoachInvalid("La versión base cambió. Pide otra propuesta.")
    a, b = source.athlete, current.athlete
    if (
        a.age != b.age
        or a.objectives != b.objectives
        or a.preferences != b.preferences
        or sorted(a.sports, key=lambda s: s.sport) != sorted(b.sports, key=lambda s: s.sport)
    ):
        raise CoachInvalid(
            "El perfil, disponibilidad, equipo o restricciones cambiaron. Pide otra propuesta."
        )
    preferences = b.preferences
    if preferences is None or not preferences.availability:
        raise CoachInvalid("Registra tus días disponibles antes de revisar una propuesta.")
    # CoachContext currently has no authorized RM read projection. Ownership in
    # the manual planning service cannot establish provenance for generated data.
    if any(
        row.rm_reference is not None or row.target_percent_rm is not None
        for session in definition.sessions
        for block in session.blocks
        for row in block.sets
    ):
        raise CoachInvalid(
            "El contexto no contiene RM autorizadas. Revisa esas referencias en la planificación manual."
        )
    allowed = {e.id for e in source.exercises or ()} & {e.id for e in current.exercises or ()}
    for session in definition.sessions:
        if session.date.isoweekday() not in preferences.availability:
            raise CoachInvalid("Una sesión queda fuera de tus días disponibles.")
        # Block totals are authoritative. Do not add interval durations again or
        # manufacture missing duration from distance, repetitions or intensity.
        seconds = sum(
            (
                metric.value
                for block in session.blocks
                for metric in block.target
                if metric.name == MetricName.DURATION_SECONDS and isinstance(metric.value, Decimal)
            ),
            Decimal(0),
        )
        if seconds > preferences.minutes_per_session * 60:
            raise CoachInvalid("La duración declarada supera tus minutos disponibles por sesión.")
        if any(row.exercise not in allowed for block in session.blocks for row in block.sets):
            raise CoachInvalid(
                "Un ejercicio no pertenece al catálogo autorizado de esta propuesta."
            )
