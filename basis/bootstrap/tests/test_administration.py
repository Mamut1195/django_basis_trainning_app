"""Real administrative routes delegate writes without weakening native permissions."""

from decimal import Decimal

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User as Account
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from basis.bootstrap.admin_actions import save_admin_profile
from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.models import User, UserExerciseRM, WorkoutData
from basis.modules.catalog.adapters.models import Classification, Exercise


class AdministrativeWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.operator = Account.objects.create_superuser(
            username="operator", email="operator@example.test", password="local-test-password"
        )
        self.client.force_login(self.operator)
        self.today = timezone.localdate()
        self.owner = account("administrative-athlete")
        self.profile = User.objects.get(account=self.owner)
        classification = Classification.objects.create(nombre="administrative")
        self.exercise = Exercise.objects.create(nombre="squat", classification=classification)

    def profile_payload(self, email: str) -> dict[str, str]:
        return {
            "nombre": "  legacy   profile ",
            "email": email,
            "fecha_inicio": str(self.today),
            "edad": "16",
            "workoutdata_set-TOTAL_FORMS": "0",
            "workoutdata_set-INITIAL_FORMS": "0",
            "workoutdata_set-MIN_NUM_FORMS": "0",
            "workoutdata_set-MAX_NUM_FORMS": "1000",
        }

    def test_unlinked_admin_profile_preserves_native_age_and_permission_capabilities(self) -> None:
        staff = Account.objects.create_user(username="profile-staff", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="basis_athletes", codename="add_user")
        )
        self.client.force_login(staff)
        response = self.client.post(
            "/admin/basis_athletes/user/add/", self.profile_payload("legacy@example.test")
        )
        self.assertEqual(response.status_code, 302)
        row = User.objects.get(email="legacy@example.test")
        self.assertIsNone(row.account_id)
        self.assertEqual(row.nombre, "Legacy Profile")
        self.assertEqual(row.edad, 16)
        self.assertFalse(row.email_verified)

    def test_workout_admin_add_uses_core_calculation_and_measured_reference(self) -> None:
        measured = UserExerciseRM.objects.create(
            user=self.profile,
            exercise=self.exercise,
            peso_maximo_rm=Decimal("100"),
            fecha_registro=self.today,
        )
        response = self.client.post(
            "/admin/basis_athletes/workoutdata/add/",
            {
                "user": str(self.profile.pk),
                "exercise": str(self.exercise.pk),
                "fecha": str(self.today),
                "sets": "2",
                "reps": "5",
                "peso": "80",
                "rpe_objetivo": "0",
                "rpe_real": "10",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = WorkoutData.objects.get(user=self.profile)
        self.assertEqual(row.carga, Decimal("800.00"))
        self.assertEqual(row.rm_referencia_id, measured.pk)
        self.assertEqual(row.intensidad_relativa, 80.0)

    def test_admin_permission_denied_before_unlinked_profile_write(self) -> None:
        staff = Account.objects.create_user(username="no-profile-permission", is_staff=True)
        row = User(nombre="Blocked", email="blocked@example.test", fecha_inicio=self.today)
        with self.assertRaises(PermissionDenied):
            save_admin_profile(staff.pk, row, False)
        self.assertFalse(User.objects.filter(email=row.email).exists())

    def test_catalog_bulk_delete_rolls_back_earlier_deletion_on_protected_reference(self) -> None:
        free = Exercise.objects.create(nombre="free", classification=self.exercise.classification)
        protected = Exercise.objects.create(
            nombre="protected", classification=self.exercise.classification
        )
        WorkoutData.objects.create(
            user=self.profile,
            exercise=protected,
            fecha=self.today,
            sets=1,
            reps=1,
            peso=Decimal(10),
        )
        request = RequestFactory().post("/admin/basis_catalog/exercise/")
        request.user = self.operator
        with self.assertRaises(ProtectedError):
            admin.site._registry[Exercise].delete_queryset(
                request, Exercise.objects.filter(pk__in=(free.pk, protected.pk)).order_by("pk")
            )
        self.assertTrue(Exercise.objects.filter(pk=free.pk).exists())
        self.assertTrue(Exercise.objects.filter(pk=protected.pk).exists())

    def test_profile_inline_workout_uses_administrative_case(self) -> None:
        payload = self.profile_payload(self.profile.email)
        payload.update(
            {
                "nombre": self.profile.nombre,
                "account": str(self.owner.pk),
                "edad": "25",
                "email_verified": "on",
                "workoutdata_set-TOTAL_FORMS": "1",
                "workoutdata_set-0-fecha": str(self.today),
                "workoutdata_set-0-exercise": str(self.exercise.pk),
                "workoutdata_set-0-sets": "2",
                "workoutdata_set-0-reps": "5",
                "workoutdata_set-0-peso": "50",
                "workoutdata_set-0-rpe_objetivo": "0",
            }
        )
        response = self.client.post(
            f"/admin/basis_athletes/user/{self.profile.pk}/change/", payload
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkoutData.objects.get(user=self.profile).carga, Decimal("500.00"))
