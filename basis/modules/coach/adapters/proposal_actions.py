"""Coach HTTP input actions use public planning projections and injected decoding."""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from basis.bootstrap.coach import contexts, proposal_decoder, proposals
from basis.bootstrap.planning import planning
from basis.bootstrap.presentation import plan_summaries
from basis.modules.coach.adapters.models import PlanProposal
from basis.modules.coach.application.proposals import AcceptProposal, EditAndAcceptProposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.coach.domain.proposals import ProposalUnavailable
from basis.modules.training.public import (
    SPORT_LABELS,
    VARIABLES,
    InvalidPlanning,
    PlanDefinition,
    PlanningUnavailable,
    PlanSummary,
    StrengthData,
)
from basis.shared.identifiers import AccountId, ExerciseId, PlanId, ProposalId


def accept_proposal(
    owner: AbstractUser, proposal_id: int, expected_review: str | None = None
) -> PlanSummary:
    try:
        result = proposals().accept(
            AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id), expected_review)
        )
        return plan_summaries().read(AccountId(owner.pk), result)
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except (CoachInvalid, InvalidPlanning, PlanningUnavailable) as error:
        raise ValidationError(str(error)) from None


def edit_and_accept_proposal(
    owner: AbstractUser, proposal_id: int, content: object, expected_review: str | None = None
) -> PlanSummary:
    try:
        result = proposals(content).edit_and_accept(
            EditAndAcceptProposal(
                AccountId(owner.pk),
                ProposalId(proposal_id),
                proposal_decoder()(content),
                expected_review,
            )
        )
        return plan_summaries().read(AccountId(owner.pk), result)
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except (CoachInvalid, InvalidPlanning, PlanningUnavailable) as error:
        raise ValidationError(str(error)) from None


def reject_proposal(
    owner: AbstractUser, proposal_id: int, expected_review: str | None = None
) -> None:
    try:
        proposals().reject(
            AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id), expected_review)
        )
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except CoachInvalid as error:
        raise ValidationError(str(error)) from None


def review_proposal(
    owner: AbstractUser,
    proposal_id: int,
    content: object = None,
    expected_review: str | None = None,
) -> str:
    try:
        result = proposals().review(
            AcceptProposal(AccountId(owner.pk), ProposalId(proposal_id), expected_review),
            proposal_decoder()(content) if content is not None else None,
        )
        return result.review_key
    except ProposalUnavailable as error:
        raise PlanProposal.DoesNotExist from error
    except (CoachInvalid, InvalidPlanning, PlanningUnavailable) as error:
        raise ValidationError(str(error)) from None


def comparison(
    owner: AbstractUser, row: PlanProposal, content: object
) -> list[tuple[str, str, str]]:
    candidate = proposal_decoder()(content)
    base = (
        planning()
        .repository.snapshot(AccountId(owner.pk), PlanId(row.base_plan_id), lock=False)
        .definition
        if row.base_plan_id is not None
        else None
    )
    context = contexts().snapshot(
        AccountId(owner.pk),
        "plan",
        PlanId(row.base_plan_id) if row.base_plan_id is not None else None,
    )
    names = {e.id: e.name for e in context.exercises or ()}
    goals = {g.id: g.title for g in context.training.goals}

    def describe_set(item: StrengthData) -> str:
        labels = (
            ("kind", "Tipo de serie"),
            ("load_type", "Tipo de carga"),
            ("tempo", "Tempo"),
            ("range_of_motion", "Recorrido"),
            ("side", "Lado"),
            ("group", "Grupo"),
            ("target_reps", "Repeticiones"),
            ("target_reps_min", "Repeticiones mínimas"),
            ("target_reps_max", "Repeticiones máximas"),
            ("target_kg", "Carga (kg)"),
            ("target_percent_rm", "RM (%)"),
            ("rm_reference", "Referencia RM"),
            ("bodyweight_kg", "Peso corporal declarado (kg)"),
            ("target_rpe", "RPE objetivo"),
            ("target_rir", "RIR objetivo"),
            ("rest_seconds", "Descanso (s)"),
            ("target_isometric_seconds", "Isometría (s)"),
        )
        values = [
            f"{label}: {getattr(item, field)}"
            for field, label in labels
            if getattr(item, field) not in (None, "")
        ]
        return (
            names.get(ExerciseId(item.exercise), "#" + str(item.exercise))
            + ": "
            + ", ".join(values)
        )

    def describe(definition: PlanDefinition | None) -> list[str]:
        if definition is None:
            return ["Sin plan base"] * 6
        cycle_names = {c.key: c.title for c in definition.cycles}
        cycles = "; ".join(
            f"{c.kind.value}: {c.title} ({c.start_date} a {c.end_date})"
            + (f" · dentro de {cycle_names.get(c.parent, c.parent)}" if c.parent else "")
            + (f" · {c.focus}" if c.focus else "")
            for c in definition.cycles
        )
        sessions: list[str] = []
        for session in definition.sessions:
            blocks: list[str] = []
            for block in session.blocks:
                targets = ", ".join(
                    f"{VARIABLES[block.sport][m.name].label}: {m.value} "
                    f"{VARIABLES[block.sport][m.name].unit}"
                    for m in block.target
                )
                sets = "; ".join(describe_set(s) for s in block.sets)
                intervals = "; ".join(
                    f"{i.repetitions} repeticiones: "
                    + ", ".join(
                        f"{VARIABLES[block.sport][m.name].label}: {m.value} "
                        f"{VARIABLES[block.sport][m.name].unit}"
                        for m in i.target
                    )
                    + f" · descanso {i.rest_seconds} s · RPE {i.target_rpe}"
                    for i in block.intervals
                )
                blocks.append(
                    f"{SPORT_LABELS[block.sport]} · {block.title}: {targets} {sets} {intervals}"
                    + (f" · {block.notes}" if block.notes else "")
                )
            sessions.append(
                f"{session.date} · {session.title} · {cycle_names.get(session.cycle_key, session.cycle_key)} · "
                + " / ".join(blocks)
                + (f" · {session.notes}" if session.notes else "")
            )
        return [
            definition.title,
            goals.get(definition.goal, "#" + str(definition.goal)),
            f"{definition.start_date} a {definition.end_date}",
            definition.notes or "Sin motivo ni supuestos declarados",
            cycles,
            "\n".join(sessions),
        ]

    return list(
        zip(
            (
                "Nombre",
                "Objetivo",
                "Fechas",
                "Motivo y supuestos declarados",
                "Ciclos",
                "Sesiones y prescripciones",
            ),
            describe(base),
            describe(candidate),
            strict=True,
        )
    )
