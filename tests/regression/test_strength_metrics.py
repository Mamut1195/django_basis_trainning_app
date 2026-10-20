"""BASIS-003: arithmetic, persistence, real admin forms and HTTP contracts."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import ClassVar, cast

from django.contrib import admin
from django.contrib.auth.models import User as Account
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from basis.modules.athletes.adapters.models import User, UserExerciseRM, WorkoutData
from basis.modules.athletes.adapters.serializers import WorkoutDataSerializer
from basis.modules.catalog.adapters.models import Exercise
from basis.modules.training.adapters.metrics import (
    calculate_legacy_strength as calculate_strength_metrics,
)
from basis.modules.training.adapters.models import StrengthSet
from basis.modules.training.public import METRICS_VERSION, MetricsInputError, StrengthMetrics

from .factories import account, exercise


class PureStrengthMetricsTests(SimpleTestCase):
    def metrics(self, **changes: object) -> StrengthMetrics:
        return calculate_strength_metrics(
            **dict(sets=3, reps=5, weight_kg="80", reference_rm_kg="100") | changes
        )

    def test_volume_and_fractional_load_are_decimal(self) -> None:
        result = self.metrics()
        self.assertEqual((result.total_reps, result.load_kg_reps), (15, Decimal("1200.00")))
        self.assertEqual(self.metrics(weight_kg="40").load_kg_reps, Decimal("600.00"))
        self.assertEqual(self.metrics(weight_kg="80.25").load_kg_reps, Decimal("1203.75"))
        self.assertIsInstance(result.relative_intensity_percent, Decimal)

    def test_round_final_volume_and_explicit_half_up_epley(self) -> None:
        with localcontext() as context:
            context.rounding = ROUND_DOWN
            result = self.metrics(weight_kg="80.25", observed_rpe="10")
            self.assertEqual(result.estimated_1rm_kg, Decimal("93.63"))
            self.assertEqual(self.metrics(reference_rm_kg="120").relative_volume, Decimal("1000"))

    def test_missing_is_distinct_from_zero_and_targets_do_not_declare_effort(self) -> None:
        result = self.metrics(reference_rm_kg=None, target_rpe=10)
        self.assertIsNone(result.relative_intensity_percent)
        self.assertIsNone(result.relative_volume)
        self.assertIsNone(result.estimated_1rm_kg)
        self.assertIsNone(self.metrics(observed_rpe=0).estimated_1rm_kg)
        self.assertIsNone(self.metrics(reference_rm_kg=0).relative_intensity_percent)

    def test_zero_inputs_clear_derived_metrics(self) -> None:
        for change in ({"sets": 0}, {"reps": 0}, {"weight_kg": "0"}):
            with self.subTest(change=change):
                result = self.metrics(observed_rpe=10, **change)
                self.assertEqual(result.load_kg_reps, 0)
                self.assertEqual(result.relative_intensity_percent, 0)
                self.assertEqual(result.relative_volume, 0)
                self.assertIsNone(result.estimated_1rm_kg)

    def test_estimate_requires_max_effort_and_one_to_ten_reps(self) -> None:
        for reps, rpe, expected in (
            (0, 10, None),
            (1, 10, "80.00"),
            (5, 10, "93.33"),
            (10, 10, "106.67"),
            (11, 10, None),
            (5, None, None),
            (5, 9.5, None),
        ):
            with self.subTest(reps=reps, rpe=rpe):
                result = self.metrics(reps=reps, observed_rpe=rpe)
                self.assertEqual(
                    result.estimated_1rm_kg, None if expected is None else Decimal(expected)
                )

    def test_incomplete_and_invalid_inputs_raise_field_errors(self) -> None:
        for changes, field in (
            ({"sets": None}, "sets"),
            ({"reps": None}, "reps"),
            ({"sets": -1}, "sets"),
            ({"reps": "1.5"}, "reps"),
            ({"sets": True}, "sets"),
            ({"weight_kg": None}, "peso"),
            ({"weight_kg": "NaN"}, "peso"),
            ({"weight_kg": "Infinity"}, "peso"),
            ({"weight_kg": "-0.01"}, "peso"),
            ({"observed_rpe": 11}, "rpe_real"),
            ({"target_rpe": 11}, "rpe_objetivo"),
        ):
            with self.subTest(changes=changes), self.assertRaises(MetricsInputError) as error:
                self.metrics(**changes)
            self.assertEqual(error.exception.field, field)

    def test_detailed_and_legacy_share_rounding_and_repetition_limits(self) -> None:
        for reps in (0, 1, 5, 10, 11):
            with self.subTest(reps=reps):
                detailed = StrengthSet(actual_reps=reps, actual_kg=Decimal("80.25"), actual_rpe=10)
                legacy = WorkoutData(sets=1, reps=reps, peso=Decimal("80.25"), rpe_real=10)
                self.assertEqual(detailed.estimated_1rm, legacy.calcular_rm_sesion())
                self.assertEqual(
                    detailed.external_volume_kg,
                    self.metrics(sets=1, reps=reps, weight_kg="80.25").load_kg_reps,
                )
        self.assertEqual(
            StrengthSet(actual_reps=5, actual_kg=Decimal("80.25"), actual_rpe=10).estimated_1rm,
            Decimal("93.63"),
        )

    def test_detailed_guards_and_separate_rir_target_and_observation(self) -> None:
        for changes in (
            {"load_type": "bodyweight"},
            {"load_type": "assisted"},
            {"kind": "warmup"},
            {"kind": "failed"},
            {"actual_rpe": None},
            {"actual_reps": None},
            {"actual_kg": None},
        ):
            with self.subTest(changes=changes):
                row = StrengthSet(
                    **dict(actual_reps=5, actual_kg=Decimal("80.25"), actual_rpe=10) | changes
                )
                self.assertIsNone(row.estimated_1rm)
                if changes.get("load_type") or "actual_reps" in changes or "actual_kg" in changes:
                    self.assertIsNone(row.external_volume_kg)
        row = StrengthSet(actual_reps=5, actual_kg=Decimal("0"), target_rpe=10, target_rir=0)
        self.assertEqual(row.external_volume_kg, Decimal("0"))
        self.assertIsNone(row.actual_rpe)
        self.assertIsNone(row.actual_rir)
        self.assertIsNone(row.estimated_1rm)
        row.actual_rir = 0
        self.assertEqual(row.actual_rir, 0)
        self.assertIsNone(row.actual_rpe)
        self.assertIsNone(row.estimated_1rm)

    def test_derived_storage_boundaries_are_portable(self) -> None:
        self.assertEqual(
            self.metrics(sets=2147483647, reps=1, weight_kg="0").total_reps, 2147483647
        )
        for changes, field in (
            ({"sets": 50000, "reps": 50000}, "total_reps"),
            ({"sets": 2000000, "reps": 1, "weight_kg": "999999.99"}, "carga"),
        ):
            with self.subTest(changes=changes), self.assertRaises(MetricsInputError) as error:
                self.metrics(**changes)
            self.assertEqual(error.exception.field, field)


class StrengthFixture(TestCase):
    owner: ClassVar[Account]
    other: ClassVar[Account]
    exercise: ClassVar[Exercise]
    other_exercise: ClassVar[Exercise]
    date: ClassVar[date]
    reference: ClassVar[UserExerciseRM]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = account("strength-owner")
        cls.other = account("strength-other")
        cls.exercise = exercise()
        cls.other_exercise = exercise()
        cls.date = timezone.localdate()
        cls.reference = UserExerciseRM.objects.create(
            user=cls.owner.athlete,
            exercise=cls.exercise,
            peso_maximo_rm="100",
            fecha_registro=cls.date - timedelta(days=1),
        )

    def row(self, **changes: object) -> WorkoutData:
        return WorkoutData.objects.create(
            **dict(
                user=self.owner.athlete,
                exercise=self.exercise,
                fecha=self.date,
                sets=3,
                reps=5,
                peso="80",
            )
            | changes
        )

    def rm(self, **changes: object) -> UserExerciseRM:
        return UserExerciseRM.objects.create(
            **dict(
                user=self.owner.athlete,
                exercise=self.exercise,
                fecha_registro=self.date,
                peso_maximo_rm="120",
            )
            | changes
        )


class StrengthRecordTests(StrengthFixture):
    def test_create_and_partial_update_persist_consistent_metrics(self) -> None:
        row = self.row()
        row.refresh_from_db()
        self.assertEqual((row.total_reps, row.carga, row.intensidad_relativa), (15, 1200, 80))
        row.peso = Decimal("40")
        row.save(update_fields=["peso"])
        row.refresh_from_db()
        self.assertEqual((row.carga, row.intensidad_relativa, row.volumen_relativo), (600, 40, 600))
        self.assertEqual(row.metrics_version, METRICS_VERSION)

    def test_partial_save_ignores_excluded_dirty_inputs(self) -> None:
        row = self.row()
        row.peso = Decimal("999")
        row.rpe_objetivo = 7
        row.save(update_fields=["rpe_objetivo"])
        row.refresh_from_db()
        self.assertEqual((row.peso, row.carga, row.rpe_objetivo), (80, 1200, 7))
        row.peso = 40
        row.save(update_fields=[])
        row.refresh_from_db()
        self.assertEqual((row.peso, row.carga), (80, 1200))

    def test_fractional_load_and_epley_survive_database_round_trip(self) -> None:
        row = self.row(peso="80.25", rpe_real=10, rpe_objetivo=6)
        row.refresh_from_db()
        self.assertEqual(row.carga, Decimal("1203.75"))
        self.assertEqual(row.rm_sesion, 93.63)
        self.assertEqual(row.calcular_rm_sesion(), Decimal("93.63"))
        self.assertEqual(row.rpe_objetivo, 6)

    def test_zero_edits_clear_previous_estimate_and_load(self) -> None:
        for field in ("sets", "reps", "peso"):
            with self.subTest(field=field):
                row = self.row(rpe_real=10)
                setattr(row, field, 0)
                row.save(update_fields=[field])
                row.refresh_from_db()
                self.assertEqual(
                    (row.carga, row.intensidad_relativa, row.volumen_relativo, row.rm_sesion),
                    (0, 0, 0, 0),
                )

    def test_observed_zero_and_absence_are_not_targets(self) -> None:
        row = self.row(rpe_objetivo=10)
        self.assertIsNone(row.rpe_real)
        self.assertIsNone(row.calcular_rpe())
        self.assertIsNone(row.calcular_rm_sesion())
        row.rpe_real = 0
        row.save(update_fields=["rpe_real"])
        row.refresh_from_db()
        self.assertEqual(row.calcular_rpe(), Decimal("0.0"))
        self.assertEqual(row.rpe_objetivo, 10)
        self.assertEqual(row.rm_sesion, 0)

    def test_future_rm_and_same_day_ties_are_deterministic(self) -> None:
        self.rm(fecha_registro=self.date + timedelta(days=1), peso_maximo_rm=300)
        self.assertEqual(self.row().rm_referencia_id, self.reference.pk)
        self.rm(peso_maximo_rm=110)
        winner = self.rm(peso_maximo_rm=120)
        self.assertEqual(self.row().rm_referencia_id, winner.pk)
        self.assertEqual(
            UserExerciseRM.get_latest_rm(self.owner.athlete, self.exercise, as_of=self.date),
            Decimal("120"),
        )

    def test_persisted_reference_survives_retroactive_same_day_rm_and_clearing(self) -> None:
        row = self.row()
        self.rm(fecha_registro=self.reference.fecha_registro, peso_maximo_rm=200)
        self.rm(peso_maximo_rm=250)
        row.rm_referencia = None
        row.peso = 40
        row.save(update_fields=["peso", "rm_referencia"])
        row.refresh_from_db()
        self.assertEqual(row.rm_referencia_id, self.reference.pk)
        self.assertEqual(row.intensidad_relativa, 40)

    def test_absent_reference_is_also_a_frozen_snapshot(self) -> None:
        row = self.row(exercise=self.other_exercise)
        self.rm(exercise=self.other_exercise)
        row.peso = 40
        row.save(update_fields=["peso"])
        row.refresh_from_db()
        self.assertIsNone(row.rm_referencia_id)
        self.assertIsNone(WorkoutDataSerializer(row).data["intensidad_relativa"])
        self.assertEqual(row.carga, Decimal("600"))

    def test_changed_context_selects_compatible_reference(self) -> None:
        row = self.row()
        replacement = self.rm(exercise=self.other_exercise)
        row.exercise = self.other_exercise
        row.save(update_fields=["exercise"])
        row.refresh_from_db()
        self.assertEqual(row.rm_referencia_id, replacement.pk)
        row.fecha = self.date - timedelta(days=5)
        row.save(update_fields=["fecha"])
        row.refresh_from_db()
        self.assertIsNone(row.rm_referencia_id)

    def test_invalid_reference_is_rejected_by_model(self) -> None:
        for reference in (
            self.rm(user=self.other.athlete),
            self.rm(exercise=self.other_exercise),
            self.rm(fecha_registro=self.date + timedelta(days=1)),
        ):
            with self.subTest(reference=reference.pk), self.assertRaises(ValidationError):
                self.row(rm_referencia=reference)
        row = self.row()
        row.rm_referencia = self.rm()
        with self.assertRaises(ValidationError):
            row.save()

    def test_rm_partial_save_validates_only_persisted_fields(self) -> None:
        reference = UserExerciseRM.objects.get(pk=self.reference.pk)
        reference.fecha_registro = self.date + timedelta(days=1)
        reference.save(update_fields=["peso_maximo_rm"])
        reference.refresh_from_db()
        self.assertEqual(reference.fecha_registro, self.date - timedelta(days=1))
        reference.peso_maximo_rm = 110
        with self.assertRaises(ValidationError):
            reference.save(update_fields=["peso_maximo_rm"])
        reference.refresh_from_db()
        self.assertEqual(reference.peso_maximo_rm, 100)

    def test_legacy_read_preserves_history_and_never_infers_observation(self) -> None:
        row = self.row()
        WorkoutData.objects.filter(pk=row.pk).update(
            rpe_objetivo=10, rm_sesion=999, metrics_version="legacy-unverified", rm_referencia=None
        )
        row.refresh_from_db()
        data = WorkoutDataSerializer(row).data
        self.assertEqual(row.rm_sesion, 999)
        self.assertIsNone(data["rm_sesion"])
        self.assertIsNone(data["rpe_real"])
        self.assertIsNone(data["intensidad_relativa"])
        row.peso = 40
        row.save(update_fields=["peso"])
        row.refresh_from_db()
        self.assertIsNone(row.rpe_real)
        self.assertEqual((row.rm_sesion, row.rpe_objetivo), (0, 10))
        self.assertEqual(row.metrics_version, METRICS_VERSION)

    def test_v2_absent_reference_stays_absent_on_explicit_edit(self) -> None:
        row = self.row(exercise=self.other_exercise)
        WorkoutData.objects.filter(pk=row.pk).update(metrics_version="legacy-volume-v2")
        self.rm(exercise=self.other_exercise)
        row.refresh_from_db()
        row.peso = 40
        row.save()
        self.assertIsNone(row.rm_referencia_id)


class StrengthAPITests(StrengthFixture):
    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_login(self.owner)

    def post(self, **changes: object) -> Response:
        return cast(
            Response,
            self.client.post(
                "/api/v1/workout-data/",
                dict(exercise_id=self.exercise.pk, fecha=str(self.date), sets=3, reps=5, peso="80")
                | changes,
                format="json",
            ),
        )

    def patch(self, row: WorkoutData, **changes: object) -> Response:
        return cast(
            Response, self.client.patch(f"/api/v1/workout-data/{row.pk}/", changes, format="json")
        )

    def test_http_create_patch_fractional_zero_and_missing(self) -> None:
        response = self.post(rpe_objetivo=10)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Decimal(response.data["carga"]), 1200)
        self.assertIsNone(response.data["rpe_real"])
        self.assertIsNone(response.data["rm_sesion"])
        row = WorkoutData.objects.get(pk=response.data["id"])
        response = self.patch(row, peso="40")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(response.data["carga"]), 600)
        response = self.patch(row, peso="80.25", rpe_real="10")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            (Decimal(response.data["carga"]), response.data["rm_sesion"]),
            (Decimal("1203.75"), 93.63),
        )
        response = self.patch(row, peso="0")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Decimal(response.data["carga"]), 0)
        self.assertIsNone(response.data["rm_sesion"])
        response = self.patch(row, rpe_real="0")
        self.assertEqual(Decimal(response.data["rpe_real"]), 0)
        response = self.patch(row, rpe_real=None)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.data["rpe_real"])
        self.assertEqual(response.data["rpe_objetivo"], 10)

    def test_http_patch_cannot_inject_foreign_or_future_reference(self) -> None:
        row = self.row()
        for reference in (
            self.rm(user=self.other.athlete),
            self.rm(fecha_registro=self.date + timedelta(days=1)),
        ):
            with self.subTest(reference=reference.pk):
                response = self.patch(row, rm_referencia=reference.pk, peso="40")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("rm_referencia", response.data)
                response = self.post(rm_referencia=reference.pk)
                self.assertEqual(response.status_code, 400, response.content)
        row.refresh_from_db()
        self.assertEqual((row.peso, row.rm_referencia_id), (80, self.reference.pk))

    def test_http_missing_snapshot_survives_retroactive_rm(self) -> None:
        response = self.post(exercise_id=self.other_exercise.pk)
        self.assertEqual(response.status_code, 201, response.content)
        row = WorkoutData.objects.get(pk=response.data["id"])
        self.rm(exercise=self.other_exercise)
        response = self.patch(row, peso="40")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.data["rm_referencia"])
        self.assertIsNone(response.data["intensidad_relativa"])
        self.assertIsNone(response.data["volumen_relativo"])

    def test_http_invalid_values_and_immutable_rm_return_400(self) -> None:
        row = self.row()
        for change in (
            {"sets": -1},
            {"peso": "-0.01"},
            {"rpe_real": 11},
            {"rpe_objetivo": 11},
            {"rpe_objetivo": "NaN"},
        ):
            with self.subTest(change=change):
                response = self.patch(row, **change)
                self.assertEqual(response.status_code, 400, response.content)
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/user-exercise-rm/{self.reference.pk}/",
                {"peso_maximo_rm": "200"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, 400, response.content)
        row.refresh_from_db()
        self.assertEqual((row.carga, row.rpe_objetivo), (1200, 0))

    def test_http_overflow_returns_400_without_partial_persistence(self) -> None:
        row = self.row()
        count = WorkoutData.objects.count()
        for changes in (
            {"sets": 50000, "reps": 50000, "peso": "1"},
            {"sets": 2000000, "reps": 1, "peso": "999999.99"},
        ):
            with self.subTest(changes=changes):
                response = self.post(**changes)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(WorkoutData.objects.count(), count)
                response = self.patch(row, **changes)
                self.assertEqual(response.status_code, 400, response.content)
                row.refresh_from_db()
                self.assertEqual((row.sets, row.reps, row.peso, row.carga), (3, 5, 80, 1200))


class StrengthAdminTests(StrengthFixture):
    def setUp(self) -> None:
        self.request = RequestFactory().get("/admin/")
        self.owner.is_staff = self.owner.is_superuser = True
        self.request.user = self.owner
        self.model_admin = cast(admin.ModelAdmin[WorkoutData], admin.site._registry[WorkoutData])
        self.inline = next(
            inline
            for inline in admin.site._registry[User].get_inline_instances(self.request)
            if inline.model is WorkoutData
        )

    def form_data(self, **changes: object) -> dict[str, object]:
        return (
            dict(
                user=self.owner.athlete.pk,
                exercise=self.exercise.pk,
                fecha=str(self.date),
                sets=3,
                reps=5,
                peso="80.25",
                rpe_objetivo="8",
                rpe_real="10",
            )
            | changes
        )

    def test_registered_admin_form_records_target_and_observation(self) -> None:
        form_class = self.model_admin.get_form(self.request)
        self.assertIn("rpe_objetivo", form_class.base_fields)
        self.assertIn("rpe_real", form_class.base_fields)
        self.assertTrue(WorkoutData.METRIC_FIELDS.isdisjoint(form_class.base_fields))
        form = form_class(data=self.form_data())
        self.assertTrue(form.is_valid(), form.errors)
        row = form.save()
        row.refresh_from_db()
        self.assertEqual(
            (row.carga, row.rm_sesion, row.rpe_objetivo, row.rpe_real),
            (Decimal("1203.75"), 93.63, 8, Decimal("10")),
        )

    def test_registered_admin_incomplete_forms_show_errors(self) -> None:
        form_class = self.model_admin.get_form(self.request)
        for changes in (
            {"sets": ""},
            {"reps": ""},
            {"peso": ""},
            {"fecha": ""},
            {"sets": "bad"},
            {"rpe_objetivo": 11},
            {"rpe_real": 11},
            {"sets": 50000, "reps": 50000},
            {"sets": 2000000, "reps": 1, "peso": "999999.99"},
        ):
            with self.subTest(changes=changes):
                form = form_class(data=self.form_data(**changes))
                self.assertFalse(form.is_valid())
                self.assertTrue(form.errors)

    def test_registered_inline_formset_saves_both_rpe_fields(self) -> None:
        formset_class = self.inline.get_formset(self.request, self.owner.athlete)
        self.assertIn("rpe_objetivo", formset_class.form.base_fields)
        self.assertIn("rpe_real", formset_class.form.base_fields)
        self.assertTrue(WorkoutData.METRIC_FIELDS.isdisjoint(formset_class.form.base_fields))
        prefix = formset_class.get_default_prefix()
        data: dict[str, object] = {
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        data.update({f"{prefix}-0-{key}": value for key, value in self.form_data().items()})
        formset = formset_class(data=data, instance=self.owner.athlete)
        self.assertTrue(formset.is_valid(), formset.errors)
        (row,) = formset.save()
        row.refresh_from_db()
        self.assertEqual(
            (row.rpe_objetivo, row.rpe_real, row.carga), (8, Decimal("10"), Decimal("1203.75"))
        )

    def test_registered_admin_edit_recalculates_and_missing_effort_stays_missing(self) -> None:
        row = self.row(rpe_real=10)
        form_class = self.model_admin.get_form(self.request, row)
        form = form_class(data=self.form_data(peso="40", rpe_real=""), instance=row)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        row.refresh_from_db()
        self.assertEqual((row.carga, row.rm_sesion, row.rpe_objetivo), (600, 0, 8))
        self.assertIsNone(row.rpe_real)

    def test_registered_rm_admin_validates_history_before_save(self) -> None:
        model_admin = cast(admin.ModelAdmin[UserExerciseRM], admin.site._registry[UserExerciseRM])
        form_class = model_admin.get_form(self.request, self.reference)
        form = form_class(
            data=dict(
                user=self.owner.athlete.pk,
                exercise=self.exercise.pk,
                peso_maximo_rm="150",
                fecha_registro=str(self.reference.fecha_registro),
            ),
            instance=self.reference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
