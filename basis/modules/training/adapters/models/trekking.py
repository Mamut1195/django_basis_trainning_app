"""Training persistence: trekking."""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from basis.adapters.django.persistence import Owned, ValidatedModel
from basis.modules.training.public import (
    InvalidTrekking,
    StageNeighbour,
    validate_stage,
)
from basis.shared.identifiers import AccountId

from .execution import Session


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
