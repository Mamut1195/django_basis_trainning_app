from __future__ import annotations

from typing import cast

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    UserExerciseRM,
    Wellness,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.public import InvalidAthleteData, require_adult


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
            "peso": "Peso legado sin fecha (kg, opcional)",
            "objetivos": "Objetivo personal (texto, gratuito)",
            "descripcion": "Sobre ti",
        }
        help_texts = {
            "peso": "Dato sin fecha: sus cambios conservan el valor anterior. Usa Registrar peso para mediciones fechadas.",
            "objetivos": "Describe tu objetivo personal. Los objetivos estructurados de un plan requieren acceso comercial; este texto es gratuito.",
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
    measured_on = forms.DateField(
        label="Fecha de medición (AAAA-MM-DD)",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        required=False,
    )

    class Meta:
        model = SportProfile
        exclude = ["owner"]
        labels = {
            "sport": "Disciplina",
            "experience": "Experiencia",
            "threshold": "Umbral declarado (opcional)",
            "threshold_unit": "Unidad",
            "measured_on": "Fecha de medición",
            "method": "Método",
            "threshold_kind": "Tipo de referencia (medido o estimado)",
            "threshold_source": "Fuente de la referencia",
        }
        widgets = {"measured_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def clean(self) -> dict[str, object]:
        data = super().clean() or {}
        sport = data.get("sport")
        existing = SportProfile.objects.filter(owner_id=self.instance.owner_id, sport=sport)
        if self.instance.pk is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if sport and existing.exists():
            self.add_error("sport", "Ya registraste esta disciplina. Edita la existente.")
        return data


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
    unit = forms.ChoiceField(
        label="Unidad canónica", choices=[("kg", "kg")], initial="kg", required=False
    )
    date = forms.DateField(
        label="Fecha de medición (AAAA-MM-DD)",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        initial=timezone.localdate,
    )

    class Meta:
        model = Measurement
        fields = ["date", "weight_kg", "notes"]
        labels = {"date": "Fecha", "weight_kg": "Peso medido (kg)", "notes": "Notas"}
        # Keep malformed input visible on the correction page. A number input
        # sanitizes values such as "abc" to an empty control in the browser.
        widgets = {"weight_kg": forms.TextInput(attrs={"inputmode": "decimal"})}
        help_texts = {
            "weight_kg": "Opcional en tu perfil. Para registrar una medición indica un peso mayor a cero en kg.",
            "notes": "Cada envío añade una observación; no reemplaza mediciones anteriores.",
        }


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
