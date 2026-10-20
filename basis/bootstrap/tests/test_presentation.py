"""Composed historical reads preserve catalog names and athlete ownership."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from basis.bootstrap.presentation import athlete_reads
from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import WorkoutData
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.shared.identifiers import AccountId


class HistoricalPresentationTests(TestCase):
    def test_archived_exercise_name_remains_visible_only_in_its_owners_history(self) -> None:
        owner, other = account("history-owner"), account("history-other")
        classification = Classification.objects.create(nombre="historical")
        exercise = Exercise.objects.create(
            nombre="Archived squat", classification=classification, archivado=True
        )
        WorkoutData.objects.create(
            user=Athlete.objects.get(account=owner),
            exercise_id=exercise.pk,
            fecha=timezone.localdate(),
            sets=2,
            reps=5,
            peso=Decimal("30"),
        )
        with self.assertNumQueries(4):
            records = athlete_reads().history(AccountId(owner.pk)).legacy_records
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].exercise.nombre, "Archived Squat")
        self.assertEqual(records[0].peso, Decimal("30"))
        self.assertEqual(athlete_reads().history(AccountId(other.pk)).legacy_records, ())
