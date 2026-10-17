import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from daily_trainning_app.strength_metrics import calculate_strength_metrics

from .domain import SPORTS, internal_load, validate_metrics


class ValidatedModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return getattr(self, "title", None) or str(self.pk or "Nuevo")


class Owned(ValidatedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        abstract = True

    def same_owner(self, *relations):
        for relation in relations:
            if relation and relation.owner_id != self.owner_id:
                raise ValidationError("La relación pertenece a otra cuenta.")


class AthleteSettings(Owned):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="training_settings"
    )
    availability = models.JSONField(default=list, blank=True, help_text="Días ISO 1–7")
    minutes_per_session = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(5), MaxValueValidator(720)]
    )
    equipment = models.TextField(blank=True)
    limitations = models.TextField(blank=True)
    timezone_name = models.CharField(max_length=60, default="America/Guayaquil")

    def clean(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if (
            not isinstance(self.availability, list)
            or any(type(d) is not int or d not in range(1, 8) for d in self.availability)
            or len(set(self.availability)) != len(self.availability)
        ):
            raise ValidationError({"availability": "Usa días únicos de 1 a 7."})
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({"timezone_name": "Zona horaria desconocida."}) from None


class SportProfile(Owned):
    sport = models.CharField(max_length=20, choices=SPORTS)
    experience = models.CharField(
        max_length=20,
        choices=[("beginner", "Inicial"), ("intermediate", "Intermedio"), ("advanced", "Avanzado")],
        default="beginner",
    )
    threshold = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    threshold_unit = models.CharField(
        max_length=20,
        choices=[
            ("bpm", "lpm"),
            ("watts", "W"),
            ("seconds_km", "s/km"),
            ("seconds_100m", "s/100m"),
        ],
        blank=True,
    )
    measured_on = models.DateField(null=True, blank=True)
    method = models.CharField(max_length=150, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "sport"], name="sport_profile_owner_sport")
        ]

    def clean(self):
        if self.threshold is not None and (
            not self.threshold_unit or not self.measured_on or not self.method
        ):
            raise ValidationError("Un umbral requiere unidad, fecha y método.")
        allowed = {
            "strength": set(),
            "cardio": {"bpm"},
            "running": {"bpm", "seconds_km"},
            "cycling": {"bpm", "watts"},
            "swimming": {"bpm", "seconds_100m"},
            "hiking": {"bpm"},
        }
        if self.threshold_unit and self.threshold_unit not in allowed.get(self.sport, set()):
            raise ValidationError("Unidad de umbral incompatible con la disciplina.")


class Measurement(Owned):
    date = models.DateField(default=timezone.localdate)
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(500)],
    )
    notes = models.CharField(max_length=300, blank=True)


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

    def clean(self):
        if self.target_value is not None and not self.target_unit:
            raise ValidationError("Indica la unidad del objetivo.")
        if self.baseline_value is not None and (not self.baseline_date or not self.target_unit):
            raise ValidationError("La línea base necesita fecha y unidad.")


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

    def clean(self):
        if not self.goal_id or not self.start_date or not self.end_date:
            return
        self.same_owner(self.goal, self.previous)
        if self.end_date < self.start_date:
            raise ValidationError("El final debe ser posterior al inicio.")
        if self.previous and (
            self.previous.lineage != self.lineage or self.version != self.previous.version + 1
        ):
            raise ValidationError("La versión debe continuar el plan anterior.")


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

    def clean(self):
        if (
            not self.plan_id
            or not self.start_date
            or not self.end_date
            or self.kind not in ("macro", "meso", "micro")
        ):
            return
        if (
            self.end_date < self.start_date
            or self.start_date < self.plan.start_date
            or self.end_date > self.plan.end_date
        ):
            raise ValidationError("El ciclo debe estar dentro de las fechas del plan.")
        expected = {"meso": "macro", "micro": "meso"}
        if self.kind == "macro" and self.parent_id:
            raise ValidationError("Un macrociclo no tiene padre.")
        if self.kind != "macro" and (not self.parent_id or self.parent.kind != expected[self.kind]):
            raise ValidationError("Jerarquía requerida: macro → meso → micro.")
        if self.parent_id and (
            self.parent.plan_id != self.plan_id
            or self.start_date < self.parent.start_date
            or self.end_date > self.parent.end_date
        ):
            raise ValidationError("El ciclo debe estar dentro de su padre y plan.")


