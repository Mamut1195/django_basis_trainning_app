from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
import re


def normalize_text(value):
    """ Normaliza el texto eliminando espacios extra y caracteres especiales. """
    return re.sub(r'\s+', ' ', value).strip().title()


class Classification(models.Model):
    nombre = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Name")
    )

    def clean(self):
        """ Normaliza y limpia el nombre antes de guardarlo. """
        self.nombre = normalize_text(self.nombre)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = _("Classification")
        verbose_name_plural = _("Classifications")


class Exercise(models.Model):
    NIVEL_FATIGA_CHOICES = [
        ('Bajo', _("Low")),
        ('Medio', _("Medium")),
        ('Alto', _("High")),
    ]

    nombre = models.CharField(max_length=255, verbose_name=_("Name"))
    video = models.URLField(blank=True, null=True, verbose_name=_("Video"))
    descripcion = models.TextField(blank=True, verbose_name=_("Description"))
    classification = models.ForeignKey(
        Classification,
        on_delete=models.CASCADE,
        verbose_name=_("Classification"))
    nivel_fatiga = models.CharField(
        max_length=10,
        choices=NIVEL_FATIGA_CHOICES,
        default='Medio',
        verbose_name=_("Fatigue Level")
    )

    def clean(self):
        self.nombre = normalize_text(self.nombre)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = _("Exercise")
        verbose_name_plural = _("Exercises")


class User(models.Model):
    nombre = models.CharField(max_length=255, verbose_name=_("Name"))
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    fecha_inicio = models.DateField(verbose_name=_("Start Date"))

    def clean(self):
        self.nombre = normalize_text(self.nombre)

    def __str__(self):
        return f"{self.nombre} ({self.email})"

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")


class UserExerciseRM(models.Model):
    """ Registro histórico del 1RM de un usuario en un ejercicio """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("User"))
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        verbose_name=_("Exercise"))
    peso_maximo_rm = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Max Lift (1RM)"),
        help_text=_("Peso máximo levantado en una repetición máxima para este ejercicio.")
    )
    fecha_registro = models.DateField(
        default=now, verbose_name=_("Date Recorded"))

    class Meta:
        verbose_name = _("User Exercise 1RM")
        verbose_name_plural = _("User Exercise 1RMs")
        # Ordenamos del más reciente al más antiguo
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.user.nombre} - {self.exercise.nombre}: {self.peso_maximo_rm} kg ({self.fecha_registro})"

    @staticmethod
    def get_latest_rm(user, exercise):
        """ Obtiene el 1RM más reciente para un usuario y ejercicio """
        latest_rm = UserExerciseRM.objects.filter(
            user=user, exercise=exercise).order_by('-fecha_registro').first()
        return latest_rm.peso_maximo_rm if latest_rm else 0

    @staticmethod
    def get_latest_rm_from_workouts(user, exercise):
        """ Obtiene el 1RM estimado más reciente desde los entrenamientos en WorkoutData """
        latest_workout = WorkoutData.objects.filter(
            user=user, exercise=exercise).order_by('-fecha').first()

        if not latest_workout:
            return 0  # Si no hay entrenamientos, devolvemos 0

        # Usamos la mejor fórmula para calcular el 1RM desde el último
        # entrenamiento
        return latest_workout.calcular_rm_sesion()


class WorkoutData(models.Model):
    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        verbose_name=_("User"))
    exercise = models.ForeignKey(
        "Exercise",
        on_delete=models.CASCADE,
        verbose_name=_("Exercise"))
    fecha = models.DateField(verbose_name=_("Date"))
    sets = models.PositiveIntegerField(default=0, verbose_name=_("Sets"))
    reps = models.PositiveIntegerField(default=0, verbose_name=_("Reps"))
    total_reps = models.PositiveIntegerField(
        default=0, verbose_name=_("Total Reps"))
    peso = models.PositiveIntegerField(
        default=0, verbose_name=_("Weight (kg)"))
    intensidad_relativa = models.FloatField(
        default=0.0, verbose_name=_("Relative Intensity (%)"))
    carga = models.PositiveIntegerField(default=0, verbose_name=_("Load (kg)"))
    volumen_relativo = models.FloatField(
        default=0.0, verbose_name=_("Relative Volume"))
    rpe_objetivo = models.FloatField(default=0.0, verbose_name=_("Target RPE"))
    rm_sesion = models.FloatField(default=0.0,
                                  verbose_name=_("Estimated 1RM (Session)"))

    def clean(self):
        """ Ajusta cálculos automáticos antes de guardar """
        if self.reps and self.sets:
            self.total_reps = self.reps * self.sets

        user_rm = UserExerciseRM.objects.filter(
            user=self.user, exercise=self.exercise).first()
        if user_rm and user_rm.peso_maximo_rm:
            self.intensidad_relativa = round(
                (self.peso / user_rm.peso_maximo_rm) * 100, 2)
        else:
            self.intensidad_relativa = 0.0

        if self.peso and self.total_reps:
            self.carga = self.total_reps * self.peso

        if self.total_reps and self.intensidad_relativa:
            self.volumen_relativo = round(
                self.total_reps * (self.intensidad_relativa), 2)

        self.rpe_objetivo = self.calcular_rpe()
        self.rm_sesion = self.calcular_rm_sesion()

    def calcular_rm_sesion(self):
        """ Calcula el 1RM estimado usando reps, RPE, carga y un factor de ajuste basado en el ejercicio """
        if self.peso == 0 or self.reps == 0 or self.rpe_objetivo < 5:
            return 0.0  # Si no hay datos suficientes, devolvemos 0

        # Definir factores de ajuste según el nivel de fatiga del ejercicio
        factores_ajuste = {"Bajo": 0.022, "Medio": 0.028, "Alto": 0.033}
        factor_ajuste = factores_ajuste.get(
            self.exercise.nivel_fatiga, 0.028)  # Default: Medio

        # Aplicar la fórmula
        rm_estimado = ((self.reps + 10 - self.rpe_objetivo) *
                       self.peso * factor_ajuste) + self.peso

        return round(rm_estimado, 2)  # Redondeamos a 2 decimales

    def calcular_rpe(self):
        """ Calcula el RPE basado en %1RM, repeticiones realizadas y ajuste por fatiga. """
        if self.peso == 0 or self.reps == 0:
            return 0.0

        user_rm = UserExerciseRM.objects.filter(
            user=self.user, exercise=self.exercise).first()
        if not user_rm or user_rm.peso_maximo_rm == 0:
            return 0.0

        porcentaje_rm = (self.peso / user_rm.peso_maximo_rm) * 100

        rir_porcentaje_rm = {
            100: 0,
            95: 1,
            90: 2,
            85: 3,
            80: 4,
            75: 5,
            70: 6,
            65: 7,
            60: 8}
        intensidad = min(
            rir_porcentaje_rm.keys(),
            key=lambda x: abs(
                x - porcentaje_rm))
        reps_en_reserva = rir_porcentaje_rm[intensidad]

        ajuste_fatiga = {"Bajo": 0, "Medio": 0.5, "Alto": 1}
        fatiga = ajuste_fatiga.get(self.exercise.nivel_fatiga, 1.0)

        rpe_estimado = round(10 - reps_en_reserva + fatiga, 2)

        return max(5, min(10, rpe_estimado))

    def __str__(self):
        return f"Workout for {self.user.nombre} on {self.fecha} - {self.exercise.nombre}"

    class Meta:
        verbose_name = _("Workout Data")
        verbose_name_plural = _("Workout Data")
