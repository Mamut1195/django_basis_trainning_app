"""Planning persistence/version/web compatibility in temporary databases."""

import copy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.planning import build_proposal, planning
from basis.bootstrap.tests.test_execution import account
from basis.modules.athletes.adapters.models import UserExerciseRM
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.training.adapters.models import (
    Block,
    Cycle,
    Goal,
    PlannedSession,
    Session,
    StrengthSet,
    TrainingPlan,
)
from basis.modules.training.adapters.planning import DjangoPlanRepository
from basis.modules.training.adapters.wire import encode_block, object_map, sequence
from basis.modules.training.public import (
    BlockData,
    CreatePlan,
    PlanningUnavailable,
    RevisePlan,
    StrengthData,
)
from basis.shared.identifiers import AccountId, GoalId, PlannedSessionId
from tests_architecture.planning_contract import PlanningContract
from tests_architecture.test_planning import TODAY, Clock, definition


@override_settings(DEVELOPMENT_ACCESS=True)
class DjangoPlanningTests(PlanningContract, TestCase):
    def setUp(self) -> None:
        self.user = account("planning")
        self.other = account("planning-other")
        self.owner = AccountId(self.user.pk)
        goal = Goal.objects.create(owner=self.user, title="Consistency", sport="running")
        self.definition = definition(GoalId(goal.pk))
        self.repository = DjangoPlanRepository()
        self.service = planning()
        self.service.clock = Clock()
        self.count_plans = lambda: TrainingPlan.objects.filter(owner=self.user).count()
        self.mark_executed = self.execute
        self.client.force_login(self.user)

    def execute(self, id: PlannedSessionId) -> None:
        row = PlannedSession.objects.get(pk=id)
        Session.objects.create(owner=self.user, planned=row, title=row.title, date=row.date)

    def proposal(self) -> dict[str, object]:
        data = self.definition
        block = encode_block(data.sessions[0].blocks[0])
        block["target"] = {"duration_seconds": 1800}
        return {
            "title": data.title,
            "goal_id": data.goal,
            "start_date": data.start_date.isoformat(),
            "end_date": data.end_date.isoformat(),
            "cycles": [
                {
                    "key": c.key,
                    "parent": c.parent,
                    "kind": c.kind.value,
                    "title": c.title,
                    "start_date": c.start_date.isoformat(),
                    "end_date": c.end_date.isoformat(),
                }
                for c in data.cycles
            ],
            "sessions": [
                {"title": "Run", "cycle_key": "mi", "date": TODAY.isoformat(), "blocks": [block]}
            ],
        }

    @staticmethod
    def first_block(content: dict[str, object]) -> dict[str, object]:
        return object_map(sequence(object_map(sequence(content["sessions"])[0])["blocks"])[0])

    def measured_rm(self, *, foreign: bool = False) -> UserExerciseRM:
        classification = Classification.objects.create(nombre="Strength")
        exercise = Exercise.objects.create(nombre="Squat", classification=classification)
        return UserExerciseRM.objects.create(
            user=self.other.athlete if foreign else self.user.athlete,
            exercise=exercise,
            peso_maximo_rm=Decimal(100),
            fecha_registro=TODAY - timedelta(days=30),
        )

    def test_revision_copies_rich_prescription_and_frozen_rm_without_actuals(self) -> None:
        rm = self.measured_rm()
        strength = StrengthData(
            exercise=rm.exercise_id,
            target_reps_min=4,
            target_reps_max=6,
            target_percent_rm=Decimal(75),
            target_rpe=Decimal(8),
            target_rir=2,
            rest_seconds=120,
            tempo="3-1-1",
            target_isometric_seconds=0,
            group="A",
            rm_reference=rm.pk,
        )
        data = replace(
            self.definition,
            sessions=(
                replace(
                    self.definition.sessions[1],
                    blocks=(BlockData("strength", "Squat", sets=(strength,)),),
                ),
            ),
        )
        original = self.service.create(CreatePlan(self.owner, data))
        new = self.service.revise(RevisePlan(self.owner, original.id))
        first = StrengthSet.objects.get(block__planned__plan_id=original.id)
        cloned = StrengthSet.objects.get(block__planned__plan_id=new.id)
        assert first.pk != cloned.pk
        for field in (
            "exercise_id",
            "target_reps_min",
            "target_reps_max",
            "target_percent_rm",
            "target_rpe",
            "target_rir",
            "rest_seconds",
            "tempo",
            "target_isometric_seconds",
            "group",
            "rm_reference_id",
        ):
            assert getattr(first, field) == getattr(cloned, field)
        assert cloned.actual_kg is None and cloned.actual_reps is None and cloned.actual_rpe is None
        assert cloned.isometric_seconds is None and cloned.actual_rest_seconds is None
        assert not Session.objects.exists()

    def test_foreign_rm_failure_rolls_back_plan_cycles_blocks_and_sessions(self) -> None:
        rm = self.measured_rm(foreign=True)
        data = replace(
            self.definition,
            sessions=(
                replace(
                    self.definition.sessions[1],
                    blocks=(
                        BlockData(
                            "strength",
                            "Squat",
                            sets=(StrengthData(exercise=rm.exercise_id, rm_reference=rm.pk),),
                        ),
                    ),
                ),
            ),
        )
        with self.assertRaises(ValidationError):
            self.service.create(CreatePlan(self.owner, data))
        assert not TrainingPlan.objects.exists() and not Cycle.objects.exists()
        assert (
            not PlannedSession.objects.exists()
            and not Block.objects.exists()
            and not StrengthSet.objects.exists()
        )

    def test_actual_zero_in_proposal_never_becomes_prescription(self) -> None:
        content = self.proposal()
        self.first_block(content)["actual"] = {"duration_seconds": 0}
        with self.assertRaises(ValidationError):
            build_proposal(self.user.pk, content)
        assert not TrainingPlan.objects.exists()

    def test_calendar_and_revision_are_scoped_to_owner(self) -> None:
        original = self.service.create(CreatePlan(self.owner, self.definition))
        assert (
            len(
                self.service.calendar(
                    self.owner, TODAY - timedelta(days=2), TODAY + timedelta(days=6)
                )
            )
            == 3
        )
        assert not self.service.calendar(
            AccountId(self.other.pk), TODAY - timedelta(days=2), TODAY + timedelta(days=6)
        )
        with self.assertRaises(PlanningUnavailable):
            self.service.revise(RevisePlan(AccountId(self.other.pk), original.id))
        assert self.count_plans() == 1

    def test_source_mutation_does_not_change_created_instance(self) -> None:
        content = self.proposal()
        original = copy.deepcopy(content)
        row = build_proposal(self.user.pk, content)
        assert row is not None
        object_map(self.first_block(content)["target"])["duration_seconds"] = 99
        object_map(sequence(content["cycles"])[0])["title"] = "Changed source"
        block = Block.objects.get(planned__plan=row)
        assert block.target == {
            "duration_seconds": str(
                object_map(self.first_block(original)["target"])["duration_seconds"]
            )
        }
        assert Cycle.objects.get(plan=row, kind="macro").title != "Changed source"

    def test_manual_draft_cycles_schedule_and_revision_conflict_forms(self) -> None:
        day = timezone.localdate()
        goal = Goal.objects.filter(owner=self.user).first()
        assert goal is not None
        response = self.client.post(
            "/plans/new/",
            {
                "title": "Manual",
                "goal": goal.pk,
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=2)).isoformat(),
            },
        )
        assert response.status_code == 302
        plan = TrainingPlan.objects.get(owner=self.user)
        assert not plan.cycles.exists() and not plan.sessions.exists()
        parent = None
        for kind in ("macro", "meso", "micro"):
            response = self.client.post(
                f"/plans/{plan.pk}/cycles/new/",
                {
                    "kind": kind,
                    "title": kind,
                    "parent": parent or "",
                    "start_date": day.isoformat(),
                    "end_date": (day + timedelta(days=2)).isoformat(),
                },
            )
            assert response.status_code == 302
            parent = Cycle.objects.get(plan=plan, kind=kind).pk
        response = self.client.post(
            "/scheduled/new/",
            {"plan": plan.pk, "cycle": parent, "title": "Manual session", "date": day.isoformat()},
        )
        assert response.status_code == 302
        scheduled = PlannedSession.objects.get(plan=plan)
        path = f"/scheduled/{scheduled.pk}/reschedule/"
        response = self.client.post(
            path, {"date": (day + timedelta(days=1)).isoformat(), "revision": 1}
        )
        assert response.status_code == 302
        scheduled.refresh_from_db()
        assert scheduled.revision == 2
        response = self.client.post(path, {"date": day.isoformat(), "revision": 1})
        assert response.status_code == 200
        scheduled.refresh_from_db()
        assert scheduled.revision == 2 and scheduled.date == day + timedelta(days=1)
        response = self.client.post(
            path, {"date": (day + timedelta(days=3)).isoformat(), "revision": 2}
        )
        assert response.status_code == 200
        scheduled.refresh_from_db()
        assert scheduled.revision == 2
