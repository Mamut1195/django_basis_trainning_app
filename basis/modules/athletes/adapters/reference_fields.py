"""Compose athlete-owned reference selection into training input fields."""

from datetime import date

from django import forms
from django.db import models

from basis.modules.athletes.adapters.form_fields import DjangoRMChoices, restrict_reference_field
from basis.shared.identifiers import AccountId


def configure_rm_choices(
    field: forms.ModelChoiceField[models.Model],
    owner: int,
    through: date,
) -> None:
    restrict_reference_field(field, DjangoRMChoices(), AccountId(owner), through)
