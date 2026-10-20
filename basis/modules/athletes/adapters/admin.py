from __future__ import annotations

from datetime import timedelta

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.timezone import now

from .models import User, UserExerciseRM, WorkoutData


class WorkoutDataInline(admin.TabularInline[WorkoutData, User]):
    model = WorkoutData
    extra = 3  # Muestra hasta 3 filas vacías en el admin
    fields = (
        "fecha",
        "exercise",
        "sets",
        "reps",
        "total_reps",
        "peso",
        "carga",
        "intensidad_relativa",
        "volumen_relativo",
        "rpe_objetivo",
        "rpe_real",
        "rm_sesion",
        "get_nivel_fatiga",
    )
    readonly_fields = (
        "total_reps",
        "carga",
        "intensidad_relativa",
        "volumen_relativo",
        "rm_sesion",
        "get_nivel_fatiga",
    )  # Campos calculados en solo lectura
    ordering = ("-fecha",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[WorkoutData]:
        """Muestra solo los entrenamientos de los últimos 10 días"""
        qs = super().get_queryset(request)
        return qs.filter(fecha__gte=now() - timedelta(days=10)).order_by("-fecha")

    @admin.display(description="Fatigue Level")
    def get_nivel_fatiga(self, obj: WorkoutData) -> str:
        """Devuelve el nivel de fatiga desde el modelo Exercise"""
        return obj.exercise.nivel_fatiga if obj.exercise else "No asignado"


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    list_display = ("id", "nombre", "email", "fecha_inicio")
    search_fields = ("nombre", "email")
    ordering = ("fecha_inicio",)
    # Permite ver los entrenamientos dentro de cada usuario
    inlines = [WorkoutDataInline]


@admin.register(UserExerciseRM)
class UserExerciseRMAdmin(admin.ModelAdmin[UserExerciseRM]):
    """
    Admin para gestionar el historial de 1RM por usuario y ejercicio.
    """

    list_display = ("user", "exercise", "peso_maximo_rm", "fecha_registro")
    list_filter = ("user", "exercise", "fecha_registro")
    search_fields = ("user__nombre", "exercise__nombre")
    ordering = ("-fecha_registro",)  # Ordena del más reciente al más antiguo


@admin.register(WorkoutData)
class WorkoutDataAdmin(admin.ModelAdmin[WorkoutData]):
    list_display = (
        "id",
        "user",
        "exercise",
        "fecha",
        "sets",
        "reps",
        "total_reps",
        "peso",
        "intensidad_relativa",
        "carga",
        "volumen_relativo",
        "rpe_objetivo",
        "rpe_real",
        "rm_sesion",
        "get_nivel_fatiga",
    )
    list_filter = ("fecha", "user", "exercise", "exercise__nivel_fatiga")
    search_fields = ("user__nombre", "exercise__nombre")
    ordering = ("-fecha",)
    readonly_fields = (
        "total_reps",
        "carga",
        "intensidad_relativa",
        "volumen_relativo",
        "rm_sesion",
        "rm_referencia",
        "metrics_version",
    )

    @admin.display(description="Fatigue Level")
    def get_nivel_fatiga(self, obj: WorkoutData) -> str:
        """Devuelve el nivel de fatiga desde Exercise"""
        return obj.exercise.nivel_fatiga if obj.exercise else "No asignado"
