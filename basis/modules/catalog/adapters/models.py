from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import gettext_lazy as _

from basis.modules.catalog.public import valid_muscle_names
from basis.shared.text import normalized_name as normalize_text


class Classification(models.Model):
    nombre = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))

    def clean(self) -> None:
        """Normaliza y limpia el nombre antes de guardarlo."""
        self.nombre = normalize_text(self.nombre)

    def __str__(self) -> str:
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

    def clean(self) -> None:
        self.nombre = normalize_text(self.nombre)

        if not valid_muscle_names(self.musculos_principales):
            raise ValidationError({"musculos_principales": "Usa una lista de nombres musculares."})

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.full_clean()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return self.nombre

    class Meta:
        verbose_name = _("Exercise")
        verbose_name_plural = _("Exercises")
