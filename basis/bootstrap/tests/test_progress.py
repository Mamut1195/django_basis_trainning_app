"""Progress projections and trekking transactions on temporary Django databases."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.progress import progress
from basis.bootstrap.tests.test_execution import account
from basis.modules.training.adapters.django import save_validated
from basis.modules.training.adapters.models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)
from basis.modules.training.application.progress import AddStage, CreateTrip, ReadProgress, ReadTrip
from basis.modules.training.domain.trekking import StageData, TrekkingUnavailable, TripData
from basis.shared.identifiers import AccountId, SessionId, TrekTripId
from tests_architecture.progress_contract import ProgressContract


@override_settings(DEVELOPMENT_ACCESS=True)
class DjangoProgressTests(ProgressContract, TestCase):
    def setUp(self) -> None:
        self.user = account("progress")
        self.other = account("progress-other")
        self.owner = AccountId(self.user.pk)
        self.service = progress()
        self.count_trips = lambda: TrekTrip.objects.filter(owner=self.user).count()
        self.today = timezone.localdate()
        self.client.force_login(self.user)

    def hiking(self, *, foreign: bool = False, completed: bool = True) -> Session:
        row = Session.objects.create(
            owner=self.other if foreign else self.user,
            title="Hike",
            date=self.today,
            status="completed" if completed else "in_progress",
            duration_seconds=60,
            reported_rpe=Decimal(5),
        )
        Block.objects.create(
            session=row,
            order=1,
            sport="hiking",
            title="Hiking",
            actual={"distance_m": "12", "ascent_m": "0"},
        )
        return row

    def test_report_uses_block_totals_without_interval_double_count_or_foreign_rows(self) -> None:
        session = self.hiking()
        self.hiking(foreign=True)
        Interval.objects.create(block=session.blocks.get(), order=1, actual={"distance_m": "12"})
        result = self.service.read(ReadProgress(self.owner))
        self.assertEqual((result.sessions, result.sports[0].sessions), (1, 1))
        self.assertEqual(result.sports[0].distance_m, Decimal(12))
        self.assertEqual(result.loads[0].value, Decimal(5))
        response = self.client.get("/progress/")
        self.assertEqual(response.status_code, 200)

    def test_adherence_uses_replacement_local_date_with_completed_history_exception(self) -> None:
        yesterday = self.today - timedelta(days=1)
        goal = Goal.objects.create(owner=self.user, title="Hike", sport="hiking")
        original = TrainingPlan.objects.create(
            owner=self.user, goal=goal, title="P", start_date=yesterday, end_date=self.today
        )
        cycle = Cycle.objects.create(
            plan=original, title="C", kind="macro", start_date=yesterday, end_date=self.today
        )
        meso = Cycle.objects.create(
            plan=original,
            parent=cycle,
            title="Meso",
            kind="meso",
            start_date=yesterday,
            end_date=self.today,
        )
        cycle = Cycle.objects.create(
            plan=original,
            parent=meso,
            title="Micro",
            kind="micro",
            start_date=yesterday,
            end_date=self.today,
        )
        prior = PlannedSession.objects.create(
            owner=self.user, plan=original, cycle=cycle, title="Prior", date=yesterday
        )
        cutoff = PlannedSession.objects.create(
            owner=self.user, plan=original, cycle=cycle, title="Cutoff", date=self.today
        )
        done = PlannedSession.objects.create(
            owner=self.user, plan=original, cycle=cycle, title="Done", date=self.today
        )
        TrainingPlan.objects.create(
            owner=self.user,
            goal=goal,
            title="P2",
            start_date=yesterday,
            end_date=self.today,
            previous=original,
            lineage=original.lineage,
            version=2,
        )
        Session.objects.create(
            owner=self.user, planned=done, title="done", date=self.today, status="completed"
        )
        result = self.service.read(ReadProgress(self.owner))
        self.assertEqual(
            (result.scheduled_past, result.completed_scheduled, result.adherence_percent),
            (2, 1, 50.0),
        )
        self.assertNotEqual(prior.pk, cutoff.pk)

    def test_trip_stage_owner_validation_order_and_summary(self) -> None:
        trip = self.service.create_trip(CreateTrip(self.owner, TripData("Trip", "Notes")))
        session = self.hiking()
        stage = self.service.add_stage(
            AddStage(self.owner, trip, StageData(SessionId(session.pk), 1, Decimal(0)))
        )
        self.assertEqual(TrekStage.objects.get(pk=stage).overnight_altitude_m, Decimal(0))
        summary = self.service.trip(ReadTrip(self.owner, trip))
        self.assertEqual(
            (summary.stages, summary.completed, summary.totals[0].value), (1, 1, Decimal(12))
        )
        with self.assertRaises(TrekkingUnavailable):
            self.service.trip(ReadTrip(AccountId(self.other.pk), trip))
        foreign = self.hiking(foreign=True)
        with self.assertRaises(TrekkingUnavailable):
            self.service.add_stage(AddStage(self.owner, trip, StageData(SessionId(foreign.pk), 2)))
        ordinary = Session.objects.create(owner=self.user, title="No hiking", date=self.today)
        with self.assertRaises(ValidationError):
            self.service.add_stage(AddStage(self.owner, trip, StageData(SessionId(ordinary.pk), 2)))
        self.assertEqual(TrekStage.objects.count(), 1)

    def test_write_failure_rolls_back_and_web_trip_creation_delegates(self) -> None:
        from basis.modules.training.adapters.progress import DjangoProgressRepository

        original = DjangoProgressRepository.create_trip

        def fail(repository: DjangoProgressRepository, command: CreateTrip) -> TrekTripId:
            original(repository, command)
            raise ValueError("after insert")

        with patch.object(DjangoProgressRepository, "create_trip", fail):
            with self.assertRaises(ValueError):
                self.service.create_trip(CreateTrip(self.owner, TripData("Rolled back")))
        self.assertFalse(TrekTrip.objects.exists())
        response = self.client.post("/records/trip/new/", {"title": "Web trip", "notes": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TrekTrip.objects.get().owner_id, self.owner)
        trip = TrekTrip.objects.get()
        session = self.hiking()
        response = self.client.post(
            f"/trekking/{trip.pk}/stages/new/",
            {"session": str(session.pk), "order": 1, "recovery_notes": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TrekStage.objects.get().session_id, session.pk)

    def test_projection_retains_session_model_order_and_first_observed_sport_protocol(self) -> None:
        older = self.hiking()
        older.date = self.today - timedelta(days=1)
        save_validated(older)
        newer = Session.objects.create(
            owner=self.user,
            title="Run",
            date=self.today,
            status="completed",
            duration_protocol="moving",
            duration_seconds=0,
            reported_rpe=Decimal(0),
        )
        Block.objects.create(session=newer, order=1, title="Running", sport="running")
        result = self.service.read(ReadProgress(self.owner))
        self.assertEqual([s.sport for s in result.sports], ["running", "hiking"])
        self.assertEqual([s.protocol.value for s in result.loads], ["moving", "elapsed"])
        self.assertEqual(result.loads[0].value, Decimal(0))
