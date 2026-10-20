from __future__ import annotations

import copy
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from basis.bootstrap.proposal_actions import validate_proposal
from basis.modules.sync.adapters.actions import Conflict
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import revise_plan, start_session
from basis.modules.training.adapters.metrics import internal_load_legacy as internal_load
from basis.modules.training.adapters.metrics import pace_seconds_legacy as pace_seconds
from basis.modules.training.adapters.metrics import validate_metrics
from basis.modules.training.adapters.models import (
    Block,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)

from .contracts import (
    build_plan,
    progress_report,
    required,
    session_snapshot,
    sync_session,
    trip_summary,
)
from .factories import account, exercise, proposal, session


class DomainTests(TestCase):
    def setUp(self) -> None:
        self.owner = account()
        self.other = account("other")

    def test_metrics_units_unknown_and_ranges(self) -> None:
        result = validate_metrics(
            "hiking",
            {
                "distance_m": "8000.5",
                "pack_kg": "6.25",
                "ascent_m": 800,
                "descent_m": 800,
                "start_altitude_m": 2000,
                "max_altitude_m": 2700,
                "end_altitude_m": 2000,
                "duration_seconds": 14400,
                "moving_seconds": 12000,
                "pause_seconds": 2400,
            },
        )
        self.assertEqual(result["pack_kg"], "6.25")
        self.assertNotIn("heart_rate_bpm", result)
        for data in (
            {"pack_kg": -1},
            {"power_w": 100},
            {"distance_m": "NaN"},
            {"distance_m": True},
            {"duration_seconds": 60, "moving_seconds": 50, "pause_seconds": 20},
            {"max_altitude_m": 2000, "start_altitude_m": 3000},
            {"difficulty_grade": "T3"},
        ):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                validate_metrics("hiking", data)

    def test_load_and_pace_do_not_treat_missing_as_zero(self) -> None:
        self.assertIsNone(internal_load(None, 5))
        self.assertIsNone(internal_load(60, None))
        self.assertEqual(internal_load(3600, 5), 300)
        self.assertEqual(pace_seconds({"distance_m": "1000", "duration_seconds": "1200"}, 100), 120)
        self.assertIsNone(pace_seconds({"distance_m": "0", "duration_seconds": "1200"}))

    def test_strength_estimate_requires_reported_max_effort(self) -> None:
        block = required(session(self.owner, "strength").blocks.first())
        row = StrengthSet.objects.create(
            block=block, exercise=exercise(), actual_reps=5, actual_kg="80.25"
        )
        self.assertIsNone(row.estimated_1rm)
        row.actual_rpe = 10
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.external_volume_kg, Decimal("401.25"))
        self.assertEqual(row.estimated_1rm, Decimal("93.63"))
        row.load_type = "assisted"
        row.save()
        self.assertIsNone(row.external_volume_kg)

    def test_plan_hierarchy_and_ownership(self) -> None:
        data = proposal(self.owner)
        validate_proposal(self.owner, data)
        self.assertEqual(TrainingPlan.objects.count(), 0)
        plan = build_plan(self.owner, data)
        self.assertEqual(plan.cycles.count(), 3)
        self.assertEqual(plan.sessions.count(), 1)
        with self.assertRaises(ValidationError):
            build_plan(self.other, data)
        invalid = copy.deepcopy(data)
        invalid["cycles"][2]["parent"] = "ma"
        with self.assertRaises(ValidationError):
            build_plan(self.owner, invalid)
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_revisions_preserve_execution_and_original_prescription(self) -> None:
        plan = build_plan(self.owner, proposal(self.owner))
        scheduled = required(plan.sessions.first())
        execution = start_session(self.owner, scheduled)
        self.assertEqual(required(execution.blocks.first()).target, {"duration_seconds": "1800"})
        self.assertEqual(required(execution.blocks.first()).actual, {})
        new = revise_plan(self.owner, plan)
        execution.refresh_from_db()
        self.assertEqual(required(execution.planned).plan_id, plan.pk)
        self.assertEqual(new.version, 2)
        self.assertEqual(new.previous, plan)
        with self.assertRaises(ValidationError):
            revise_plan(self.owner, plan)

    def test_multisport_totals_keep_units_and_protocol_separate(self) -> None:
        running = session(
            self.owner, "running", status="completed", duration_seconds=1800, reported_rpe=4
        )
        Block.objects.filter(session=running).update(actual={"distance_m": "5000"})
        swimming = session(
            self.owner,
            "swimming",
            status="completed",
            duration_seconds=1800,
            reported_rpe=4,
            duration_protocol="moving",
        )
        Block.objects.filter(session=swimming).update(actual={"distance_m": "1000"})
        session(self.owner, "running", status="completed")
        report = progress_report(self.owner)
        self.assertEqual(
            {row["sport"]: row["distance_m"] for row in report["sports"]},
            {"running": 5000, "swimming": 1000},
        )
        self.assertEqual(len(report["loads"]), 2)
        self.assertEqual(sum(row["missing"] for row in report["loads"]), 1)

    def test_trek_counts_each_stage_once(self) -> None:
        trip = TrekTrip.objects.create(owner=self.owner, title="Dos días")
        for index in range(2):
            item = session(
                self.owner,
                "hiking",
                status="completed",
                date=timezone.localdate() + timedelta(days=index),
                duration_seconds=3600,
                reported_rpe=5,
            )
            block = required(item.blocks.first())
            block.actual = {
                "distance_m": "5000",
                "ascent_m": "600",
                "descent_m": "400",
                "pack_kg": "7.5",
            }
            block.save()
            TrekStage.objects.create(
                trip=trip, session=item, order=index + 1, overnight_altitude_m=2800
            )
        summary = trip_summary(trip)
        self.assertEqual(summary["totals"]["distance_m"], 10000)
        self.assertEqual(summary["totals"]["ascent_m"], 1200)
        self.assertEqual(progress_report(self.owner)["sports"][0]["distance_m"], 10000)


