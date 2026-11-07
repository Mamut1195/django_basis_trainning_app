"""Personal records for every exercise and sport, computed from completed sessions."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import Block, Session, StrengthSet

from .factories import account


class RecordTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("records")
        self.client.force_login(self.owner)
        classification, _ = Classification.objects.get_or_create(nombre="Fuerza")
        self.squat = Exercise.objects.create(nombre="Sentadilla", classification=classification)
        self.pushup = Exercise.objects.create(nombre="Flexiones", classification=classification)
        self.strength = Session.objects.create(
            owner=self.owner,
            title="Fuerza de prueba",
            status="completed",
            date=timezone.localdate(),
            duration_seconds=3000,
        )
        block = Block.objects.create(
            session=self.strength, sport="strength", title="Fuerza", order=1
        )
        StrengthSet.objects.create(
            block=block,
            exercise=self.squat,
            order=1,
            kind="work",
            load_type="external",
            actual_kg=Decimal("80"),
            actual_reps=5,
        )
        StrengthSet.objects.create(
            block=block,
            exercise=self.pushup,
            order=2,
            kind="work",
            load_type="bodyweight",
            actual_reps=12,
        )
        self.run_session = Session.objects.create(
            owner=self.owner,
            title="Rodaje",
            status="completed",
            date=timezone.localdate(),
            duration_seconds=1500,
        )
        Block.objects.create(
            session=self.run_session,
            sport="running",
            title="Rodaje",
            order=1,
            actual={"distance_m": "5000"},
        )

    def test_every_exercise_has_a_record_or_an_explicit_empty_state(self) -> None:
        response = self.client.get(reverse("records"))
        self.assertContains(response, "Todas tus marcas")
        self.assertContains(response, "1RM estimado")
        self.assertContains(response, "93,3")
        self.assertContains(response, "Mejor serie")
        self.assertContains(response, "12,0")
        self.assertContains(response, "5.0 km")
        self.assertContains(response, "5:00 /km")

    def test_search_filters_exercises_without_hiding_sports(self) -> None:
        response = self.client.get(reverse("records"), {"q": "Flex"})
        self.assertContains(response, "Flexiones")
        self.assertNotContains(response, "<strong>Sentadilla</strong>", html=True)
        self.assertContains(response, "5.0 km")
