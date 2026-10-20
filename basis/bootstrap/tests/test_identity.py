"""ARCH-03 integration against temporary Django databases and existing web/API contracts."""

import re
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.accounts import identity
from basis.bootstrap.athletes import athletes
from basis.bootstrap.catalog import catalog
from basis.modules.accounts.adapters.django import DjangoVerification
from basis.modules.accounts.public import Account
from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    Wellness,
)
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.public import (
    AthleteUnavailable,
    MeasurementData,
    RecordMeasurement,
    RecordSport,
    RecordWellness,
    SportData,
    WellnessData,
)
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.catalog.adapters.record_actions import save_exercise
from basis.modules.catalog.public import CatalogDenied, DeleteClassification
from basis.shared.identifiers import AccountId, ClassificationId, SportProfileId, WellnessId
from tests_architecture.identity_contract import IdentityContract


def account(name: str = "owner", *, active: bool = True) -> int:
    row = get_user_model().objects.create_user(
        username=name,
        email=name + "@example.test",
        password="Example-password-824!",
        is_active=active,
    )
    Athlete.objects.create(
        account=row,
        nombre=name,
        email=row.email,
        fecha_inicio=timezone.localdate(),
        email_verified=active,
    )
    AthleteSettings.objects.create(owner=row)
    return row.pk


class DjangoIdentityTests(IdentityContract, TestCase):
    def setUp(self) -> None:
        self.service = identity()
        self.counts = lambda: (
            get_user_model().objects.count(),
            Athlete.objects.count(),
            BillingAccount.objects.count(),
        )
        self.fail_delivery = self.fail_mail
        self.token_for = self.token
        self.active = lambda id: get_user_model().objects.get(pk=id).is_active
        self.verified = lambda id: Athlete.objects.get(account_id=id).email_verified

    def fail_mail(self) -> None:
        failure = patch.object(DjangoVerification, "send", side_effect=OSError("test mail failure"))
        failure.start()
        self.addCleanup(failure.stop)

    def token(self, account: Account) -> str:
        return signing.dumps({"uid": account.id, "email": account.email}, salt="basis-verify")

    def test_verification_invalid_expired_and_mismatched_claims(self) -> None:
        owner = account(active=False)
        row = get_user_model().objects.get(pk=owner)
        token = self.token(Account(AccountId(owner), row.email, "owner", False))
        from django.urls import reverse

        assert self.client.get(reverse("verify-email", args=["invalid"])).status_code == 400
        with patch(
            "django.core.signing.time.time", return_value=timezone.now().timestamp() + 86401
        ):
            assert self.client.post(reverse("verify-email", args=[token])).status_code == 400
        mismatch = self.token(Account(AccountId(owner), "other@example.test", "owner", False))
        assert self.client.post(reverse("verify-email", args=[mismatch])).status_code == 404
        assert not get_user_model().objects.get(pk=owner).is_active

    def test_resend_is_non_enumerating_and_rate_limited(self) -> None:
        owner = account(active=False)
        from django.urls import reverse

        path = reverse("resend-verification")
        known = self.client.post(path, {"email": "owner@example.test"})
        unknown = self.client.post(path, {"email": "unknown@example.test"})
        assert known.status_code == unknown.status_code == 200
        assert known.context["title"] == unknown.context["title"]
        assert known.context["text"] == unknown.context["text"]
        assert len(mail.outbox) == 1
        for _ in range(3):
            assert self.client.post(path, {"email": "unknown@example.test"}).status_code == 200
        assert self.client.post(path, {"email": "owner@example.test"}).status_code == 429
        assert not get_user_model().objects.get(pk=owner).is_active

    def test_password_recovery_preserves_active_user_filter_and_one_use_token(self) -> None:
        owner = account()
        account("pending", active=False)
        from django.urls import reverse

        path = reverse("password_reset")
        responses = [
            self.client.post(path, {"email": email})
            for email in ("missing@example.test", "pending@example.test", "owner@example.test")
        ]
        assert all(response.status_code == 302 for response in responses)
        assert len(mail.outbox) == 1
        link = re.search(r"https?://[^/]+([^\s]+)", str(mail.outbox[0].body))
        assert link is not None
        first = self.client.get(link.group(1))
        assert first.status_code == 302
        reset_path = first.headers["Location"]
        result = self.client.post(
            reset_path,
            {"new_password1": "Other-password-932!", "new_password2": "Other-password-932!"},
        )
        assert result.status_code == 302
        assert get_user_model().objects.get(pk=owner).check_password("Other-password-932!")
        assert self.client.get(link.group(1)).status_code == 200
        assert not self.client.get(link.group(1)).context["validlink"]

    def test_registration_hashes_password_and_creates_no_session(self) -> None:
        result = self.client.post(
            "/accounts/signup/",
            {
                "email": "NEW@example.test",
                "name": "New",
                "adult": "on",
                "password1": "Example-password-824!",
                "password2": "Example-password-824!",
            },
        )
        assert result.status_code == 200
        row = get_user_model().objects.get(username="new@example.test")
        assert row.check_password("Example-password-824!")
        assert not row.is_active and "_auth_user_id" not in self.client.session
        assert row.athlete.email == row.email
        assert BillingAccount.objects.filter(owner=row).exists()

    def test_explicit_link_preserves_history_and_does_not_verify_email(self) -> None:
        owner = get_user_model().objects.create_user(
            username="operator-target", email="legacy@example.test"
        )
        legacy = Athlete.objects.create(
            nombre="Legacy", email=owner.email, fecha_inicio=timezone.localdate()
        )
        call_command("link_legacy_profile", account_id=owner.pk, profile_id=legacy.pk, verbosity=0)
        legacy.refresh_from_db()
        assert legacy.account_id == owner.pk and not legacy.email_verified
        other = get_user_model().objects.create_user(username="other", email=owner.email)
        with self.assertRaises(CommandError):
            call_command(
                "link_legacy_profile", account_id=other.pk, profile_id=legacy.pk, verbosity=0
            )
        legacy.refresh_from_db()
        assert legacy.account_id == owner.pk


