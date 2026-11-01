"""MAM-624: optional check-ins, private history and migration of existing rows."""

import json
import logging
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from typing import cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from basis.bootstrap.athletes import athletes
from basis.bootstrap.coach import contexts
from basis.bootstrap.presentation import athlete_reads
from basis.bootstrap.tests.test_identity import account
from basis.modules.athletes.adapters.django import DjangoAthleteRecords, wellness_data
from basis.modules.athletes.adapters.models import AthleteSettings, Wellness
from basis.modules.athletes.adapters.web.forms import WellnessForm
from basis.modules.athletes.public import InvalidAthleteData, RecordWellness
from basis.modules.coach.adapters.context_wire import decode_context, encode_context, mapping
from basis.shared.identifiers import AccountId


@override_settings(DEVELOPMENT_ACCESS=True)
class WellnessTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account(), account("other")
        self.user = get_user_model().objects.get(pk=self.owner)
        self.client.force_login(self.user)
        self.day = timezone.localdate()
        self.new = reverse("owned-new", args=["wellness"])
        self.history = reverse("wellness-history")

    def form(self, values: dict[str, str], row: Wellness | None = None) -> WellnessForm:
        return WellnessForm(
            {"date": self.day.isoformat(), "moment": "day", **values},
            instance=row if row is not None else Wellness(owner_id=self.owner),
        )

    def test_form_empty_observations_and_partial_values_are_valid(self) -> None:
        for values in ({}, {"fatigue": "1"}, {"sleep_hours": "0", "pain_score": "0"}):
            form = self.form(values)
            self.assertTrue(form.is_valid(), form.errors)
            row = form.save(commit=False)
            self.assertIsNone(row.hrv_ms)
            self.assertIsNone(row.readiness)
        for name, field in self.form({}).fields.items():
            self.assertEqual(field.required, name in {"date", "moment"}, name)

    def test_form_and_model_preserve_historical_hrv_and_pain_requirements(self) -> None:
        for values, message in (
            ({"hrv_ms": "0"}, "Indica el método de medición HRV."),
            ({"hrv_ms": "42"}, "Indica el método de medición HRV."),
            ({"pain_score": "1"}, "Indica dónde sientes dolor."),
            ({"pain_score": "10"}, "Indica dónde sientes dolor."),
        ):
            with self.subTest(values=values):
                form = self.form(values)
                self.assertFalse(form.is_valid())
                self.assertIn(message, form.non_field_errors())
                with self.assertRaisesMessage(ValidationError, message):
                    form.instance.full_clean()
        for values in (
            {},
            {"pain_score": "0"},
            {"hrv_ms": "0", "hrv_method": "reloj"},
            {"hrv_ms": "42", "hrv_method": "reloj"},
            {"pain_score": "1", "pain_regions": "pierna"},
            {"pain_score": "10", "pain_regions": "pierna, espalda"},
            {"hrv_method": "reloj", "pain_regions": "pierna"},
        ):
            with self.subTest(values=values):
                form = self.form(values)
                self.assertTrue(form.is_valid(), form.errors)
                form.instance.full_clean()

    def test_form_help_explains_historical_dependencies(self) -> None:
        form = self.form({})
        for field in ("hrv_ms", "hrv_method"):
            self.assertIn("Si indicas HRV, indica también el método", form.fields[field].help_text)
        for field in ("pain_score", "pain_regions"):
            self.assertIn(
                "Si el dolor es mayor que 0, indica la zona", form.fields[field].help_text
            )
        response = self.client.get(self.new)
        self.assertContains(response, "Si indicas HRV, indica también el método")
        self.assertContains(response, "Si el dolor es mayor que 0, indica la zona")

    def test_form_scales_help_and_invalid_numbers_dates_moment(self) -> None:
        form = self.form({})
        for field in ("sleep_quality", "fatigue", "stress", "soreness", "readiness"):
            self.assertIn("1 =", form.fields[field].help_text)
            self.assertIn("5 =", form.fields[field].help_text)
            for value in ("0", "6", "bad"):
                invalid = self.form({field: value})
                self.assertFalse(invalid.is_valid())
                self.assertIn(field, invalid.errors)
        for values in (
            {"moment": "invalid"},
            {"date": "bad"},
            {"date": "2026-02-30"},
            {"date": (self.day + timedelta(days=1)).isoformat()},
            {"sleep_hours": "25"},
            {"pain_score": "11"},
            {"pain_score": "-1"},
            {"resting_hr_bpm": "19"},
            {"hrv_ms": "-1"},
        ):
            with self.subTest(values=values):
                self.assertFalse(self.form(values).is_valid())

    def test_duplicate_form_and_web_create_do_not_overwrite(self) -> None:
        row = Wellness.objects.create(owner_id=self.owner, moment="before", fatigue=2)
        form = self.form({"moment": "before"})
        self.assertFalse(form.is_valid())
        self.assertIn("Ya registraste un check-in", str(form.non_field_errors()))
        result = self.client.post(
            self.new, {"date": self.day.isoformat(), "moment": "before", "fatigue": 5}
        )
        self.assertContains(result, "Ya registraste un check-in")
        row.refresh_from_db()
        self.assertEqual(row.fatigue, 2)
        self.assertEqual(Wellness.objects.filter(owner_id=self.owner).count(), 1)
        self.assertTrue(self.form({"moment": "after"}).is_valid())
        self.assertTrue(self.form({"moment": "before"}, row).is_valid())

    def test_create_before_after_and_day_same_date_then_edit(self) -> None:
        for moment in ("before", "after", "day"):
            response = self.client.post(self.new, {"date": self.day.isoformat(), "moment": moment})
            self.assertRedirects(response, self.history)
        rows = Wellness.objects.filter(owner_id=self.owner)
        self.assertEqual(set(rows.values_list("moment", flat=True)), {"before", "after", "day"})
        self.assertFalse(Wellness.objects.filter(owner_id=self.other).exists())
        row = rows.get(moment="before")
        response = self.client.post(
            reverse("wellness-edit", args=[row.pk]),
            {"date": self.day.isoformat(), "moment": "before", "fatigue": 3},
        )
        self.assertRedirects(response, self.history)
        row.refresh_from_db()
        self.assertEqual(row.fatigue, 3)
        response = self.client.post(
            reverse("wellness-edit", args=[row.pk]),
            {"date": self.day.isoformat(), "moment": "after"},
        )
        self.assertContains(response, "Ya registraste un check-in")
        self.assertEqual(rows.count(), 3)

    def test_application_duplicate_is_spanish_error(self) -> None:
        row = Wellness.objects.create(owner_id=self.owner, moment="before")
        with self.assertRaisesMessage(InvalidAthleteData, "Ya registraste un check-in"):
            athletes().record_wellness(RecordWellness(AccountId(self.owner), wellness_data(row)))

    def test_unique_race_is_translated_after_savepoint(self) -> None:
        # Simulate a database uniqueness race after the preliminary duplicate query.
        data = wellness_data(Wellness(owner_id=self.owner, moment="before"))
        with (
            patch("django.db.models.query.QuerySet.exists", side_effect=[False, True]),
            patch("basis.modules.athletes.adapters.django.persist", side_effect=IntegrityError),
            self.assertRaisesMessage(InvalidAthleteData, "Ya registraste un check-in"),
        ):
            DjangoAthleteRecords().save_wellness(AccountId(self.owner), data, None)
        self.assertFalse(Wellness.objects.exists())

    def test_database_rejects_duplicate_owner_date_moment(self) -> None:
        Wellness.objects.create(owner_id=self.owner, date=self.day, moment="before")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Wellness.objects.bulk_create(
                [Wellness(owner_id=self.owner, date=self.day, moment="before")]
            )
        self.assertEqual(Wellness.objects.filter(owner_id=self.owner).count(), 1)

    def test_csrf_valid_token_allows_create_and_edit(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.get(self.new).status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post(
            self.new,
            {"date": self.day.isoformat(), "moment": "before", "csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)
        row = Wellness.objects.get(owner_id=self.owner)
        response = client.post(
            reverse("wellness-edit", args=[row.pk]),
            {
                "date": self.day.isoformat(),
                "moment": "before",
                "fatigue": 3,
                "csrfmiddlewaretoken": token,
            },
        )
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.fatigue, 3)

    def test_prefill_accepts_only_before_and_after(self) -> None:
        for value, expected in (("before", "before"), ("after", "after"), ("bad", "day")):
            response = self.client.get(self.new, {"moment": value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["form"].instance.moment, expected)

    def test_account_timezone_controls_prefill_validation_and_history_window(self) -> None:
        instant = datetime(2026, 1, 1, 2, tzinfo=datetime_timezone.utc)
        for zone, day in (
            ("America/New_York", date(2025, 12, 31)),
            ("Asia/Tokyo", date(2026, 1, 1)),
        ):
            with self.subTest(zone=zone):
                AthleteSettings.objects.filter(owner_id=self.owner).update(timezone_name=zone)
                with patch(
                    "basis.modules.athletes.adapters.local_dates.timezone.now", return_value=instant
                ):
                    new = self.client.get(self.new, {"moment": "before"})
                    self.assertEqual(new.context["form"].instance.date, day)
                    history = self.client.get(self.history)
                    self.assertEqual(history.context["form"].data["end"], day.isoformat())
                    self.assertEqual(
                        self.client.post(
                            self.new, {"date": day.isoformat(), "moment": "before"}
                        ).status_code,
                        302,
                    )
                    future = self.client.post(
                        self.new, {"date": (day + timedelta(days=1)).isoformat(), "moment": "after"}
                    )
                    self.assertEqual(future.status_code, 200)
                    self.assertTrue(future.context["form"].errors)

    def test_history_displays_all_private_fields_and_escapes_notes(self) -> None:
        Wellness.objects.create(
            owner_id=self.owner,
            moment="before",
            pain_score=2,
            pain_regions="rodilla",
            resting_hr_bpm=65,
            hrv_ms=Decimal("42.50"),
            hrv_method="medición manual",
            notes="<script>privado</script>",
        )
        response = self.client.get(self.history)
        for value in (
            "rodilla",
            "65",
            "42,50",
            "medición manual",
            "&lt;script&gt;privado&lt;/script&gt;",
        ):
            self.assertContains(response, value)
        self.assertNotContains(response, "<script>privado</script>")

    def test_login_csrf_and_foreign_edit_404(self) -> None:
        foreign = Wellness.objects.create(owner_id=self.other, notes="foreign-private")
        edit = reverse("wellness-edit", args=[foreign.pk])
        anonymous = Client()
        for url in (self.new, self.history, edit):
            self.assertEqual(anonymous.get(url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        for url in (self.new, edit):
            self.assertEqual(
                csrf.post(url, {"date": self.day.isoformat(), "moment": "day"}).status_code,
                403,
            )
        self.assertEqual(self.client.get(edit).status_code, 404)
        self.assertEqual(
            self.client.post(edit, {"date": self.day.isoformat(), "moment": "day"}).status_code,
            404,
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.notes, "foreign-private")

    @override_settings(DEVELOPMENT_ACCESS=False)
    def test_read_without_subscription_but_writes_keep_commercial_policy(self) -> None:
        self.assertEqual(self.client.get(self.history).status_code, 200)
        self.assertEqual(self.client.get(self.new).status_code, 403)

    def test_history_own_rows_all_scales_missing_zero_and_empty(self) -> None:
        own = Wellness.objects.create(owner_id=self.owner, moment="before", sleep_hours=0)
        after = Wellness.objects.create(owner_id=self.owner, moment="after", fatigue=5)
        Wellness.objects.create(owner_id=self.other, moment="before", readiness=4)
        response = self.client.get(self.history)
        self.assertEqual(list(response.context["wellness_records"]), [after, own])
        self.assertContains(response, "Antes de entrenar")
        self.assertContains(response, "Después de entrenar")
        self.assertContains(response, "Sin dato")
        self.assertContains(response, "<dd>0,0</dd>", html=True)
        for label in (
            "Sueño (h)",
            "Calidad del sueño (1–5)",
            "Fatiga (1–5)",
            "Estrés (1–5)",
            "Dolor muscular (1–5)",
            "Disposición (1–5)",
            "Dolor (0–10)",
        ):
            self.assertContains(response, label)
        self.assertContains(response, "Solo un registro para tu seguimiento")
        Wellness.objects.filter(owner_id=self.owner).delete()
        response = self.client.get(self.history)
        self.assertContains(response, "Sin registros para este rango")
        self.assertEqual(list(response.context["wellness_records"]), [])

    def test_history_default_and_explicit_inclusive_range(self) -> None:
        rows = [
            Wellness.objects.create(owner_id=self.owner, date=self.day - timedelta(days=offset))
            for offset in (0, 29, 30, 60)
        ]
        self.assertEqual(list(self.client.get(self.history).context["wellness_records"]), rows[:2])
        response = self.client.get(
            self.history,
            {"start": rows[3].date.isoformat(), "end": rows[2].date.isoformat()},
        )
        self.assertEqual(list(response.context["wellness_records"]), rows[2:])
        response = self.client.get(self.history, {"start": self.day.isoformat()})
        self.assertEqual(list(response.context["wellness_records"]), rows[:1])
        for params in (
            {"start": "invalid"},
            {"end": "2026-02-30"},
            {"start": ""},
            {"start": self.day.isoformat(), "end": rows[1].date.isoformat()},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.history, params)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(list(response.context["wellness_records"]), [])

    def test_presentation_coach_wire_and_export_keep_moments(self) -> None:
        # Deliberately create in reverse priority order.
        after = Wellness.objects.create(owner_id=self.owner, moment="after", fatigue=1)
        Wellness.objects.create(owner_id=self.owner, moment="before", fatigue=2)
        Wellness.objects.create(owner_id=self.owner, moment="day", fatigue=3)
        Wellness.objects.create(owner_id=self.other, moment="after", fatigue=5)
        reads = athlete_reads()
        selected = reads.wellness(AccountId(self.owner), self.day)
        assert selected is not None
        self.assertEqual((selected.moment, selected.fatigue), ("after", 1))
        self.assertIsNone(reads.wellness(AccountId(self.owner), self.day - timedelta(days=1)))
        self.assertEqual(
            [item.moment for item in reads.history(AccountId(self.owner)).wellness_records],
            ["after", "before", "day"],
        )
        encoded = encode_context(contexts().snapshot(AccountId(self.owner), "plan", None))
        self.assertEqual(mapping(encoded["wellness_latest"])["moment"], "after")
        self.assertEqual(encode_context(decode_context(encoded)), encoded)
        del mapping(encoded["wellness_latest"])["moment"]
        legacy = decode_context(encoded).athlete.wellness
        assert legacy is not None
        self.assertEqual(legacy.moment, "day")
        exported = cast(dict[str, object], json.loads(self.client.get(reverse("export")).content))
        rows = cast(list[dict[str, object]], exported["wellness"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["pk"], after.pk)
        self.assertEqual(
            {cast(dict[str, object], row["fields"])["moment"] for row in rows},
            {"after", "before", "day"},
        )

    def test_payload_values_never_appear_in_logs(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        root = logging.getLogger()
        root.addHandler(handler)
        sentinel = "synthetic-private-wellness-payload"
        try:
            for fatigue in ("1", "invalid"):
                self.client.post(
                    self.new,
                    {
                        "date": self.day.isoformat(),
                        "moment": "before",
                        "fatigue": fatigue,
                        "notes": sentinel,
                        "pain_regions": sentinel,
                        "hrv_method": sentinel,
                    },
                )
            self.client.get(self.history)
        finally:
            root.removeHandler(handler)
        self.assertNotIn(sentinel, output.getvalue())


class WellnessMigrationTests(TransactionTestCase):
    def test_existing_rows_keep_values_and_receive_day_moment(self) -> None:
        executor = MigrationExecutor(connection)
        previous = [("basis_athletes", "0003_sportprofile_threshold_kind_and_more")]
        targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(previous)
            old_apps = executor.loader.project_state(previous).apps
            user = old_apps.get_model("auth", "User").objects.create(username="migration-owner")
            row = old_apps.get_model("basis_athletes", "Wellness").objects.create(
                owner_id=user.pk, date=timezone.localdate(), sleep_hours=Decimal(0), pain_score=0
            )
            executor = MigrationExecutor(connection)
            executor.migrate(targets)
            migrated = (
                executor.loader.project_state(targets)
                .apps.get_model("basis_athletes", "Wellness")
                .objects.get(pk=row.pk)
            )
            self.assertEqual(migrated.moment, "day")
            self.assertEqual(migrated.owner_id, user.pk)
            self.assertEqual(migrated.date, row.date)
            self.assertEqual(migrated.sleep_hours, Decimal(0))
            self.assertEqual(migrated.pain_score, 0)
            self.assertIsNone(migrated.fatigue)
        finally:
            MigrationExecutor(connection).migrate(targets)
