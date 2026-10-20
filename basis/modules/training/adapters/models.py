import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from basis.bootstrap.persistence import Owned, ValidatedModel
from basis.modules.athletes.public import (
    RMReferences,
)
from basis.modules.training.adapters.metrics import (
    estimated_1rm_legacy as estimated_1rm,
)
from basis.modules.training.adapters.metrics import (
    external_volume_legacy as external_volume,
)
from basis.modules.training.adapters.metrics import (
    internal_load_legacy as internal_load,
)
from basis.modules.training.adapters.metrics import (
    validate_metrics,
)
from basis.modules.training.public import (
    SPORTS,
    CycleDefinition,
    CycleKind,
    GoalData,
    InvalidExecution,
    InvalidPlanning,
    InvalidTrekking,
    ScheduledDefinition,
    StageNeighbour,
    validate_component_sport,
    validate_cycle,
    validate_dates,
    validate_goal,
    validate_plan_version,
    validate_prescribed_results,
    validate_repetition_prescription,
    validate_schedule,
    validate_stage,
    validate_strength_reference,
)
from basis.shared.identifiers import AccountId, ExerciseId, LineageId, MeasuredRMId

_rm_references: RMReferences | None = None


def configure_rm_references(references: RMReferences) -> None:
    global _rm_references
    _rm_references = references


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


class Session(Owned):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    planned = models.ForeignKey(
        PlannedSession, on_delete=models.PROTECT, null=True, blank=True, related_name="executions"
    )
    title = models.CharField(max_length=160)
    date = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(
        max_length=15,
        choices=[("in_progress", "En curso"), ("completed", "Completada")],
        default="in_progress",
    )
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(604800)]
    )
    duration_protocol = models.CharField(
        max_length=10,
        choices=[("elapsed", "Tiempo total"), ("moving", "Tiempo activo")],
        default="elapsed",
    )
    reported_rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    notes = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["owner", "date"])]

    def clean(self) -> None:
        self.same_owner(self.planned)

    @property
    def load(self) -> Decimal | None:
        return (
            internal_load(self.duration_seconds, self.reported_rpe)
            if self.status == "completed"
            else None
        )


class Block(ValidatedModel):
    planned = models.ForeignKey(
        PlannedSession, on_delete=models.PROTECT, null=True, blank=True, related_name="blocks"
    )
    session = models.ForeignKey(
        Session, on_delete=models.PROTECT, null=True, blank=True, related_name="blocks"
    )
    order = models.PositiveIntegerField(default=1)
    sport = models.CharField(max_length=20, choices=SPORTS)
    title = models.CharField(max_length=160)
    target = models.JSONField(default=dict, blank=True)
    actual = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(planned__isnull=False, session__isnull=True)
                    | Q(planned__isnull=True, session__isnull=False)
                ),
                name="block_exact_parent",
            )
        ]

    def clean(self) -> None:
        if bool(self.planned_id) == bool(self.session_id):
            raise ValidationError("Un bloque pertenece a prescripción o ejecución.")
        self.target = validate_metrics(self.sport, self.target)
        self.actual = validate_metrics(self.sport, self.actual)
        if self.planned_id:
            try:
                validate_prescribed_results(bool(self.actual), block_level=True)
            except InvalidPlanning as error:
                raise ValidationError(str(error)) from error

    @property
    def owner_id(self) -> int:
        parent = self.session if self.session_id else self.planned
        if parent is None:
            raise ValidationError("Un bloque requiere una prescripcion o ejecucion.")
        return parent.owner_id


