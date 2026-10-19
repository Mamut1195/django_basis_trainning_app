import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from basis.modules.athletes.public import (
    InvalidAthleteData,
    MeasuredRMData,
    MeasuredRMState,
    require_unchanged_rm,
)
from basis.modules.catalog.public import valid_muscle_names
from basis.modules.training.public import ReferenceContext, reference_is_frozen, reference_matches
from basis.shared.identifiers import AthleteId, ExerciseId
from basis.shared.text import normalized_name

from .strength_metrics import METRICS_VERSION, MetricsInputError, calculate_strength_metrics


def normalize_text(value):
    """Normaliza el texto eliminando espacios extra y caracteres especiales."""
    return normalized_name(value)


class Classification(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    def clean(self):
        """Normaliza y limpia el nombre antes de guardarlo."""
        self.nombre = normalize_text(self.nombre)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = _("Classification")
        verbose_name_plural = _("Classifications")


class Exercise(models.Model):
    patron_movimiento = models.CharField(max_length=100, blank=True)
    musculos_principales = models.JSONField(default=list, blank=True)
    equipo = models.CharField(max_length=300, blank=True)
    variante = models.CharField(max_length=150, blank=True)
    archivado = models.BooleanField(default=False)
    NIVEL_FATIGA_CHOICES = [
        ("Bajo", _("Low")),
        ("Medio", _("Medium")),
        ("Alto", _("High")),
    ]

    nombre = models.CharField(max_length=255, verbose_name=_("Name"))
    video = models.URLField(blank=True, null=True, verbose_name=_("Video"))
    descripcion = models.TextField(blank=True, verbose_name=_("Description"))
    classification = models.ForeignKey(
        Classification, on_delete=models.PROTECT, verbose_name=_("Classification")
    )
    nivel_fatiga = models.CharField(
        max_length=10,
        choices=NIVEL_FATIGA_CHOICES,
        default="Medio",
        verbose_name=_("Fatigue Level"),
    )

    def clean(self):
        self.nombre = normalize_text(self.nombre)
        from django.core.exceptions import ValidationError

        if not valid_muscle_names(self.musculos_principales):
            raise ValidationError({"musculos_principales": "Usa una lista de nombres musculares."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = _("Exercise")
        verbose_name_plural = _("Exercises")


class User(models.Model):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="athlete",
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email_verified = models.BooleanField(default=False)
    nombre = models.CharField(max_length=255, verbose_name=_("Nombre"))
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    fecha_inicio = models.DateField(verbose_name=_("Fecha de Inicio"))
    titulo = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Título"))
    pais = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("País"))
    ciudad = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Ciudad"))
    especialidad = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_("Especialidad")
    )
    edad = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)], verbose_name=_("Edad")
    )
    peso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Peso (kg)"),
    )
    objetivos = models.TextField(null=True, blank=True, verbose_name=_("Objetivos"))
    descripcion = models.TextField(null=True, blank=True, verbose_name=_("Descripción"))

    def clean(self):
        if self.nombre:
            self.nombre = normalize_text(self.nombre)
        if self.titulo:
            self.titulo = normalize_text(self.titulo)
        if self.pais:
            self.pais = normalize_text(self.pais)
        if self.ciudad:
            self.ciudad = normalize_text(self.ciudad)
        if self.especialidad:
            self.especialidad = normalize_text(self.especialidad)

    def __str__(self):
        return f"{self.nombre} ({self.email})"

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")


