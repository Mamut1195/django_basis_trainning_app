"""Athletes persistence: profile."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from basis.adapters.django.persistence import Owned, ValidatedModel
from basis.modules.athletes.public import (
    InvalidAthleteData,
    SportData,
    valid_availability,
    validate_observation_date,
    validate_sport,
)
from basis.modules.training.public import (
    SPORTS,
)
from basis.shared.text import normalized_name as normalize_text


class User(ValidatedModel):
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

    def clean(self) -> None:
        if self.nombre:
            self.nombre = normalize_text(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Indica un nombre."})
        if self.titulo:
            self.titulo = normalize_text(self.titulo)
        if self.pais:
            self.pais = normalize_text(self.pais)
        if self.ciudad:
            self.ciudad = normalize_text(self.ciudad)
        if self.especialidad:
            self.especialidad = normalize_text(self.especialidad)

    def __str__(self) -> str:
        return f"{self.nombre} ({self.email})"

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")


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

    def clean(self) -> None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if not valid_availability(self.availability):
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

    def clean(self) -> None:
        try:
            validate_sport(
                SportData(
                    self.sport,
                    self.experience,
                    self.threshold,
                    self.threshold_unit,
                    self.measured_on,
                    self.method,
                )
            )
            if self.measured_on is not None:
                validate_observation_date(self.measured_on, timezone.localdate())
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error