class StrengthSet(ValidatedModel):
    block = models.ForeignKey(Block, on_delete=models.PROTECT, related_name="sets")
    exercise = models.ForeignKey("basis_catalog.Exercise", on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=1)
    kind = models.CharField(
        max_length=12,
        choices=[("warmup", "Calentamiento"), ("work", "Trabajo"), ("failed", "Fallida")],
        default="work",
    )
    load_type = models.CharField(
        max_length=12,
        choices=[
            ("external", "Carga externa"),
            ("bodyweight", "Peso corporal"),
            ("assisted", "Asistida"),
        ],
        default="external",
    )
    target_reps = models.PositiveIntegerField(null=True, blank=True)
    target_reps_min = models.PositiveIntegerField(null=True, blank=True)
    target_reps_max = models.PositiveIntegerField(null=True, blank=True)
    target_percent_rm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(200)],
    )
    actual_reps = models.PositiveIntegerField(null=True, blank=True)
    target_kg = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    actual_kg = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    bodyweight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    target_rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    actual_rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    target_rir = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(20)]
    )
    actual_rir = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(20)]
    )
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    actual_rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    tempo = models.CharField(
        max_length=30, blank=True, help_text="Excéntrica-pausa-concéntrica-pausa"
    )
    range_of_motion = models.CharField(max_length=80, blank=True)
    side = models.CharField(
        max_length=10,
        choices=[("both", "Bilateral"), ("left", "Izquierda"), ("right", "Derecha")],
        default="both",
    )
    isometric_seconds = models.PositiveIntegerField(null=True, blank=True)
    target_isometric_seconds = models.PositiveIntegerField(null=True, blank=True)
    group = models.CharField(max_length=80, blank=True, help_text="Superserie o circuito")
    rm_reference = models.ForeignKey(
        "basis_athletes.UserExerciseRM", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        ordering = ["order", "pk"]

    def clean(self) -> None:
        try:
            validate_repetition_prescription(
                self.target_reps,
                self.target_reps_min,
                self.target_reps_max,
                self.target_percent_rm,
                bool(self.rm_reference_id),
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        try:
            validate_component_sport(self.block.sport, strength=True)
        except InvalidExecution as error:
            raise ValidationError(str(error)) from error
        has_results = any(
            value is not None
            for value in (
                self.actual_kg,
                self.actual_reps,
                self.actual_rpe,
                self.actual_rir,
                self.actual_rest_seconds,
                self.isometric_seconds,
            )
        )
        if self.block.planned_id:
            try:
                validate_prescribed_results(has_results)
            except InvalidPlanning as error:
                raise ValidationError(str(error)) from error
        if self.rm_reference_id:
            parent = self.block.session if self.block.session_id else self.block.planned
            if parent is None:
                raise ValidationError("Un bloque requiere una prescripcion o ejecucion.")
            if _rm_references is None:
                raise RuntimeError("Training RM reference port has not been configured.")
            reference = _rm_references.get(MeasuredRMId(self.rm_reference_id))
            try:
                validate_strength_reference(
                    reference.owner if reference is not None else None,
                    reference.exercise if reference is not None else None,
                    reference.measured_on if reference is not None else None,
                    AccountId(parent.owner_id),
                    ExerciseId(self.exercise_id),
                    parent.date,
                )
            except ValueError as error:
                raise ValidationError(str(error)) from error

    @property
    def external_volume_kg(self) -> Decimal | None:
        return external_volume(self.load_type, self.actual_kg, self.actual_reps)

    @property
    def estimated_1rm(self) -> Decimal | None:
        return estimated_1rm(
            self.load_type, self.kind, self.actual_kg, self.actual_reps, self.actual_rpe
        )


class Interval(ValidatedModel):
    block = models.ForeignKey(Block, on_delete=models.PROTECT, related_name="intervals")
    order = models.PositiveIntegerField(default=1)
    repetitions = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    target = models.JSONField(default=dict, blank=True)
    actual = models.JSONField(default=dict, blank=True)
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    actual_rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    target_rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    actual_rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )

    class Meta:
        ordering = ["order", "pk"]

    def clean(self) -> None:
        try:
            validate_component_sport(self.block.sport, strength=False)
        except InvalidExecution as error:
            raise ValidationError(str(error)) from error
        self.target = validate_metrics(self.block.sport, self.target)
        self.actual = validate_metrics(self.block.sport, self.actual)
        if self.block.planned_id:
            try:
                validate_prescribed_results(
                    bool(self.actual)
                    or self.actual_rpe is not None
                    or self.actual_rest_seconds is not None
                )
            except InvalidPlanning as error:
                raise ValidationError(str(error)) from error


class TrekTrip(Owned):
    title = models.CharField(max_length=160)
    notes = models.TextField(blank=True)


class TrekStage(ValidatedModel):
    trip = models.ForeignKey(TrekTrip, on_delete=models.PROTECT, related_name="stages")
    session = models.OneToOneField(Session, on_delete=models.PROTECT, related_name="trek_stage")
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    overnight_altitude_m = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(-500), MaxValueValidator(9000)],
    )
    recovery_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["trip", "order"], name="trek_stage_order")]

    def clean(self) -> None:
        if not self.trip_id or not self.session_id:
            return
        try:
            validate_stage(
                AccountId(self.trip.owner_id),
                AccountId(self.session.owner_id),
                self.session.blocks.filter(sport="hiking").exists(),
                self.order,
                self.session.date,
                tuple(
                    StageNeighbour(stage.order, stage.session.date)
                    for stage in self.trip.stages.exclude(pk=self.pk).select_related("session")
                ),
            )
        except InvalidTrekking as error:
            raise ValidationError(str(error)) from error
