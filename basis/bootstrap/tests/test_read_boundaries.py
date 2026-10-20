"""Framework composition preserves catalog display and private RM selection."""

from datetime import timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import patch

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Model
from django.test import TestCase
from django.utils import timezone

from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.admin import WorkoutDataAdmin, WorkoutDataInline
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import UserExerciseRM, WorkoutData
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import Block, Session
from basis.modules.training.adapters.web.forms import StrengthSetForm


class CrossModuleReadTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("choice-owner"), account("choice-other")
        self.profile = Athlete.objects.get(account=self.owner)
        self.other_profile = Athlete.objects.get(account=self.other)
        self.today = timezone.localdate()
        classification = Classification.objects.create(nombre="choice")
        self.exercise = Exercise.objects.create(
            classification=classification,
            nombre="Historical Exercise",
            archivado=True,
            nivel_fatiga="Alto",
        )

    def test_both_admin_displays_resolve_catalog_fatigue_through_composition(self) -> None:
        row = WorkoutData(user=self.profile, exercise_id=self.exercise.pk, fecha=self.today)
        inline = WorkoutDataInline(Athlete, admin.site)
        standalone = WorkoutDataAdmin(WorkoutData, admin.site)
        self.assertEqual(inline.get_nivel_fatiga(row), "Alto")
        self.assertEqual(standalone.get_nivel_fatiga(row), "Alto")
        with patch(
            "basis.bootstrap.presentation.DjangoExerciseNames.fatigue", return_value="Medio"
        ):
            self.assertEqual(inline.get_nivel_fatiga(row), "Medio")
            self.assertEqual(standalone.get_nivel_fatiga(row), "Medio")

    def test_rm_field_preserves_owner_date_order_labels_and_invalid_choice(self) -> None:
        earlier = UserExerciseRM.objects.create(
            user=self.profile,
            exercise_id=self.exercise.pk,
            peso_maximo_rm=Decimal("70"),
            fecha_registro=self.today - timedelta(days=1),
        )
        eligible = UserExerciseRM.objects.create(
            user=self.profile,
            exercise_id=self.exercise.pk,
            peso_maximo_rm=Decimal("80"),
            fecha_registro=self.today,
        )
        future = UserExerciseRM.objects.create(
            user=self.profile,
            exercise_id=self.exercise.pk,
            peso_maximo_rm=Decimal("90"),
            fecha_registro=self.today + timedelta(days=1),
        )
        foreign = UserExerciseRM.objects.create(
            user=self.other_profile,
            exercise_id=self.exercise.pk,
            peso_maximo_rm=Decimal("100"),
            fecha_registro=self.today,
        )
        session = Session.objects.create(owner=self.owner, title="Session", date=self.today)
        block = Block.objects.create(session=session, sport="strength", title="Work")
        form = StrengthSetForm(block=block)
        field = cast(forms.ModelChoiceField[Model], form.fields["rm_reference"])
        assert field.queryset is not None
        self.assertEqual(
            list(field.queryset.values_list("pk", flat=True)), [eligible.pk, earlier.pk]
        )
        self.assertEqual(field.label, "RM medido de referencia")
        self.assertFalse(field.required)
        self.assertEqual(field.label_from_instance(eligible), str(eligible))
        self.assertEqual(field.clean(str(eligible.pk)).pk, eligible.pk)
        for excluded in (future, foreign):
            with self.subTest(id=excluded.pk), self.assertRaises(ValidationError) as failure:
                field.clean(str(excluded.pk))
            self.assertEqual(failure.exception.code, "invalid_choice")
