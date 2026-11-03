"""MAM-815 synthetic manual observations through the existing progress service."""

from datetime import date
from decimal import Decimal
from typing import cast

from django.test import TestCase

from basis.bootstrap.progress import progress
from basis.modules.athletes.adapters.models import Wellness
from basis.modules.training.adapters.actions import progress_report
from basis.modules.training.adapters.models import (
    Block,
    Interval,
    Session,
    StrengthSet,
    TrekStage,
    TrekTrip,
)
from basis.modules.training.adapters.progress import DjangoProgressRepository
from basis.modules.training.application.progress import ReadProgress, ReadTrip
from basis.shared.identifiers import AccountId, TrekTripId

from .factories import account, exercise


class MultisportProgressTests(TestCase):
    def setUp(self) -> None:
        self.owner = account("multisport-815")
        self.other = account("multisport-815-other")
        self.service = progress()
        self.owner_id = AccountId(self.owner.pk)
        self.client.force_login(self.owner)

    def session(
        self,
        day: int,
        sport: str,
        *,
        protocol: str = "elapsed",
        duration: int | None = 600,
        rpe: Decimal | None = Decimal(5),
        distance: str | None = None,
    ) -> Session:
        row = Session.objects.create(
            owner=self.owner,
            title=sport,
            date=date(2026, 10, day),
            status="completed",
            duration_protocol=protocol,
            duration_seconds=duration,
            reported_rpe=rpe,
        )
        Block.objects.create(
            session=row,
            order=1,
            sport=sport,
            title=sport,
            actual={"distance_m": distance} if distance is not None else {},
        )
        return row

    def test_all_disciplines_keep_units_protocols_missingness_and_source_totals(self) -> None:
        strength = self.session(12, "strength")
        StrengthSet.objects.create(
            block=strength.blocks.get(),
            exercise=exercise(),
            order=1,
            actual_reps=10,
            actual_kg=Decimal(20),
        )
        # A mixed session has one internal load even with repeated sport blocks.
        Block.objects.create(
            session=strength, order=2, sport="cardio", title="Cardio", actual={"distance_m": "20"}
        )
        Block.objects.create(
            session=strength, order=3, sport="cardio", title="Cardio", actual={"distance_m": "30"}
        )
        self.session(12, "running", distance="3000")
        self.session(13, "cycling", protocol="moving", distance="20000")
        self.session(13, "swimming", rpe=Decimal(0), distance="800")
        hiking = self.session(14, "hiking", distance="1000")
        unknown = self.session(15, "hiking", duration=None, distance=None)
        self.session(17, "running", rpe=None)
        trip = TrekTrip.objects.create(owner=self.owner, title="Two stages")
        TrekStage.objects.create(
            trip=trip,
            session=hiking,
            order=1,
            overnight_altitude_m=Decimal(0),
            recovery_notes="Dormí bien; observación declarada.",
        )
        TrekStage.objects.create(trip=trip, session=unknown, order=2)
        Interval.objects.create(
            block=hiking.blocks.get(), order=1, actual={"distance_m": "1000"}, actual_rpe=10
        )
        partial = Session.objects.create(
            owner=self.owner, title="Partial", date=date(2026, 10, 16), status="in_progress"
        )
        Block.objects.create(
            session=partial,
            order=1,
            title="Partial",
            sport="running",
            actual={"distance_m": "99999"},
        )
        result = progress_report(self.owner)
        sports = {row.sport: row for row in self.service.read(ReadProgress(self.owner_id)).sports}
        self.assertEqual(
            set(sports), {"strength", "cardio", "running", "cycling", "swimming", "hiking"}
        )
        self.assertEqual(sports["strength"].external_volume_kg, Decimal(200))
        self.assertIsNone(sports["strength"].distance_m)
        for sport, total in (
            ("cardio", 50),
            ("running", 3000),
            ("cycling", 20000),
            ("swimming", 800),
            ("hiking", 1000),
        ):
            self.assertEqual(sports[sport].distance_m, Decimal(total))
            self.assertIsNone(sports[sport].external_volume_kg)
        self.assertEqual((sports["cardio"].sessions, sports["cardio"].rpe_known), (1, 1))
        self.assertEqual(
            (sports["hiking"].distance_coverage.known, sports["hiking"].distance_coverage.missing),
            (1, 1),
        )
        loads = {row["protocol"]: row for row in cast(list[dict[str, object]], result["loads"])}
        self.assertEqual(
            (loads["elapsed"]["value"], loads["elapsed"]["known"], loads["elapsed"]["missing"]),
            (Decimal(150), 4, 2),
        )
        self.assertEqual((loads["moving"]["value"], loads["moving"]["known"]), (Decimal(50), 1))
        self.assertEqual(result["sessions"], 7)
        summary = self.service.trip(ReadTrip(self.owner_id, TrekTripId(trip.pk)))
        self.assertEqual((summary.completed, summary.totals[0].value), (2, Decimal(1000)))
        context = {
            row["session_id"]: row for row in cast(list[dict[str, object]], result["context"])
        }
        self.assertEqual(len(context), 7)
        self.assertEqual(context[str(strength.pk)]["sports"], ["strength", "cardio"])
        self.assertEqual(context[str(strength.pk)]["internal_load"], Decimal(50))
        self.assertEqual(context[str(hiking.pk)]["consecutive_days"], 3)
        self.assertEqual(context[str(unknown.pk)]["consecutive_days"], 4)
        self.assertIsNone(context[str(unknown.pk)]["internal_load"])
        recovery = cast(dict[str, object], context[str(hiking.pk)]["stage_recovery"])
        self.assertEqual(recovery["overnight_altitude_m"], Decimal(0))
        self.assertIn("observación declarada", cast(str, recovery["recovery_notes"]))
        missing = cast(dict[str, object], context[str(unknown.pk)]["stage_recovery"])
        self.assertIsNone(missing["overnight_altitude_m"])
        self.assertEqual(missing["recovery_notes"], "")
        self.assertIsNone(context[str(strength.pk)]["stage_recovery"])

    def test_web_range_context_is_private_and_wellness_remains_declared(self) -> None:
        self.session(12, "running", distance="1000")
        hiking = self.session(13, "hiking", duration=0, rpe=Decimal(0), distance="0")
        foreign = Session.objects.create(
            owner=self.other,
            title="Private foreign session",
            date=date(2026, 10, 13),
            status="completed",
        )
        Block.objects.create(
            session=foreign, order=1, sport="running", title="Private foreign block"
        )
        Wellness.objects.create(owner=self.owner, date=date(2026, 10, 13), sleep_hours=0)
        Wellness.objects.create(
            owner=self.other, date=date(2026, 10, 13), pain_regions="Foreign private pain"
        )
        response = self.client.get("/progress/", {"period": "day", "reference": "2026-10-13"})
        self.assertEqual(response.status_code, 200)
        report = response.context["report"]
        self.assertEqual(report["sessions"], 1)
        (row,) = report["context"]
        self.assertEqual(row["session_id"], str(hiking.pk))
        self.assertEqual(row["internal_load"], Decimal(0))
        self.assertIsNone(row["previous_date"])
        self.assertEqual(row["consecutive_days"], 1)
        self.assertIn("período seleccionado", report["context_method"])
        self.assertIn("session-rpe-v1", report["load_method"])
        self.assertContains(response, "Sin datos")
        self.assertContains(response, "Recuperación")
        self.assertNotContains(response, "Foreign private")
        (wellness,) = response.context["wellness_records"]
        self.assertEqual(wellness.date, date(2026, 10, 13))
        self.assertEqual(wellness.sleep_hours, Decimal(0))
        self.assertEqual(wellness.pain_regions, "")
        self.client.force_login(self.other)
        other = self.client.get("/progress/")
        self.assertEqual(
            [r["session_id"] for r in other.context["report"]["context"]], [str(foreign.pk)]
        )
        self.assertNotIn(str(hiking.pk), str(other.context["report"]))

    def test_recovery_projection_and_trip_summary_reject_malformed_foreign_links(self) -> None:
        hiking = self.session(12, "hiking", distance="1000")
        own_trip = TrekTrip.objects.create(owner=self.owner, title="Own")
        foreign_trip = TrekTrip.objects.create(owner=self.other, title="Foreign private trip")
        stage = TrekStage.objects.create(trip=own_trip, session=hiking, order=1)
        # Simulate an administrative SQL inconsistency, bypassing validated writes.
        TrekStage.objects.filter(pk=stage.pk).update(
            trip=foreign_trip, recovery_notes="Foreign private notes"
        )
        context = progress_report(self.owner)["context"]
        self.assertIsNone(cast(list[dict[str, object]], context)[0]["stage_recovery"])
        summary = self.service.trip(ReadTrip(AccountId(self.other.pk), TrekTripId(foreign_trip.pk)))
        self.assertEqual((summary.stages, summary.completed), (0, 0))
        self.assertNotIn("Foreign private", str(progress_report(self.owner)))

    def test_projection_reads_stages_in_bulk_and_does_not_fetch_interval_detail(self) -> None:
        trip = TrekTrip.objects.create(owner=self.owner, title="Bulk")
        for order in range(1, 5):
            session = self.session(10 + order, "hiking", distance="1000")
            TrekStage.objects.create(trip=trip, session=session, order=order)
            Interval.objects.create(
                block=session.blocks.get(), order=1, actual={"distance_m": "1000"}
            )
        with self.assertNumQueries(3):
            sessions = DjangoProgressRepository().sessions(self.owner_id)
        self.assertEqual(len(sessions), 4)
        self.assertTrue(all(s.stage_recovery is not None for s in sessions))
