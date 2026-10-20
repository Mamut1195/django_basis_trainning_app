"""Native catalog admin entry hooks use explicit application workflows."""

from typing import TypeVar

from django import forms
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from basis.adapters.web.framework import owner
from basis.modules.catalog.adapters.administration_actions import (
    delete_admin_classifications,
    delete_admin_exercises,
    save_admin_classification,
    save_admin_exercise,
)

from .models import Classification, Exercise

CatalogT = TypeVar("CatalogT", Classification, Exercise)


class CatalogAdministrativeAdmin(admin.ModelAdmin[CatalogT]):
    def save_model(
        self, request: HttpRequest, obj: CatalogT, form: forms.ModelForm[CatalogT], change: bool
    ) -> None:
        if isinstance(obj, Classification):
            save_admin_classification(owner(request).pk, obj, change)
        else:
            save_admin_exercise(owner(request).pk, obj, change)

    def delete_model(self, request: HttpRequest, obj: CatalogT) -> None:
        if isinstance(obj, Classification):
            delete_admin_classifications(owner(request).pk, (obj.pk,))
        else:
            delete_admin_exercises(owner(request).pk, (obj.pk,))

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[CatalogT]) -> None:
        ids = tuple(queryset.values_list("pk", flat=True))
        if self.model is Classification:
            delete_admin_classifications(owner(request).pk, ids)
        else:
            delete_admin_exercises(owner(request).pk, ids)
