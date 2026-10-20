from __future__ import annotations

from django.contrib import admin

from .admin_actions import CatalogAdministrativeAdmin
from .models import Classification, Exercise


@admin.register(Classification)
class ClassificationAdmin(CatalogAdministrativeAdmin[Classification]):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(Exercise)
class ExerciseAdmin(CatalogAdministrativeAdmin[Exercise]):
    list_display = ("id", "nombre", "classification", "video", "nivel_fatiga")
    list_filter = ("classification", "nivel_fatiga")
    search_fields = ("nombre", "descripcion")
    ordering = ("nombre",)
