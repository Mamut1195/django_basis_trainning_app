"""BASIS-004 history, ordinary persistence and repeatable demo acceptance."""

import ast
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.presentation import athlete_reads
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import UserExerciseRM, WorkoutData
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import Block, Session, StrengthSet, TrainingPlan
from basis.shared.identifiers import AccountId
from tests.regression.factories import account

ROOT = Path(__file__).resolve().parents[3]


class NormalizationIntegrityTests(TestCase):
    def test_ordinary_orm_creation_and_update_normalize_names(self) -> None:
        classification = Classification.objects.create(nombre="  fuerza    base  ")
        classification.refresh_from_db()
        self.assertEqual(classification.nombre, "Fuerza Base")
        classification.nombre = "  movilidad    diaria "
        classification.save()
        classification.refresh_from_db()
        self.assertEqual(classification.nombre, "Movilidad Diaria")
        athlete = Athlete.objects.create(
            nombre="  ana    prueba  ",
            email="normalization@example.test",
            fecha_inicio=timezone.localdate(),
            ciudad="  puerto    nuevo ",
        )
        athlete.refresh_from_db()
        self.assertEqual((athlete.nombre, athlete.ciudad), ("Ana Prueba", "Puerto Nuevo"))
        athlete.nombre = "  ana    revisada  "
        athlete.save()
        athlete.refresh_from_db()
        self.assertEqual(athlete.nombre, "Ana Revisada")

    def test_partial_update_only_persists_explicit_columns(self) -> None:
        athlete = Athlete.objects.create(
            nombre="Original", email="partial@example.test", fecha_inicio=timezone.localdate()
        )
        athlete.nombre, athlete.ciudad = "  nueva    persona  ", "Ciudad Sin Guardar"
        athlete.save(update_fields=["nombre"])
        athlete.refresh_from_db()
        self.assertEqual(athlete.nombre, "Nueva Persona")
        self.assertIsNone(athlete.ciudad)
        classification = Classification.objects.create(nombre="Original")
        classification.nombre = "No Guardar"
        classification.save(update_fields=[])
        classification.refresh_from_db()
        self.assertEqual(classification.nombre, "Original")

    def test_normalized_unique_name_and_invalid_profile_never_persist(self) -> None:
        Classification.objects.create(nombre="Fuerza Base")
        with self.assertRaises(ValidationError):
            Classification.objects.create(nombre="  fuerza    base  ")
        with self.assertRaises(ValidationError):
            Athlete.objects.create(
                nombre="Invalid", email="not-an-email", fecha_inicio=timezone.localdate()
            )
        self.assertEqual(Classification.objects.count(), 1)
        self.assertEqual(Athlete.objects.count(), 0)

    def test_whitespace_only_names_are_rejected_after_normalization(self) -> None:
        classification = Classification.objects.create(nombre="Valid")
        rows = (
            Classification(nombre="   "),
            Exercise(nombre="  \t ", classification=classification),
            Athlete(
                nombre="  \n ", email="empty-name@example.test", fecha_inicio=timezone.localdate()
            ),
        )
        for row in rows:
            with self.subTest(model=row._meta.label), self.assertRaises(ValidationError):
                row.save()
        self.assertEqual(Classification.objects.count(), 1)
        self.assertEqual(Exercise.objects.count(), 0)
        self.assertEqual(Athlete.objects.count(), 0)

    def test_api_and_real_admin_share_name_normalization(self) -> None:
        operator = get_user_model().objects.create_superuser(
            username="integrity-admin", email="admin@example.test", password="local-test-password"
        )
        self.client.force_login(operator)
        response = self.client.post("/api/v1/classifications/", {"nombre": "  api    catalog  "})
        self.assertEqual(response.status_code, 201)
        classification = Classification.objects.get(nombre="Api Catalog")
        response = self.client.post(
            "/api/v1/exercises/",
            {"nombre": "  press    inclinado  ", "classification_id": classification.pk},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Exercise.objects.filter(nombre="Press Inclinado").exists())
        response = self.client.post(
            "/admin/basis_catalog/classification/add/", {"nombre": "  admin    catalog "}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Classification.objects.filter(nombre="Admin Catalog").exists())

    def test_model_sources_have_no_shadowed_clean_definition(self) -> None:
        for module_name in (
            "basis.modules.catalog.adapters.models",
            "basis.modules.athletes.adapters.models.profile",
            "basis.modules.athletes.adapters.models.strength",
        ):
            spec = importlib.util.find_spec(module_name)
            assert spec is not None and spec.origin is not None
            tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8-sig"))
            for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
                with self.subTest(module=module_name, model=cls.name):
                    self.assertLessEqual(
                        sum(
                            isinstance(node, ast.FunctionDef) and node.name == "clean"
                            for node in cls.body
                        ),
                        1,
                    )


class HistoricalIntegrityTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("integrity-owner")
        self.profile = Athlete.objects.get(account=self.owner)
        self.classification = Classification.objects.create(nombre="History")
        self.exercise = Exercise.objects.create(
            nombre="Historical squat", classification=self.classification
        )
        self.reference = UserExerciseRM.objects.create(
            user=self.profile,
            exercise=self.exercise,
            peso_maximo_rm=100,
            fecha_registro=timezone.localdate(),
        )
        self.workout = WorkoutData.objects.create(
            user=self.profile,
            exercise=self.exercise,
            fecha=timezone.localdate(),
            sets=2,
            reps=5,
            peso=50,
        )
        self.session = Session.objects.create(owner=self.owner, title="Historical session")
        block = Block.objects.create(session=self.session, sport="strength", title="Strength")
        self.strength = StrengthSet.objects.create(
            block=block,
            exercise=self.exercise,
            rm_reference=self.reference,
            actual_kg=50,
            actual_reps=5,
        )
        self.client.force_login(self.owner)

    def test_archive_preserves_readable_rm_workout_session_and_export(self) -> None:
        self.exercise.archivado = True
        self.exercise.save(update_fields=["archivado"])
        self.assertFalse(Exercise.objects.filter(archivado=False, pk=self.exercise.pk).exists())
        response = self.client.get(f"/api/v1/exercises/{self.exercise.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/v1/user-exercise-rm/{self.reference.pk}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/v1/workout-data/{self.workout.pk}/").status_code, 200
        )
        response = self.client.get(f"/sessions/{self.session.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Historical Squat")
        history = athlete_reads().history(AccountId(self.owner.pk))
        self.assertEqual(history.legacy_records[0].exercise.nombre, "Historical Squat")
        response = self.client.get("/export/")
        payload = cast(dict[str, object], json.loads(response.content))
        self.assertEqual(len(cast(list[object], payload["userexerciserm"])), 1)
        self.assertEqual(len(cast(list[object], payload["workoutdata"])), 1)
        self.strength.refresh_from_db()
        self.assertEqual(self.strength.rm_reference_id, self.reference.pk)

    def test_deletion_cannot_cascade_through_catalog_profile_or_account(self) -> None:
        for row in (self.exercise, self.classification, self.profile, self.owner, self.session):
            with self.subTest(model=row._meta.label), self.assertRaises(ProtectedError):
                row.delete()
        self.assertTrue(WorkoutData.objects.filter(pk=self.workout.pk).exists())
        self.assertTrue(UserExerciseRM.objects.filter(pk=self.reference.pk).exists())
        self.assertTrue(StrengthSet.objects.filter(pk=self.strength.pk).exists())
        self.assertEqual(
            self.client.delete(f"/api/v1/workout-data/{self.workout.pk}/").status_code, 409
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/user-exercise-rm/{self.reference.pk}/").status_code, 409
        )

    def test_database_constraints_reject_invalid_parent_and_duplicate_classification(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            Block.objects.bulk_create([Block(sport="running", title="Orphan")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Classification.objects.bulk_create([Classification(nombre=self.classification.nombre)])
        self.assertEqual(Block.objects.count(), 1)
        self.assertEqual(Classification.objects.count(), 1)


@override_settings(DEBUG=True, DEVELOPMENT_ACCESS=True)
class DemoIntegrityTests(TestCase):
    def test_repeated_demo_preserves_existing_data_password_and_row_identity(self) -> None:
        existing = account("existing-before-demo")
        preserved_password = existing.password
        sentinel = Classification.objects.create(nombre="Keep Existing")
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": "first-local-test-password"}):
            call_command("seed_demo", stdout=io.StringIO())
        demo = get_user_model().objects.get(username="demo@basis.test")
        demo_password = demo.password
        before = (
            tuple(Exercise.objects.values_list("pk", "nombre", "classification_id")),
            tuple(Athlete.objects.values_list("pk", "email")),
            tuple(TrainingPlan.objects.values_list("pk", "owner_id")),
        )
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": "second-local-test-password"}):
            call_command("seed_demo", stdout=io.StringIO())
        after = (
            tuple(Exercise.objects.values_list("pk", "nombre", "classification_id")),
            tuple(Athlete.objects.values_list("pk", "email")),
            tuple(TrainingPlan.objects.values_list("pk", "owner_id")),
        )
        self.assertEqual(before, after)
        demo.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(demo.password, demo_password)
        self.assertEqual(existing.password, preserved_password)
        self.assertTrue(Classification.objects.filter(pk=sentinel.pk).exists())

    def test_demo_reuses_existing_case_variants_without_changing_them(self) -> None:
        # bulk_create deliberately represents rows written before normalization was enforced.
        classification = Classification(nombre="Fuerza general")
        Classification.objects.bulk_create([classification])
        exercise = Exercise(nombre="Press de banca", classification=classification)
        Exercise.objects.bulk_create([exercise])
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": "case-local-test-password"}):
            call_command("seed_demo", stdout=io.StringIO())
        self.assertEqual(Classification.objects.filter(nombre__iexact="Fuerza General").count(), 1)
        self.assertEqual(Exercise.objects.filter(nombre__iexact="Press De Banca").count(), 1)
        exercise.refresh_from_db()
        self.assertEqual(exercise.nombre, "Press de banca")

    def test_ambiguous_previous_classifications_reject_demo_and_roll_back_all_writes(self) -> None:
        Classification.objects.bulk_create(
            [Classification(nombre="FUERZA GENERAL"), Classification(nombre="Fuerza general")]
        )
        before = tuple(Classification.objects.values_list("pk", "nombre"))
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": "ambiguous-local-test-password"}):
            with self.assertRaisesRegex(CommandError, "clasificaciones equivalentes"):
                call_command("seed_demo", stdout=io.StringIO())
        self.assertEqual(tuple(Classification.objects.values_list("pk", "nombre")), before)
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(Athlete.objects.count(), 0)
        self.assertEqual(Exercise.objects.count(), 0)
        self.assertEqual(TrainingPlan.objects.count(), 0)

    def test_demo_rejects_disabled_flags_and_missing_password_without_writes(self) -> None:
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": "valid-local-test-password"}):
            for flags in ({"DEBUG": False}, {"DEVELOPMENT_ACCESS": False}):
                with self.subTest(flags=flags), override_settings(**flags):
                    with self.assertRaises(CommandError):
                        call_command("seed_demo", stdout=io.StringIO())
        with patch.dict(os.environ, {"BASIS_DEMO_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("seed_demo", stdout=io.StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(Exercise.objects.count(), 0)

    def test_retired_seed_rejects_execution_and_import_before_django(self) -> None:
        for mode in ("script", "import"):
            code = (
                "import importlib.util,runpy,sys; sys.modules['django']=None; "
                "path='seed.py'; "
                + (
                    "runpy.run_path(path,run_name='__main__')"
                    if mode == "script"
                    else "spec=importlib.util.spec_from_file_location('retired_seed',path); "
                    "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)"
                )
            )
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", code],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            with self.subTest(mode=mode):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("RuntimeError", result.stderr)
                self.assertIn("seed_demo", result.stderr)
                self.assertNotIn("ModuleNotFoundError", result.stderr)
