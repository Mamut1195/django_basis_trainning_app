"""Athletes persistence: strength."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.base import ModelBase
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from basis.modules.athletes.public import (
    InvalidAthleteData,
    InvalidAthleteField,
    MeasuredRMData,
    MeasuredRMState,
    decide_workout_reference,
    require_unchanged_rm,
    validate_workout_reference,
)
from basis.modules.training.public import (
    METRICS_VERSION,
    MetricsInputError,
    ReferenceContext,
)
from basis.shared.identifiers import AthleteId, ExerciseId, MeasuredRMId

from ..workout_metrics import calculate_strength_metrics
from .profile import User


class UserExerciseRM(models.Model):
    """Registro histórico del 1RM de un usuario en un ejercicio"""

    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name=_("User"))
    exercise = models.ForeignKey(
        "basis_catalog.Exercise", on_delete=models.PROTECT, verbose_name=_("Exercise")
    )
    peso_maximo_rm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        default=0,
        verbose_name=_("Max Lift (1RM)"),
        help_text=_("Peso máximo levantado en una repetición máxima para este ejercicio."),
    )
    fecha_registro = models.DateField(default=now, verbose_name=_("Date Recorded"))

    class Meta:
        verbose_name = _("User Exercise 1RM")
        verbose_name_plural = _("User Exercise 1RMs")
        # Ordenamos del más reciente al más antiguo
        ordering = ["-fecha_registro"]

    def __str__(self) -> str:
        return f"{self.user.nombre} - {self.exercise.nombre}: {self.peso_maximo_rm} kg ({self.fecha_registro})"

    def clean(self) -> None:
        fields = ("user_id", "exercise_id", "peso_maximo_rm", "fecha_registro")
        previous = (
            type(self).objects.filter(pk=self.pk).values(*fields).first() if self.pk else None
        )
        if previous:
            try:
                require_unchanged_rm(
                    MeasuredRMState(
                        AthleteId(previous["user_id"]),
                        MeasuredRMData(
                            ExerciseId(previous["exercise_id"]),
                            previous["peso_maximo_rm"],
                            previous["fecha_registro"],
                        ),
                    ),
                    MeasuredRMState(
                        AthleteId(self.user_id),
                        MeasuredRMData(
                            ExerciseId(self.exercise_id),
                            self.peso_maximo_rm,
                            self.fecha_registro,
                        ),
                    ),
                )
            except InvalidAthleteData as error:
                raise ValidationError(str(error)) from error

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
            if not self.pk:
                raise ValueError("Cannot force an update in save() with no primary key.")
            candidate = type(self).objects.get(pk=self.pk)
            for field in self._meta.concrete_fields:
                if field.name in update_fields or field.attname in update_fields:
                    setattr(candidate, field.attname, getattr(self, field.attname))
            candidate.full_clean()
        else:
            self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @staticmethod
    def get_latest_rm(
        user: User, exercise: models.Model | int, as_of: date | None = None
    ) -> Decimal | None:
        """Obtiene el 1RM más reciente para un usuario y ejercicio"""
        latest_rm = (
            UserExerciseRM.objects.filter(
                user=user,
                exercise_id=exercise.pk if isinstance(exercise, models.Model) else exercise,
                fecha_registro__lte=as_of or now().date(),
                peso_maximo_rm__gt=0,
            )
            .order_by("-fecha_registro", "-pk")
            .first()
        )
        return latest_rm.peso_maximo_rm if latest_rm else None

    @staticmethod
    def get_latest_rm_from_workouts(
        user: User, exercise: models.Model | int, as_of: date | None = None
    ) -> Decimal | None:
        """Obtiene el 1RM estimado más reciente desde los entrenamientos en WorkoutData"""
        latest_workout = (
            WorkoutData.objects.filter(
                user=user,
                exercise_id=exercise.pk if isinstance(exercise, models.Model) else exercise,
                fecha__lte=as_of or now().date(),
            )
            .order_by("-fecha", "-pk")
            .first()
        )

        if not latest_workout:
            return None

        # Usamos la mejor fórmula para calcular el 1RM desde el último
        # entrenamiento
        return latest_workout.calcular_rm_sesion()


class WorkoutData(models.Model):
    user = models.ForeignKey("User", on_delete=models.PROTECT, verbose_name=_("User"))
    exercise = models.ForeignKey(
        "basis_catalog.Exercise", on_delete=models.PROTECT, verbose_name=_("Exercise")
    )
    fecha = models.DateField(verbose_name=_("Date"))
    sets = models.PositiveIntegerField(default=0, verbose_name=_("Sets"))
    reps = models.PositiveIntegerField(default=0, verbose_name=_("Reps"))
    total_reps = models.PositiveIntegerField(default=0, verbose_name=_("Total Reps"))
    peso = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        verbose_name=_("Weight (kg)"),
    )
    intensidad_relativa = models.FloatField(default=0.0, verbose_name=_("Relative Intensity (%)"))
    carga = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name=_("Load (kg)")
    )
    volumen_relativo = models.FloatField(default=0.0, verbose_name=_("Relative Volume"))
    rpe_objetivo = models.FloatField(default=0.0, verbose_name=_("Target RPE"))
    rm_sesion = models.FloatField(default=0.0, verbose_name=_("Estimated 1RM (Session)"))
    rpe_real = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    rm_referencia = models.ForeignKey(
        UserExerciseRM, on_delete=models.PROTECT, null=True, blank=True
    )
    metrics_version = models.CharField(max_length=30, default="legacy-unverified")

    METRIC_FIELDS = frozenset(
        {
            "total_reps",
            "carga",
            "intensidad_relativa",
            "volumen_relativo",
            "rm_sesion",
            "rm_referencia",
            "metrics_version",
        }
    )

    def _resolve_rm_reference(self) -> UserExerciseRM | None:
        """Freeze even an absent reference once calculated for this context."""
        previous = (
            type(self)
            .objects.filter(pk=self.pk)
            .values("user_id", "exercise_id", "fecha", "rm_referencia_id", "metrics_version")
            .first()
            if self.pk
            else None
        )
        current = ReferenceContext(
            AthleteId(self.user_id), ExerciseId(self.exercise_id), self.fecha
        )
        decision = decide_workout_reference(
            current,
            ReferenceContext(
                AthleteId(previous["user_id"]),
                ExerciseId(previous["exercise_id"]),
                previous["fecha"],
            )
            if previous
            else None,
            MeasuredRMId(previous["rm_referencia_id"])
            if previous and previous["rm_referencia_id"] is not None
            else None,
            previous["metrics_version"] if previous else "",
        )
        if previous and decision.reuse_previous:
            if self.rm_referencia_id not in (None, previous["rm_referencia_id"]):
                raise ValidationError({"rm_referencia": "La referencia histórica es estable."})
            self.rm_referencia_id = decision.reference
            reference = self.rm_referencia if self.rm_referencia_id else None
        else:
            # A changed athlete/exercise/date needs its own dated reference.
            if previous and self.rm_referencia_id == previous["rm_referencia_id"]:
                self.rm_referencia = None
            if self.rm_referencia_id:
                try:
                    reference = self.rm_referencia
                except UserExerciseRM.DoesNotExist:
                    raise ValidationError({"rm_referencia": "La referencia no existe."}) from None
            else:
                reference = (
                    UserExerciseRM.objects.filter(
                        user_id=self.user_id,
                        exercise_id=self.exercise_id,
                        fecha_registro__lte=self.fecha,
                        peso_maximo_rm__gt=0,
                    )
                    .order_by("-fecha_registro", "-pk")
                    .first()
                )
        try:
            validate_workout_reference(
                ReferenceContext(
                    AthleteId(reference.user_id),
                    ExerciseId(reference.exercise_id),
                    reference.fecha_registro,
                )
                if reference
                else None,
                current,
            )
        except InvalidAthleteField as error:
            raise ValidationError({error.field: str(error)}) from error
        return reference

    def clean(self) -> None:
        """Shared rules for ModelForms, direct saves and API writes."""
        date_field = self._meta.get_field("fecha")
        assert isinstance(date_field, models.Field)
        self.fecha = date_field.clean(self.fecha, self)
        reference = self._resolve_rm_reference()
        try:
            metrics = calculate_strength_metrics(
                sets=self.sets,
                reps=self.reps,
                weight_kg=self.peso,
                reference_rm_kg=reference.peso_maximo_rm if reference else None,
                observed_rpe=self.rpe_real,
                target_rpe=self.rpe_objetivo,
            )
        except MetricsInputError as exc:
            field = NON_FIELD_ERRORS if exc.field in self.METRIC_FIELDS else exc.field
            raise ValidationError({field: f"{exc.field}: {exc}"}) from exc
        self.rm_referencia = reference
        self.total_reps = metrics.total_reps
        self.carga = metrics.load_kg_reps
        # Float storage and zero sentinels are kept for legacy compatibility.
        self.intensidad_relativa = float(metrics.relative_intensity_percent or 0)
        self.volumen_relativo = float(metrics.relative_volume or 0)
        self.rm_sesion = float(metrics.estimated_1rm_kg or 0)
        self.metrics_version = METRICS_VERSION
        # full_clean() validates fields BEFORE clean(); validate the new values too.
        errors: list[str] = []
        for name in ("total_reps", "carga", "intensidad_relativa", "volumen_relativo", "rm_sesion"):
            try:
                metric_field = self._meta.get_field(name)
                assert isinstance(metric_field, models.Field)
                metric_field.clean(getattr(self, name), self)
            except ValidationError as exc:
                errors.extend(f"{name}: {message}" for message in exc.messages)
        if errors:
            # Derived fields are excluded from the real admin ModelForms.
            raise ValidationError({NON_FIELD_ERRORS: errors})

    def calcular_rm_sesion(self) -> Decimal | None:
        return calculate_strength_metrics(
            sets=self.sets, reps=self.reps, weight_kg=self.peso, observed_rpe=self.rpe_real
        ).estimated_1rm_kg

    def calcular_rpe(self) -> Decimal | None:
        return self.rpe_real

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
            if not self.pk:
                raise ValueError("Cannot force an update in save() with no primary key.")
            # Excluded dirty attributes must not influence persisted derivatives.
            candidate = type(self).objects.get(pk=self.pk)
            for field in self._meta.concrete_fields:
                if field.name in update_fields or field.attname in update_fields:
                    setattr(candidate, field.attname, getattr(self, field.attname))
            candidate.full_clean()
            for name in self.METRIC_FIELDS:
                metric_field = self._meta.get_field(name)
                assert isinstance(metric_field, models.Field)
                setattr(self, metric_field.attname, getattr(candidate, metric_field.attname))
            update_fields = update_fields | self.METRIC_FIELDS
        else:
            self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return f"Workout for {self.user.nombre} on {self.fecha} - {self.exercise.nombre}"

    class Meta:
        verbose_name = _("Workout Data")
        verbose_name_plural = _("Workout Data")
