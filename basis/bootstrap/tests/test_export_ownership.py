"""Every export relationship is selected by the authenticated account."""

import json
from decimal import Decimal
from typing import cast

from django.contrib.auth.models import User as Account
from django.db import models
from django.test import TestCase
from django.utils import timezone

from basis.modules.athletes.adapters.models import (
    AthleteSettings,
    Measurement,
    SportProfile,
    User,
    UserExerciseRM,
    Wellness,
    WorkoutData,
)
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.coach.adapters.models import AIJob, PlanProposal, UsagePeriod
from basis.modules.training.adapters.models import (
    Block,
    Cycle,
    Goal,
    Interval,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
    TrekStage,
    TrekTrip,
)


class ExportOwnershipTests(TestCase):
    def records(self, owner: Account, exercise: Exercise) -> dict[str, list[models.Model]]:
        day = timezone.localdate()
        athlete = User.objects.create(
            account=owner, nombre=owner.username, email=owner.email, fecha_inicio=day
        )
        preferences = AthleteSettings.objects.create(owner=owner)
        measurement = Measurement.objects.create(owner=owner, weight_kg=Decimal("70"))
        sport = SportProfile.objects.create(owner=owner, sport="running")
        wellness = Wellness.objects.create(owner=owner)
        rm = UserExerciseRM.objects.create(
            user=athlete, exercise=exercise, peso_maximo_rm=Decimal("100"), fecha_registro=day
        )
        workout = WorkoutData.objects.create(
            user=athlete, exercise=exercise, fecha=day, sets=3, reps=5, peso=Decimal("50")
        )
        goal = Goal.objects.create(owner=owner, title=owner.username + " goal", sport="running")
        plan = TrainingPlan.objects.create(
            owner=owner, goal=goal, title=owner.username + " plan", start_date=day, end_date=day
        )
        cycles: list[Cycle] = []
        for kind in ("macro", "meso", "micro"):
            cycles.append(
                Cycle.objects.create(
                    plan=plan,
                    parent=cycles[-1] if cycles else None,
                    kind=kind,
                    title=kind,
                    start_date=day,
                    end_date=day,
                )
            )
        planned = PlannedSession.objects.create(
            owner=owner, plan=plan, cycle=cycles[-1], title="Scheduled", date=day
        )
        planned_strength = Block.objects.create(planned=planned, sport="strength", title="Strength")
        planned_running = Block.objects.create(planned=planned, sport="running", title="Running")
        prescribed_set = StrengthSet.objects.create(block=planned_strength, exercise=exercise)
        prescribed_interval = Interval.objects.create(block=planned_running)
        session = Session.objects.create(owner=owner, planned=planned, title="Execution", date=day)
        executed_strength = Block.objects.create(
            session=session, sport="strength", title="Strength"
        )
        executed_running = Block.objects.create(session=session, sport="running", title="Running")
        hiking = Block.objects.create(session=session, sport="hiking", title="Hiking")
        sets = [
            prescribed_set,
            StrengthSet.objects.create(block=executed_strength, exercise=exercise),
        ]
        intervals = [prescribed_interval, Interval.objects.create(block=executed_running)]
        trip = TrekTrip.objects.create(owner=owner, title="Trekking")
        stage = TrekStage.objects.create(trip=trip, session=session, order=1)
        period = UsagePeriod.objects.create(owner=owner, key="export-test")
        job = AIJob.objects.create(
            owner=owner,
            kind="plan",
            prompt=owner.username + " private prompt",
            context={"account": owner.pk},
            usage_period=period,
            reservation=Decimal("0.01"),
            requested_model="offline-test",
            base_plan=plan,
        )
        proposal = PlanProposal.objects.create(
            owner=owner, job=job, base_plan=plan, content={"x": 1}
        )
        return {
            "athlete": [athlete],
            "athletesettings": [preferences],
            "measurement": [measurement],
            "sportprofile": [sport],
            "wellness": [wellness],
            "workoutdata": [workout],
            "userexerciserm": [rm],
            "goal": [goal],
            "trainingplan": [plan],
            "cycle": list(cycles),
            "plannedsession": [planned],
            "session": [session],
            "block": [
                planned_strength,
                executed_strength,
                planned_running,
                executed_running,
                hiking,
            ],
            "strengthset": list(sets),
            "interval": list(intervals),
            "trektrip": [trip],
            "trekstage": [stage],
            "aijob": [job],
            "planproposal": [proposal],
        }

    def test_all_nineteen_sections_preserve_v1_and_exclude_every_foreign_relationship(self) -> None:
        owner = Account.objects.create_user(username="export-all-owner", email="own@example.test")
        foreign = Account.objects.create_user(
            username="export-all-foreign", email="other@example.test"
        )
        exercise = Exercise.objects.create(
            nombre="Export exercise", classification=Classification.objects.create(nombre="Export")
        )
        own = self.records(owner, exercise)
        other = self.records(foreign, exercise)
        self.assertEqual(len(own), 19)
        self.client.force_login(owner)
        response = self.client.get("/export/")
        self.assertEqual(response.status_code, 200)
        payload = cast(dict[str, object], json.loads(response.content))
        self.assertEqual(payload["schema"], "basis-export-v1")
        self.assertEqual(set(payload), set(own) | {"schema", "exported_at"})
        legacy_labels = {
            "athlete": "daily_trainning_app.user",
            "workoutdata": "daily_trainning_app.workoutdata",
            "userexerciserm": "daily_trainning_app.userexerciserm",
        }
        for section, expected in own.items():
            with self.subTest(section=section):
                rows = cast(list[dict[str, object]], payload[section])
                identifiers = {str(row["pk"]) for row in rows}
                self.assertEqual(identifiers, {str(row.pk) for row in expected})
                self.assertTrue(identifiers.isdisjoint(str(row.pk) for row in other[section]))
                label = legacy_labels.get(section, "training." + section)
                for row in rows:
                    self.assertEqual(set(row), {"pk", "model", "fields"})
                    self.assertEqual(row["model"], label)
                    fields = cast(dict[str, object], row["fields"])
                    self.assertEqual(
                        set(fields),
                        {
                            field.name
                            for field in expected[0]._meta.concrete_fields
                            if not field.primary_key
                        },
                    )
                    if "owner" in fields:
                        self.assertEqual(fields["owner"], owner.pk)
                    if section in ("workoutdata", "userexerciserm"):
                        self.assertEqual(fields["user"], own["athlete"][0].pk)
        self.assertNotContains(response, foreign.email)
        self.assertNotContains(response, "export-all-foreign private prompt")
