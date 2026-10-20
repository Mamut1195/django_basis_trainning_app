from __future__ import annotations

from django.contrib import admin

from .models import Classification, Exercise


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin[Classification]):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin[Exercise]):
    list_display = ("id", "nombre", "classification", "video", "nivel_fatiga")
    list_filter = ("classification", "nivel_fatiga")
    search_fields = ("nombre", "descripcion")
    ordering = ("nombre",)
