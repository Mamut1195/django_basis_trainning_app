"""Execute the synthetic week in docs/fixtures; no external providers or live athlete data."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal
from pathlib import Path
from typing import cast
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from basis.modules.athletes.adapters.models import SportProfile, UserExerciseRM
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.sync.adapters.actions import Conflict
from basis.modules.training.adapters.actions import revise_plan, start_session
from basis.modules.training.adapters.metrics import internal_load_legacy as internal_load
from basis.modules.training.adapters.metrics import pace_seconds_legacy as pace_seconds
from basis.modules.training.adapters.metrics import validate_metrics
from basis.modules.training.adapters.models import (
    Block,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)
from basis.modules.training.adapters.planning_actions import validate_proposal
from basis.modules.training.public import SPORTS

from .contracts import (
    ProgressDocument,
    SessionDocument,
    build_plan,
    progress_report,
    required,
    session_snapshot,
    sync_session,
    trip_summary,
)
from .factories import account

FIXTURE = Path(__file__).resolve().parents[2] / "docs" / "fixtures" / "training_week.json"


@contextmanager
def on_day(value: str) -> Iterator[None]:
    """Freeze actual dates AND created_at, needed by the versioned adherence query."""
    day = date.fromisoformat(value)
    instant = datetime.combine(day, time(17), tzinfo=datetime_timezone.utc)
    with patch("django.utils.timezone.now", return_value=instant):
        yield


class TrainingContractTests(TestCase):
    def setUp(self) -> None:
        self.week = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with on_day(self.week["days"][0]["date"]):
            self.owner = account("contract-athlete")
            athlete = self.owner.athlete
            athlete.edad = self.week["athlete"]["age"]
            athlete.save()
            preferences = self.owner.training_settings
            for key, value in self.week["athlete"].items():
                if key != "age":
                    setattr(preferences, key, value)
            preferences.save()
            for sport, _ in SPORTS:
                SportProfile.objects.create(
                    owner=self.owner, sport=sport, experience="intermediate"
                )
            self.goal = Goal.objects.create(owner=self.owner, **self.week["goal"])
            classification = Classification.objects.create(nombre="Fuerza contractual")
            exercises = {
                key: Exercise.objects.create(classification=classification, **fields).pk
                for key, fields in self.week["exercises"].items()
            }
            self.content = copy.deepcopy(self.week["plan"])
            self.content["goal_id"] = self.goal.pk
            for scheduled in self.content["sessions"]:
                for block in scheduled["blocks"]:
                    for row in block.get("sets", []):
                        row["exercise"] = exercises[row["exercise"]]
            validate_proposal(self.owner, self.content)
            self.assertEqual(TrainingPlan.objects.count(), 0)
            self.plan = build_plan(self.owner, self.content)
        self.scheduled = {s.title: s for s in self.plan.sessions.all()}

    def record(
        self,
        title: str,
        *,
        planned: PlannedSession | None = None,
        results: SessionDocument | None = None,
    ) -> Session:
        planned = planned or self.scheduled[title]
        session = start_session(self.owner, planned)
        snapshot = session_snapshot(session)
        results = results if results is not None else self.week["executions"][title]
        for key, value in results.items():
            if key != "blocks":
                cast(dict[str, object], snapshot)[key] = value
        for block, changes in zip(snapshot["blocks"], results["blocks"], strict=True):
            for key, value in changes.items():
                if key in ("sets", "intervals"):
                    for row, actual in zip(
                        cast(list[dict[str, object]], cast(dict[str, object], block)[key]),
                        cast(list[dict[str, object]], value),
                        strict=True,
                    ):
                        row.update(actual)
                else:
                    cast(dict[str, object], block)[key] = value
        result = sync_session(self.owner, uuid.uuid4(), snapshot)
        session.refresh_from_db()
        persisted = session_snapshot(session)
        # DecimalField reload adds scale ("5" -> "5.0"); compare its numeric value.
        for value in (result, persisted):
            if value["reported_rpe"] is not None:
                value["reported_rpe"] = Decimal(cast(Decimal | float | str, value["reported_rpe"]))
        self.assertEqual(result, persisted)
        return session

    def first_days(self) -> tuple[Session, Session]:
        with on_day("2026-10-12"):
            completed = self.record("Fuerza y cardio suave")
        with on_day("2026-10-13"):
            partial = self.record("Running cómodo")
        return completed, partial

    def prescription_snapshot(self) -> dict[str, object]:
        blocks = Block.objects.filter(planned__plan=self.plan)
        return {
            "plan": TrainingPlan.objects.filter(pk=self.plan.pk).values().get(),
            "cycles": list(self.plan.cycles.order_by("pk").values()),
            "scheduled": list(self.plan.sessions.order_by("pk").values()),
            "blocks": list(blocks.order_by("pk").values()),
            "sets": list(StrengthSet.objects.filter(block__in=blocks).order_by("pk").values()),
            "intervals": list(Interval.objects.filter(block__in=blocks).order_by("pk").values()),
        }

    def assert_report(self, expected: Mapping[str, object]) -> ProgressDocument:
        report = progress_report(self.owner)
        for key, value in expected.items():
            self.assertEqual(cast(dict[str, object], report)[key], value, key)
        return report

    def test_full_week_revision_history_adherence_and_nonduplicated_units(self) -> None:
        completed, partial = self.first_days()
        original = self.prescription_snapshot()
        observations = [session_snapshot(s) for s in (completed, partial)]
        review = self.week["review"]
        with on_day(review["date"]):
            self.assert_report(self.week["expected"]["before_review"])
            self.assertFalse(self.scheduled["Natación técnica"].executions.exists())
            self.assertEqual(partial.status, "in_progress")
            self.assertIsNone(partial.load)
            new = revise_plan(self.owner, self.plan, review["reason"])
            self.assertEqual(
                (new.lineage, new.version, new.previous_id), (self.plan.lineage, 2, self.plan.pk)
            )
            self.assertEqual(new.cycles.count(), 3)
            self.assertSetEqual(
                set(new.sessions.values_list("title", flat=True)),
                {review["session"], "Senderismo etapa 1", "Senderismo etapa 2"},
            )
            # Merely cloning has not moved the due session or changed adherence.
            self.assert_report(self.week["expected"]["before_review"])
            moved = new.sessions.get(title=review["session"])
            self.assertEqual(moved.date.isoformat(), review["from"])
            self.client.force_login(self.owner)
            response = self.client.post(
                reverse("scheduled-reschedule", args=[moved.pk]),
                {"date": review["to"], "revision": moved.revision, "reason": review["reason"]},
            )
            self.assertEqual(response.status_code, 302)
            original_moved = moved
            moved = PlannedSession.objects.get(
                pk=int(response["Location"].rstrip("/").split("/")[-1])
            )
            self.assertEqual(original_moved.date.isoformat(), review["from"])
            self.assertEqual((moved.date.isoformat(), moved.revision), (review["to"], 3))
            new = moved.plan
            self.assert_report(self.week["expected"]["after_reschedule"])
            with self.assertRaises(ValidationError):
                revise_plan(self.owner, self.plan)
        self.assertEqual(original, self.prescription_snapshot())
        self.assertEqual(observations, [session_snapshot(s) for s in (completed, partial)])
        self.assertEqual(partial.planned_id, self.scheduled[partial.title].pk)
        with on_day(review["to"]):
            cycling = self.record(review["session"], planned=moved)
            self.assertEqual(cycling.date, moved.date)
            self.assertNotIn("power_w", cycling.blocks.get().actual)
            self.assertNotIn("cadence_rpm", cycling.blocks.get().actual)
        trip = TrekTrip.objects.create(owner=self.owner, title=self.week["trek"]["title"])
        for row in self.week["trek"]["stages"]:
            planned = new.sessions.get(title=row["session"])
            with on_day(planned.date.isoformat()):
                item = self.record(row["session"], planned=planned)
                TrekStage.objects.create(
                    trip=trip, session=item, **{k: v for k, v in row.items() if k != "session"}
                )
        with on_day("2026-10-18"):
            report = self.assert_report(self.week["expected"]["week_end"])
        sports = {row["sport"]: row for row in report["sports"]}
        self.assertSetEqual(set(sports), set(self.week["expected"]["sports"]))
        for sport, expected in self.week["expected"]["sports"].items():
            for key, value in expected.items():
                self.assertEqual(
                    cast(dict[str, object], sports[sport])[key],
                    Decimal(value) if isinstance(value, str) else value,
                    (sport, key),
                )
        # The mixed session counts once globally, once within each of its two sports.
        self.assertEqual(sum(s["sessions"] for s in sports.values()), report["sessions"] + 1)
        self.assertNotIn("running", sports)  # Partial actuals are retained, excluded from totals.
        self.assertNotIn("swimming", sports)  # Unexecuted targets are never actual distance.
        loads = {row["protocol"]: row for row in report["loads"]}
        self.assertSetEqual(set(loads), {"elapsed", "moving"})
        for protocol, expected in self.week["expected"]["loads"].items():
            for key, value in expected.items():
                self.assertEqual(
                    cast(dict[str, object], loads[protocol])[key],
                    Decimal(value) if key == "value" else value,
                )
        summary = trip_summary(trip)
        self.assertEqual((summary["stages"], summary["completed"]), (2, 2))
        self.assertEqual(
            summary["totals"], {k: Decimal(v) for k, v in self.week["expected"]["trip"].items()}
        )
        self.assertEqual(summary["totals"]["distance_m"], sports["hiking"]["distance_m"])
        self.assertIsNone(trip.stages.get(order=2).overnight_altitude_m)
        # Human goal comparison is explicitly per hiking stage, not mixed-sport totals.
        observed_stage = trip.stages.get(order=1).session.blocks.get(sport="hiking")
        self.assertEqual(self.goal.target_unit, "m")
        self.assertEqual(Decimal(observed_stage.actual["distance_m"]), self.goal.target_value)
        self.assertEqual(self.goal.baseline_value, Decimal("6000"))
        self.assertEqual(original, self.prescription_snapshot())
        self.assertEqual(Session.objects.filter(owner=self.owner).count(), 5)

    def test_partial_can_finish_below_target_without_rewriting_prescription(self) -> None:
        _, partial = self.first_days()
        with on_day("2026-10-13"):
            self.assertEqual(start_session(self.owner, required(partial.planned)).pk, partial.pk)
            self.assertEqual(progress_report(self.owner)["sessions"], 1)
            stale = session_snapshot(partial)
            finished = self.record(
                partial.title, results=self.week["running_completion_alternative"]
            )
            self.assertEqual(
                (finished.pk, finished.revision, finished.status), (partial.pk, 3, "completed")
            )
            block = finished.blocks.get()
            self.assertEqual(block.target["distance_m"], "4000")
            self.assertEqual(block.actual["distance_m"], "3000")
            self.assertEqual(required(finished.planned).blocks.get().actual, {})
            self.assertEqual(finished.load, Decimal("125.00"))
            self.assertEqual(
                pace_seconds(block.actual),
                Decimal(self.week["expected"]["alternative_running_pace_seconds_km"]),
            )
            report = self.assert_report(
                {
                    "sessions": 2,
                    "scheduled_past": 2,
                    "completed_scheduled": 2,
                    "adherence_percent": 100.0,
                }
            )
            self.assertEqual(
                next(s for s in report["sports"] if s["sport"] == "running")["distance_m"],
                Decimal("3000"),
            )
            with self.assertRaises(Conflict):
                sync_session(self.owner, uuid.uuid4(), stale)
            immutable = session_snapshot(finished)
            edit = copy.deepcopy(immutable)
            edit["duration_seconds"] = 999
            with self.assertRaises(Conflict):
                sync_session(self.owner, uuid.uuid4(), edit)
            self.assertEqual(session_snapshot(Session.objects.get(pk=finished.pk)), immutable)

    def test_seven_days_hierarchy_sport_catalog_and_manual_provenance(self) -> None:
        days = [date.fromisoformat(d["date"]) for d in self.week["days"]]
        self.assertEqual(days, [date(2026, 10, 12) + timedelta(days=i) for i in range(7)])
        self.assertEqual(self.week["contract_version"], "basis-005-v1")
        self.assertEqual(self.week["provenance"]["kind"], "synthetic_manual_example")
        self.assertGreaterEqual(required(self.owner.athlete.edad), 18)
        self.assertEqual(self.owner.training_settings.timezone_name, "America/Guayaquil")
        self.assertEqual(self.plan.goal_id, self.goal.pk)
        macro = self.plan.cycles.get(kind="macro")
        meso = self.plan.cycles.get(kind="meso")
        micro = self.plan.cycles.get(kind="micro")
        self.assertIsNone(macro.parent_id)
        self.assertEqual((meso.parent_id, micro.parent_id), (macro.pk, meso.pk))
        self.assertTrue(all(s.cycle_id == micro.pk for s in self.scheduled.values()))
        self.assertSetEqual(
            set(Block.objects.values_list("sport", flat=True)), {sport for sport, _ in SPORTS}
        )
        self.assertFalse(Block.objects.exclude(actual={}).exists())

    def test_accounts_cannot_execute_revise_reschedule_or_import_others_goal(self) -> None:
        _, partial = self.first_days()
        with on_day("2026-10-15"):
            other = account("contract-other")
            with self.assertRaises(ValidationError):
                build_plan(other, self.content)
            with self.assertRaises(PlannedSession.DoesNotExist):
                start_session(other, required(partial.planned))
            with self.assertRaises(TrainingPlan.DoesNotExist):
                revise_plan(other, self.plan)
            with self.assertRaises(ValidationError):
                sync_session(other, uuid.uuid4(), session_snapshot(partial))
            self.client.force_login(other)
            response = self.client.post(
                reverse("scheduled-reschedule", args=[self.scheduled["Bicicleta fácil"].pk]),
                {"date": "2026-10-16", "revision": 1},
            )
            self.assertEqual(response.status_code, 404)
            report = progress_report(other)
            self.assertEqual((report["sessions"], report["scheduled_past"]), (0, 0))
            self.assertIsNone(report["adherence_percent"])
            self.assertEqual(report["sports"], [])
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_unknown_zero_pace_and_estimator_are_not_inferred_intensity(self) -> None:
        metrics = validate_metrics("cycling", {"ascent_m": 0, "power_w": None})
        self.assertEqual(metrics, {"ascent_m": "0"})
        self.assertIsNone(internal_load(1800, None))
        self.assertEqual(internal_load(1800, 0), Decimal("0.00"))
        self.assertIsNone(pace_seconds({"distance_m": "0", "duration_seconds": "1200"}))
        self.assertIsNone(pace_seconds({"distance_m": "800"}, 100))
        self.assertEqual(
            pace_seconds({"distance_m": "800", "duration_seconds": "1200"}, 100), Decimal("150.00")
        )
        with on_day("2026-10-12"):
            actual = copy.deepcopy(self.week["executions"]["Fuerza y cardio suave"])
            actual["blocks"][0]["sets"][1]["actual_rpe"] = "10"
            item = self.record("Fuerza y cardio suave", results=actual)
            rows = list(item.blocks.get(sport="strength").sets.all())
            self.assertIsNone(rows[0].estimated_1rm)  # Warmup.
            self.assertEqual(rows[1].estimated_1rm, Decimal("31.67"))
            self.assertIsNone(rows[2].estimated_1rm)  # Effort 7 is not maximal.
            self.assertIsNone(rows[4].external_volume_kg)  # Bodyweight is not external kg.
            self.assertIsNone(rows[4].estimated_1rm)
            reference = UserExerciseRM.objects.create(
                user=self.owner.athlete,
                exercise=rows[1].exercise,
                peso_maximo_rm="50",
                fecha_registro="2026-10-04",
            )
            prescription = copy.deepcopy(self.content)
            row = prescription["sessions"][0]["blocks"][0]["sets"][1]
            row.update(rm_reference=reference.pk, target_percent_rm="50", target_rpe=None)
            plan = build_plan(self.owner, prescription)
            copied = start_session(self.owner, plan.sessions.get(title=item.title))
            prescribed = copied.blocks.get(sport="strength").sets.get(order=2)
            self.assertIsNone(prescribed.actual_rpe)
            self.assertIsNone(prescribed.target_rpe)
            self.assertIsNone(prescribed.actual_kg)
            self.assertIsNone(prescribed.estimated_1rm)

    def test_invalid_prescription_results_and_unreferenced_rm_roll_back(self) -> None:
        for invalid in (
            "actual",
            "block_actual",
            "interval_actual",
            "rm",
            "hierarchy",
            "sport_metric",
        ):
            with self.subTest(invalid=invalid):
                content = copy.deepcopy(self.content)
                if invalid == "actual":
                    content["sessions"][0]["blocks"][0]["sets"][0]["actual_reps"] = 8
                elif invalid == "block_actual":
                    content["sessions"][1]["blocks"][0]["actual"] = {"distance_m": 1000}
                elif invalid == "interval_actual":
                    content["sessions"][1]["blocks"][0]["intervals"][0]["actual_rpe"] = "5"
                elif invalid == "rm":
                    content["sessions"][0]["blocks"][0]["sets"][0]["target_percent_rm"] = "75"
                elif invalid == "hierarchy":
                    content["cycles"][2]["parent"] = "macro"
                else:
                    content["sessions"][1]["blocks"][0]["target"]["power_w"] = 150
                with self.assertRaises(ValidationError):
                    validate_proposal(self.owner, content)
                self.assertEqual(TrainingPlan.objects.count(), 1)
        self.assertEqual(timezone.get_default_timezone_name(), "America/Guayaquil")
