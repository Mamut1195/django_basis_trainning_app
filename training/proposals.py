from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from .access import require_write_access
from .models import Cycle, Goal, PlannedSession, PlanProposal, TrainingPlan
from .services import save_blocks


@transaction.atomic
def build_plan(owner, content, previous=None):
    if not isinstance(content, dict) or set(content) - {
        "title",
        "goal_id",
        "start_date",
        "end_date",
        "notes",
        "cycles",
        "sessions",
    }:
        raise ValidationError("Formato de propuesta inválido.")
    try:
        goal = Goal.objects.get(pk=content["goal_id"], owner=owner)
        start, end = (
            date.fromisoformat(content["start_date"]),
            date.fromisoformat(content["end_date"]),
        )
        if end < start or (end - start).days > 366:
            raise ValueError
        cycles, sessions = content["cycles"], content["sessions"]
        if (
            not isinstance(cycles, list)
            or not 3 <= len(cycles) <= 100
            or not isinstance(sessions, list)
            or not 1 <= len(sessions) <= 14
        ):
            raise ValueError
        extra = (
            {"lineage": previous.lineage, "version": previous.version + 1, "previous": previous}
            if previous
            else {}
        )
        plan = TrainingPlan.objects.create(
            owner=owner,
            goal=goal,
            title=content["title"],
            start_date=start,
            end_date=end,
            notes=content.get("notes", ""),
            **extra,
        )
        mapping = {}
        for kind in ("macro", "meso", "micro"):
            for row in cycles:
                if not isinstance(row, dict) or set(row) - {
                    "key",
                    "parent",
                    "kind",
                    "title",
                    "start_date",
                    "end_date",
                    "focus",
                }:
                    raise ValueError
                if row.get("kind") != kind:
                    continue
                key = row["key"]
                if (
                    not isinstance(key, str)
                    or key in mapping
                    or (row.get("parent") and row["parent"] not in mapping)
                ):
                    raise ValueError
                mapping[key] = Cycle.objects.create(
                    plan=plan,
                    parent=mapping.get(row.get("parent")),
                    kind=kind,
                    title=row["title"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    focus=row.get("focus", ""),
                )
        if len(mapping) != len(cycles):
            raise ValueError
        for row in sessions:
            if (
                not isinstance(row, dict)
                or set(row) - {"title", "date", "cycle_key", "blocks"}
                or row["cycle_key"] not in mapping
            ):
                raise ValueError
            scheduled = PlannedSession.objects.create(
                owner=owner,
                plan=plan,
                cycle=mapping[row["cycle_key"]],
                title=row["title"],
                date=row["date"],
            )
            save_blocks(scheduled, row["blocks"])
        return plan
    except (KeyError, TypeError, ValueError, Goal.DoesNotExist):
        raise ValidationError(
            "Propuesta incompleta, objetivo ajeno o estructura inválida."
        ) from None


def validate_proposal(owner, content):
    # Exercise exactly the same model/range/ownership checks as acceptance, without persisting.
    with transaction.atomic():
        build_plan(owner, content)
        transaction.set_rollback(True)


@transaction.atomic
def accept_proposal(owner, proposal_id):
    require_write_access(owner)
    proposal = PlanProposal.objects.select_for_update().get(pk=proposal_id, owner=owner)
    if proposal.status == "accepted":
        return proposal.accepted_plan
    if proposal.status != "pending":
        raise ValidationError("Esta propuesta ya fue rechazada.")
    if proposal.base_plan_id and TrainingPlan.objects.filter(previous=proposal.base_plan).exists():
        raise ValidationError("El plan cambió desde la propuesta. Revisa una nueva versión.")
    plan = build_plan(owner, proposal.content, previous=proposal.base_plan)
    proposal.status, proposal.accepted_plan = "accepted", plan
    proposal.save()
    return plan
