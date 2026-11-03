"""MAM-820: trekking invariants across session updates."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from threading import Barrier
from typing import cast
from uuid import uuid4

from django.db import close_old_connections
from django.http import HttpResponse
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.models import TrekStage, TrekTrip

from .contracts import SessionDocument, session_snapshot
from .factories import account, session


class TrekkingMutationTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("trek820")
        self.client.force_login(self.owner)
        self.first = session(self.owner, sport="hiking", date=date(2026, 1, 1))
        self.second = session(self.owner, sport="hiking", date=date(2026, 1, 2))
        self.trip = TrekTrip.objects.create(owner=self.owner, title="Trek")
        TrekStage.objects.create(trip=self.trip, session=self.first, order=1)
        TrekStage.objects.create(trip=self.trip, session=self.second, order=2)

    def sync(self, payload: SessionDocument) -> HttpResponse:
        return cast(
            HttpResponse,
            self.client.post(
                "/api/sync/",
                {
                    "account": str(self.owner.athlete.public_id),
                    "mutation_id": str(uuid4()),
                    "session": payload,
                },
                content_type="application/json",
            ),
        )

    def test_sync_rejects_date_reversing_stages_atomically(self) -> None:
        payload = session_snapshot(self.first)
        payload["date"] = "2026-01-03"
        response = self.sync(payload)
        self.assertEqual(response.status_code, 400, response.content)
        self.first.refresh_from_db()
        self.assertEqual(self.first.date, date(2026, 1, 1))
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_sync_cannot_change_last_hiking_block_to_another_sport(self) -> None:
        payload = session_snapshot(self.first)
        payload["blocks"][0]["sport"] = "running"
        response = self.sync(payload)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.first.blocks.get().sport, "hiking")
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_edit_stage_private_preserves_journey_and_export(self) -> None:
        stage = self.trip.stages.get(order=1)
        url = f"/trekking/{self.trip.pk}/stages/{stage.pk}/edit/"
        response = self.client.post(
            url,
            {
                "order": 1,
                "overnight_altitude_m": "2300.25",
                "recovery_notes": "Descanso ficticio",
                "session": str(self.second.pk),
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        stage.refresh_from_db()
        self.assertEqual(stage.session_id, self.first.pk)
        self.assertEqual(str(stage.overnight_altitude_m), "2300.25")
        self.assertContains(self.client.get(f"/trekking/{self.trip.pk}/"), "Descanso ficticio")
        self.assertContains(self.client.get("/export/"), "Descanso ficticio")
        other = account("foreign820")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"order": 3}).status_code, 404)
        self.assertNotContains(self.client.get("/export/"), "Descanso ficticio")

    def test_valid_replacement_and_invalid_removal(self) -> None:
        payload = session_snapshot(self.first)
        payload["blocks"][0]["sport"] = "running"
        replacement = deepcopy(payload["blocks"][0])
        replacement.pop("id", None)
        replacement["sport"] = "hiking"
        replacement["order"] = 2
        payload["blocks"].append(replacement)
        response = self.sync(payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(self.first.blocks.values_list("sport", flat=True)), {"running", "hiking"}
        )

    def test_orm_date_reversal_rejected(self) -> None:
        from django.core.exceptions import ValidationError

        self.first.date = date(2026, 1, 3)
        with self.assertRaises(ValidationError):
            self.first.save()
        self.first.refresh_from_db()
        self.assertEqual(self.first.date, date(2026, 1, 1))

    def test_repair_session_previously_left_without_hiking(self) -> None:
        self.first.blocks.update(sport="running")  # reproduce previously persisted invalid data
        payload = session_snapshot(self.first)
        replacement = deepcopy(payload["blocks"][0])
        replacement.pop("id", None)
        replacement["sport"] = "hiking"
        replacement["order"] = 2
        payload["blocks"].append(replacement)
        response = self.sync(payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(self.first.blocks.filter(sport="hiking").exists())

    def test_direct_block_change_is_rejected(self) -> None:
        from django.core.exceptions import ValidationError

        block = self.first.blocks.get()
        block.sport = "running"
        with self.assertRaises(ValidationError):
            block.save()
        block.refresh_from_db()
        self.assertEqual(block.sport, "hiking")

    def test_stage_edit_revalidation_error_is_rendered(self) -> None:
        from unittest.mock import patch

        from django.core.exceptions import ValidationError

        stage = self.trip.stages.get(order=1)
        url = f"/trekking/{self.trip.pk}/stages/{stage.pk}/edit/"
        with patch("basis.modules.training.adapters.web.trekking.progress") as factory:
            factory.return_value.edit_stage.side_effect = ValidationError("Conflicto de etapas")
            response = self.client.post(
                url, {"order": 1, "overnight_altitude_m": "0", "recovery_notes": ""}
            )
        self.assertContains(response, "Conflicto de etapas")
        stage.refresh_from_db()
        self.assertIsNone(stage.overnight_altitude_m)

    def test_stage_new_revalidation_error_is_rendered(self) -> None:
        from unittest.mock import patch

        from django.core.exceptions import ValidationError

        third = session(self.owner, sport="hiking", date=date(2026, 1, 3))
        url = f"/trekking/{self.trip.pk}/stages/new/"
        with patch(
            "basis.modules.training.adapters.web.trekking.save_stage",
            side_effect=ValidationError("Conflicto de etapas"),
        ):
            response = self.client.post(
                url,
                {
                    "session": str(third.pk),
                    "order": 3,
                    "overnight_altitude_m": "",
                    "recovery_notes": "",
                },
            )
        self.assertContains(response, "Conflicto de etapas")
        self.assertEqual(self.trip.stages.count(), 2)

    def test_summary_labels_units_and_zero_are_human_readable(self) -> None:
        block = self.first.blocks.get()
        block.actual = {"distance_m": "0"}
        block.save()
        self.first.status = "completed"
        self.first.save()
        response = self.client.get(f"/trekking/{self.trip.pk}/")
        self.assertContains(response, "Distancia (m)")
        self.assertContains(response, "<dd>0</dd>", html=True)
        self.assertContains(response, "Sin datos")
        self.assertNotContains(response, "distance_m")


@skipUnlessDBFeature("has_select_for_update")
class TrekkingConcurrencyTests(TransactionTestCase):
    def test_concurrent_session_edits_preserve_stage_date_order(self) -> None:
        owner = account("concurrent820")
        first = session(owner, sport="hiking", date=date(2026, 1, 1))
        second = session(owner, sport="hiking", date=date(2026, 1, 3))
        trip = TrekTrip.objects.create(owner=owner, title="Trek")
        TrekStage.objects.create(trip=trip, session=first, order=1)
        TrekStage.objects.create(trip=trip, session=second, order=2)
        first_payload, second_payload = session_snapshot(first), session_snapshot(second)
        first_payload["date"] = "2026-01-03"
        second_payload["date"] = "2026-01-01"
        account_id = str(owner.athlete.public_id)
        gate = Barrier(2)

        def write(payload: SessionDocument) -> int:
            close_old_connections()
            try:
                client = Client()
                client.force_login(owner)
                gate.wait(timeout=10)
                response = client.post(
                    "/api/sync/",
                    {"account": account_id, "mutation_id": str(uuid4()), "session": payload},
                    content_type="application/json",
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, (first_payload, second_payload)))
        self.assertEqual(sorted(results), [200, 400])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLessEqual(first.date, second.date)
        self.assertEqual(SyncReceipt.objects.count(), 1)
