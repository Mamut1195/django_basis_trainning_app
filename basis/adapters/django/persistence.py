"""Shared Django model mechanics; business rules live in module contracts."""

from collections.abc import Iterable
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.base import ModelBase


class OwnedRelation(Protocol):
    @property
    def owner_id(self) -> int: ...


class ValidatedModel(models.Model):
    class Meta:
        abstract = True

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
        title = getattr(self, "title", None)
        return str(title or self.pk or "Nuevo")


class Owned(ValidatedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        abstract = True

    def same_owner(self, *relations: OwnedRelation | None) -> None:
        for relation in relations:
            if relation and relation.owner_id != self.owner_id:
                raise ValidationError("La relaci\u00f3n pertenece a otra cuenta.")
