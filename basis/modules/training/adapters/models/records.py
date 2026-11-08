"""Materialized personal marks, refreshed from completed sessions."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from basis.adapters.django.persistence import Owned


class PersonalRecord(Owned):
    class Kind(models.TextChoices):
        STRENGTH = "strength", "Fuerza"
        SPORT = "sport", "Deporte"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    context = models.CharField(max_length=160)
    label = models.CharField(max_length=160)
    metric = models.CharField(max_length=60)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    display = models.CharField(max_length=60)
    detail = models.CharField(max_length=255, blank=True)
    achieved_on = models.DateField(null=True, blank=True)
    session = models.ForeignKey(
        "Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_records",
    )
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "kind", "context", "metric"],
                name="personal_record_unique",
            )
        ]
        ordering = ["kind", "label", "metric"]
