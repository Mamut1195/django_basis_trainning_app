"""Versioned editor using the same authorization, aggregate lock and unit of work."""

from dataclasses import dataclass
from datetime import date

from basis.shared.identifiers import AccountId, GoalId, PlanId

from ..domain.plan_editor import edit_definition, template_definition
from ..domain.planning import (
    CycleDefinition,
    PlanHeader,
    require_plan_ownership,
    require_reason,
)
from .planning import Planning


@dataclass(frozen=True)
class EditPlan:
    owner: AccountId
    plan: PlanId
    title: str
    start: date
    end: date
    notes: str
    reason: str
    cycle: CycleDefinition | None = None


@dataclass(frozen=True)
class CopyTemplate:
    owner: AccountId
    source: PlanId
    goal: GoalId
    title: str
    start: date
    reason: str


class PlanEditor:
    def __init__(self, planning: Planning) -> None:
        self.planning = planning

    def edit(self, command: EditPlan) -> PlanHeader:
        p = self.planning
        with p.uow() as work:
            p.authorization.require(command.owner)
            snapshot = p.repository.snapshot(command.owner, command.plan, lock=True)
            reason = require_reason(command.reason)
            definition = edit_definition(
                snapshot,
                p.today(command.owner),
                command.title,
                command.start,
                command.end,
                command.notes,
                command.cycle,
            )
            result = p.repository.create(command.owner, definition, snapshot.header)
            p.repository.annotate_change(result, reason, "edit", p.today(command.owner))
            work.commit()
            return result

    def copy(self, command: CopyTemplate) -> PlanHeader:
        p = self.planning
        with p.uow() as work:
            p.authorization.require(command.owner)
            snapshot = p.repository.snapshot(command.owner, command.source, lock=True)
            require_plan_ownership(command.owner, p.repository.goal_owner(command.goal), None)
            reason = require_reason(command.reason)
            definition = template_definition(snapshot, command.goal, command.title, command.start)
            result = p.repository.create(command.owner, definition, None)
            p.repository.annotate_change(result, reason, "template", p.today(command.owner))
            work.commit()
            return result
