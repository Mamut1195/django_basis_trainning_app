"""Training persistence: planning."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from basis.adapters.django.persistence import Owned, ValidatedModel
from basis.modules.training.public import (
    SPORTS,
    CycleDefinition,
    CycleKind,
    GoalData,
    InvalidPlanning,
    ScheduledDefinition,
    validate_cycle,
    validate_dates,
    validate_goal,
    validate_plan_version,
    validate_schedule,
)
from basis.shared.identifiers import LineageId


class Goal(Owned):
    priority = models.CharField(
        max_length=10,
        choices=[("primary", "Principal"), ("secondary", "Secundario")],
        default="primary",
    )
    baseline_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    baseline_date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=160)
    sport = models.CharField(max_length=20, choices=SPORTS)
    target_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_unit = models.CharField(max_length=30, blank=True)

    def clean(self) -> None:
        try:
            validate_goal(
                GoalData(
                    self.title,
                    self.sport,
                    self.priority,
                    self.baseline_value,
                    self.baseline_date,
                    self.target_date,
                    self.description,
                    self.target_value,
                    self.target_unit,
                )
            )
        except InvalidPlanning as error:
            raise ValidationError(str(error)) from error


class TrainingPlan(Owned):
    lineage = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    previous = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="next_version"
    )
    goal = models.ForeignKey(Goal, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lineage", "version"], name="plan_lineage_version"),
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")), name="plan_date_order"
            ),
        ]

    def clean(self) -> None:
        if not self.goal_id or not self.start_date or not self.end_date:
            return
        self.same_owner(self.goal, self.previous)
        try:
            validate_dates(self.start_date, self.end_date)
        except InvalidPlanning as error:
            raise ValidationError(str(error)) from error
        previous = self.previous
        try:
            validate_plan_version(
                LineageId(self.lineage),
                self.version,
                LineageId(previous.lineage) if previous is not None else None,
                previous.version if previous is not None else None,
            )
        except InvalidPlanning as error:
            raise ValidationError(str(error)) from error


class Cycle(ValidatedModel):
    plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="cycles")
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    kind = models.CharField(
        max_length=10,
        choices=[("macro", "Macrociclo"), ("meso", "Mesociclo"), ("micro", "Microciclo")],
    )
    title = models.CharField(max_length=160)
    start_date = models.DateField()
    end_date = models.DateField()
    focus = models.TextField(blank=True)

    def clean(self) -> None:
        if (
            not self.plan_id
            or not self.start_date
            or not self.end_date
            or self.kind not in ("macro", "meso", "micro")
        ):
            return

        def definition(row: Cycle) -> CycleDefinition:
            return CycleDefinition(
                str(row.pk),
                str(row.parent_id) if row.parent_id is not None else None,
                CycleKind(row.kind),
                row.title,
                row.start_date,
                row.end_date,
                row.focus,
            )

        parent = self.parent
        try:
            validate_cycle(
                definition(self),
                self.plan.start_date,
                self.plan.end_date,
                definition(parent) if parent is not None else None,
                same_plan=parent is None or parent.plan_id == self.plan_id,
            )
        except InvalidPlanning as error:
            raise ValidationError(str(error)) from error


class PlannedSession(Owned):
    plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="sessions")
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["owner", "date"])]

    def clean(self) -> None:
        if not self.plan_id or not self.cycle_id or not self.date:
            return
        self.same_owner(self.plan)
        try:
            validate_schedule(
                ScheduledDefinition(str(self.cycle_id), self.title, self.date),
                CycleDefinition(
                    str(self.cycle.pk),
                    str(self.cycle.parent_id) if self.cycle.parent_id else None,
                    CycleKind(self.cycle.kind),
                    self.cycle.title,
                    self.cycle.start_date,
                    self.cycle.end_date,
                    self.cycle.focus,
                ),
                same_plan=self.cycle.plan_id == self.plan_id,
            )
        except InvalidPlanning as error:
            raise ValidationError(str(error)) from error
