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
    list_display = (
        "id",
        "nombre",
        "classification",
        "video",
        "nivel_fatiga",
        "equipo",
        "variante_de",
        "archivado",
    )
    list_select_related = ("classification", "variante_de")
    list_filter = ("classification", "nivel_fatiga", "archivado", "equipo", "patron_movimiento")
    search_fields = ("nombre", "descripcion", "variante")
    autocomplete_fields = ("variante_de",)
    ordering = ("nombre",)
