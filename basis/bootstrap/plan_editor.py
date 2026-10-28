"""Compose the private planning editor with the existing planning ports."""

from basis.modules.training.application.plan_editor import PlanEditor

from .planning import planning


def plan_editor() -> PlanEditor:
    return PlanEditor(planning())