class UserExerciseRM(models.Model):
    """Registro histórico del 1RM de un usuario en un ejercicio"""

    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name=_("User"))
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, verbose_name=_("Exercise"))
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

    def __str__(self):
        return f"{self.user.nombre} - {self.exercise.nombre}: {self.peso_maximo_rm} kg ({self.fecha_registro})"

    def clean(self):
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
                            previous["peso_maximo_rm"], previous["fecha_registro"],
                        ),
                    ),
                    MeasuredRMState(
                        AthleteId(self.user_id),
                        MeasuredRMData(
                            ExerciseId(self.exercise_id), self.peso_maximo_rm, self.fecha_registro,
                        ),
                    ),
                )
            except InvalidAthleteData as error:
                raise ValidationError(str(error)) from error


    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
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
            kwargs["update_fields"] = update_fields
        else:
            self.full_clean()
        super().save(*args, **kwargs)

    @staticmethod
    def get_latest_rm(user, exercise, as_of=None):
        """Obtiene el 1RM más reciente para un usuario y ejercicio"""
        latest_rm = (
            UserExerciseRM.objects.filter(
                user=user,
                exercise=exercise,
                fecha_registro__lte=as_of or now().date(),
                peso_maximo_rm__gt=0,
            )
            .order_by("-fecha_registro", "-pk")
            .first()
        )
        return latest_rm.peso_maximo_rm if latest_rm else None

    @staticmethod
    def get_latest_rm_from_workouts(user, exercise, as_of=None):
        """Obtiene el 1RM estimado más reciente desde los entrenamientos en WorkoutData"""
        latest_workout = (
            WorkoutData.objects.filter(
                user=user, exercise=exercise, fecha__lte=as_of or now().date()
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
    exercise = models.ForeignKey("Exercise", on_delete=models.PROTECT, verbose_name=_("Exercise"))
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

    def _resolve_rm_reference(self):
        """Freeze even an absent reference once calculated for this context."""
        previous = (
            type(self)
            .objects.filter(pk=self.pk)
            .values("user_id", "exercise_id", "fecha", "rm_referencia_id", "metrics_version")
            .first()
            if self.pk
            else None
        )
        same_context = previous and all(
            previous[name] == getattr(self, name) for name in ("user_id", "exercise_id", "fecha")
        )
        if previous and reference_is_frozen(
            bool(same_context), previous["rm_referencia_id"], previous["metrics_version"]
        ):
            if self.rm_referencia_id not in (None, previous["rm_referencia_id"]):
                raise ValidationError({"rm_referencia": "La referencia histórica es estable."})
            self.rm_referencia_id = previous["rm_referencia_id"]
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
        if reference and not reference_matches(
            ReferenceContext(AthleteId(reference.user_id), ExerciseId(reference.exercise_id), reference.fecha_registro),
            ReferenceContext(AthleteId(self.user_id), ExerciseId(self.exercise_id), self.fecha),
        ):
            raise ValidationError({"rm_referencia": "Referencia RM ajena, incompatible o futura."})
        return reference

    def clean(self):
        """Shared rules for ModelForms, direct saves and API writes."""
        self.fecha = self._meta.get_field("fecha").clean(self.fecha, self)
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
        errors = []
        for name in ("total_reps", "carga", "intensidad_relativa", "volumen_relativo", "rm_sesion"):
            try:
                self._meta.get_field(name).clean(getattr(self, name), self)
            except ValidationError as exc:
                errors.extend(f"{name}: {message}" for message in exc.messages)
        if errors:
            # Derived fields are excluded from the real admin ModelForms.
            raise ValidationError({NON_FIELD_ERRORS: errors})

    def calcular_rm_sesion(self):
        return calculate_strength_metrics(
            sets=self.sets, reps=self.reps, weight_kg=self.peso, observed_rpe=self.rpe_real
        ).estimated_1rm_kg

    def calcular_rpe(self):
        return self.rpe_real

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
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
                field = self._meta.get_field(name)
                setattr(self, field.attname, getattr(candidate, field.attname))
            kwargs["update_fields"] = update_fields | self.METRIC_FIELDS
        else:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Workout for {self.user.nombre} on {self.fecha} - {self.exercise.nombre}"

    class Meta:
        verbose_name = _("Workout Data")
        verbose_name_plural = _("Workout Data")
