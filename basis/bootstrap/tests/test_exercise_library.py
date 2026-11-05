"""The seeded strength library covers every muscle group and is idempotent."""

from django.core.management import call_command
from django.test import TestCase

from basis.modules.catalog.adapters.management.commands.seed_exercise_library import (
    EXERCISES,
    MUSCLES,
    PATTERNS,
)
from basis.modules.catalog.adapters.models import Exercise


class ExerciseLibraryTests(TestCase):
    def test_library_covers_every_muscle_group(self) -> None:
        call_command("seed_exercise_library", verbosity=0)

        self.assertGreaterEqual(Exercise.objects.count(), 60)
        for muscle in MUSCLES:
            count = sum(1 for row in Exercise.objects.all() if muscle in row.musculos_principales)
            self.assertGreaterEqual(count, 3, f"{muscle} tiene solo {count} ejercicios")

    def test_seed_is_idempotent(self) -> None:
        call_command("seed_exercise_library", verbosity=0)
        first = Exercise.objects.count()
        call_command("seed_exercise_library", verbosity=0)
        self.assertEqual(Exercise.objects.count(), first)

    def test_dry_run_writes_nothing(self) -> None:
        call_command("seed_exercise_library", "--dry-run", verbosity=0)
        self.assertEqual(Exercise.objects.count(), 0)

    def test_vocabulary_is_valid(self) -> None:
        call_command("seed_exercise_library", verbosity=0)
        rows = list(Exercise.objects.all())
        self.assertEqual(len(rows), len(EXERCISES))
        for row in rows:
            self.assertIn(row.patron_movimiento, PATTERNS, row.nombre)
            self.assertTrue(set(row.musculos_principales) <= set(MUSCLES), row.nombre)
            self.assertIn(row.nivel_fatiga, ("Bajo", "Medio", "Alto"), row.nombre)
            self.assertTrue(row.equipo, row.nombre)
