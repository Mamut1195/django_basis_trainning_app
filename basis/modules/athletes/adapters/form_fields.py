"""Athlete-owned measured-reference selection and Django field construction."""

from datetime import date

from django import forms
from django.db import models

from basis.modules.athletes.public import RMChoices
from basis.shared.identifiers import AccountId, MeasuredRMId

from .models import UserExerciseRM


class DjangoRMChoices:
    def eligible(self, owner: AccountId, through: date) -> tuple[MeasuredRMId, ...]:
        return tuple(
            MeasuredRMId(value)
            for value in UserExerciseRM.objects.filter(
                user__account_id=owner,
                fecha_registro__lte=through,
            ).values_list("pk", flat=True)
        )


def restrict_reference_field(
    field: forms.ModelChoiceField[models.Model],
    choices: RMChoices,
    owner: AccountId,
    through: date,
) -> None:
    assert field.queryset is not None
    field.queryset = UserExerciseRM.objects.filter(pk__in=choices.eligible(owner, through))