class PlannedSession(Owned):
    plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="sessions")
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    date = models.DateField(db_index=True)
    notes = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["owner", "date"])]

    def clean(self):
        if not self.plan_id or not self.cycle_id or not self.date:
            return
        self.same_owner(self.plan)
        if (
            self.cycle.plan_id != self.plan_id
            or self.cycle.kind != "micro"
            or not self.cycle.start_date <= self.date <= self.cycle.end_date
        ):
            raise ValidationError("La sesión debe pertenecer a un microciclo y sus fechas.")


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

    def clean(self):
        self.same_owner(self.planned)

    @property
    def load(self):
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

    def clean(self):
        if bool(self.planned_id) == bool(self.session_id):
            raise ValidationError("Un bloque pertenece a prescripción o ejecución.")
        self.target = validate_metrics(self.sport, self.target)
        self.actual = validate_metrics(self.sport, self.actual)
        if self.planned_id and self.actual:
            raise ValidationError("Una prescripción no contiene resultados reales.")

    @property
    def owner_id(self):
        return self.session.owner_id if self.session_id else self.planned.owner_id


class StrengthSet(ValidatedModel):
    block = models.ForeignKey(Block, on_delete=models.PROTECT, related_name="sets")
    exercise = models.ForeignKey("daily_trainning_app.Exercise", on_delete=models.PROTECT)
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
        "daily_trainning_app.UserExerciseRM", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        ordering = ["order", "pk"]

    def clean(self):
        if (self.target_reps_min is None) != (self.target_reps_max is None) or (
            self.target_reps_min is not None and self.target_reps_min > self.target_reps_max
        ):
            raise ValidationError("Indica un rango de repeticiones completo y ordenado.")
        if self.target_reps is not None and self.target_reps_min is not None:
            raise ValidationError("Usa repeticiones fijas o un rango, no ambos.")
        if self.target_percent_rm is not None and not self.rm_reference_id:
            raise ValidationError("El porcentaje RM requiere una referencia medida.")
        if self.block.sport != "strength":
            raise ValidationError("Las series de fuerza requieren un bloque de fuerza.")
        if self.block.planned_id and any(
            value is not None
            for value in (
                self.actual_kg,
                self.actual_reps,
                self.actual_rpe,
                self.actual_rir,
                self.actual_rest_seconds,
                self.isometric_seconds,
            )
        ):
            raise ValidationError("La prescripción no contiene resultados reales.")
        if self.rm_reference_id:
            parent = self.block.session if self.block.session_id else self.block.planned
            if (
                self.rm_reference.user.account_id != parent.owner_id
                or self.rm_reference.exercise_id != self.exercise_id
                or self.rm_reference.fecha_registro > parent.date
            ):
                raise ValidationError("Referencia RM ajena, incompatible o futura.")

    @property
    def external_volume_kg(self):
        if self.load_type != "external" or self.actual_kg is None or self.actual_reps is None:
            return None
        return calculate_strength_metrics(
            sets=1, reps=self.actual_reps, weight_kg=self.actual_kg
        ).load_kg_reps

    @property
    def estimated_1rm(self):
        if (
            self.load_type != "external"
            or self.kind != "work"
            or self.actual_rpe != 10
            or not self.actual_kg
            or not self.actual_reps
            or self.actual_reps > 10
        ):
            return None
        return calculate_strength_metrics(
            sets=1,
            reps=self.actual_reps,
            weight_kg=self.actual_kg,
            observed_rpe=self.actual_rpe,
        ).estimated_1rm_kg


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

    def clean(self):
        if self.block.sport == "strength":
            raise ValidationError("Usa series para fuerza.")
        self.target = validate_metrics(self.block.sport, self.target)
        self.actual = validate_metrics(self.block.sport, self.actual)
        if self.block.planned_id and (
            self.actual or self.actual_rpe is not None or self.actual_rest_seconds is not None
        ):
            raise ValidationError("La prescripción no contiene resultados reales.")


