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
    date = forms.DateField(
        label="Fecha (AAAA-MM-DD)",
        input_formats=["%Y-%m-%d"],
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        error_messages={"invalid": "Indica una fecha válida en formato AAAA-MM-DD."},
    )

    class Meta:
        model = Wellness
        exclude = ["owner"]
        labels = {
            "date": "Fecha",
            "moment": "Momento del check-in",
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
        help_texts = {
            "moment": "General del día, antes o después de entrenar. Los demás datos son opcionales.",
            "sleep_hours": "Horas de sueño (h), entre 0 y 24. Puedes dejarlo vacío.",
            "sleep_quality": "1 = muy mala; 5 = muy buena.",
            "fatigue": "1 = nada cansado; 5 = muy cansado.",
            "stress": "1 = nada de estrés; 5 = mucho estrés.",
            "soreness": "1 = nada de dolor muscular; 5 = mucho dolor muscular.",
            "readiness": "1 = sin ganas; 5 = con muchas ganas.",
            "pain_regions": "Si el dolor es mayor que 0, indica la zona.",
            "pain_score": (
                "0 = sin dolor; 10 = máximo dolor percibido. Escala 0–10. "
                "Si el dolor es mayor que 0, indica la zona."
            ),
            "resting_hr_bpm": "Latidos por minuto (lpm), entre 20 y 250; dato opcional.",
            "hrv_ms": "Milisegundos (ms); dato opcional. Si indicas HRV, indica también el método.",
            "hrv_method": "Cómo obtuviste el dato de HRV. Si indicas HRV, indica también el método.",
        }

    def clean(self) -> dict[str, object]:
        data = super().clean() or {}
        day, moment = data.get("date"), data.get("moment")
        if day and moment:
            existing = Wellness.objects.filter(
                owner_id=self.instance.owner_id, date=day, moment=moment
            )
            if self.instance.pk is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                self.add_error(
                    None,
                    "Ya registraste un check-in para esa fecha y momento. Edita el existente.",
                )
        return data


class WellnessRangeForm(forms.Form):
    start = forms.DateField(
        label="Desde (AAAA-MM-DD)",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        error_messages={"invalid": "Indica una fecha inicial válida (AAAA-MM-DD)."},
    )
    end = forms.DateField(
        label="Hasta (AAAA-MM-DD)",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        error_messages={"invalid": "Indica una fecha final válida (AAAA-MM-DD)."},
    )

    def clean(self) -> dict[str, object]:
        data = super().clean() or {}
        start, end = self.cleaned_data.get("start"), self.cleaned_data.get("end")
        if start and end and start > end:
            raise ValidationError("La fecha inicial no puede ser posterior a la final.")
        return data


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
