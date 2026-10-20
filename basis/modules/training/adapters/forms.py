from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar, cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Model

from basis.modules.training.public import SPORTS, VARIABLES

from .models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)


class GoalForm(forms.ModelForm[Goal]):
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


OwnedT = TypeVar("OwnedT", bound=TrainingPlan | PlannedSession)


class OwnerForm(forms.ModelForm[OwnedT]):
    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        owner: AbstractBaseUser,
        instance: OwnedT | None = None,
    ) -> None:
        super().__init__(data=data, instance=instance)
        self.instance.owner_id = owner.pk
        for field, model in (("goal", Goal), ("plan", TrainingPlan)):
            if field in self.fields:
                cast(
                    forms.ModelChoiceField[Model], self.fields[field]
                ).queryset = model.objects.filter(owner_id=owner.pk)
        if "cycle" in self.fields:
            cast(
                forms.ModelChoiceField[Cycle], self.fields["cycle"]
            ).queryset = Cycle.objects.filter(plan__owner_id=owner.pk, kind="micro")


class PlanForm(OwnerForm[TrainingPlan]):
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


class CycleForm(forms.ModelForm[Cycle]):
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

    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        plan: TrainingPlan,
        instance: Cycle | None = None,
    ) -> None:
        super().__init__(data=data, instance=instance)
        self.instance.plan = plan
        cast(forms.ModelChoiceField[Cycle], self.fields["parent"]).queryset = plan.cycles.all()


class PlannedSessionForm(OwnerForm[PlannedSession]):
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


class SessionForm(forms.ModelForm[Session]):
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
    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        sport: str,
        initial: Mapping[str, object] | None = None,
        prefix: str | None = None,
    ) -> None:
        super().__init__(
            data=data, initial=dict(initial) if initial is not None else None, prefix=prefix
        )
        for key, spec in VARIABLES[sport].items():
            label = spec.label + (" (" + spec.unit + ")" if spec.unit else "")
            if spec.kind == "text":
                field: forms.Field = forms.CharField(label=label, required=False, max_length=500)
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

    def clean(self) -> dict[str, object]:
        from basis.modules.training.adapters.metrics import validate_metrics

        return dict(validate_metrics(self.sport, super().clean()))


class StrengthSetForm(forms.ModelForm[StrengthSet]):
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

    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        block: Block,
        instance: StrengthSet | None = None,
    ) -> None:
        super().__init__(data=data, instance=instance)
        self.instance.block = block
        parent = block.session if block.session_id else block.planned
        assert parent is not None
        rm_field = cast(forms.ModelChoiceField[Model], self.fields["rm_reference"])
        assert rm_field.queryset is not None
        rm_field.queryset = rm_field.queryset.filter(
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


class IntervalForm(forms.ModelForm[Interval]):
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

    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        block: Block,
        instance: Interval | None = None,
    ) -> None:
        super().__init__(data=data, instance=instance)
        self.instance.block = block
        if block.planned_id:
            self.fields.pop("actual_rest_seconds")
            self.fields.pop("actual_rpe")


class TrekTripForm(forms.ModelForm[TrekTrip]):
    class Meta:
        model = TrekTrip
        fields = ["title", "notes"]
        labels = {"title": "Nombre del trekking", "notes": "Notas"}


class TrekStageForm(forms.ModelForm[TrekStage]):
    class Meta:
        model = TrekStage
        exclude = ["trip"]
        labels = {
            "session": "Sesión de hiking",
            "order": "Número de etapa",
            "overnight_altitude_m": "Altitud de pernocta (m)",
            "recovery_notes": "Recuperación entre jornadas",
        }

    def __init__(
        self,
        data: Mapping[str, object] | None = None,
        *,
        trip: TrekTrip,
        instance: TrekStage | None = None,
    ) -> None:
        super().__init__(data=data, instance=instance)
        self.instance.trip = trip
        cast(
            forms.ModelChoiceField[Session], self.fields["session"]
        ).queryset = Session.objects.filter(
            owner=trip.owner, blocks__sport="hiking", trek_stage__isnull=True
        ).distinct()
