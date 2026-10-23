"""MAM817: presentation and expiry conservation, complementing existing Polar tests."""

import copy
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.utils.formats import date_format

from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.coach.adapters.actions import enqueue
from basis.modules.coach.adapters.models import AIJob, UsagePeriod
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import session_snapshot
from basis.modules.training.adapters.models import Block

from .factories import account, session


@override_settings(DEVELOPMENT_ACCESS=False, AI_ENABLED=False)
class EntitlementPresentationTests(TestCase):
    def test_initial_date_is_conditional_without_fallback_and_keeps_end_and_portal(self) -> None:
        owner = account("date-owner")
        self.client.force_login(owner)
        start = datetime(2026, 10, 20, 18, 17, tzinfo=datetime_timezone.utc)
        end = start + timedelta(days=7)
        for status in ("active", "trialing", "inactive", "past_due", "canceled", "unpaid"):
            for initial in (start, None):
                with self.subTest(status=status, initial=initial):
                    BillingAccount.objects.filter(owner=owner).update(
                        status=status, period_start=initial, period_end=end
                    )
                    response = self.client.get("/billing/")
                    self.assertEqual(response.status_code, 200)
                    if status in ("active", "trialing") and initial is not None:
                        self.assertContains(response, "Inicio del período:")
                        self.assertContains(
                            response, date_format(timezone.localtime(start), "j M Y H:i")
                        )
                    else:
                        self.assertNotContains(response, "Inicio del período:")
                        self.assertNotContains(
                            response, date_format(timezone.localtime(start), "j M Y H:i")
                        )
                    self.assertContains(response, date_format(timezone.localtime(end), "j M Y H:i"))
                    self.assertContains(response, 'action="/billing/portal/"')
                    self.assertContains(response, "Gestionar o cancelar en Polar")
                    label = (
                        "Primer cobro al finalizar la prueba:"
                        if status == "trialing"
                        else "Próxima renovación:"
                    )
                    self.assertContains(response, label)

    def test_cancellation_label_and_absent_end_do_not_invent_dates(self) -> None:
        owner = account("cancel-date")
        self.client.force_login(owner)
        BillingAccount.objects.filter(owner=owner).update(cancel_at_period_end=True)
        self.assertContains(self.client.get("/billing/"), "Acceso hasta:")
        BillingAccount.objects.filter(owner=owner).update(period_start=None, period_end=None)
        response = self.client.get("/billing/")
        for label in ("Inicio del período:", "Acceso hasta:", "Próxima renovación:"):
            self.assertNotContains(response, label)
        self.assertContains(response, "Gestionar o cancelar en Polar")


@override_settings(DEVELOPMENT_ACCESS=False, AI_ENABLED=False)
class ExpiredConservationTests(TestCase):
    def test_expiry_rejects_the_same_new_operation_without_receipt_or_server_changes(self) -> None:
        owner, other = account("expired-owner"), account("expired-other")
        own = session(owner, sport="hiking")
        foreign = session(other)
        own.title = "Historial privado MAM817"
        own.save(update_fields=["title"])
        foreign.title = "Historial ajeno MAM817"
        foreign.save(update_fields=["title"])
        client = Client(enforce_csrf_checks=True)
        client.force_login(owner)
        snapshot_url = f"/api/sessions/{own.pk}/snapshot/"
        downloaded = client.get(snapshot_url)
        self.assertEqual(downloaded.status_code, 200)
        before = session_snapshot(own)
        payload = copy.deepcopy(before)
        payload["title"] = "Edición local pendiente MAM817"
        body = {
            "account": str(owner.athlete.public_id),
            "mutation_id": str(uuid4()),
            "created": 1792756800000,
            "session": payload,
        }
        original = copy.deepcopy(body)
        self.assertEqual(client.get("/api/csrf/").status_code, 200)
        token = client.cookies["csrftoken"].value
        BillingAccount.objects.filter(owner=owner).update(period_end=timezone.now())
        with (
            patch("basis.modules.billing.adapters.actions.polar_request") as polar,
            patch("basis.modules.coach.adapters.actions.httpx.Client") as provider,
        ):
            for _ in range(2):
                response = client.post(
                    "/api/sync/", body, content_type="application/json", HTTP_X_CSRFTOKEN=token
                )
                self.assertEqual(response.status_code, 403)
                self.assertIn("suscripción activa", response.json()["detail"])
                self.assertEqual(body, original)
                own.refresh_from_db()
                self.assertEqual(session_snapshot(own), before)
                self.assertFalse(SyncReceipt.objects.exists())
            polar.assert_not_called()
            provider.assert_not_called()
        self.assertEqual(client.get(snapshot_url).json()["session"], before)
        self.assertContains(client.get(f"/sessions/{own.pk}/"), own.title)
        exported = client.get("/export/")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual([row["pk"] for row in exported.json()["session"]], [str(own.pk)])
        self.assertNotIn(foreign.title, exported.content.decode())
        self.assertNotIn(payload["title"], exported.content.decode())
        self.assertEqual(Block.objects.get(session=own).actual, {})
        client.force_login(other)
        self.assertEqual(client.get(snapshot_url).status_code, 404)
        self.assertEqual(client.get(f"/sessions/{own.pk}/").status_code, 404)
        other_export = client.get("/export/")
        self.assertNotIn(own.title, other_export.content.decode())
        self.assertNotIn(str(own.pk), other_export.content.decode())
        client.get("/api/csrf/")
        response = client.post(
            "/api/sync/",
            body,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "La cola pertenece a otra cuenta."})
        self.assertFalse(SyncReceipt.objects.exists())
        own.refresh_from_db()
        self.assertEqual(session_snapshot(own), before)

    @override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-local-only")
    def test_repeated_quota_rejection_has_no_jobs_usage_changes_or_provider_calls(self) -> None:
        owner = account("quota-no-overcharge")
        first = enqueue(owner, "short", "Consulta sintética", uuid4())
        usage = first.usage_period
        usage.short_count = 200
        usage.save(update_fields=["short_count"])
        before = list(UsagePeriod.objects.values())
        with (
            patch("basis.modules.coach.adapters.actions.httpx.Client") as provider,
            patch("basis.modules.billing.adapters.actions.polar_request") as polar,
        ):
            for _ in range(3):
                with self.assertRaises(ValidationError):
                    enqueue(owner, "short", "Consulta rechazada", uuid4())
            provider.assert_not_called()
            polar.assert_not_called()
        self.assertEqual(AIJob.objects.count(), 1)
        self.assertEqual(list(UsagePeriod.objects.values()), before)
        usage.refresh_from_db()
        self.assertEqual(usage.spent, Decimal("0"))
        self.client.force_login(owner)
        response = self.client.get("/billing/")
        self.assertContains(response, "$5")
        self.assertContains(response, "Sin cargos automáticos por exceder el uso de IA.")
