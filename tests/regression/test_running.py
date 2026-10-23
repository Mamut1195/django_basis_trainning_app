"""MAM812: manual running presentation, owner-scoped web and wire regressions."""

import json
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.metrics import pace_seconds_legacy, validate_metrics
from basis.modules.training.adapters.models import Block, Interval, Session
from basis.modules.training.adapters.templatetags.training_tags import metric_rows
from basis.modules.training.adapters.web.forms import MetricsForm
from basis.modules.training.domain.sports import OUTDOOR, VARIABLES, pace_seconds

from .contracts import build_plan, required, session_snapshot
from .factories import account, proposal, session


class RunningTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("fictitious-running812"), account("fictitious-other812")
        self.client.force_login(self.owner)

    def test_dictionary_form_and_pause_boundaries(self) -> None:
        self.assertIs(VARIABLES["running"]["pause_seconds"], OUTDOOR["pause_seconds"])
        valid_cases: tuple[dict[str, object], ...] = (
            {"pause_seconds": None},
            {"pause_seconds": "0"},
            {"duration_seconds": "120", "pause_seconds": "120"},
        )
        for values in valid_cases:
            form = MetricsForm(values, sport="running")
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data, validate_metrics("running", values))
        invalid_cases: tuple[dict[str, object], ...] = (
            {"duration_seconds": "5", "pause_seconds": "6"},
            {"pause_seconds": -1},
            {"pause_seconds": "NaN"},
            {"pause_seconds": True},
        )
        for invalid in invalid_cases:
            with self.subTest(values=invalid), self.assertRaises(ValidationError):
                validate_metrics("running", invalid)
        self.assertFalse(
            MetricsForm({"duration_seconds": "5", "pause_seconds": "6"}, sport="running").is_valid()
        )

    def test_pace_adapter_domain_and_rows_match_independent_literals(self) -> None:
        # Expected values are analytical literals, not results from either implementation.
        for distance, duration, expected in (
            (None, None, None),
            (None, "0", None),
            ("5000", None, None),
            ("0", "60", None),
            ("0", "0", None),
            ("5000", "0", "0.00"),
            ("5000", "1500", "300.00"),
            ("5000", "1800", "360.00"),
            ("400", "60", "150.00"),
            ("3", "1", "333.33"),
        ):
            with self.subTest(distance=distance, duration=duration):
                values = {
                    key: value
                    for key, value in (("distance_m", distance), ("duration_seconds", duration))
                    if value is not None
                }
                oracle = None if expected is None else Decimal(expected)
                domain = pace_seconds(
                    None if distance is None else Decimal(distance),
                    None if duration is None else Decimal(duration),
                )
                self.assertEqual(domain, oracle)
                self.assertEqual(pace_seconds_legacy(values), oracle)
                block = Block(sport="running", target=values, actual=values)
                interval = Interval(block=block, target=values, actual=values)
                for item in (block, interval):
                    for source in ("target", "actual"):
                        self.assertEqual(metric_rows(item, source)[-1]["value"], oracle)

    def test_prefetched_interval_metrics_render_without_additional_queries(self) -> None:
        item = session(self.owner)
        block = item.blocks.get()
        for order in range(1, 4):
            Interval.objects.create(
                block=block,
                order=order,
                target={"duration_seconds": "60", "distance_m": "400"},
                actual={"duration_seconds": "1800", "distance_m": "5000"},
            )
        # The existing detail-view prefetch also populates each interval's reverse FK cache.
        prefetched = Session.objects.prefetch_related("blocks__intervals").get(pk=item.pk)
        with self.assertNumQueries(0):
            blocks = list(prefetched.blocks.all())
            intervals = list(blocks[0].intervals.all())
            self.assertEqual(len(intervals), 3)
            for interval in intervals:
                self.assertIs(interval.block, blocks[0])
                self.assertEqual(metric_rows(interval, "target")[-1]["value"], Decimal("150.00"))
                self.assertEqual(metric_rows(interval)[-1]["value"], Decimal("360.00"))
            rendered = render_to_string("training/execution/_intervals.html", {"block": blocks[0]})
            self.assertEqual(rendered.count("150,00 s/km"), 3)
            self.assertEqual(rendered.count("360,00 s/km"), 3)

    def test_rows_match_sources_and_handle_true_null_empty_and_zero(self) -> None:
        block = Block(
            sport="running",
            target={"duration_seconds": "1500", "distance_m": "5000"},
        )
        self.assertEqual(metric_rows(block, "target")[-1]["value"], Decimal("300.00"))
        for actual, expected in (
            ({}, None),
            ({"duration_seconds": None, "distance_m": "5000", "heart_rate_bpm": None}, None),
            ({"duration_seconds": "1800", "distance_m": None}, None),
            ({"duration_seconds": "", "distance_m": "5000"}, None),
            ({"duration_seconds": "1800", "distance_m": "0"}, None),
            ({"duration_seconds": "0", "distance_m": "5000"}, Decimal("0.00")),
            (
                {"duration_seconds": "1800", "distance_m": "5000", "pause_seconds": "120"},
                Decimal("360.00"),
            ),
        ):
            with self.subTest(actual=actual):
                block.actual = actual
                interval = Interval(block=block, target=block.target, actual=actual)
                self.assertEqual(metric_rows(block)[-1]["value"], expected)
                self.assertEqual(metric_rows(interval), metric_rows(block))
                self.assertEqual(metric_rows(interval, "target")[-1]["value"], Decimal("300.00"))
                rendered = render_to_string("training/execution/_metrics.html", {"block": interval})
                self.assertIn("Resultado real · registro manual", rendered)
                self.assertIn("Objetivo / prescripción", rendered)
                self.assertIn("no se restan", rendered)
                self.assertNotIn("None", rendered)
                if expected is None:
                    self.assertIn("— s/km", rendered)
                else:
                    self.assertNotIn("— s/km", rendered)
        block.actual = {"heart_rate_bpm": None, "cadence_spm": "0", "ascent_m": "0"}
        rows = metric_rows(block)
        self.assertIsNone(rows[0]["value"])
        self.assertEqual(rows[1]["value"], "0")
        block.sport = "cycling"
        self.assertFalse(any(row["unit"] == "s/km" for row in metric_rows(block)))

    def test_real_web_metrics_interval_edit_and_unknown_results(self) -> None:
        item = session(self.owner)
        block = item.blocks.get()
        detail = reverse("session-detail", args=[item.pk])
        self.assertContains(self.client.get(detail), "— s/km")
        response = self.client.post(
            reverse("block-metrics", args=[block.pk]),
            {
                "revision": item.revision,
                "owner": self.other.pk,
                "duration_seconds": "1800",
                "distance_m": "5000",
                "pause_seconds": "120",
                "ascent_m": "0",
                "descent_m": "0",
                "surface": "Pista ficticia",
                "session_type": "Rodaje manual",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        block.refresh_from_db()
        self.assertEqual(block.actual["pause_seconds"], "120")
        self.assertNotIn("heart_rate_bpm", block.actual)
        item.refresh_from_db()
        response = self.client.post(
            reverse("interval-new", args=[block.pk]),
            {
                "revision": item.revision,
                "repetitions": 2,
                "rest_seconds": 0,
                "target-duration_seconds": "60",
                "target-distance_m": "400",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        interval = block.intervals.get()
        self.assertEqual(interval.actual, {})
        response = self.client.get(detail)
        self.assertContains(response, "— s/km")
        self.assertNotContains(response, "<pre>")
        item.refresh_from_db()
        response = self.client.post(
            reverse("interval-edit", args=[interval.pk]),
            {
                "revision": item.revision,
                "repetitions": 2,
                "rest_seconds": 0,
                "actual_rest_seconds": 0,
                "metrics-duration_seconds": "60",
                "metrics-distance_m": "400",
                "metrics-pause_seconds": "0",
                "metrics-cadence_spm": "0",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        interval.refresh_from_db()
        self.assertEqual(interval.target, {"duration_seconds": "60", "distance_m": "400"})
        self.assertEqual(metric_rows(interval)[-1]["value"], Decimal("150.00"))
        response = self.client.get(detail)
        for text in ("s/km", "pasos/min", "Resultado real · registro manual", "no se restan"):
            self.assertContains(response, text)
        # Only the unprescribed block target remains unknown; both interval sources are known.
        self.assertContains(response, "— s/km", count=1)
        interval_html = render_to_string("training/execution/_metrics.html", {"block": interval})
        self.assertNotIn("— s/km", interval_html)
        self.assertContains(response, "360,00 s/km")
        self.assertContains(response, "150,00 s/km", count=2)

    def test_plan_copy_target_unchanged_and_no_target_fallback(self) -> None:
        document = proposal(self.owner)
        source_data = document["sessions"][0]["blocks"][0]
        source_data["target"] = {
            "duration_seconds": "1500",
            "distance_m": "5000",
            "pause_seconds": "0",
        }
        source_data["intervals"] = [
            {"target": {"duration_seconds": "60", "distance_m": "400"}, "rest_seconds": 0}
        ]
        plan = build_plan(self.owner, document)
        source = plan.sessions.get().blocks.get()
        target = deepcopy(source.target)
        interval_target = deepcopy(source.intervals.get().target)
        item = start_session(self.owner, required(source.planned))
        block = item.blocks.get()
        interval = block.intervals.get()
        self.assertEqual(block.target, target)
        self.assertEqual(interval.target, interval_target)
        self.assertEqual(block.actual, {})
        self.assertEqual(interval.actual, {})
        self.assertIsNone(metric_rows(block)[-1]["value"])
        self.assertIsNone(metric_rows(interval)[-1]["value"])
        response = self.client.post(
            reverse("block-metrics", args=[block.pk]),
            {"revision": item.revision, "duration_seconds": "1800", "distance_m": "5000"},
        )
        self.assertEqual(response.status_code, 302, response.content)
        source.refresh_from_db()
        block.refresh_from_db()
        self.assertEqual(source.target, target)
        self.assertEqual(source.intervals.get().target, interval_target)
        self.assertEqual(block.target, target)
        self.assertEqual(metric_rows(block)[-1]["value"], Decimal("360.00"))

    def test_sync_export_forged_owner_and_cross_account_read_write(self) -> None:
        item = session(self.owner)
        item.title = "PRIVATE-RUNNING-812"
        item.save()
        block = item.blocks.get()
        interval = Interval.objects.create(block=block, target={"distance_m": "400"})
        payload = session_snapshot(item)
        payload["blocks"][0]["actual"] = {
            "duration_seconds": "1800",
            "distance_m": "5000",
            "pause_seconds": "120",
            "heart_rate_bpm": None,
            "cadence_spm": "0",
            "ascent_m": "0",
        }
        payload["blocks"][0]["intervals"][0]["actual"] = {
            "duration_seconds": "0",
            "distance_m": "400",
            "pause_seconds": "0",
        }
        mutation = str(uuid4())
        body = {
            "account": str(self.owner.athlete.public_id),
            "owner": self.other.pk,
            "mutation_id": mutation,
            "session": payload,
        }
        response = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        replay = self.client.post("/api/sync/", body, content_type="application/json")
        self.assertEqual(json.loads(replay.content), json.loads(response.content))
        block.refresh_from_db()
        interval.refresh_from_db()
        self.assertEqual(block.owner_id, self.owner.pk)
        self.assertEqual(block.actual["cadence_spm"], "0")
        self.assertNotIn("heart_rate_bpm", block.actual)
        self.assertEqual(metric_rows(block)[-1]["value"], Decimal("360.00"))
        self.assertEqual(metric_rows(interval)[-1]["value"], Decimal("0.00"))
        self.assertContains(self.client.get("/export/"), "PRIVATE-RUNNING-812")
        self.assertContains(self.client.get("/export/"), "pause_seconds")
        # Compare complete persisted rows, including revisions, targets and receipts.
        before = (
            list(Session.objects.order_by("pk").values()),
            list(Block.objects.order_by("pk").values()),
            list(Interval.objects.order_by("pk").values()),
            list(SyncReceipt.objects.order_by("pk").values()),
        )
        self.client.force_login(self.other)
        for name, pk in (
            ("session-detail", item.pk),
            ("snapshot-api", item.pk),
            ("block-metrics", block.pk),
            ("interval-edit", interval.pk),
        ):
            url = reverse(name, args=[pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            if name in ("block-metrics", "interval-edit"):
                self.assertEqual(self.client.post(url, {"revision": 2}).status_code, 404)
        self.assertNotContains(self.client.get("/export/"), "PRIVATE-RUNNING-812")
        for account_id, status, detail in (
            (str(self.other.athlete.public_id), 400, ["La sesión no está disponible."]),
            (str(self.owner.athlete.public_id), 403, "La cola pertenece a otra cuenta."),
        ):
            with self.subTest(account=account_id):
                body["account"] = account_id
                rejected_mutation = str(uuid4())
                body["mutation_id"] = rejected_mutation
                denied = self.client.post("/api/sync/", body, content_type="application/json")
                self.assertEqual(denied.status_code, status, denied.content)
                self.assertEqual(json.loads(denied.content)["detail"], detail)
                self.assertFalse(SyncReceipt.objects.filter(mutation_id=rejected_mutation).exists())
                self.assertEqual(
                    (
                        list(Session.objects.order_by("pk").values()),
                        list(Block.objects.order_by("pk").values()),
                        list(Interval.objects.order_by("pk").values()),
                        list(SyncReceipt.objects.order_by("pk").values()),
                    ),
                    before,
                )
