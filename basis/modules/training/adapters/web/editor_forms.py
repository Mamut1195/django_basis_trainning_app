"""Scoped editor inputs; writes are performed by application commands."""

from collections.abc import Mapping
from typing import cast

from django import forms

from basis.modules.training.adapters.models import Cycle, Goal, TrainingPlan

from .forms import CycleForm, PlanChangeForm, PlannedSessionForm


class PlanEditForm(PlanChangeForm):
    title = forms.CharField(label="Nombre del plan", max_length=160)
    start_date = forms.DateField(
        label="Inicio", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    end_date = forms.DateField(
        label="Final", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    notes = forms.CharField(label="Notas", required=False, widget=forms.Textarea)


class TemplateForm(PlanChangeForm):
    source = forms.ModelChoiceField(
        label="Plan propio como plantilla", queryset=TrainingPlan.objects.none()
    )
    goal = forms.ModelChoiceField(label="Objetivo", queryset=Goal.objects.none())
    title = forms.CharField(label="Nombre del nuevo plan", max_length=160)
    start_date = forms.DateField(
        label="Nuevo inicio", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )

    def __init__(self, data: Mapping[str, object] | None, *, owner: int) -> None:
        super().__init__(data)
        cast(
            forms.ModelChoiceField[TrainingPlan], self.fields["source"]
        ).queryset = TrainingPlan.objects.filter(owner_id=owner)
        cast(forms.ModelChoiceField[Goal], self.fields["goal"]).queryset = Goal.objects.filter(
            owner_id=owner
        )


class CycleEditForm(CycleForm):
    reason = forms.CharField(label="Motivo del cambio", max_length=1000, widget=forms.Textarea)


class ScheduledEditForm(PlanChangeForm):
    title = forms.CharField(label="Nombre de sesión", max_length=160)
    notes = forms.CharField(label="Notas", required=False, widget=forms.Textarea)
    revision = forms.IntegerField(widget=forms.HiddenInput)


class ScopedSessionForm(PlannedSessionForm):
    def __init__(self, data: Mapping[str, object] | None, *, plan: TrainingPlan) -> None:
        super().__init__(data, owner=plan.owner)
        cast(
            forms.ModelChoiceField[TrainingPlan], self.fields["plan"]
        ).queryset = TrainingPlan.objects.filter(pk=plan.pk)
        self.fields["plan"].initial = plan.pk
        cast(forms.ModelChoiceField[Cycle], self.fields["cycle"]).queryset = plan.cycles.filter(
            kind="micro"
        )
