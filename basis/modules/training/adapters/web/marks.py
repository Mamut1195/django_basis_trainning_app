"""Private, read-only strength mark history."""

from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from basis.adapters.web.framework import owner
from basis.bootstrap.marks import estimated_marks, exercise_choices, measured_marks
from basis.shared.identifiers import AccountId, ExerciseId


class MarkFilter(forms.Form):
    exercise = forms.ChoiceField(label="Ejercicio", required=False)
    start = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self) -> dict[str, object]:
        data = super().clean() or {}
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("La fecha inicial no puede superar la final.")
        return data


def page_number(raw: str | None) -> int:
    try:
        return int(raw or "1")
    except ValueError:
        return 1


@login_required
@require_safe
def strength_marks(request: HttpRequest) -> HttpResponse:
    form = MarkFilter(request.GET)
    cast(forms.ChoiceField, form.fields["exercise"]).choices = [
        ("", "Todos los ejercicios"),
        *[
            (str(id), name + (" (archivado)" if archived else ""))
            for id, name, archived in exercise_choices().all()
        ],
    ]
    if not form.is_valid():
        return render(
            request, "training/progress/marks.html", {"form": form, "valid": False}, status=400
        )
    account = AccountId(owner(request).pk)
    exercise = form.cleaned_data["exercise"]
    args = (
        account,
        ExerciseId(int(exercise)) if exercise else None,
        form.cleaned_data["start"],
        form.cleaned_data["end"],
    )
    measured = measured_marks().read(*args, page_number(request.GET.get("measured_page")))
    estimated = estimated_marks().read(*args, page_number(request.GET.get("estimated_page")))
    measured_params = request.GET.copy()
    measured_params.pop("measured_page", None)
    estimated_params = request.GET.copy()
    estimated_params.pop("estimated_page", None)
    return render(
        request,
        "training/progress/marks.html",
        {
            "form": form,
            "valid": True,
            "measured": measured,
            "estimated": estimated,
            "chart_exercise_selected": bool(exercise),
            "measured_max": max((row.kg for row in measured.rows), default=None),
            "estimated_max": max((row.kg for row in estimated.rows), default=None),
            "measured_query": measured_params.urlencode(),
            "estimated_query": estimated_params.urlencode(),
        },
    )
