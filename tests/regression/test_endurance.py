"""MAM811: actual dictionary boundaries, private references and frozen copies."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from basis.modules.athletes.adapters.models import SportProfile
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.references import DjangoSportThresholds
from basis.modules.athletes.domain.records import InvalidAthleteData, SportData, validate_sport
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.metrics import validate_metrics
from basis.modules.training.adapters.models import Block, Session
from basis.modules.training.adapters.planning_actions import revise
from basis.modules.training.adapters.web.forms import MetricsForm
from basis.modules.training.adapters.wire import blocks, encode_block
from basis.modules.training.domain.execution import IntervalData
from basis.modules.training.domain.manual import (
    ManualInvalid,
    ParentState,
    SessionParent,
    validate_interval,
)
from basis.modules.training.domain.sports import VARIABLES
from basis.shared.identifiers import AccountId, Revision, SessionId

from .contracts import build_plan, required, session_snapshot
from .factories import account, proposal


class EnduranceTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("endurance811"), account("other811")
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def threshold(self, **values: object) -> SportProfile:
        defaults: dict[str, object] = {
            "owner": self.owner,
            "sport": "running",
            "threshold": Decimal("300"),
            "threshold_unit": "seconds_km",
            "measured_on": self.today,
            "method": "Manual field test",
            "threshold_kind": "measured",
            "threshold_source": "Synthetic reference 811",
        }
        return SportProfile.objects.create(**{**defaults, **values})

    def prescribe(self) -> Block:
        data = proposal(self.owner)
        data["sessions"][0]["date"] = (
            self.today + timedelta(days=(5 - self.today.weekday()) % 7)
        ).isoformat()
        data["sessions"][0]["blocks"] = [
            {"sport": "running", "title": "Referencia privada", "target": {"distance_m": "2000"}},
            {
                "sport": "cardio",
                "title": "Sábado cardio",
                "target": {"duration_seconds": "900"},
                "intervals": [
                    {
                        "repetitions": 3,
                        "target": {"duration_seconds": "120"},
                        "rest_seconds": 0,
                        "target_rpe": "5",
                    }
                ],
            },
        ]
        plan = build_plan(self.owner, data)
        return plan.sessions.get().blocks.get(sport="running")

    def send(self, payload: object, mutation: object = None) -> HttpResponse:
        return cast(
            HttpResponse,
            self.client.post(
                "/api/sync/",
                {
                    "account": str(self.owner.athlete.public_id),
                    "mutation_id": str(mutation or uuid4()),
                    "session": payload,
                },
                content_type="application/json",
            ),
        )

    def test_dictionary_every_numeric_boundary_missing_zero_and_units(self) -> None:
        count = 0
        for sport, variables in VARIABLES.items():
            for name, spec in variables.items():
                count += 1
                with self.subTest(sport=sport, variable=name):
                    self.assertEqual(validate_metrics(sport, {name: None}), {})
                    self.assertEqual(validate_metrics(sport, {name: ""}), {})
                    if spec.kind in {"text", "choice"}:
                        continue
                    minimum = -500 if spec.kind == "altitude" else 0
                    for value in (minimum, 0, spec.maximum):
                        # Difficulty fields and other coupled constraints are absent.
                        self.assertEqual(
                            Decimal(validate_metrics(sport, {name: value})[name]), value
                        )
                    for invalid in (
                        minimum - 1,
                        spec.maximum + 1,
                        True,
                        "NaN",
                        "Infinity",
                        "12 kg",
                    ):
                        with self.assertRaises(ValidationError):
                            validate_metrics(sport, {name: invalid})
                    if spec.kind == "integer":
                        with self.assertRaises(ValidationError):
                            validate_metrics(sport, {name: "1.5"})
        self.assertEqual(count, 55)

    def test_incompatible_discipline_variable_and_pause_without_movement(self) -> None:
        for sport, values in (
            ("running", {"power_w": 200}),
            ("cardio", {"ascent_m": 1}),
            ("swimming", {"cadence_rpm": 50}),
            ("strength", {"distance_m": 0}),
            ("running", {"distance_km": 1}),
            ("hiking", {"duration_seconds": 5, "pause_seconds": 6}),
        ):
            with self.subTest(sport=sport, values=values), self.assertRaises(ValidationError):
                validate_metrics(sport, values)
        self.assertEqual(validate_metrics("hiking", {"pause_seconds": 0}), {"pause_seconds": "0"})

    def test_interval_types_bounds_and_form_share_dictionary(self) -> None:
        parent = ParentState(
            SessionParent(SessionId(uuid4())), AccountId(self.owner.pk), self.today, Revision(1)
        )
        for row in (
            IntervalData(repetitions=True),
            IntervalData(repetitions=1001),
            IntervalData(rest_seconds=True),
            IntervalData(rest_seconds=-1),
            IntervalData(target_rpe=Decimal("10.1")),
        ):
            with self.subTest(row=row), self.assertRaises(ManualInvalid):
                validate_interval("cardio", parent, row)
        validate_interval("cardio", parent, IntervalData(rest_seconds=0, actual_rest_seconds=None))
        form = MetricsForm({"distance_m": "0", "heart_rate_bpm": "251"}, sport="cardio")
        self.assertFalse(form.is_valid())
        form = MetricsForm({"distance_m": "0"}, sport="cardio")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data, {"distance_m": "0"})

    def test_threshold_units_dates_values_and_provenance(self) -> None:
        data = SportData(
            "running",
            "beginner",
            Decimal("300"),
            "seconds_km",
            self.today,
            "manual",
            "estimated",
            "synthetic",
        )
        for bad in (
            replace(data, sport="unknown"),
            replace(data, threshold=Decimal(0)),
            replace(data, threshold=Decimal("NaN")),
            replace(data, threshold_unit="watts"),
            replace(data, method=" "),
            replace(data, threshold=None),
            replace(data, threshold_kind="sensor-fiction"),
        ):
            with self.subTest(data=bad), self.assertRaises(InvalidAthleteData):
                validate_sport(bad)
        for changes in (
            {"measured_on": self.today + timedelta(days=1)},
            {"threshold_kind": ""},
            {"threshold_source": " "},
            {"sport": "cycling", "threshold_unit": "seconds_km"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.threshold(**changes)
        reference = self.threshold(threshold_kind="estimated")
        self.assertEqual(reference.threshold_kind, "estimated")

    def test_snapshot_freezes_values_source_and_does_not_fill_results(self) -> None:
        ref = self.threshold()
        source = self.prescribe()
        frozen = deepcopy(required(source.threshold_snapshot))
        self.assertEqual(frozen["profile_id"], ref.pk)
        self.assertEqual(frozen["value"], "300.00")
        ref.threshold, ref.method, ref.threshold_kind = Decimal(320), "Later method", "estimated"
        ref.save()
        item = start_session(self.owner, required(source.planned))
        copied = item.blocks.get(sport="running")
        self.assertEqual(copied.threshold_snapshot, frozen)
        self.assertEqual(copied.actual, {})
        self.assertEqual(copied.target, source.target)
        self.assertEqual(copied.source_id, source.pk)
        segment = item.blocks.get(sport="cardio").intervals.get()
        self.assertEqual(
            (segment.target, segment.actual, segment.rest_seconds, segment.actual_rest_seconds),
            ({"duration_seconds": "120"}, {}, 0, None),
        )
        self.assertIsNone(segment.actual_rpe)
        source.refresh_from_db()
        self.assertEqual(source.threshold_snapshot, frozen)
        ref.threshold = Decimal(330)
        ref.save()
        copied.refresh_from_db()
        self.assertEqual(copied.threshold_snapshot, frozen)

    def test_deep_copy_and_legacy_null_never_refresh_from_current_profile(self) -> None:
        ref = self.threshold()
        source = self.prescribe()
        frozen = deepcopy(source.threshold_snapshot)
        ref.threshold = Decimal(310)
        ref.save()
        revised = revise(
            self.owner.pk, required(source.planned).plan_id, "Disponibilidad del sábado"
        )
        copied = revised.sessions.get().blocks.get(sport="running")
        self.assertNotEqual(copied.pk, source.pk)
        self.assertEqual(copied.threshold_snapshot, frozen)
        self.assertEqual(copied.intervals.count(), source.intervals.count())
        cardio = revised.sessions.get().blocks.get(sport="cardio")
        self.assertEqual(cardio.intervals.get().target, {"duration_seconds": "120"})
        self.assertIsNone(cardio.threshold_snapshot)
        from django.urls import reverse

        response = self.client.get(reverse("scheduled-detail", args=[revised.sessions.get().pk]))
        self.assertContains(response, "Synthetic reference 811")
        self.assertNotContains(response, "Later method")
        self.assertContains(response, "Sábado cardio")

    def test_sync_codec_preserves_snapshot_ids_zero_and_legacy_omission(self) -> None:
        self.threshold()
        source = self.prescribe()
        item = start_session(self.owner, required(source.planned))
        payload = session_snapshot(item)
        for block in payload["blocks"]:
            self.assertEqual(
                encode_block(blocks([block])[0])["threshold_snapshot"], block["threshold_snapshot"]
            )
            block.pop("threshold_snapshot")  # Existing offline codec did not know it.
        payload["blocks"][0]["actual"] = {"distance_m": "0"}
        key = uuid4()
        response = self.send(payload, key)
        self.assertEqual(response.status_code, 200, response.content)
        import json

        self.assertEqual(json.loads(self.send(payload, key).content), json.loads(response.content))
        copied = item.blocks.get(sport="running")
        self.assertEqual(copied.threshold_snapshot, source.threshold_snapshot)
        self.assertEqual(copied.actual, {"distance_m": "0"})
        self.assertEqual(json.loads(response.content)["session"]["blocks"][0]["source"], source.pk)

    def test_snapshot_forgery_is_atomic_and_private_read_is_scoped(self) -> None:
        self.threshold()
        source = self.prescribe()
        item = start_session(self.owner, required(source.planned))
        payload = session_snapshot(item)
        required(payload["blocks"][0]["threshold_snapshot"])["value"] = "999"
        self.assertEqual(self.send(payload).status_code, 400)
        self.assertEqual(
            item.blocks.get(sport="running").threshold_snapshot, source.threshold_snapshot
        )
        self.client.force_login(self.other)
        from django.urls import reverse

        self.assertEqual(
            self.client.get(reverse("session-detail", args=[item.pk])).status_code, 404
        )
        self.assertIsNone(
            DjangoSportThresholds().current(AccountId(self.other.pk), "running", self.today)
        )

    def test_reader_uses_account_not_athlete_pk_and_never_future_reference(self) -> None:
        # Decouple legacy profile PK from account PK without touching ownership.
        Athlete.objects.filter(account=self.owner).update(id=50000)
        ref = self.threshold()
        reader = DjangoSportThresholds()
        self.assertEqual(
            required(reader.current(AccountId(self.owner.pk), "running", self.today)).profile_id,
            ref.pk,
        )
        self.assertIsNone(reader.current(AccountId(50000), "running", self.today))
        self.assertIsNone(
            reader.current(AccountId(self.owner.pk), "running", self.today - timedelta(days=1))
        )
        self.assertIsNone(reader.current(AccountId(self.owner.pk), "cycling", self.today))

    def test_absent_reference_stays_unknown_after_profile_created(self) -> None:
        source = self.prescribe()
        self.assertIsNone(source.threshold_snapshot)
        self.threshold()
        copied_plan = revise(
            self.owner.pk, required(source.planned).plan_id, "Copiar sin inventar historia"
        )
        copied = copied_plan.sessions.get().blocks.get(sport="running")
        self.assertIsNone(copied.threshold_snapshot)
        item = start_session(self.owner, required(copied.planned))
        self.assertIsNone(item.blocks.get(sport="running").threshold_snapshot)

    def test_sync_rejects_invalid_interval_variables_units_and_ranges_atomically(self) -> None:
        for interval in (
            {"target": {"power_w": 120}},
            {"target": {"duration_seconds": "2 min"}},
            {"target": {"duration_seconds": -1}},
            {"repetitions": True},
            {"rest_seconds": -1},
            {"target_rpe": "11"},
        ):
            payload = {
                "id": str(uuid4()),
                "revision": 0,
                "blocks": [
                    {
                        "sport": "cardio",
                        "title": "Manual",
                        "intervals": [interval],
                    }
                ],
            }
            with self.subTest(interval=interval):
                self.assertEqual(self.send(payload).status_code, 400)
                self.assertFalse(Session.objects.exists())

    def test_private_profile_post_and_export_do_not_accept_another_owner(self) -> None:
        response = self.client.post(
            "/records/sport/new/",
            {
                "owner": self.other.pk,
                "sport": "running",
                "experience": "beginner",
                "threshold": "300",
                "threshold_unit": "seconds_km",
                "measured_on": self.today.isoformat(),
                "method": "Manual test",
                "threshold_kind": "estimated",
                "threshold_source": "PRIVATE-811",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        self.assertEqual(SportProfile.objects.get().owner_id, self.owner.pk)
        source = self.prescribe()
        exported = self.client.get("/export/")
        self.assertContains(exported, "PRIVATE-811")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get("/export/"), "PRIVATE-811")
        self.client.force_login(self.owner)
        item = start_session(self.owner, required(source.planned))
        payload = session_snapshot(item)
        payload["status"] = "completed"
        self.assertEqual(self.send(payload).status_code, 200)
        ref = SportProfile.objects.get()
        ref.threshold, ref.threshold_source = Decimal(330), "NEW-811"
        ref.save()
        copied = item.blocks.get(sport="running")
        self.assertEqual(required(copied.threshold_snapshot)["source"], "PRIVATE-811")
        copied.threshold_snapshot = {**required(copied.threshold_snapshot), "value": "999"}
        with self.assertRaises(ValidationError):
            copied.save()


class EnduranceUpgradeTests(TransactionTestCase):
    def test_upgrade_leaves_legacy_references_unknown(self) -> None:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        targets = [
            ("basis_training", "0003_execution_identity"),
            ("basis_athletes", "0002_measurement_origin"),
        ]
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        try:
            apps = executor.loader.project_state(targets).apps
            owner = apps.get_model("auth", "User").objects.create(username="legacy811")
            profile = apps.get_model("basis_athletes", "SportProfile").objects.create(
                owner_id=owner.pk,
                sport="running",
                threshold="300",
                threshold_unit="seconds_km",
                measured_on=timezone.localdate(),
                method="legacy",
            )
            item = apps.get_model("basis_training", "Session").objects.create(
                owner_id=owner.pk,
                title="Historical",
                date=timezone.localdate(),
                status="completed",
            )
            block = apps.get_model("basis_training", "Block").objects.create(
                session_id=item.pk,
                sport="running",
                title="Legacy",
                actual={"distance_m": "0"},
            )
            ids = profile.pk, item.pk, block.pk
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
        restored = Block.objects.get(pk=ids[2])
        self.assertEqual(restored.actual, {"distance_m": "0"})
        self.assertIsNone(restored.threshold_snapshot)
        self.assertEqual(Session.objects.get(pk=ids[1]).status, "completed")
        profile = SportProfile.objects.get(pk=ids[0])
        self.assertEqual((profile.threshold_kind, profile.threshold_source), ("", ""))
        profile.experience = "advanced"
        profile.save()  # Existing unknown provenance remains readable/editable.
