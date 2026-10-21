"""Athletes persistence: observations."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from basis.adapters.django.persistence import Owned
from basis.modules.athletes.public import (
    InvalidAthleteData,
    MeasurementData,
    WellnessData,
    validate_measurement,
    validate_wellness,
)


class Measurement(Owned):
    date = models.DateField(default=timezone.localdate, null=True, blank=True)
    origin = models.CharField(
        max_length=20,
        choices=[("measured", "Medición"), ("legacy_profile", "Perfil sin fecha")],
        default="measured",
    )
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("999.99"))],
    )
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        origin="measured",
                        date__isnull=False,
                        weight_kg__gte=Decimal("0.01"),
                        weight_kg__lte=500,
                    )
                    | Q(
                        origin="legacy_profile",
                        date__isnull=True,
                        weight_kg__gte=0,
                        weight_kg__lte=Decimal("999.99"),
                    )
                ),
                name="measurement_origin_date_weight",
            )
        ]

    def clean(self) -> None:
        # ModelForm still invokes clean() after field errors, with an unassigned
        # weight (None). Direct ORM validation may likewise retain a raw value.
        # Reject it explicitly: skipping it here would weaken model validation.
        if not isinstance(self.weight_kg, Decimal):
            raise ValidationError({"weight_kg": "Indica un peso decimal válido en kg."})
        if self.origin == "legacy_profile":
            if self.date is not None:
                raise ValidationError(
                    {"date": "El peso legado no tiene fecha de medición conocida."}
                )
            return
        if not isinstance(self.date, date):
            raise ValidationError({"date": "Indica una fecha de medición válida."})
        try:
            validate_measurement(
                MeasurementData(self.date, self.weight_kg, self.notes), timezone.localdate()
            )
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error


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

    def clean(self) -> None:
        try:
            validate_wellness(
                WellnessData(
                    self.date,
                    self.sleep_hours,
                    self.sleep_quality,
                    self.fatigue,
                    self.stress,
                    self.soreness,
                    self.readiness,
                    self.pain_regions,
                    self.pain_score,
                    self.resting_hr_bpm,
                    self.hrv_ms,
                    self.hrv_method,
                    self.notes,
                )
            )
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error
