"""MAM-819: manual hiking observations through web and the existing offline transport."""

from decimal import Decimal
from itertools import combinations
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.metrics import validate_metrics
from basis.modules.training.adapters.models import Block, Session
from basis.modules.training.adapters.web.forms import MetricsForm

from .contracts import session_snapshot
from .factories import account, session


def hiking_observations() -> dict[str, str]:
    return {
        "distance_m": "8000.50",
        "duration_seconds": "14400",
        "moving_seconds": "12000",
        "pause_seconds": "2400",
        "ascent_m": "800.25",
        "descent_m": "700.15",
        "start_altitude_m": "2000.10",
        "max_altitude_m": "2700.20",
        "end_altitude_m": "2100.20",
        "terrain": "Terreno manual ficticio 819",
        "difficulty_scale": "Escala declarada ficticia",
        "difficulty_grade": "Grado propio",
        "difficulty_source": "Fuente manual ficticia 819",
        "pack_kg": "6.25",
    }


class HikingTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("hiking819"), account("other-hiking819")
        self.client.force_login(self.owner)

    def rows_state(self) -> object:
        return (
            list(Session.objects.order_by("pk").values()),
            list(Block.objects.order_by("pk").values()),
            list(SyncReceipt.objects.order_by("pk").values()),
        )

    def test_form_units_decimal_pack_absence_and_difficulty_completeness(self) -> None:
        form = MetricsForm(sport="hiking")
        measured = hiking_observations()
        for key in measured:
            self.assertIn(key, form.fields)
            self.assertFalse(form.fields[key].required)
        for key, unit in (
            ("distance_m", "m"),
            ("duration_seconds", "s"),
            ("moving_seconds", "s"),
            ("pause_seconds", "s"),
            ("ascent_m", "m"),
            ("descent_m", "m"),
            ("start_altitude_m", "m"),
            ("max_altitude_m", "m"),
            ("end_altitude_m", "m"),
            ("pack_kg", "kg"),
        ):
            self.assertIn(f"({unit})", str(form.fields[key].label))
        for values in ({}, measured, {"pack_kg": "0"}, {"pack_kg": "6.255"}):
            submitted = MetricsForm(values, sport="hiking")
            self.assertTrue(submitted.is_valid(), submitted.errors)
            self.assertEqual(submitted.cleaned_data, validate_metrics("hiking", values))
        difficulty = {
            key: value for key, value in measured.items() if key.startswith("difficulty_")
        }
        for count in (1, 2):
            for keys in combinations(difficulty, count):
                values = {key: difficulty[key] for key in keys}
                with self.subTest(values=values):
                    self.assertFalse(MetricsForm(values, sport="hiking").is_valid())
                    with self.assertRaises(ValidationError):
                        validate_metrics("hiking", values)
        for key in difficulty:
            self.assertFalse(MetricsForm({**difficulty, key: "   "}, sport="hiking").is_valid())

    def test_real_web_create_edit_render_and_pack_is_independent_per_session(self) -> None:
        response = self.client.post(
            reverse("session-new"),
            {
                "owner": self.other.pk,
                "title": "Hiking manual ficticio 819",
                "date": timezone.localdate().isoformat(),
                "duration_protocol": "elapsed",
                "block-sport": "hiking",
                "block-title": "Salida ficticia 819",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        item = Session.objects.get()
        block = item.blocks.get()
        self.assertEqual(item.owner_id, self.owner.pk)
        self.assertEqual((block.target, block.actual), ({}, {}))
        measured = hiking_observations()
        response = self.client.post(
            reverse("block-metrics", args=[block.pk]), {**measured, "revision": item.revision}
        )
        self.assertEqual(response.status_code, 302, response.content)
        block.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(block.actual, measured)
        self.assertEqual(block.target, {})
        self.assertIsNone(item.duration_seconds)  # A block does not invent a session-wide summary.
        self.assertEqual(item.revision, 2)
        page = self.client.get(reverse("session-detail", args=[item.pk]))
        for text in (
            "Resultado real · registro manual",
            "8000.50 m",
            "14400 s",
            "12000 s",
            "2400 s",
            "800.25 m",
            "700.15 m",
            "2000.10 m",
            "2700.20 m",
            "2100.20 m",
            "6.25 kg",
            measured["terrain"],
            measured["difficulty_scale"],
            measured["difficulty_grade"],
            measured["difficulty_source"],
        ):
            self.assertContains(page, text)
        next_item = session(self.owner, sport="hiking")
        next_block = next_item.blocks.get()
        response = self.client.post(
            reverse("block-metrics", args=[next_block.pk]),
            {"pack_kg": "0", "revision": next_item.revision},
        )
        self.assertEqual(response.status_code, 302, response.content)
        next_block.refresh_from_db()
        block.refresh_from_db()
        self.assertEqual(next_block.actual, {"pack_kg": "0"})
        self.assertEqual(Decimal(block.actual["pack_kg"]), Decimal("6.25"))

    def test_invalid_web_sync_and_model_writes_leave_rows_and_receipts_unchanged(self) -> None:
        item = session(self.owner, sport="hiking")
        block = item.blocks.get()
        invalid_cases = (
            {**hiking_observations(), "descent_m": "700.14"},
            {"start_altitude_m": "2000", "max_altitude_m": "2500", "ascent_m": "499"},
            {"end_altitude_m": "2000", "max_altitude_m": "2500", "descent_m": "499"},
            {"start_altitude_m": "2000", "end_altitude_m": "2500", "ascent_m": "499"},
            {"start_altitude_m": "2500", "end_altitude_m": "2000", "descent_m": "499"},
            {"start_altitude_m": "2000", "max_altitude_m": "1999"},
            {"end_altitude_m": "2000", "max_altitude_m": "1999"},
            {"duration_seconds": "60", "moving_seconds": "50", "pause_seconds": "11"},
            {"duration_seconds": "-1"},
            {"moving_seconds": "-1"},
            {"pause_seconds": "-1"},
            {"pack_kg": "-0.01"},
            {"pack_kg": "NaN"},
            {"difficulty_source": "Fuente sin escala ni grado"},
        )
        for values in invalid_cases:
            with self.subTest(values=values):
                before = self.rows_state()
                response = self.client.post(
                    reverse("block-metrics", args=[block.pk]),
                    {**values, "revision": item.revision},
                )
                self.assertContains(response, "error")
                self.assertEqual(self.rows_state(), before)
                payload = session_snapshot(item)
                payload["blocks"][0]["actual"] = dict[str, object](values)
                response = self.client.post(
                    "/api/sync/",
                    {
                        "account": str(self.owner.athlete.public_id),
                        "mutation_id": str(uuid4()),
                        "session": payload,
                    },
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(self.rows_state(), before)
                block.actual = values
                with self.assertRaises(ValidationError):
                    block.save()
                self.assertEqual(self.rows_state(), before)

    def test_offline_snapshot_schema_sync_replay_and_account_isolation(self) -> None:
        item = session(self.owner, sport="hiking")
        block = item.blocks.get()
        schema = self.client.get("/offline/")
        for key in hiking_observations():
            self.assertContains(schema, f'"{key}"')
        prepared = self.client.get(reverse("snapshot-api", args=[item.pk]))
        self.assertEqual(prepared.json()["account"], str(self.owner.athlete.public_id))
        self.assertIn("no-store", prepared["Cache-Control"])
        payload = session_snapshot(item)
        payload["blocks"][0]["actual"] = dict[str, object](hiking_observations())
        body = {
            "account": str(self.owner.athlete.public_id),
            "mutation_id": str(uuid4()),
            "session": payload,
        }
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        replay = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(replay.json(), response.json())
        self.assertEqual(SyncReceipt.objects.count(), 1)
        block.refresh_from_db()
        self.assertEqual(block.actual, hiking_observations())
        downloaded = self.client.get(reverse("snapshot-api", args=[item.pk]))
        self.assertEqual(downloaded.json()["session"]["blocks"][0]["actual"], block.actual)
        self.assertContains(self.client.get("/export/"), hiking_observations()["terrain"])
        before = self.rows_state()
        self.client.force_login(self.other)
        for name, pk in (
            ("session-detail", item.pk),
            ("snapshot-api", item.pk),
            ("session-edit", item.pk),
            ("block-metrics", block.pk),
        ):
            with self.subTest(route=name):
                url = reverse(name, args=[pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                if name in ("session-edit", "block-metrics"):
                    self.assertEqual(
                        self.client.post(url, {"revision": 2, "pack_kg": "99"}).status_code,
                        404,
                    )
        for account_id, expected in (
            (str(self.owner.athlete.public_id), 403),
            (str(self.other.athlete.public_id), 400),
        ):
            body["account"], body["mutation_id"] = account_id, str(uuid4())
            denied = self.client.post("/api/sync/", body, content_type="application/json")
            self.assertEqual(denied.status_code, expected, denied.content)
            self.assertEqual(self.rows_state(), before)
        self.assertNotContains(self.client.get("/export/"), hiking_observations()["terrain"])
