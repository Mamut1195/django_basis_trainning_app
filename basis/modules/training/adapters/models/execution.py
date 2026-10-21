"""Training persistence: execution."""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from basis.adapters.django.persistence import Owned, ValidatedModel
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
    InvalidExecution,
    InvalidPlanning,
    validate_component_sport,
    validate_prescribed_results,
    validate_repetition_prescription,
    validate_strength_reference,
)
from basis.shared.identifiers import AccountId, ExerciseId, MeasuredRMId

from .planning import PlannedSession

_rm_references: RMReferences | None = None


def require_mutable_prescription(block: "Block") -> None:
    if block.planned_id:
        from .planning import TrainingPlan

        planned = block.planned
        assert planned is not None
        if (
            planned.executions.exists()
            or TrainingPlan.objects.using(planned._state.db)
            .filter(previous_id=planned.plan_id)
            .exists()
        ):
            raise ValidationError("La prescripción histórica es inmutable. Crea otra versión.")


def configure_rm_references(references: RMReferences) -> None:
    global _rm_references
    _rm_references = references


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
    source = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="execution_copies",
        editable=False,
    )
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
        require_mutable_prescription(self)
        source, session = self.source, self.session
        if source is not None and (
            session is None
            or source.planned_id != session.planned_id
            or source.session_id is not None
        ):
            raise ValidationError("Origen de bloque incompatible con esta ejecución.")
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
    source = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="execution_copies",
        editable=False,
    )
    actual_exercise = models.ForeignKey(
        "basis_catalog.Exercise",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="performed_sets",
    )
    actual_load_type = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        choices=[
            ("external", "Carga externa"),
            ("bodyweight", "Peso corporal"),
            ("assisted", "Asistida"),
        ],
    )
    actual_kind = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        choices=[("warmup", "Calentamiento"), ("work", "Trabajo"), ("failed", "Fallida")],
    )
    actual_tempo = models.CharField(max_length=30, null=True, blank=True)
    actual_range_of_motion = models.CharField(max_length=80, null=True, blank=True)
    actual_side = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=[("both", "Bilateral"), ("left", "Izquierda"), ("right", "Derecha")],
    )
    actual_group = models.CharField(max_length=80, null=True, blank=True)
    adaptation_reason = models.CharField(max_length=1000, blank=True)
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
        from ...domain.execution_updates import validate_adaptation
        from ..manual_repository import strength_data

        try:
            validate_adaptation(strength_data(self))
        except InvalidExecution as error:
            raise ValidationError(str(error)) from error
        source = self.source
        if source is not None and (
            source.block_id != self.block.source_id or not self.block.session_id
        ):
            raise ValidationError("Origen de serie incompatible con este bloque.")
        if self.block.planned_id and (
            self.adaptation_reason
            or any(
                getattr(self, name) is not None
                for name in (
                    "actual_exercise_id",
                    "actual_load_type",
                    "actual_kind",
                    "actual_tempo",
                    "actual_range_of_motion",
                    "actual_side",
                    "actual_group",
                )
            )
        ):
            raise ValidationError("Una prescripción no contiene adaptaciones realizadas.")
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
        require_mutable_prescription(self.block)
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
        return external_volume(
            self.actual_load_type or self.load_type, self.actual_kg, self.actual_reps
        )

    @property
    def estimated_1rm(self) -> Decimal | None:
        return estimated_1rm(
            self.actual_load_type or self.load_type,
            self.actual_kind or self.kind,
            self.actual_kg,
            self.actual_reps,
            self.actual_rpe,
        )


class Interval(ValidatedModel):
    source = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="execution_copies",
        editable=False,
    )
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
        require_mutable_prescription(self.block)
        source = self.source
        if source is not None and (
            source.block_id != self.block.source_id or not self.block.session_id
        ):
            raise ValidationError("Origen de intervalo incompatible con este bloque.")
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
