"""Native Django admin hooks bind concrete typed administrative cases."""

from typing import TypeVar

from django import forms
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from basis.adapters.web.framework import owner
from basis.modules.athletes.adapters.administration_actions import (
    delete_admin_profiles,
    delete_admin_rms,
    delete_admin_workouts,
    save_admin_profile,
    save_admin_rm,
    save_admin_workout,
)

from .models import User, UserExerciseRM, WorkoutData

AdminT = TypeVar("AdminT", User, UserExerciseRM, WorkoutData)


class AthleteAdministrativeAdmin(admin.ModelAdmin[AdminT]):
    def save_model(
        self, request: HttpRequest, obj: AdminT, form: forms.ModelForm[AdminT], change: bool
    ) -> None:
        actor = owner(request).pk
        if isinstance(obj, User):
            save_admin_profile(actor, obj, change)
        elif isinstance(obj, UserExerciseRM):
            save_admin_rm(actor, obj, change)
        else:
            save_admin_workout(actor, obj, change)

    def delete_model(self, request: HttpRequest, obj: AdminT) -> None:
        actor = owner(request).pk
        if isinstance(obj, User):
            delete_admin_profiles(actor, (obj.pk,))
        elif isinstance(obj, UserExerciseRM):
            delete_admin_rms(actor, (obj.pk,))
        else:
            delete_admin_workouts(actor, (obj.pk,))

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[AdminT]) -> None:
        actor = owner(request).pk
        ids = tuple(queryset.values_list("pk", flat=True))
        if self.model is User:
            delete_admin_profiles(actor, ids)
        elif self.model is UserExerciseRM:
            delete_admin_rms(actor, ids)
        else:
            delete_admin_workouts(actor, ids)
