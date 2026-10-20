from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict, cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.forms.boundfield import BoundField

from basis.bootstrap.presentation import goal_choices
from basis.modules.training.public import VARIABLES


class FieldGroup(TypedDict):
    title: str
    names: list[str]
    fields: list[BoundField]


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Invalid plan object")
    return cast(dict[str, object], value)


def rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("Invalid plan rows")
    return [mapping(row) for row in value]


class ProposalReviewForm(forms.Form):
    """Human-readable fields; the client cannot inject arbitrary JSON or foreign IDs."""

    def __init__(
        self, data: Mapping[str, object] | None = None, *, content: object, owner: AbstractBaseUser
    ) -> None:
        from copy import deepcopy

        super().__init__(data=data)
        content = mapping(content)
        self.content = deepcopy(content)
        self.paths: dict[str, list[str | int]] = {}
        self.groups: list[FieldGroup] = []
        current: list[str] = []

        def add(path: list[str | int], field: forms.Field, value: object) -> None:
            name = "value_" + str(len(self.paths))
            self.paths[name] = path
            self.fields[name] = field
            self.initial[name] = value
            current.append(name)

        def group(title: str) -> None:
            nonlocal current
            current = []
            self.groups.append({"title": title, "names": current, "fields": []})

        group("Resumen del plan")
        add(
            ["title"],
            forms.CharField(label="Nombre del plan", max_length=160),
            content.get("title"),
        )
        add(
            ["goal_id"],
            forms.TypedChoiceField(
                label="Objetivo", choices=[("", "---------"), *goal_choices(owner.pk)], coerce=int
            ),
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
        for index, cycle in enumerate(rows(content.get("cycles", []))):
            group(
                {"macro": "Macrociclo", "meso": "Mesociclo", "micro": "Microciclo"}.get(
                    str(cycle["kind"]), "Ciclo"
                )
                + ": "
                + str(cycle["title"])
            )
            for key, label in (
                ("title", "Nombre"),
                ("start_date", "Inicio"),
                ("end_date", "Final"),
                ("focus", "Enfoque"),
            ):
                field: forms.Field = (
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
        for index, session in enumerate(rows(content.get("sessions", []))):
            group("Sesión: " + str(session["title"]))
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
            for number, block in enumerate(rows(session.get("blocks", []))):
                group(str(session["title"]) + " · " + str(block["title"]))
                prefix: list[str | int] = ["sessions", index, "blocks", number]
                for key, spec in VARIABLES[str(block["sport"])].items():
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
                    add(prefix + ["target", key], field, mapping(block.get("target", {})).get(key))
                for set_index, row in enumerate(rows(block.get("sets", []))):
                    group(str(session["title"]) + " · Serie " + str(set_index + 1))
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
        for item in self.groups:
            item["fields"] = [self[name] for name in item["names"]]

    def to_content(self) -> dict[str, object]:
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
            node: object = content
            for key in path[:-1]:
                if isinstance(node, dict):
                    node.setdefault(key, {})
                    node = cast(dict[str | int, object], node)[key]
                else:
                    node = cast(list[object], node)[int(key)]
            if isinstance(node, dict):
                target = cast(dict[str | int, object], node)
                if "target" in path and value in (None, ""):
                    target.pop(path[-1], None)
                else:
                    target[path[-1]] = value
            else:
                cast(list[object], node)[int(path[-1])] = value
        return content
