"""MAM-620: private resumable setup, append-only observations and export scope."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import (
    Client,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from basis.bootstrap.athletes import athletes, personal_authorization
from basis.bootstrap.billing import billing
from basis.bootstrap.planning import planning
from basis.modules.athletes.adapters.django import (
    DjangoAthleteRecords,
    preferences_data,
    profile_data,
)
from basis.modules.athletes.adapters.models import AthleteSettings, Measurement, SportProfile
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.personal_access import DjangoPersonalAuthorization
from basis.modules.athletes.public import (
    EditPreferences,
    EditProfile,
    InvalidAthleteData,
    MeasuredRMData,
    MeasurementData,
    RecordMeasurement,
    RecordRM,
    RecordSport,
    SportData,
    validate_measurement,
)
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.coach.adapters.actions import enqueue
from basis.modules.coach.adapters.models import AIJob, UsagePeriod
from basis.modules.training.adapters.models import Goal, Session
from basis.modules.training.public import GoalData, SaveGoal
from basis.shared.identifiers import AccountId, ExerciseId

from .factories import account, exercise


class ProfileOnboardingTests(TestCase):
    def setUp(self) -> None:
        # Deliberately make the athlete and account PKs different.
        Athlete.objects.create(
            nombre="Unlinked", email="unlinked@example.test", fecha_inicio=timezone.localdate()
        )
        self.owner, self.other = account("setup-owner"), account("setup-other")
        self.client.force_login(self.owner)
        self.day = timezone.localdate()

    def measurement(self, **changes: str) -> dict[str, str]:
        return {
            "date": self.day.isoformat(),
            "weight_kg": "72.35",
            "unit": "kg",
            "notes": "manual",
            **changes,
        }

    def test_partial_setup_remains_readable_and_can_be_completed_later(self) -> None:
        AthleteSettings.objects.filter(owner=self.owner).update(availability=[])
        first = self.client.get("/profile/")
        self.assertContains(first, "Puedes completar tu configuración después")
        self.assertContains(first, "Sin medición fechada")
        self.assertFalse(first.context["configuration_ready"])
        response = self.client.post(
            "/records/goal/new/",
            {
                "title": "Mi meta medida",
                "sport": "running",
                "priority": "primary",
                "target_value": "5000",
                "target_unit": "m",
                "baseline_value": "0",
                "baseline_date": self.day.isoformat(),
                "target_date": (self.day + timedelta(days=30)).isoformat(),
            },
        )
        self.assertRedirects(response, "/profile/")
        response = self.client.post(
            "/profile/preferences/",
            {
                "availability": [1, 4],
                "minutes_per_session": "45",
                "equipment": "Banda",
                "limitations": "Sin saltos",
                "timezone_name": "America/Guayaquil",
                "owner": self.other.pk,
            },
        )
        self.assertRedirects(response, "/profile/")
        ready = self.client.get("/profile/")
        self.assertTrue(ready.context["configuration_ready"])
        for text in (
            "Mi meta medida",
            "Lunes, Jueves",
            "45 min",
            "Banda",
            "Sin saltos",
            "5000",
            "Línea base: 0",
        ):
            self.assertContains(ready, text)
        self.assertEqual(AthleteSettings.objects.get(owner=self.other).availability, [1, 3, 5])
        self.assertIsNone(Athlete.objects.get(account=self.owner).peso)
        self.assertFalse(Measurement.objects.exists())

    def test_weight_observations_append_even_on_same_day_and_never_change_training(self) -> None:
        session = Session.objects.create(
            owner=self.owner, title="Historic", date=self.day, duration_seconds=123
        )
        for weight in ("72.35", "71.80"):
            self.assertRedirects(
                self.client.post("/records/measurement/new/", self.measurement(weight_kg=weight)),
                "/profile/",
            )
        self.assertEqual(
            list(
                Measurement.objects.filter(owner=self.owner)
                .order_by("pk")
                .values_list("weight_kg", flat=True)
            ),
            [Decimal("72.35"), Decimal("71.80")],
        )
        self.assertContains(
            self.client.get("/profile/measurements/"), self.day.isoformat(), count=2
        )
        session.refresh_from_db()
        self.assertEqual(session.duration_seconds, 123)
        self.assertIsNone(Athlete.objects.get(account=self.owner).peso)

    def test_replacing_or_clearing_legacy_weight_archives_zero_without_inventing_date(self) -> None:
        for weight in ("0", "73.25", ""):
            result = self.client.post("/profile/edit/", {"nombre": "Owner", "peso": weight})
            self.assertRedirects(result, "/profile/")
        rows = list(Measurement.objects.filter(owner=self.owner).order_by("pk"))
        self.assertEqual([r.weight_kg for r in rows], [Decimal(0), Decimal("73.25")])
        self.assertTrue(all(r.date is None and r.origin == "legacy_profile" for r in rows))
        self.assertIsNone(Athlete.objects.get(account=self.owner).peso)
        self.assertContains(
            self.client.get("/profile/measurements/"), "Fecha de medición desconocida", count=2
        )
        self.assertContains(self.client.get("/profile/"), "Sin medición fechada")
        exported = self.client.get("/export/").json()["measurement"]
        self.assertEqual(
            [
                (r["fields"]["date"], r["fields"]["weight_kg"], r["fields"]["origin"])
                for r in exported
            ],
            [(None, "0.00", "legacy_profile"), (None, "73.25", "legacy_profile")],
        )

    def test_profile_archive_and_write_roll_back_together(self) -> None:
        profile = Athlete.objects.get(account=self.owner)
        profile.peso = Decimal("70")
        profile.save()
        with patch.object(
            DjangoAthleteRecords, "save_profile", side_effect=ValidationError("rejected")
        ):
            response = self.client.post("/profile/edit/", {"nombre": "Owner", "peso": "71"})
        self.assertContains(response, "rejected")
        self.assertFalse(Measurement.objects.exists())
        profile.refresh_from_db()
        self.assertEqual(profile.peso, Decimal("70"))

    def test_invalid_units_dates_and_zero_preserve_inputs_without_records(self) -> None:
        for payload in (
            self.measurement(unit="lb"),
            self.measurement(weight_kg="0"),
            self.measurement(date=(self.day + timedelta(days=1)).isoformat()),
            self.measurement(date="21/10/2026"),
            self.measurement(date=""),
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/records/measurement/new/", payload)
                self.assertContains(response, "data-error-summary")
                self.assertContains(response, 'value="manual"')
                self.assertFalse(Measurement.objects.exists())
        with self.assertRaises(InvalidAthleteData):
            validate_measurement(MeasurementData(self.day, Decimal("NaN"), ""), self.day)

    def test_malformed_weight_returns_bound_errors_and_can_be_corrected(self) -> None:
        BillingAccount.objects.filter(owner=self.owner).delete()
        for value in ("", "abc", "NaN", "Infinity", "1234567", "70.123"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/records/measurement/new/",
                    self.measurement(weight_kg=value, notes="preserve-invalid-weight"),
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].has_error("weight_kg"))
                self.assertEqual(response.context["form"].data["weight_kg"], value)
                self.assertEqual(
                    response.context["form"]["notes"].value(), "preserve-invalid-weight"
                )
                self.assertContains(response, "data-error-summary")
                self.assertFalse(Measurement.objects.exists())
        self.assertRedirects(
            self.client.post("/records/measurement/new/", self.measurement(weight_kg="70.25")),
            "/profile/",
        )
        self.assertEqual(Measurement.objects.get(owner=self.owner).weight_kg, Decimal("70.25"))

    def test_orm_rejects_missing_or_malformed_weight_without_bypassing_validation(self) -> None:
        for value in (
            None,
            "",
            "abc",
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("70.123"),
            Decimal("1234567"),
            Decimal("0"),
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                row = Measurement(owner=self.owner, date=self.day)
                # Deliberately simulate raw/partially assigned model state.
                setattr(row, "weight_kg", value)
                row.save()
        for origin in ("measured", "legacy_profile"):
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                Measurement.objects.create(owner=self.owner, date=None, origin=origin)
            with self.subTest(excluded_weight_origin=origin), self.assertRaises(ValidationError):
                Measurement(owner=self.owner, date=None, origin=origin).full_clean(
                    exclude=["weight_kg"]
                )
        with self.assertRaises(ValidationError):
            Measurement.objects.create(owner=self.owner, date="invalid", weight_kg="70.25")
        self.assertFalse(Measurement.objects.exists())
        snapshot = Measurement.objects.create(
            owner=self.owner, date=None, weight_kg=0, origin="legacy_profile"
        )
        self.assertEqual(snapshot.weight_kg, Decimal(0))
        self.assertIsNone(snapshot.date)
        measured = Measurement.objects.create(owner=self.owner, date=self.day, weight_kg="70.25")
        setattr(measured, "weight_kg", None)
        with self.assertRaises(ValidationError):
            measured.save(update_fields=["weight_kg"])
        measured.refresh_from_db()
        self.assertEqual(measured.weight_kg, Decimal("70.25"))

    def test_measurement_numeric_date_and_unit_boundaries_are_controlled(self) -> None:
        for changes in (
            {"weight_kg": "-0.01"},
            {"weight_kg": "0"},
            {"weight_kg": "0.001"},
            {"weight_kg": "500.01"},
            {"weight_kg": "999.99"},
            {"weight_kg": "-Infinity"},
            {"weight_kg": "sNaN"},
            {"date": ""},
            {"date": "not-a-date"},
            {"date": (self.day + timedelta(days=1)).isoformat()},
            {"unit": "lb"},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(
                    "/records/measurement/new/", self.measurement(**changes)
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(Measurement.objects.exists())
        for weight in ("0.01", "500.00"):
            self.assertRedirects(
                self.client.post("/records/measurement/new/", self.measurement(weight_kg=weight)),
                "/profile/",
            )
        self.assertEqual(
            list(
                Measurement.objects.filter(owner=self.owner)
                .order_by("pk")
                .values_list("weight_kg", flat=True)
            ),
            [Decimal("0.01"), Decimal("500.00")],
        )

    def test_measurement_spoofed_identifiers_and_origin_do_not_select_owner_or_update(self) -> None:
        foreign = Measurement.objects.create(owner=self.other, date=self.day, weight_kg=88)
        self.assertRedirects(
            self.client.post(
                "/records/measurement/new/",
                {
                    **self.measurement(),
                    "owner": self.other.pk,
                    "pk": foreign.pk,
                    "id": foreign.pk,
                    "origin": "legacy_profile",
                    "user_id": self.other.athlete.pk,
                },
            ),
            "/profile/",
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.weight_kg, 88)
        own = Measurement.objects.get(owner=self.owner)
        self.assertEqual(own.origin, "measured")

    def test_discipline_duplicate_returns_bound_form_and_edit_is_owner_scoped(self) -> None:
        payload = {"sport": "running", "experience": "beginner", "method": "nota conservada"}
        self.assertRedirects(self.client.post("/records/sport/new/", payload), "/profile/")
        duplicate = self.client.post("/records/sport/new/", payload)
        self.assertContains(duplicate, "Ya registraste esta disciplina")
        self.assertContains(duplicate, 'value="nota conservada"')
        own = SportProfile.objects.get(owner=self.owner)
        self.assertRedirects(
            self.client.post(
                f"/profile/sports/{own.pk}/edit/", {**payload, "experience": "advanced"}
            ),
            "/profile/",
        )
        own.refresh_from_db()
        self.assertEqual(own.experience, "advanced")
        foreign = SportProfile.objects.create(owner=self.other, sport="cycling")
        self.assertEqual(
            self.client.post(f"/profile/sports/{foreign.pk}/edit/", payload).status_code, 404
        )
        self.assertEqual(SportProfile.objects.filter(owner=self.owner).count(), 1)

    def test_threshold_unit_and_provenance_validation(self) -> None:
        payload = {
            "sport": "cycling",
            "experience": "beginner",
            "threshold": "200",
            "threshold_unit": "seconds_km",
            "measured_on": self.day.isoformat(),
            "method": "manual",
        }
        self.assertContains(
            self.client.post("/records/sport/new/", payload), "Unidad de umbral incompatible"
        )
        self.assertContains(
            self.client.post(
                "/records/sport/new/", {**payload, "threshold_unit": "watts", "method": ""}
            ),
            "Un umbral requiere",
        )
        self.assertContains(
            self.client.post(
                "/records/sport/new/",
                {
                    **payload,
                    "threshold_unit": "watts",
                    "measured_on": "2099-01-01",
                },
            ),
            "Una medición realizada no puede tener fecha futura",
        )
        self.assertContains(
            self.client.post(
                "/records/sport/new/",
                {
                    **payload,
                    "threshold_unit": "watts",
                    "measured_on": "21/10/2026",
                },
            ),
            "data-error-summary",
        )
        self.assertFalse(SportProfile.objects.exists())

    def test_read_history_export_privacy_and_no_password_or_tokens(self) -> None:
        Measurement.objects.create(
            owner=self.owner, date=self.day, weight_kg="72.35", notes="own-observation"
        )
        Measurement.objects.create(
            owner=self.other, date=self.day, weight_kg="88.88", notes="foreign-observation"
        )
        Goal.objects.create(owner=self.other, title="Foreign goal", sport="running")
        Session.objects.create(owner=self.other, title="Foreign session", date=self.day)
        Goal.objects.create(owner=self.owner, title="Own planned goal", sport="running")
        Session.objects.create(owner=self.owner, title="Own executed session", date=self.day)
        exported = self.client.get("/export/?owner=" + str(self.other.pk))
        payload = exported.json()
        self.assertEqual(payload["schema"], "basis-export-v1")
        self.assertEqual(len(payload["measurement"]), 1)
        self.assertEqual(payload["measurement"][0]["fields"]["weight_kg"], "72.35")
        self.assertEqual(payload["measurement"][0]["fields"]["date"], self.day.isoformat())
        self.assertEqual(len(payload["athlete"]), 1)
        self.assertEqual([r["fields"]["title"] for r in payload["goal"]], ["Own planned goal"])
        self.assertEqual(
            [r["fields"]["title"] for r in payload["session"]], ["Own executed session"]
        )
        text = exported.content.decode()
        for secret in (
            "foreign-observation",
            "Foreign goal",
            "Foreign session",
            self.owner.password,
            "password",
            "access_token",
            "refresh_token",
            "csrfmiddlewaretoken",
        ):
            self.assertNotIn(secret, text)
        self.assertNotContains(
            self.client.get("/profile/measurements/?owner=" + str(self.other.pk)),
            "foreign-observation",
        )
        self.assertNotContains(self.client.get("/profile/"), "Foreign goal")
        self.assertEqual(exported.headers["Cache-Control"], "private, no-store")

    def test_expired_access_still_reads_exports_and_only_personal_writes_are_free(self) -> None:
        BillingAccount.objects.filter(owner=self.owner).update(status="canceled")
        for path in ("/profile/", "/profile/measurements/", "/export/"):
            self.assertEqual(self.client.get(path).status_code, 200)
        for path in (
            "/measurements/rm/new/",
            "/records/goal/new/",
            "/records/wellness/new/",
            "/sessions/new/",
            "/plans/new/",
            "/scheduled/new/",
        ):
            self.assertEqual(self.client.post(path, {}).status_code, 403)
        self.assertRedirects(
            self.client.post(
                "/profile/edit/", {"nombre": "Free owner", "objetivos": "Caminar con constancia"}
            ),
            "/profile/",
        )
        self.assertRedirects(
            self.client.post("/records/measurement/new/", self.measurement()), "/profile/"
        )

    def test_anonymous_csrf_and_no_profile_never_create_implicit_identity(self) -> None:
        anonymous = Client()
        self.assertEqual(anonymous.get("/profile/measurements/").status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(
            strict.post("/records/measurement/new/", self.measurement()).status_code, 403
        )
        empty = get_user_model().objects.create_user(username="without-profile")
        self.client.force_login(empty)
        self.assertEqual(self.client.get("/profile/").status_code, 404)
        self.assertFalse(AthleteSettings.objects.filter(owner=empty).exists())

    def test_profile_fields_do_not_mutate_identity_and_invalid_age_retains_form(self) -> None:
        before = Athlete.objects.get(account=self.owner)
        response = self.client.post(
            "/profile/edit/",
            {
                "nombre": "Updated",
                "edad": "17",
                "email_verified": "1",
                "account": self.other.pk,
            },
        )
        self.assertContains(response, "personas adultas")
        self.assertContains(response, 'value="Updated"')
        self.assertRedirects(
            self.client.post(
                "/profile/edit/",
                {
                    "nombre": "Updated",
                    "edad": "",
                    "email": "injected@example.test",
                    "email_verified": "0",
                    "account": self.other.pk,
                    "fecha_inicio": "2099-01-01",
                },
            ),
            "/profile/",
        )
        after = Athlete.objects.get(account=self.owner)
        self.assertEqual(
            (
                after.pk,
                after.public_id,
                after.account_id,
                after.email,
                after.email_verified,
                after.fecha_inicio,
            ),
            (
                before.pk,
                before.public_id,
                before.account_id,
                before.email,
                before.email_verified,
                before.fecha_inicio,
            ),
        )


class FreePersonalAccessTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("free-personal")
        self.other = account("free-other")
        self.client.force_login(self.owner)
        self.day = timezone.localdate()

    def set_billing(self, state: str) -> None:
        if state == "absent":
            BillingAccount.objects.filter(owner=self.owner).delete()
        elif state == "expired":
            BillingAccount.objects.filter(owner=self.owner).update(
                status="active", period_end=timezone.now() - timedelta(seconds=1)
            )
        else:
            BillingAccount.objects.update_or_create(
                owner=self.owner,
                defaults={
                    "status": state,
                    "period_start": timezone.now() - timedelta(days=1),
                    "period_end": timezone.now() + timedelta(days=1),
                },
            )

    def test_http_personal_setup_is_free_without_trial_active_or_expired_subscription(self) -> None:
        for state in ("absent", "active", "expired", "canceled"):
            with self.subTest(state=state):
                self.set_billing(state)
                before = list(BillingAccount.objects.filter(owner=self.owner).values())
                self.assertRedirects(
                    self.client.post(
                        "/profile/edit/",
                        {
                            "nombre": "Free",
                            "objetivos": "Caminar con constancia",
                            "owner": self.other.pk,
                            "email_verified": "1",
                        },
                    ),
                    "/profile/",
                )
                self.assertRedirects(
                    self.client.post(
                        "/profile/preferences/",
                        {
                            "availability": [2, 6],
                            "minutes_per_session": "35",
                            "timezone_name": "UTC",
                            "equipment": "Banda",
                            "limitations": "Sin saltos",
                            "owner": self.other.pk,
                        },
                    ),
                    "/profile/",
                )
                self.assertRedirects(
                    self.client.post(
                        "/records/measurement/new/",
                        {
                            "date": self.day.isoformat(),
                            "weight_kg": "70.25",
                            "unit": "kg",
                            "owner": self.other.pk,
                        },
                    ),
                    "/profile/",
                )
                sport = SportProfile.objects.filter(owner=self.owner).first()
                path = f"/profile/sports/{sport.pk}/edit/" if sport else "/records/sport/new/"
                self.assertRedirects(
                    self.client.post(path, {"sport": "running", "experience": "beginner"}),
                    "/profile/",
                )
                self.assertEqual(self.client.get("/export/").status_code, 200)
                self.assertEqual(
                    list(BillingAccount.objects.filter(owner=self.owner).values()), before
                )
        self.assertEqual(Measurement.objects.filter(owner=self.owner).count(), 4)
        self.assertFalse(Measurement.objects.filter(owner=self.other).exists())
        self.assertFalse(AIJob.objects.exists())
        self.assertFalse(UsagePeriod.objects.exists())

    def test_use_cases_independently_allow_verified_personal_data_without_billing(self) -> None:
        self.set_billing("absent")
        service, owner = athletes(), AccountId(self.owner.pk)
        self.assertFalse(billing().can_write(owner))
        data = profile_data(Athlete.objects.get(account=self.owner))
        service.edit_profile(EditProfile(owner, replace(data, objetivos="Objetivo gratis")))
        prefs = preferences_data(AthleteSettings.objects.get(owner=self.owner))
        service.edit_preferences(EditPreferences(owner, replace(prefs, availability=(2,))))
        service.record_sport(
            RecordSport(owner, SportData("running", "beginner", None, "", None, ""))
        )
        service.record_measurement(
            RecordMeasurement(owner, MeasurementData(self.day, Decimal("70"), "free"))
        )
        self.assertEqual(Athlete.objects.get(account=self.owner).objetivos, "Objetivo gratis")
        self.assertFalse(BillingAccount.objects.filter(owner=self.owner).exists())

    def test_personal_text_goal_completes_free_setup_without_unlocking_plan_goal(self) -> None:
        self.set_billing("absent")
        self.assertRedirects(
            self.client.post(
                "/profile/edit/", {"nombre": "Free", "objetivos": "Mi dirección personal"}
            ),
            "/profile/",
        )
        page = self.client.get("/profile/")
        self.assertTrue(page.context["configuration_ready"])
        self.assertContains(page, "Mi dirección personal")
        self.assertContains(page, "Tu perfil personal es gratuito")
        self.assertContains(page, "requiere prueba o suscripción activa")
        self.assertNotContains(page, 'href="/records/goal/new/"')
        self.assertNotContains(page, 'href="/measurements/rm/new/"')
        self.assertContains(page, "Definir objetivo personal")
        self.assertEqual(self.client.post("/records/goal/new/", {}).status_code, 403)
        self.assertFalse(Goal.objects.exists())

    def test_unverified_and_inactive_account_are_denied_even_if_payload_or_object_says_verified(
        self,
    ) -> None:
        for state in ("unverified", "inactive"):
            with self.subTest(state=state):
                Athlete.objects.filter(account=self.owner).update(
                    email_verified=state != "unverified"
                )
                get_user_model().objects.filter(pk=self.owner.pk).update(
                    is_active=state != "inactive"
                )
                self.client.force_login(self.owner)
                self.assertEqual(
                    self.client.post(
                        "/profile/edit/", {"nombre": "Forged", "email_verified": "1"}
                    ).status_code,
                    403,
                )
                for path in (
                    "/profile/preferences/",
                    "/records/measurement/new/",
                    "/records/sport/new/",
                ):
                    self.assertEqual(
                        self.client.post(
                            path, {"email_verified": "1", "account": self.other.pk}
                        ).status_code,
                        403,
                    )
                with self.assertRaises(PermissionDenied):
                    personal_authorization().require(AccountId(self.owner.pk))
                data = profile_data(Athlete.objects.get(account=self.owner))
                with self.assertRaises(PermissionDenied):
                    athletes().edit_profile(
                        EditProfile(AccountId(self.owner.pk), replace(data, nombre="Forged"))
                    )
                prefs = preferences_data(AthleteSettings.objects.get(owner=self.owner))
                with self.assertRaises(PermissionDenied):
                    athletes().edit_preferences(EditPreferences(AccountId(self.owner.pk), prefs))
                with self.assertRaises(PermissionDenied):
                    athletes().record_sport(
                        RecordSport(
                            AccountId(self.owner.pk),
                            SportData("running", "beginner", None, "", None, ""),
                        )
                    )
                with self.assertRaises(PermissionDenied):
                    athletes().record_measurement(
                        RecordMeasurement(
                            AccountId(self.owner.pk),
                            MeasurementData(self.day, Decimal("70"), "denied"),
                        )
                    )
        self.assertFalse(Measurement.objects.exists())
        self.assertFalse(SportProfile.objects.exists())

    def test_unlinked_legacy_same_email_and_pk_are_not_authority_or_auto_enrollment(self) -> None:
        legacy = Athlete.objects.create(
            pk=9001,
            nombre="Legacy",
            email="legacy-free@example.test",
            fecha_inicio=self.day,
            email_verified=True,
        )
        owner = get_user_model().objects.create_user(
            pk=legacy.pk, username="legacy-free", email=legacy.email, is_active=True
        )
        self.client.force_login(owner)
        self.assertEqual(
            self.client.post(
                "/profile/edit/", {"nombre": "Claim", "email_verified": "1", "account": owner.pk}
            ).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            personal_authorization().require(AccountId(owner.pk))
        legacy.refresh_from_db()
        self.assertIsNone(legacy.account_id)
        self.assertFalse(AthleteSettings.objects.filter(owner=owner).exists())

    def test_anonymous_personal_writes_return_403_without_creating_rows(self) -> None:
        client = Client()
        for path in (
            "/profile/edit/",
            "/profile/preferences/",
            "/records/measurement/new/",
            "/records/sport/new/",
        ):
            self.assertEqual(client.post(path, {"email_verified": "1"}).status_code, 403)
        self.assertFalse(Measurement.objects.exists())

    def test_http_successful_check_does_not_replace_use_case_authorization(self) -> None:
        with patch.object(
            DjangoPersonalAuthorization,
            "require",
            side_effect=[None, PermissionDenied("verification changed")],
        ):
            self.assertEqual(
                self.client.post("/profile/edit/", {"nombre": "Must not persist"}).status_code, 403
            )
        self.assertNotEqual(Athlete.objects.get(account=self.owner).nombre, "Must not persist")

    @override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-live")
    def test_free_personal_access_never_unlocks_training_rm_planning_or_ai_reservations(
        self,
    ) -> None:
        self.set_billing("absent")
        for path in (
            "/measurements/rm/new/",
            "/sessions/new/",
            "/plans/new/",
            "/scheduled/new/",
            "/records/goal/new/",
            "/records/wellness/new/",
        ):
            self.assertEqual(self.client.post(path, {}).status_code, 403)
        item = exercise()
        with self.assertRaises(PermissionDenied):
            athletes().record_rm(
                RecordRM(
                    AccountId(self.owner.pk),
                    MeasuredRMData(ExerciseId(item.pk), Decimal(100), self.day),
                )
            )
        with self.assertRaises(PermissionDenied):
            planning().save_goal(
                SaveGoal(
                    AccountId(self.owner.pk),
                    GoalData("Paid", "running", "primary", None, None, None, "", None, ""),
                )
            )
        response = self.client.post(
            "/coach/ask/",
            {
                "kind": "short",
                "prompt": "Personal setup is not paid AI",
                "request_key": str(uuid4()),
            },
            follow=True,
        )
        self.assertContains(response, "La IA requiere una prueba o suscripción verificada en Polar")
        with self.assertRaisesMessage(
            ValidationError, "La IA requiere una prueba o suscripción verificada en Polar"
        ):
            enqueue(self.owner, "short", "Personal setup does not buy AI", uuid4())
        self.assertFalse(AIJob.objects.exists())
        self.assertFalse(UsagePeriod.objects.exists())
        self.assertFalse(billing().can_write(AccountId(self.owner.pk)))

    def test_unverified_profile_ui_keeps_read_export_and_explains_verification_without_write_ctas(
        self,
    ) -> None:
        Athlete.objects.filter(account=self.owner).update(email_verified=False)
        page = self.client.get("/profile/")
        self.assertContains(page, "Verifica tu correo con una cuenta activa")
        self.assertNotContains(page, 'href="/profile/edit/"')
        self.assertContains(page, 'href="/export/"')
        self.assertEqual(self.client.get("/export/").status_code, 200)


@skipUnlessDBFeature("has_select_for_update")
class ProfileConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.owner = account("profile-race")
        BillingAccount.objects.filter(owner=self.owner).delete()

    def parallel(self, operation: str) -> list[str]:
        barrier = threading.Barrier(2)

        def run(index: int) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                service, owner = athletes(), AccountId(self.owner.pk)
                if operation == "profile":
                    data = profile_data(Athlete.objects.get(account_id=owner))
                    service.edit_profile(
                        EditProfile(owner, replace(data, peso=Decimal(71 + index)))
                    )
                elif operation == "measurement":
                    service.record_measurement(
                        RecordMeasurement(
                            owner,
                            MeasurementData(timezone.localdate(), Decimal(71 + index), "parallel"),
                        )
                    )
                else:
                    try:
                        service.record_sport(
                            RecordSport(owner, SportData("running", "beginner", None, "", None, ""))
                        )
                    except InvalidAthleteData:
                        return "duplicate"
                return "saved"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_concurrent_profile_changes_preserve_every_replaced_weight(self) -> None:
        Athlete.objects.filter(account=self.owner).update(peso=70)
        self.assertEqual(self.parallel("profile"), ["saved", "saved"])
        history = list(
            Measurement.objects.filter(owner=self.owner).values_list("weight_kg", flat=True)
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(
            set(history + [Athlete.objects.get(account=self.owner).peso]),
            {Decimal(70), Decimal(71), Decimal(72)},
        )

    def test_concurrent_measurements_append_without_losing_same_day_observations(self) -> None:
        self.assertEqual(self.parallel("measurement"), ["saved", "saved"])
        self.assertEqual(Measurement.objects.filter(owner=self.owner, origin="measured").count(), 2)

    def test_concurrent_duplicate_discipline_is_a_domain_error_not_integrity_failure(self) -> None:
        self.assertCountEqual(self.parallel("sport"), ["saved", "duplicate"])
        self.assertEqual(SportProfile.objects.filter(owner=self.owner).count(), 1)


class ProfileMigrationTests(TransactionTestCase):
    def test_upgrade_from_final_initial_preserves_identity_settings_and_measurements(self) -> None:
        executor = MigrationExecutor(connection)
        target = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("basis_athletes", "0001_initial")])
            old = executor.loader.project_state([("basis_athletes", "0001_initial")]).apps
            owner = old.get_model("auth", "User").objects.create(username="migration-owner")
            profile = old.get_model("basis_athletes", "User").objects.create(
                account_id=owner.pk,
                nombre="Keep",
                email="migration@example.test",
                fecha_inicio=timezone.localdate(),
                email_verified=True,
                peso=0,
            )
            legacy = old.get_model("basis_athletes", "User").objects.create(
                nombre="Unlinked",
                email="legacy-migration@example.test",
                fecha_inicio=timezone.localdate(),
            )
            old.get_model("basis_athletes", "AthleteSettings").objects.create(
                owner_id=owner.pk, availability=[2, 6], minutes_per_session=35
            )
            row = old.get_model("basis_athletes", "Measurement").objects.create(
                owner_id=owner.pk, date=timezone.localdate(), weight_kg="70.50"
            )
            identity = (profile.pk, profile.public_id, profile.account_id, profile.email_verified)
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            saved = Athlete.objects.get(pk=profile.pk)
            self.assertEqual(
                (saved.pk, saved.public_id, saved.account_id, saved.email_verified), identity
            )
            self.assertEqual(saved.peso, 0)
            self.assertIsNone(Athlete.objects.get(pk=legacy.pk).account_id)
            self.assertEqual(AthleteSettings.objects.get(owner_id=owner.pk).availability, [2, 6])
            measured = Measurement.objects.get(pk=row.pk)
            self.assertEqual(
                (measured.owner_id, measured.weight_kg, measured.origin),
                (owner.pk, Decimal("70.50"), "measured"),
            )
            self.assertIsNotNone(measured.date)
        finally:
            MigrationExecutor(connection).migrate(target)
