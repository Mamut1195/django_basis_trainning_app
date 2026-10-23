"""Manual cycling reuses MAM-811; all accounts/references here are fictional."""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID, uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.modules.athletes.adapters.models import SportProfile
from basis.modules.athletes.adapters.references import DjangoSportThresholds
from basis.modules.training.adapters.models import Block, Session
from basis.modules.training.adapters.web.forms import MetricsForm
from basis.shared.identifiers import AccountId

from .contracts import build_plan, required, session_snapshot
from .factories import account, proposal


class CyclingTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("fictional-cycling813")
        self.other = account("fictional-other-cycling813")
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def threshold_data(self) -> dict[str, object]:
        return {
            "sport": "cycling",
            "experience": "beginner",
            "threshold": "220",
            "threshold_unit": "watts",
            "measured_on": self.today.isoformat(),
            "method": "Prueba manual ficticia 813",
            "threshold_kind": "measured",
            "threshold_source": "https://cycling813.example.test/referencia-ficticia",
        }

    def create_threshold(self) -> SportProfile:
        response = self.client.post(
            "/records/sport/new/", {**self.threshold_data(), "owner": self.other.pk}
        )
        self.assertEqual(response.status_code, 302, response.content)
        reference = SportProfile.objects.get(owner=self.owner, sport="cycling")
        self.assertFalse(SportProfile.objects.filter(owner=self.other).exists())
        return reference

    def prescribe(self, duration: str = "1800", distance: str = "12000") -> Block:
        data = proposal(self.owner)
        data["sessions"][0]["blocks"] = [
            {
                "sport": "cycling",
                "title": "Ciclismo ficticio 813",
                "target": {
                    "duration_seconds": duration,
                    "distance_m": distance,
                    "ascent_m": "120",
                    "descent_m": "100",
                    "environment": "outdoor",
                },
                "intervals": [
                    {
                        "repetitions": 3,
                        "target": {"duration_seconds": "120", "power_w": "200"},
                        "rest_seconds": 0,
                        "target_rpe": "5",
                    }
                ],
            }
        ]
        return build_plan(self.owner, data).sessions.get().blocks.get()

    def start(self, source: Block) -> Session:
        planned = required(source.planned)
        response = self.client.post(reverse("scheduled-start", args=[planned.pk]))
        self.assertEqual(response.status_code, 302, response.content)
        return Session.objects.get(planned=planned)

    def test_form_units_spanish_labels_and_unchanged_wire_values(self) -> None:
        form = MetricsForm(sport="cycling")
        for key, unit in (
            ("power_w", "W"),
            ("cadence_rpm", "rpm"),
            ("heart_rate_bpm", "lpm"),
            ("max_heart_rate_bpm", "lpm"),
        ):
            with self.subTest(key=key):
                self.assertIn(f"({unit})", str(form.fields[key].label))
                self.assertFalse(form.fields[key].required)
        html = str(form["environment"])
        self.assertIn('<option value="indoor">Interior</option>', html)
        self.assertIn('<option value="outdoor">Exterior</option>', html)
        self.assertIn("Sin registrar", html)
        for environment in ("indoor", "outdoor"):
            submitted = MetricsForm({"environment": environment}, sport="cycling")
            self.assertTrue(submitted.is_valid(), submitted.errors)
            self.assertEqual(submitted.cleaned_data, {"environment": environment})
        for invalid in ("Interior", "Exterior", "road"):
            submitted = MetricsForm({"environment": invalid}, sport="cycling")
            self.assertFalse(submitted.is_valid())

    def test_manual_http_create_optional_unknown_then_measured_zero(self) -> None:
        response = self.client.post(
            reverse("session-new"),
            {
                "owner": self.other.pk,
                "title": "Rodillo ficticio 813",
                "date": self.today.isoformat(),
                "duration_protocol": "elapsed",
                "block-sport": "cycling",
                "block-title": "Interior ficticio",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        item = Session.objects.get()
        self.assertEqual(item.owner_id, self.owner.pk)
        block = item.blocks.get()
        self.assertEqual((block.target, block.actual, block.threshold_snapshot), ({}, {}, None))
        page = self.client.get(reverse("block-metrics", args=[block.pk]))
        self.assertContains(page, '<option value="indoor">Interior</option>', html=True)
        self.assertContains(page, '<option value="outdoor">Exterior</option>', html=True)
        for unit in ("(W)", "(rpm)", "(lpm)"):
            self.assertContains(page, unit)
        base = {
            "duration_seconds": "900",
            "distance_m": "5000",
            "ascent_m": "0",
            "descent_m": "0",
            "environment": "indoor",
        }
        for observations in (
            {"power_w": "", "cadence_rpm": "", "heart_rate_bpm": ""},
            {"power_w": "0", "cadence_rpm": "0", "heart_rate_bpm": "0"},
        ):
            item.refresh_from_db()
            response = self.client.post(
                reverse("block-metrics", args=[block.pk]),
                {**base, **observations, "revision": item.revision},
            )
            self.assertEqual(response.status_code, 302, response.content)
            block.refresh_from_db()
            self.assertEqual(block.actual, {**base, **{k: v for k, v in observations.items() if v}})
            self.assertEqual(block.target, {})
            self.assertIsNone(block.threshold_snapshot)
        self.assertIsNone(
            DjangoSportThresholds().current(AccountId(self.owner.pk), "cycling", self.today)
        )
        self.assertFalse(SportProfile.objects.filter(owner=self.owner, sport="cycling").exists())

    def test_distance_duration_never_infer_power_or_threshold_even_after_start(self) -> None:
        for duration, distance in (("600", "10000"), ("7200", "1000"), ("0", "0")):
            with self.subTest(duration=duration, distance=distance):
                source = self.prescribe(duration, distance)
                self.assertIsNone(source.threshold_snapshot)
                self.assertNotIn("power_w", source.target)
                item = self.start(source)
                copied = item.blocks.get()
                self.assertEqual(copied.target, source.target)
                self.assertEqual(copied.actual, {})
                self.assertIsNone(copied.threshold_snapshot)
                self.assertEqual(copied.intervals.get().actual, {})
                # An explicitly prescribed interval power is not a measurement or threshold.
                self.assertEqual(copied.intervals.get().target["power_w"], "200")
        self.assertFalse(SportProfile.objects.exists())

    def test_http_lifecycle_preserves_targets_intervals_and_frozen_provenance(self) -> None:
        reference = self.create_threshold()
        source = self.prescribe()
        planned = required(source.planned)
        frozen = deepcopy(required(source.threshold_snapshot))
        self.assertEqual(
            frozen,
            {
                "profile_id": reference.pk,
                "sport": "cycling",
                "value": "220.00",
                "unit": "watts",
                "measured_on": self.today.isoformat(),
                "method": self.threshold_data()["method"],
                "kind": "measured",
                "source": self.threshold_data()["threshold_source"],
            },
        )
        self.assertContains(
            self.client.get(reverse("scheduled-detail", args=[planned.pk])), frozen["source"]
        )
        item = self.start(source)
        copied = item.blocks.get()
        segment = copied.intervals.get()
        original_interval = source.intervals.get()
        self.assertEqual(copied.source_id, source.pk)
        self.assertEqual(segment.source_id, original_interval.pk)
        self.assertEqual(copied.target, source.target)
        self.assertEqual(copied.actual, {})
        self.assertEqual(segment.target, original_interval.target)
        self.assertEqual(segment.actual, {})
        self.assertEqual((segment.rest_seconds, segment.actual_rest_seconds), (0, None))
        self.assertIsNone(segment.actual_rpe)
        measured = {
            "duration_seconds": "1700",
            "distance_m": "11000",
            "ascent_m": "110",
            "descent_m": "90",
            "environment": "outdoor",
            "power_w": "180",
            "cadence_rpm": "85",
            "heart_rate_bpm": "140",
            "max_heart_rate_bpm": "160",
        }
        response = self.client.post(
            reverse("block-metrics", args=[copied.pk]), {**measured, "revision": item.revision}
        )
        self.assertEqual(response.status_code, 302, response.content)
        item.refresh_from_db()
        response = self.client.post(
            reverse("interval-edit", args=[segment.pk]),
            {
                "revision": item.revision,
                # A tampered POST cannot change disabled prescription fields.
                "repetitions": 99,
                "rest_seconds": 999,
                "target_rpe": "9",
                "actual_rest_seconds": 0,
                "actual_rpe": "0",
                "metrics-duration_seconds": "100",
                "metrics-power_w": "0",
                "metrics-cadence_rpm": "0",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        segment.refresh_from_db()
        self.assertEqual(segment.target, original_interval.target)
        self.assertEqual((segment.repetitions, segment.rest_seconds, segment.target_rpe), (3, 0, 5))
        self.assertEqual(
            segment.actual, {"duration_seconds": "100", "power_w": "0", "cadence_rpm": "0"}
        )
        self.assertEqual((segment.actual_rest_seconds, segment.actual_rpe), (0, Decimal(0)))
        reference.threshold, reference.method = Decimal(250), "Método posterior ficticio"
        reference.threshold_kind = "estimated"
        reference.threshold_source = "https://cycling813.example.test/posterior-ficticia"
        reference.save()
        item.refresh_from_db()
        payload = session_snapshot(item)
        payload["status"] = "completed"
        response = self.client.post(
            "/api/sync/",
            {
                "account": str(self.owner.athlete.public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        item.refresh_from_db()
        copied.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(item.status, "completed")
        self.assertEqual(copied.actual, measured)
        self.assertEqual(copied.target, source.target)
        self.assertEqual(source.actual, {})
        self.assertEqual(copied.threshold_snapshot, frozen)
        self.assertEqual(source.threshold_snapshot, frozen)
        self.assertEqual(source.intervals.get().actual, {})
        self.assertEqual(copied.intervals.get().actual, segment.actual)
        exported = self.client.get("/export/")
        self.assertContains(exported, frozen["source"])
        self.assertContains(exported, "cadence_rpm")
        before = session_snapshot(item)
        response = self.client.post(
            reverse("block-metrics", args=[copied.pk]),
            {"revision": item.revision, "power_w": "999"},
        )
        self.assertEqual(response.status_code, 400, response.content)
        item.refresh_from_db()
        self.assertEqual(session_snapshot(item), before)

    def test_foreign_reads_posts_sync_and_export_cannot_access_cycling(self) -> None:
        reference = self.create_threshold()
        source = self.prescribe()
        planned = required(source.planned)
        item = self.start(source)
        copied = item.blocks.get()
        segment = copied.intervals.get()
        before = session_snapshot(item)
        planned_target = deepcopy(source.target)
        self.client.force_login(self.other)
        routes = (
            ("scheduled-detail", [planned.pk]),
            ("session-detail", [item.pk]),
            ("snapshot-api", [item.pk]),
            ("sport-edit", [reference.pk]),
            ("block-metrics", [source.pk]),
            ("block-metrics", [copied.pk]),
            ("interval-edit", [segment.pk]),
            ("interval-new", [copied.pk]),
            ("session-edit", [item.pk]),
        )
        for name, args in routes:
            with self.subTest(route=name, args=args):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404)
        attacks: tuple[tuple[str, list[int | UUID], dict[str, object]], ...] = (
            ("scheduled-start", [planned.pk], {}),
            ("block-metrics", [source.pk], {"power_w": "999"}),
            ("block-metrics", [copied.pk], {"power_w": "999"}),
            ("interval-edit", [segment.pk], {"metrics-power_w": "999", "repetitions": 99}),
            ("interval-new", [copied.pk], {"repetitions": 99}),
            ("session-edit", [item.pk], {"title": "Ataque ficticio"}),
            ("sport-edit", [reference.pk], {**self.threshold_data(), "threshold": "999"}),
        )
        for name, post_args, values in attacks:
            with self.subTest(post=name, args=post_args):
                response = self.client.post(
                    reverse(name, args=post_args),
                    {**values, "owner": self.owner.pk, "revision": item.revision},
                )
                self.assertEqual(response.status_code, 404, response.content)
        payload = deepcopy(before)
        payload["blocks"][0]["actual"] = {"power_w": "999"}
        response = self.client.post(
            "/api/sync/",
            {
                "account": str(self.other.athlete.public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json(), {"detail": ["La sesión no está disponible."]})
        self.assertNotContains(
            self.client.get("/export/"), str(self.threshold_data()["threshold_source"])
        )
        self.assertIsNone(
            DjangoSportThresholds().current(AccountId(self.other.pk), "cycling", self.today)
        )
        item.refresh_from_db()
        source.refresh_from_db()
        reference.refresh_from_db()
        self.assertEqual(session_snapshot(item), before)
        self.assertEqual(source.target, planned_target)
        self.assertEqual(reference.threshold, Decimal(220))
        self.assertEqual(Session.objects.filter(planned=planned).count(), 1)

    def test_optional_null_and_zero_in_sync_remain_distinct(self) -> None:
        item = self.start(self.prescribe())
        for value, expected in ((None, {}), (0, {"power_w": "0", "cadence_rpm": "0"})):
            with self.subTest(value=value):
                item.refresh_from_db()
                payload = session_snapshot(item)
                payload["blocks"][0]["actual"] = {"power_w": value, "cadence_rpm": value}
                response = self.client.post(
                    "/api/sync/",
                    {
                        "account": str(self.owner.athlete.public_id),
                        "mutation_id": str(uuid4()),
                        "session": payload,
                    },
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200, response.content)
                copied = item.blocks.get()
                self.assertEqual(copied.actual, expected)
                self.assertIsNone(copied.threshold_snapshot)
