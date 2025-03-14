from django.contrib import admin
from django.utils.timezone import now
from datetime import timedelta
from .models import Classification, Exercise, User, UserExerciseRM, WorkoutData


admin.site.site_header = "Training APP Panel"
admin.site.site_title = "BASIS TRAINING SYSTEM"
admin.site.index_title = "BASIS TRAINING SYSTEM"


class WorkoutDataInline(admin.TabularInline):
    model = WorkoutData
    extra = 3  # Muestra hasta 3 filas vacías en el admin
    fields = (
        'fecha',
        'exercise',
        'sets',
        'reps',
        'total_reps',
        'peso',
        'carga',
        'intensidad_relativa',
        'volumen_relativo',
        'rpe_objetivo',
        'rm_sesion',
        'get_nivel_fatiga')
    readonly_fields = (
        'total_reps',
        'carga',
        'intensidad_relativa',
        'volumen_relativo',
        'rpe_objetivo',
        'rm_sesion',
        'get_nivel_fatiga')  # Campos calculados en solo lectura
    ordering = ('-fecha',)

    def get_queryset(self, request):
        """ Muestra solo los entrenamientos de los últimos 10 días """
        qs = super().get_queryset(request)
        return qs.filter(
            fecha__gte=now() -
            timedelta(
                days=10)).order_by('-fecha')

    def get_nivel_fatiga(self, obj):
        """ Devuelve el nivel de fatiga desde el modelo Exercise """
        return obj.exercise.nivel_fatiga if obj.exercise else "No asignado"
    get_nivel_fatiga.short_description = "Fatigue Level"


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)
    ordering = ('nombre',)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'classification', 'video', 'nivel_fatiga')
    list_filter = ('classification', 'nivel_fatiga')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'email', 'fecha_inicio')
    search_fields = ('nombre', 'email')
    ordering = ('fecha_inicio',)
    # Permite ver los entrenamientos dentro de cada usuario
    inlines = [WorkoutDataInline]


@admin.register(UserExerciseRM)
class UserExerciseRMAdmin(admin.ModelAdmin):
    """
    Admin para gestionar el historial de 1RM por usuario y ejercicio.
    """
    list_display = ('user', 'exercise', 'peso_maximo_rm', 'fecha_registro')
    list_filter = ('user', 'exercise', 'fecha_registro')
    search_fields = ('user__nombre', 'exercise__nombre')
    ordering = ('-fecha_registro',)  # Ordena del más reciente al más antiguo


@admin.register(WorkoutData)
class WorkoutDataAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'exercise',
        'fecha',
        'sets',
        'reps',
        'total_reps',
        'peso',
        'intensidad_relativa',
        'carga',
        'volumen_relativo',
        'rpe_objetivo',
        'rm_sesion',
        'get_nivel_fatiga')
    list_filter = ('fecha', 'user', 'exercise', 'exercise__nivel_fatiga')
    search_fields = ('user__nombre', 'exercise__nombre')
    ordering = ('-fecha',)
    readonly_fields = (
        'total_reps',
        'carga',
        'intensidad_relativa',
        'volumen_relativo',
        'rpe_objetivo',
        'rm_sesion')

    def get_nivel_fatiga(self, obj):
        """ Devuelve el nivel de fatiga desde Exercise """
        return obj.exercise.nivel_fatiga if obj.exercise else "No asignado"
    get_nivel_fatiga.short_description = "Fatigue Level"
