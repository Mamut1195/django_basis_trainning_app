"""Athletes persistence: observations."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from basis.adapters.django.persistence import Owned
from basis.modules.athletes.public import (
    InvalidAthleteData,
    WellnessData,
    validate_wellness,
)


class Measurement(Owned):
    date = models.DateField(default=timezone.localdate)
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(500)],
    )
    notes = models.CharField(max_length=300, blank=True)


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
