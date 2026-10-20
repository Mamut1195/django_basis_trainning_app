from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from basis.modules.athletes.adapters.models import UserExerciseRM, WorkoutData

from .factories import account, exercise, session


class IsolationTests(TestCase):
    def setUp(self):
        self.owner, self.other = account("one"), account("two")
        self.exercise = exercise()
        self.record = WorkoutData.objects.create(
            user=self.other.athlete,
            exercise=self.exercise,
            fecha=timezone.localdate(),
            sets=3,
            reps=5,
            peso=40,
        )
        self.client = APIClient()

    def test_anonymous_cannot_read_or_write_api(self):
        for path in ("users", "workout-data", "user-exercise-rm", "exercises", "classifications"):
            self.assertEqual(self.client.get(f"/api/v1/{path}/").status_code, 403)
        self.assertEqual(
            self.client.post("/api/v1/exercises/", {"nombre": "Injected"}).status_code, 403
        )

    def test_lists_and_details_are_scoped(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/v1/users/")
        self.assertEqual([row["id"] for row in response.json()["results"]], [self.owner.athlete.pk])
        self.assertEqual(
            self.client.get(f"/api/v1/users/{self.other.athlete.pk}/").status_code, 404
        )
        self.assertEqual(self.client.get("/api/v1/workout-data/").json()["count"], 0)
        self.assertEqual(
            self.client.patch(f"/api/v1/workout-data/{self.record.pk}/", {"peso": 20}).status_code,
            404,
        )

    def test_owner_is_assigned_and_cannot_be_reassigned(self):
        self.client.force_login(self.owner)
        data = {
            "exercise_id": self.exercise.pk,
            "fecha": str(timezone.localdate()),
            "sets": 3,
            "reps": 5,
            "peso": "20.25",
        }
        response = self.client.post("/api/v1/workout-data/", data)
        self.assertEqual(response.status_code, 201, response.content)
        saved = WorkoutData.objects.get(pk=response.json()["id"])
        self.assertEqual(saved.user_id, self.owner.athlete.pk)
        response = self.client.patch(
            f"/api/v1/workout-data/{saved.pk}/", {"user_id": self.other.athlete.pk}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post("/api/v1/exercises/", {"nombre": "Injected"}).status_code, 403
        )

    def test_expired_can_read_export_but_not_write(self):
        billing = self.owner.billing
        billing.period_end = timezone.now() - timedelta(seconds=1)
        billing.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/export/").status_code, 200)
        self.assertEqual(self.client.get("/sessions/new/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/user-exercise-rm/",
                {
                    "exercise_id": self.exercise.pk,
                    "peso_maximo_rm": 100,
                    "fecha_registro": str(timezone.localdate()),
                },
            ).status_code,
            403,
        )

    def test_web_and_snapshots_are_private(self):
        other_session = session(self.other)
        self.client.force_login(self.owner)
        for path in (
            f"/sessions/{other_session.pk}/",
            f"/api/sessions/{other_session.pk}/snapshot/",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_csrf_is_required_for_sync(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post("/api/sync/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)


class LegacyMetricsTests(TestCase):
    def test_rm_and_profile_history_cannot_be_overwritten_or_cascaded(self):
        from django.core.exceptions import ValidationError
        from django.db.models.deletion import ProtectedError

        reference = UserExerciseRM.objects.create(
            user=self.user.athlete,
            exercise=self.exercise,
            peso_maximo_rm=100,
            fecha_registro=self.date,
        )
        reference.peso_maximo_rm = 150
        with self.assertRaises(ValidationError):
            reference.save()
        with self.assertRaises(ProtectedError):
            self.user.athlete.delete()

    def setUp(self):
        self.user = account()
        self.exercise = exercise()
        self.date = timezone.localdate()

    def test_rm_is_as_of_session_and_snapshot_is_preserved(self):
        reference = UserExerciseRM.objects.create(
            user=self.user.athlete,
            exercise=self.exercise,
            peso_maximo_rm=100,
            fecha_registro=self.date - timedelta(days=1),
        )
        UserExerciseRM.objects.create(
            user=self.user.athlete,
            exercise=self.exercise,
            peso_maximo_rm=200,
            fecha_registro=self.date + timedelta(days=1),
        )
        row = WorkoutData.objects.create(
            user=self.user.athlete, exercise=self.exercise, fecha=self.date, sets=3, reps=5, peso=80
        )
        self.assertEqual(row.intensidad_relativa, 80)
        self.assertEqual(row.rm_referencia, reference)
        self.assertEqual(row.rpe_objetivo, 0)
        self.assertIsNone(row.rpe_real)
        self.assertEqual(row.rm_sesion, 0)
        row.peso = 40
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.carga, 600)
        row.sets = row.reps = 0
        row.peso = 0
        row.save()
        row.refresh_from_db()
        self.assertEqual((row.total_reps, row.carga, row.volumen_relativo), (0, 0, 0))

    def test_exercise_deletion_cannot_destroy_history(self):
        from django.db.models.deletion import ProtectedError

        WorkoutData.objects.create(
            user=self.user.athlete, exercise=self.exercise, fecha=self.date, sets=1, reps=1, peso=50
        )
        with self.assertRaises(ProtectedError):
            self.exercise.delete()
