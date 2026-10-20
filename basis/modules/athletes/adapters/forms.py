from __future__ import annotations

from typing import cast

from django import forms
from django.core.exceptions import ValidationError

from basis.modules.athletes.public import InvalidAthleteData, require_adult

from .models import AthleteSettings, Measurement, SportProfile, UserExerciseRM, Wellness
from .models import User as Athlete


class AthleteForm(forms.ModelForm[Athlete]):
    class Meta:
        model = Athlete
        fields = [
            "nombre",
            "titulo",
            "pais",
            "ciudad",
            "especialidad",
            "edad",
            "peso",
            "objetivos",
            "descripcion",
        ]
        labels = {
            "nombre": "Nombre",
            "titulo": "Título",
            "pais": "País",
            "ciudad": "Ciudad",
            "especialidad": "Especialidad",
            "edad": "Edad",
            "peso": "Peso actual (kg)",
            "objetivos": "Objetivos",
            "descripcion": "Sobre ti",
        }

    def clean_edad(self) -> int | None:
        age = self.cleaned_data.get("edad")
        try:
            require_adult(age)
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error
        return cast(int | None, age)


class PreferencesForm(forms.ModelForm[AthleteSettings]):
    availability = forms.TypedMultipleChoiceField(
        label="Días disponibles",
        choices=[
            (1, "Lunes"),
            (2, "Martes"),
            (3, "Miércoles"),
            (4, "Jueves"),
            (5, "Viernes"),
            (6, "Sábado"),
            (7, "Domingo"),
        ],
        coerce=int,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = AthleteSettings
        fields = [
            "availability",
            "minutes_per_session",
            "equipment",
            "limitations",
            "timezone_name",
        ]
        labels = {
            "minutes_per_session": "Minutos disponibles por sesión",
            "equipment": "Equipo disponible",
            "limitations": "Limitaciones y preferencias",
            "timezone_name": "Zona horaria",
        }


class SportProfileForm(forms.ModelForm[SportProfile]):
    class Meta:
        model = SportProfile
        exclude = ["owner"]
        labels = {
            "sport": "Disciplina",
            "experience": "Experiencia",
            "threshold": "Umbral medido (opcional)",
            "threshold_unit": "Unidad",
            "measured_on": "Fecha de medición",
            "method": "Método",
        }
        widgets = {"measured_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class WellnessForm(forms.ModelForm[Wellness]):
    class Meta:
        model = Wellness
        exclude = ["owner"]
        labels = {
            "date": "Fecha",
            "sleep_hours": "Sueño (h)",
            "sleep_quality": "Calidad del sueño (1–5)",
            "fatigue": "Fatiga (1–5)",
            "stress": "Estrés (1–5)",
            "soreness": "Dolor muscular (1–5)",
            "readiness": "Disposición percibida (1–5)",
            "pain_regions": "Regiones con dolor",
            "pain_score": "Dolor (0–10)",
            "resting_hr_bpm": "FC reposo medida (lpm)",
            "hrv_ms": "HRV medida (ms)",
            "hrv_method": "Método HRV",
            "notes": "Notas",
        }
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class MeasurementForm(forms.ModelForm[Measurement]):
    class Meta:
        model = Measurement
        exclude = ["owner"]
        labels = {"date": "Fecha", "weight_kg": "Peso medido (kg)", "notes": "Notas"}
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class RMForm(forms.ModelForm[UserExerciseRM]):
    class Meta:
        model = UserExerciseRM
        fields = ["exercise", "peso_maximo_rm", "fecha_registro"]
        labels = {
            "exercise": "Ejercicio",
            "peso_maximo_rm": "1RM medido (kg)",
            "fecha_registro": "Fecha de medición",
        }
        widgets = {"fecha_registro": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}