class Wellness(Owned):
    date = models.DateField(default=timezone.localdate)
    sleep_hours = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    sleep_quality = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    fatigue = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    stress = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    soreness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    readiness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    pain_regions = models.CharField(max_length=300, blank=True)
    pain_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10)]
    )
    resting_hr_bpm = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(20), MaxValueValidator(250)]
    )
    hrv_ms = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    hrv_method = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "date"], name="wellness_owner_date")
        ]

    def clean(self):
        if self.hrv_ms is not None and not self.hrv_method:
            raise ValidationError("Indica el método de medición HRV.")
        if self.pain_score is not None and self.pain_score > 0 and not self.pain_regions:
            raise ValidationError("Indica dónde sientes dolor.")


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

    def clean(self):
        if not self.trip_id or not self.session_id:
            return
        if self.trip.owner_id != self.session.owner_id:
            raise ValidationError("La etapa pertenece a otra cuenta.")
        if not self.session.blocks.filter(sport="hiking").exists():
            raise ValidationError("La etapa debe tener al menos un bloque de hiking.")
        neighbours = self.trip.stages.exclude(pk=self.pk).select_related("session")
        if any(
            (s.order < self.order and s.session.date > self.session.date)
            or (s.order > self.order and s.session.date < self.session.date)
            for s in neighbours
        ):
            raise ValidationError("Las fechas de etapas deben seguir su orden.")


class BillingAccount(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="billing"
    )
    polar_customer_id = models.CharField(max_length=100, null=True, unique=True, blank=True)
    subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, default="inactive")
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_used = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    needs_reconciliation = models.BooleanField(default=False)
    checkout_url = models.TextField(blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)

    @property
    def entitled(self):
        return (
            self.status in ("active", "trialing")
            and self.period_start is not None
            and self.period_end is not None
            and self.period_start <= timezone.now() < self.period_end
            and not self.needs_reconciliation
        )

    @property
    def status_label(self):
        return {
            "active": "Activa",
            "trialing": "Prueba activa",
            "inactive": "Sin acceso activo",
            "past_due": "Pago pendiente",
            "canceled": "Cancelada",
        }.get(self.status, "Pendiente de comprobar")


class WebhookReceipt(models.Model):
    event_id = models.CharField(max_length=200, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    customer_external_id = models.UUIDField(null=True)


class UsagePeriod(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    is_trial = models.BooleanField(default=False)
    spent = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    short_count = models.PositiveIntegerField(default=0)
    plan_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "key"], name="usage_owner_period")]


class TrialFund(models.Model):
    month = models.CharField(max_length=7, unique=True)
    spent = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    reserved = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    cap = models.DecimalField(max_digits=12, decimal_places=8, default=5)


class AIJob(Owned):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(default=uuid.uuid4)
    kind = models.CharField(
        max_length=10, choices=[("short", "Consulta breve"), ("plan", "Propuesta de plan")]
    )
    prompt = models.TextField()
    context = models.JSONField(default=dict)
    status = models.CharField(max_length=15, default="pending")
    usage_period = models.ForeignKey(UsagePeriod, on_delete=models.PROTECT)
    trial_fund = models.ForeignKey(TrialFund, null=True, blank=True, on_delete=models.PROTECT)
    reservation = models.DecimalField(max_digits=12, decimal_places=8)
    cost = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    requested_model = models.CharField(max_length=100)
    base_plan = models.ForeignKey("TrainingPlan", on_delete=models.PROTECT, null=True, blank=True)
    reported_model = models.CharField(max_length=100, blank=True)
    pricing_version = models.CharField(max_length=30, default="flash-peak-2026-10-17")
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    cache_hit_tokens = models.PositiveIntegerField(null=True, blank=True)
    answer = models.TextField(blank=True)
    error = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["owner", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["owner", "request_key"], name="ai_request_idempotent")
        ]


class PlanProposal(Owned):
    job = models.OneToOneField(AIJob, on_delete=models.PROTECT)
    base_plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, null=True, blank=True)
    content = models.JSONField()
    status = models.CharField(max_length=12, default="pending")
    accepted_plan = models.OneToOneField(
        TrainingPlan, on_delete=models.PROTECT, null=True, blank=True, related_name="proposal"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        self.same_owner(self.job, self.base_plan, self.accepted_plan)


class AIServiceState(models.Model):
    key = models.CharField(max_length=20, primary_key=True, default="deepseek")
    blocked = models.BooleanField(default=False)
    reason = models.CharField(max_length=150, blank=True)


class SyncReceipt(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mutation_id = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "mutation_id"], name="sync_owner_mutation")
        ]


class RateWindow(models.Model):
    key = models.CharField(max_length=100, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
