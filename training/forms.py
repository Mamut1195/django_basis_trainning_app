from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from basis.bootstrap.accounts import identity
from basis.modules.athletes.public import InvalidAthleteData, require_adult
from daily_trainning_app.models import User as Athlete
from daily_trainning_app.models import UserExerciseRM

from .domain import SPORTS, VARIABLES
from .models import (
    AthleteSettings,
    Cycle,
    Goal,
    Interval,
    Measurement,
    PlannedSession,
    Session,
    SportProfile,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
    Wellness,
)


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico", max_length=150)
    name = forms.CharField(label="Nombre", max_length=100)
    adult = forms.BooleanField(label="Tengo 18 años o más")

    class Meta:
        model = get_user_model()
        fields = ["email", "name", "password1", "password2", "adult"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if identity().email_in_use(email):
            raise ValidationError(
                "Usa recuperación de acceso o contacta soporte si ya tienes un perfil."
            )
        return email


class AthleteForm(forms.ModelForm):
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

    def clean_edad(self):
        age = self.cleaned_data.get("edad")
        try:
            require_adult(age)
        except InvalidAthleteData as error:
            raise ValidationError(str(error)) from error
        return age


class PreferencesForm(forms.ModelForm):
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


class SportProfileForm(forms.ModelForm):
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


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        exclude = ["owner"]
        labels = {
            "priority": "Prioridad",
            "baseline_value": "Valor de referencia inicial",
            "baseline_date": "Fecha de referencia inicial",
            "title": "Objetivo",
            "sport": "Disciplina",
            "target_date": "Fecha objetivo",
            "description": "Descripción",
            "target_value": "Meta numérica (opcional)",
            "target_unit": "Unidad",
        }
        widgets = {
            key: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for key in ("target_date", "baseline_date")
        }


class OwnerForm(forms.ModelForm):
    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner
        for field, model in (("goal", Goal), ("plan", TrainingPlan)):
            if field in self.fields:
                self.fields[field].queryset = model.objects.filter(owner=owner)
        if "cycle" in self.fields:
            self.fields["cycle"].queryset = Cycle.objects.filter(plan__owner=owner, kind="micro")


class PlanForm(OwnerForm):
    class Meta:
        model = TrainingPlan
        fields = ["title", "goal", "start_date", "end_date", "notes"]
        labels = {
            "title": "Nombre del plan",
            "goal": "Objetivo",
            "start_date": "Inicio",
            "end_date": "Final",
            "notes": "Notas",
        }
        widgets = {
            key: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for key in ("start_date", "end_date")
        }


class CycleForm(forms.ModelForm):
    class Meta:
        model = Cycle
        exclude = ["plan"]
        labels = {
            "title": "Nombre del ciclo",
            "parent": "Ciclo padre",
            "kind": "Tipo",
            "start_date": "Inicio",
            "end_date": "Final",
            "focus": "Enfoque",
        }
        widgets = {
            key: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for key in ("start_date", "end_date")
        }

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.plan = plan
        self.fields["parent"].queryset = plan.cycles.all()


class PlannedSessionForm(OwnerForm):
    class Meta:
        model = PlannedSession
        exclude = ["owner", "revision"]
        labels = {
            "title": "Nombre de sesión",
            "date": "Fecha",
            "plan": "Plan",
            "cycle": "Microciclo",
            "notes": "Notas",
        }
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["title", "date", "duration_seconds", "duration_protocol", "reported_rpe", "notes"]
        labels = {
            "title": "Nombre de sesión",
            "date": "Fecha",
            "duration_seconds": "Duración (segundos)",
            "duration_protocol": "Protocolo de duración",
            "reported_rpe": "RPE real de la sesión (0–10, opcional)",
            "notes": "Notas",
        }
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class BlockForm(forms.Form):
    sport = forms.ChoiceField(label="Disciplina", choices=SPORTS)
    title = forms.CharField(label="Nombre del bloque", max_length=160)


class MetricsForm(forms.Form):
    def __init__(self, *args, sport, **kwargs):
        super().__init__(*args, **kwargs)
        for key, spec in VARIABLES[sport].items():
            label = spec.label + (" (" + spec.unit + ")" if spec.unit else "")
            if spec.kind == "text":
                field = forms.CharField(label=label, required=False, max_length=500)
            elif spec.kind == "choice":
                field = forms.ChoiceField(
                    label=label,
                    required=False,
                    choices=[("", "Sin registrar"), *[(v, v) for v in spec.choices]],
                )
            else:
                cls = forms.IntegerField if spec.kind == "integer" else forms.DecimalField
                field = cls(
                    label=label,
                    required=False,
                    min_value=-500 if spec.kind == "altitude" else 0,
                    max_value=spec.maximum,
                )
                field.widget.attrs["inputmode"] = "decimal"
            self.fields[key] = field
        self.sport = sport

    def clean(self):
        from .domain import validate_metrics

        return validate_metrics(self.sport, super().clean())


class StrengthSetForm(forms.ModelForm):
    class Meta:
        model = StrengthSet
        exclude = ["block", "order"]
        labels = {
            "exercise": "Ejercicio",
            "kind": "Tipo de serie",
            "load_type": "Tipo de carga",
            "target_reps": "Repeticiones objetivo",
            "target_reps_min": "Rango: repeticiones mínimas",
            "target_reps_max": "Rango: repeticiones máximas",
            "target_percent_rm": "Intensidad objetivo (% RM medido)",
            "actual_reps": "Repeticiones reales",
            "target_kg": "Carga objetivo (kg)",
            "actual_kg": "Carga real (kg)",
            "bodyweight_kg": "Peso corporal medido (kg)",
            "target_rpe": "RPE objetivo",
            "actual_rpe": "RPE real",
            "target_rir": "RIR objetivo",
            "actual_rir": "RIR real",
            "rest_seconds": "Descanso objetivo (s)",
            "actual_rest_seconds": "Descanso real (s)",
            "tempo": "Tempo",
            "range_of_motion": "Rango de movimiento",
            "side": "Lado",
            "isometric_seconds": "Isometría real (s)",
            "target_isometric_seconds": "Isometría objetivo (s)",
            "group": "Superserie / circuito",
            "rm_reference": "RM medido de referencia",
        }

    def __init__(self, *args, block, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.block = block
        parent = block.session if block.session_id else block.planned
        self.fields["rm_reference"].queryset = UserExerciseRM.objects.filter(
            user__account_id=parent.owner_id, fecha_registro__lte=parent.date
        )
        if block.planned_id:
            for key in (
                "actual_reps",
                "actual_kg",
                "actual_rpe",
                "actual_rir",
                "actual_rest_seconds",
                "isometric_seconds",
            ):
                self.fields.pop(key)


class IntervalForm(forms.ModelForm):
    class Meta:
        model = Interval
        fields = ["repetitions", "rest_seconds", "actual_rest_seconds", "target_rpe", "actual_rpe"]
        labels = {
            "repetitions": "Repeticiones",
            "rest_seconds": "Descanso objetivo (s)",
            "actual_rest_seconds": "Descanso real (s)",
            "target_rpe": "RPE objetivo",
            "actual_rpe": "RPE real",
        }

    def __init__(self, *args, block, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.block = block
        if block.planned_id:
            self.fields.pop("actual_rest_seconds")
            self.fields.pop("actual_rpe")


class WellnessForm(forms.ModelForm):
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


class MeasurementForm(forms.ModelForm):
    class Meta:
        model = Measurement
        exclude = ["owner"]
        labels = {"date": "Fecha", "weight_kg": "Peso medido (kg)", "notes": "Notas"}
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class TrekTripForm(forms.ModelForm):
    class Meta:
        model = TrekTrip
        fields = ["title", "notes"]
        labels = {"title": "Nombre del trekking", "notes": "Notas"}


class TrekStageForm(forms.ModelForm):
    class Meta:
        model = TrekStage
        exclude = ["trip"]
        labels = {
            "session": "Sesión de hiking",
            "order": "Número de etapa",
            "overnight_altitude_m": "Altitud de pernocta (m)",
            "recovery_notes": "Recuperación entre jornadas",
        }

    def __init__(self, *args, trip, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.trip = trip
        self.fields["session"].queryset = Session.objects.filter(
            owner=trip.owner, blocks__sport="hiking", trek_stage__isnull=True
        ).distinct()


class RMForm(forms.ModelForm):
    class Meta:
        model = UserExerciseRM
        fields = ["exercise", "peso_maximo_rm", "fecha_registro"]
        labels = {
            "exercise": "Ejercicio",
            "peso_maximo_rm": "1RM medido (kg)",
            "fecha_registro": "Fecha de medición",
        }
        widgets = {"fecha_registro": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}


class ProposalReviewForm(forms.Form):
    """Human-readable fields; the client cannot inject arbitrary JSON or foreign IDs."""

    def __init__(self, *args, content, owner, **kwargs):
        from copy import deepcopy

        super().__init__(*args, **kwargs)
        self.content = deepcopy(content)
        self.paths = {}
        self.groups = []
        current = []

        def add(path, field, value):
            name = "value_" + str(len(self.paths))
            self.paths[name] = path
            self.fields[name] = field
            self.initial[name] = value
            current.append(name)

        def group(title):
            nonlocal current
            current = []
            self.groups.append({"title": title, "names": current})

        group("Resumen del plan")
        add(
            ["title"],
            forms.CharField(label="Nombre del plan", max_length=160),
            content.get("title"),
        )
        add(
            ["goal_id"],
            forms.ModelChoiceField(label="Objetivo", queryset=Goal.objects.filter(owner=owner)),
            content.get("goal_id"),
        )
        for key, label in (("start_date", "Inicio del plan"), ("end_date", "Final del plan")):
            add(
                [key],
                forms.DateField(
                    label=label, widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
                ),
                content.get(key),
            )
        add(
            ["notes"],
            forms.CharField(label="Notas y enfoque", required=False, widget=forms.Textarea),
            content.get("notes", ""),
        )
        for index, cycle in enumerate(content.get("cycles", [])):
            group(
                {"macro": "Macrociclo", "meso": "Mesociclo", "micro": "Microciclo"}.get(
                    cycle["kind"], "Ciclo"
                )
                + ": "
                + cycle["title"]
            )
            for key, label in (
                ("title", "Nombre"),
                ("start_date", "Inicio"),
                ("end_date", "Final"),
                ("focus", "Enfoque"),
            ):
                field = (
                    forms.DateField(
                        label=label,
                        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                    )
                    if key.endswith("date")
                    else forms.CharField(
                        label=label,
                        required=key == "title",
                        max_length=2000 if key == "focus" else 160,
                    )
                )
                add(["cycles", index, key], field, cycle.get(key))
        for index, session in enumerate(content.get("sessions", [])):
            group("Sesión: " + session["title"])
            add(
                ["sessions", index, "title"],
                forms.CharField(label="Nombre", max_length=160),
                session["title"],
            )
            add(
                ["sessions", index, "date"],
                forms.DateField(
                    label="Fecha", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
                ),
                session["date"],
            )
            for number, block in enumerate(session.get("blocks", [])):
                group(session["title"] + " · " + block["title"])
                prefix = ["sessions", index, "blocks", number]
                for key, spec in VARIABLES[block["sport"]].items():
                    label = spec.label + (" (" + spec.unit + ")" if spec.unit else "")
                    field = (
                        forms.CharField(label=label, required=False, max_length=500)
                        if spec.kind in ("text", "choice")
                        else forms.DecimalField(
                            label=label,
                            required=False,
                            min_value=-500 if spec.kind == "altitude" else 0,
                            max_value=spec.maximum,
                        )
                    )
                    add(prefix + ["target", key], field, block.get("target", {}).get(key))
                for set_index, row in enumerate(block.get("sets", [])):
                    group(session["title"] + " · Serie " + str(set_index + 1))
                    for key, label in (
                        ("target_reps", "Repeticiones objetivo"),
                        ("target_reps_min", "Repeticiones mínimas"),
                        ("target_reps_max", "Repeticiones máximas"),
                        ("target_kg", "Carga objetivo (kg)"),
                        ("target_rpe", "RPE objetivo"),
                        ("target_rir", "RIR objetivo"),
                        ("rest_seconds", "Descanso (s)"),
                    ):
                        field = (
                            forms.IntegerField(label=label, required=False, min_value=0)
                            if key
                            in (
                                "target_reps",
                                "target_reps_min",
                                "target_reps_max",
                                "target_rir",
                                "rest_seconds",
                            )
                            else forms.DecimalField(label=label, required=False, min_value=0)
                        )
                        add(prefix + ["sets", set_index, key], field, row.get(key))
        for group in self.groups:
            group["fields"] = [self[name] for name in group["names"]]

    def to_content(self):
        from copy import deepcopy
        from datetime import date
        from decimal import Decimal

        content = deepcopy(self.content)
        for name, path in self.paths.items():
            value = self.cleaned_data[name]
            if isinstance(value, date):
                value = value.isoformat()
            if isinstance(value, Decimal):
                value = str(value)
            if isinstance(value, Goal):
                value = value.pk
            node = content
            for key in path[:-1]:
                if isinstance(node, dict) and key not in node:
                    node[key] = {}
                node = node[key]
            if "target" in path and value in (None, ""):
                node.pop(path[-1], None)
            else:
                node[path[-1]] = value
        return content
