"""MAM814 manual swimming: independent pace, real forms, privacy and block authority."""

import json
from copy import deepcopy
from decimal import Decimal
from typing import cast
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.metrics import pace_seconds_legacy, validate_metrics
from basis.modules.training.adapters.models import Block, Interval, Session
from basis.modules.training.adapters.templatetags.training_tags import metric_rows
from basis.modules.training.adapters.web.forms import MetricsForm
from basis.modules.training.domain.sports import pace_seconds

from .contracts import build_plan, progress_report, required, session_snapshot, sync_session
from .factories import account, proposal, session


class SwimmingTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("fictitious-swimming814"), account("fictitious-other814")
        self.client.force_login(self.owner)

    def rows_state(self) -> object:
        return (
            list(Session.objects.order_by("pk").values()),
            list(Block.objects.order_by("pk").values()),
            list(Interval.objects.order_by("pk").values()),
            list(SyncReceipt.objects.order_by("pk").values()),
        )

    def prescribe(self) -> Block:
        data = proposal(self.owner)
        data["sessions"][0]["blocks"] = [
            {
                "sport": "swimming",
                "title": "PRIVATE-SWIMMING-814",
                "target": {
                    "distance_m": "800",
                    "duration_seconds": "1200",
                    "pool_length_m": "25",
                    "laps": "32",
                    "stroke": "Crol propio",
                    "drill": "Técnica manual ficticia",
                },
                "intervals": [
                    {
                        "repetitions": 4,
                        "rest_seconds": 60,
                        "target": {"distance_m": "50", "duration_seconds": "100"},
                    }
                ],
            }
        ]
        return build_plan(self.owner, data).sessions.get().blocks.get()

    def send(self, item: Session, actual: dict[str, object]) -> HttpResponse:
        item.refresh_from_db()
        payload = session_snapshot(item)
        payload["blocks"][0]["actual"] = actual
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

    def test_pace_literals_domain_adapter_block_interval_source_parity(self) -> None:
        for distance, duration, expected in (
            (None, None, None),
            (None, "0", None),
            ("800", None, None),
            ("0", "1200", None),
            ("0", "0", None),
            ("800", "0", "0.00"),
            ("800", "1200", "150.00"),
            ("50", "100", "200.00"),
            ("3", "1", "33.33"),
            ("32", "1", "3.12"),
        ):
            with self.subTest(distance=distance, duration=duration):
                values = {
                    key: value
                    for key, value in (("distance_m", distance), ("duration_seconds", duration))
                    if value is not None
                }
                expected_value = None if expected is None else Decimal(expected)
                self.assertEqual(
                    pace_seconds(
                        None if distance is None else Decimal(distance),
                        None if duration is None else Decimal(duration),
                        per_metres=100,
                    ),
                    expected_value,
                )
                self.assertEqual(pace_seconds_legacy(values, per_metres=100), expected_value)
                block = Block(sport="swimming", target=values, actual=values)
                interval = Interval(block=block, target=values, actual=values)
                for row in (block, interval):
                    for source in ("target", "actual"):
                        self.assertEqual(
                            metric_rows(row, source)[-1],
                            {
                                "label": "Ritmo derivado transcurrido",
                                "value": expected_value,
                                "unit": "s/100 m",
                            },
                        )
        for sport, unit, expected_pace in (
            ("running", "s/km", Decimal("1500.00")),
            ("swimming", "s/100 m", Decimal("150.00")),
        ):
            block = Block(sport=sport, actual={"distance_m": "800", "duration_seconds": "1200"})
            self.assertEqual(metric_rows(block)[-1]["unit"], unit)
            self.assertEqual(metric_rows(block)[-1]["value"], expected_pace)
        for sport in ("cardio", "cycling", "hiking", "strength"):
            self.assertEqual(metric_rows(Block(sport=sport)), [])

    def test_null_empty_zero_no_fallback_no_lap_inference_and_spanish(self) -> None:
        target = {"distance_m": "800", "duration_seconds": "1200"}
        for actual, expected in (
            ({}, None),
            ({"distance_m": "800", "duration_seconds": None}, None),
            ({"distance_m": "800", "duration_seconds": ""}, None),
            ({"distance_m": None, "duration_seconds": "1200"}, None),
            ({"distance_m": "", "duration_seconds": "1200"}, None),
            ({"distance_m": "0", "duration_seconds": "1200"}, None),
            ({"laps": "32", "pool_length_m": "25", "duration_seconds": "1200"}, None),
            ({"distance_m": "800", "duration_seconds": "0", "strokes": "0"}, Decimal("0.00")),
        ):
            block = Block(sport="swimming", target=target, actual=actual)
            interval = Interval(block=block, target=target, actual=actual, actual_rest_seconds=60)
            for row in (block, interval):
                self.assertEqual(metric_rows(row)[-1]["value"], expected)
                self.assertEqual(metric_rows(row, "target")[-1]["value"], Decimal("150.00"))
                html = render_to_string("training/execution/_metrics.html", {"block": row})
                for text in (
                    "Objetivo / prescripción",
                    "Resultado real · registro manual",
                    "no se restan",
                    "totales del bloque son autoritativos",
                    "no se suman de nuevo",
                    "No se infiere distancia",
                ):
                    self.assertIn(text, html)
                self.assertNotIn("None", html)
                self.assertEqual("— s/100 m" in html, expected is None)
        unsafe = Block(sport="swimming", actual={"stroke": "<script>alert(1)</script>"})
        html = render_to_string("training/execution/_metrics.html", {"block": unsafe})
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_form_units_validation_ranges_counts_text_and_optional_hr(self) -> None:
        form = MetricsForm(sport="swimming")
        for key, unit in (("distance_m", "m"), ("duration_seconds", "s"), ("pool_length_m", "m")):
            self.assertIn(f"({unit})", str(form.fields[key].label))
        for field in form.fields.values():
            self.assertFalse(field.required)
        for values in (
            {},
            {"heart_rate_bpm": None},
            {"heart_rate_bpm": "0", "max_heart_rate_bpm": "0"},
            {"heart_rate_bpm": "150", "max_heart_rate_bpm": "160"},
            {"laps": "0", "strokes": "0", "pool_length_m": "0"},
            {"laps": "10000", "strokes": "100000", "pool_length_m": "100"},
            {"distance_m": "1000000", "duration_seconds": "1000000"},
            {"stroke": "  Estilo libre propio  ", "drill": "  Remadas ficticias  "},
        ):
            with self.subTest(values=values):
                submitted = MetricsForm(values, sport="swimming")
                self.assertTrue(submitted.is_valid(), submitted.errors)
                self.assertEqual(submitted.cleaned_data, validate_metrics("swimming", values))
        invalid_cases: tuple[dict[str, object], ...] = (
            {"laps": "1.5"},
            {"strokes": "2.1"},
            {"laps": "10001"},
            {"strokes": "100001"},
            {"pool_length_m": "101"},
            {"distance_m": "1000001"},
            {"duration_seconds": "-1"},
            {"distance_m": "NaN"},
            {"distance_m": "Infinity"},
            {"distance_m": "800 m"},
            {"heart_rate_bpm": "251"},
            {"heart_rate_bpm": "160", "max_heart_rate_bpm": "150"},
            {"stroke": "x" * 501},
            {"drill": "x" * 501},
        )
        for invalid_values in invalid_cases:
            with self.subTest(values=invalid_values):
                self.assertFalse(MetricsForm(invalid_values, sport="swimming").is_valid())
                with self.assertRaises(ValidationError):
                    validate_metrics("swimming", invalid_values)
        for invalid_value in (
            {"laps": True},
            {"strokes": False},
            {"power_w": 1},
            {"distance_km": 1},
        ):
            with self.assertRaises(ValidationError):
                validate_metrics("swimming", invalid_value)

    def test_real_http_create_edit_interval_and_explicit_zero(self) -> None:
        response = self.client.post(
            reverse("session-new"),
            {
                "owner": self.other.pk,
                "title": "Natación manual ficticia",
                "date": timezone.localdate().isoformat(),
                "duration_protocol": "elapsed",
                "block-sport": "swimming",
                "block-title": "Piscina ficticia",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        item = Session.objects.get()
        block = item.blocks.get()
        self.assertEqual(item.owner_id, self.owner.pk)
        self.assertEqual((block.target, block.actual), ({}, {}))
        self.assertContains(self.client.get(reverse("session-detail", args=[item.pk])), "— s/100 m")
        measured = {
            "duration_seconds": "1200",
            "distance_m": "800",
            "pool_length_m": "25",
            "laps": "31",
            "strokes": "0",
            "stroke": "Crol propio",
            "drill": "Remadas ficticias",
        }
        response = self.client.post(
            reverse("block-metrics", args=[block.pk]), {**measured, "revision": item.revision}
        )
        self.assertEqual(response.status_code, 302, response.content)
        block.refresh_from_db()
        self.assertEqual(block.actual, measured)
        self.assertNotIn("heart_rate_bpm", block.actual)
        item.refresh_from_db()
        response = self.client.post(
            reverse("interval-new", args=[block.pk]),
            {
                "revision": item.revision,
                "repetitions": 4,
                "rest_seconds": 60,
                "target-duration_seconds": "100",
                "target-distance_m": "50",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        interval = block.intervals.get()
        self.assertEqual(interval.actual, {})
        self.assertIsNone(interval.actual_rest_seconds)
        item.refresh_from_db()
        response = self.client.post(
            reverse("interval-edit", args=[interval.pk]),
            {
                "revision": item.revision,
                "repetitions": 4,
                "rest_seconds": 60,
                "actual_rest_seconds": 0,
                "metrics-duration_seconds": "120",
                "metrics-distance_m": "50",
                "metrics-strokes": "0",
                "metrics-heart_rate_bpm": "0",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        interval.refresh_from_db()
        self.assertEqual(interval.target, {"duration_seconds": "100", "distance_m": "50"})
        self.assertEqual(interval.actual_rest_seconds, 0)
        self.assertEqual(interval.actual["heart_rate_bpm"], "0")
        page = self.client.get(reverse("session-detail", args=[item.pk]))
        for text in ("150,00 s/100 m", "200,00 s/100 m", "240,00 s/100 m", "no se restan"):
            self.assertContains(page, text)
        self.assertContains(page, "4 repeticiones")
        self.assertNotContains(page, "<pre>")

    def test_plan_copy_disabled_intent_and_completed_immutability(self) -> None:
        source = self.prescribe()
        original = deepcopy(source.target)
        original_interval = source.intervals.get()
        planned = required(source.planned)
        response = self.client.post(reverse("scheduled-start", args=[planned.pk]))
        self.assertEqual(response.status_code, 302, response.content)
        item = Session.objects.get(planned=planned)
        block = item.blocks.get()
        interval = block.intervals.get()
        self.assertEqual((block.source_id, interval.source_id), (source.pk, original_interval.pk))
        self.assertEqual(block.target, original)
        self.assertEqual((block.actual, interval.actual), ({}, {}))
        self.assertEqual((interval.rest_seconds, interval.actual_rest_seconds), (60, None))
        self.assertIsNone(metric_rows(block)[-1]["value"])
        self.assertIsNone(metric_rows(interval)[-1]["value"])
        response = self.client.post(
            reverse("interval-edit", args=[interval.pk]),
            {
                "revision": item.revision,
                "repetitions": 99,
                "rest_seconds": 999,
                "actual_rest_seconds": 30,
                "metrics-distance_m": "50",
                "metrics-duration_seconds": "120",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        interval.refresh_from_db()
        self.assertEqual((interval.repetitions, interval.rest_seconds), (4, 60))
        self.assertEqual(interval.target, original_interval.target)
        self.assertEqual(interval.actual_rest_seconds, 30)
        self.assertEqual(metric_rows(interval)[-1]["value"], Decimal("240.00"))
        item.refresh_from_db()
        payload = session_snapshot(item)
        payload["status"] = "completed"
        sync_session(self.owner, uuid4(), payload)
        item.refresh_from_db()
        before = self.rows_state()
        response = self.client.post(
            reverse("block-metrics", args=[block.pk]),
            {"revision": item.revision, "distance_m": "999"},
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.rows_state(), before)
        source.refresh_from_db()
        self.assertEqual(source.target, original)
        self.assertEqual(source.actual, {})
        self.assertEqual(source.intervals.get().actual, {})

    def test_prefetched_interval_rows_render_without_queries(self) -> None:
        item = session(self.owner, sport="swimming")
        block = item.blocks.get()
        for order in range(1, 4):
            Interval.objects.create(
                block=block,
                order=order,
                target={"distance_m": "50", "duration_seconds": "100"},
                actual={"distance_m": "800", "duration_seconds": "1200"},
            )
        prefetched = Session.objects.prefetch_related("blocks__intervals").get(pk=item.pk)
        with self.assertNumQueries(0):
            copied = list(prefetched.blocks.all())[0]
            html = render_to_string("training/execution/_intervals.html", {"block": copied})
            self.assertEqual(html.count("200,00 s/100 m"), 3)
            self.assertEqual(html.count("150,00 s/100 m"), 3)

    def test_sync_export_and_foreign_denial_leave_all_rows_and_receipts_unchanged(self) -> None:
        source = self.prescribe()
        item = start_session(self.owner, required(source.planned))
        block = item.blocks.get()
        interval = block.intervals.get()
        payload = session_snapshot(item)
        payload["blocks"][0]["actual"] = {
            "distance_m": "800",
            "duration_seconds": "1200",
            "pool_length_m": "25",
            "laps": "32",
            "stroke": "PRIVATE-STROKE-814",
            "drill": "PRIVATE-DRILL-814",
            "strokes": "0",
            "heart_rate_bpm": None,
        }
        payload["blocks"][0]["intervals"][0]["actual"] = {
            "distance_m": "50",
            "duration_seconds": "0",
        }
        body = {
            "account": str(self.owner.athlete.public_id),
            "owner": self.other.pk,
            "mutation_id": str(uuid4()),
            "session": payload,
        }
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        replay = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(json.loads(replay.content), json.loads(response.content))
        block.refresh_from_db()
        interval.refresh_from_db()
        self.assertEqual(block.owner_id, self.owner.pk)
        self.assertNotIn("heart_rate_bpm", block.actual)
        self.assertEqual(block.actual["strokes"], "0")
        self.assertEqual(metric_rows(interval)[-1]["value"], Decimal("0.00"))
        exported = self.client.get("/export/")
        for text in ("PRIVATE-SWIMMING-814", "PRIVATE-STROKE-814", "PRIVATE-DRILL-814", "laps"):
            self.assertContains(exported, text)
        before = self.rows_state()
        self.client.force_login(self.other)
        for name, pk in (
            ("scheduled-detail", required(source.planned).pk),
            ("session-detail", item.pk),
            ("snapshot-api", item.pk),
            ("block-metrics", block.pk),
            ("interval-edit", interval.pk),
            ("interval-new", block.pk),
            ("session-edit", item.pk),
        ):
            with self.subTest(route=name):
                url = reverse(name, args=[pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                if name not in ("scheduled-detail", "session-detail", "snapshot-api"):
                    self.assertEqual(
                        self.client.post(url, {"revision": 2, "distance_m": "999"}).status_code,
                        404,
                    )
        self.assertEqual(
            self.client.post(
                reverse("scheduled-start", args=[required(source.planned).pk])
            ).status_code,
            404,
        )
        foreign_export = self.client.get("/export/")
        for text in ("PRIVATE-SWIMMING-814", "PRIVATE-STROKE-814", "PRIVATE-DRILL-814"):
            self.assertNotContains(foreign_export, text)
        for account_id, expected_status in (
            (str(self.other.athlete.public_id), 400),
            (str(self.owner.athlete.public_id), 403),
        ):
            body["account"], body["mutation_id"] = account_id, str(uuid4())
            denied = self.client.post("/api/sync/", body, content_type="application/json")
            self.assertEqual(denied.status_code, expected_status, denied.content)
            self.assertEqual(self.rows_state(), before)

    def test_invalid_http_and_sync_are_atomic_including_inconsistent_hr(self) -> None:
        item = session(self.owner, sport="swimming")
        block = item.blocks.get()
        for values in (
            {"laps": "1.5"},
            {"pool_length_m": "101"},
            {"heart_rate_bpm": "160", "max_heart_rate_bpm": "150"},
        ):
            before = self.rows_state()
            response = self.client.post(
                reverse("block-metrics", args=[block.pk]), {**values, "revision": item.revision}
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "error")
            self.assertEqual(self.rows_state(), before)
            self.assertEqual(self.send(item, dict[str, object](values)).status_code, 400)
            self.assertEqual(self.rows_state(), before)

    def test_completed_aggregate_authority_partial_intervals_and_laps_only(self) -> None:
        source = self.prescribe()
        item = start_session(self.owner, required(source.planned))
        payload = session_snapshot(item)
        payload["blocks"][0]["actual"] = {
            "distance_m": "700",  # Not 800 from laps and not 4*50 interval detail.
            "duration_seconds": "1200",
            "laps": "32",
            "pool_length_m": "25",
        }
        payload["blocks"][0]["intervals"][0]["actual"] = {
            "distance_m": "50",
            "duration_seconds": "120",
        }
        payload["blocks"][0]["intervals"].append(
            {"repetitions": 3, "target": {"distance_m": "200"}, "actual": {}}
        )
        sync_session(self.owner, uuid4(), payload)
        self.assertEqual(progress_report(self.owner)["sessions"], 0)
        item.refresh_from_db()
        payload = session_snapshot(item)
        payload["status"] = "completed"
        sync_session(self.owner, uuid4(), payload)
        report = progress_report(self.owner)
        self.assertEqual(report["sessions"], 1)
        self.assertEqual(report["sports"][0]["distance_m"], Decimal(700))
        self.assertEqual(report["sports"][0]["sessions"], 1)
        # A completed block with laps/pool and an interval distance still has unknown distance.
        laps_only = session(self.other, sport="swimming")
        unknown_payload = session_snapshot(laps_only)
        unknown_payload["status"] = "completed"
        unknown_payload["blocks"][0]["actual"] = {"laps": "32", "pool_length_m": "25"}
        unknown_payload["blocks"][0]["intervals"] = [
            {"repetitions": 4, "actual": {"distance_m": "50"}}
        ]
        sync_session(self.other, uuid4(), unknown_payload)
        self.assertIsNone(progress_report(self.other)["sports"][0]["distance_m"])
        self.assertEqual(progress_report(self.owner)["sports"][0]["distance_m"], Decimal(700))