class SyncTests(TestCase):
    def setUp(self) -> None:
        self.owner = account()
        self.other = account("other")
        self.session = session(self.owner)

    def test_retry_is_idempotent_and_mismatched_reuse_is_rejected(self) -> None:
        payload = session_snapshot(self.session)
        payload["duration_seconds"] = 1200
        key = uuid.uuid4()
        first = sync_session(self.owner, key, payload)
        self.assertEqual(sync_session(self.owner, key, payload), first)
        self.assertEqual(SyncReceipt.objects.count(), 1)
        payload["duration_seconds"] = 1500
        with self.assertRaises(ValidationError):
            sync_session(self.owner, key, payload)

    def test_conflicts_and_completed_history(self) -> None:
        payload = session_snapshot(self.session)
        new = sync_session(self.owner, uuid.uuid4(), payload)
        with self.assertRaises(Conflict):
            sync_session(self.owner, uuid.uuid4(), payload)
        new["status"] = "completed"
        completed = sync_session(self.owner, uuid.uuid4(), new)
        with self.assertRaises(Conflict):
            sync_session(self.owner, uuid.uuid4(), completed)

    def test_cross_account_and_invalid_children_roll_back(self) -> None:
        payload = session_snapshot(self.session)
        with self.assertRaises(ValidationError):
            sync_session(self.other, uuid.uuid4(), payload)
        payload["blocks"][0]["actual"] = {"pack_kg": 20}
        with self.assertRaises(ValidationError):
            sync_session(self.owner, uuid.uuid4(), payload)
        self.session.refresh_from_db()
        self.assertEqual(self.session.revision, 1)
        self.assertEqual(self.session.blocks.count(), 1)

    def test_new_offline_session_uuid(self) -> None:
        payload = session_snapshot(self.session)
        payload["id"] = str(uuid.uuid4())
        payload["revision"] = 0
        result = sync_session(self.owner, uuid.uuid4(), payload)
        self.assertEqual(result["revision"], 1)
        self.assertEqual(Session.objects.filter(owner=self.owner).count(), 2)