@override_settings(DEVELOPMENT_ACCESS=True)
class AthleteIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.owner = account()
        self.other = account("other")
        self.client.force_login(get_user_model().objects.get(pk=self.owner))

    def test_profile_and_preferences_forms_change_only_owner(self) -> None:
        result = self.client.post(
            "/profile/edit/", {"nombre": "  new name  ", "edad": 30, "peso": "0"}
        )
        assert result.status_code == 302
        profile = Athlete.objects.get(account_id=self.owner)
        assert profile.nombre == "New Name" and profile.peso == Decimal(0)
        assert Athlete.objects.get(account_id=self.other).nombre == "other"
        result = self.client.post(
            "/profile/preferences/",
            {
                "availability": [1, 4],
                "minutes_per_session": 45,
                "equipment": "bar",
                "timezone_name": "America/Guayaquil",
            },
        )
        assert result.status_code == 302
        assert AthleteSettings.objects.get(owner_id=self.owner).availability == [1, 4]
        assert AthleteSettings.objects.get(owner_id=self.other).availability == []

    def test_wellness_web_update_preserves_identifier_zero_and_missing(self) -> None:
        day = timezone.localdate()
        for notes in ("first", "second"):
            result = self.client.post(
                "/records/wellness/new/",
                {"date": day.isoformat(), "sleep_hours": "0", "pain_score": "0", "notes": notes},
            )
            assert result.status_code == 302
        row = Wellness.objects.get(owner_id=self.owner)
        assert row.sleep_hours == Decimal(0) and row.pain_score == 0
        assert row.hrv_ms is None and row.fatigue is None and row.notes == "second"
        assert not Wellness.objects.filter(owner_id=self.other).exists()

    def test_use_cases_reject_foreign_observation_ids(self) -> None:
        day = timezone.localdate()
        sport = SportProfile.objects.create(owner_id=self.other, sport="running")
        wellness = Wellness.objects.create(owner_id=self.other, date=day)
        service = athletes()
        with self.assertRaises(AthleteUnavailable):
            service.record_sport(
                RecordSport(
                    AccountId(self.owner),
                    SportData("running", "advanced", None, "", None, ""),
                    SportProfileId(sport.pk),
                )
            )
        with self.assertRaises(AthleteUnavailable):
            service.record_wellness(
                RecordWellness(
                    AccountId(self.owner),
                    WellnessData(
                        day, None, None, None, None, None, None, "", None, None, None, "", ""
                    ),
                    WellnessId(wellness.pk),
                )
            )
        sport.refresh_from_db()
        assert sport.experience == "beginner"
        assert not SportProfile.objects.filter(owner_id=self.owner).exists()

    def test_invalid_measurement_rolls_back_and_valid_decimal_keeps_owner(self) -> None:
        service = athletes()
        with self.assertRaises(ValidationError):
            service.record_measurement(
                RecordMeasurement(
                    AccountId(self.owner),
                    MeasurementData(timezone.localdate(), Decimal(0), "invalid"),
                )
            )
        assert not Measurement.objects.exists()
        id = service.record_measurement(
            RecordMeasurement(
                AccountId(self.owner),
                MeasurementData(timezone.localdate(), Decimal("72.35"), "measured"),
            )
        )
        row = Measurement.objects.get(pk=id)
        assert row.owner_id == self.owner and row.weight_kg == Decimal("72.35")


class CatalogIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.owner = account()
        self.user = get_user_model().objects.get(pk=self.owner)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)

    def test_staff_create_partial_update_archive_and_read_visibility(self) -> None:
        classification = self.client.post(
            "/api/v1/classifications/", {"nombre": "  lower body  "}
        ).json()
        assert classification["nombre"] == "Lower Body"
        response = self.client.post(
            "/api/v1/exercises/",
            {
                "nombre": "squat",
                "classification_id": classification["id"],
                "musculos_principales": ["quads"],
            },
            content_type="application/json",
        )
        assert response.status_code == 201
        id = response.json()["id"]
        response = self.client.patch(
            f"/api/v1/exercises/{id}/", {"archivado": True}, content_type="application/json"
        )
        assert response.status_code == 200 and response.json()["classification"] == classification
        assert self.client.get(f"/api/v1/exercises/{id}/").status_code == 404
        assert Exercise.objects.get(pk=id).nombre == "Squat"

    def test_protected_delete_rolls_back_and_nonstaff_service_cannot_delete(self) -> None:
        classification = Classification.objects.create(nombre="Strength")
        Exercise.objects.create(classification=classification, nombre="Squat")
        command = DeleteClassification(AccountId(self.owner), ClassificationId(classification.pk))
        with self.assertRaises(ProtectedError):
            catalog().delete_classification(command)
        assert Classification.objects.filter(pk=classification.pk).exists()
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        with self.assertRaises(CatalogDenied):
            catalog().delete_classification(command)

    def test_json_muscle_shape_is_validated_before_tuple_conversion(self) -> None:
        classification = Classification.objects.create(nombre="Strength")
        for invalid in ("quads", {"quads": True}, ["x" * 81]):
            with self.assertRaises(ValidationError):
                save_exercise(
                    self.owner,
                    {
                        "nombre": "Squat",
                        "classification": classification,
                        "musculos_principales": invalid,
                    },
                )
        assert not Exercise.objects.exists()
