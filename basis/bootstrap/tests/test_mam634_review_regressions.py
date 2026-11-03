"""MAM-634 independent-review regressions: numeric boundary and visible state."""

import copy
import json
from dataclasses import replace

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from basis.bootstrap.coach import proposal_decoder, proposals
from basis.bootstrap.planning import planning
from basis.bootstrap.tests.test_mam634_proposals import account, draft, job_for, source
from basis.modules.coach.adapters.jobs import job_state
from basis.modules.coach.adapters.models import PlanProposal
from basis.modules.coach.adapters.proposal_actions import (
    accept_proposal,
    comparison,
    review_proposal,
)
from basis.modules.coach.adapters.proposals import DjangoProposalSink
from basis.modules.training.adapters.models import Goal, PlannedSession, TrainingPlan
from basis.modules.training.public import ChangeScheduledSession, ScheduleStatus
from basis.shared.identifiers import AccountId, PlannedSessionId, Revision


class ReviewRegressions634Tests(TestCase):
    def setUp(self) -> None:
        self.owner = account("mam634-review-regressions")
        goal = Goal.objects.create(owner=self.owner, title="Constancia", sport="running")
        self.content = source(goal)

    def duration(self, value: str) -> dict[str, object]:
        content = copy.deepcopy(self.content)
        content["sessions"] = [
            {
                "title": "Carrera suave",
                "date": "2027-01-04",
                "cycle_key": "micro",
                "blocks": [
                    {"sport": "running", "title": "Suave", "target": {"duration_seconds": value}}
                ],
            }
        ]
        return content

    def test_sink_controls_nonfinite_and_extreme_durations_without_uncaught_decimal_error(
        self,
    ) -> None:
        sink = DjangoProposalSink(proposals, proposal_decoder())
        for value in ("NaN", "sNaN", "Infinity", "-Infinity", "1E9999999", "-1E9999999"):
            with self.subTest(value=value):
                job = job_for(self.owner)
                answer = replace(job_state(job), answer=json.dumps(self.duration(value)))
                self.assertFalse(sink.complete(answer))
                self.assertFalse(PlanProposal.objects.exists())
                self.assertFalse(TrainingPlan.objects.exists())
                self.assertFalse(PlannedSession.objects.exists())

    def test_review_and_acceptance_of_old_nan_draft_are_controlled_and_atomic(self) -> None:
        row = draft(self.owner, self.content)
        PlanProposal.objects.filter(pk=row.pk).update(content=self.duration("NaN"))
        with self.assertRaises(ValidationError):
            review_proposal(self.owner, row.pk)
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("proposal-review", args=[row.pk]))
        self.assertContains(response, "No se aplicó ningún cambio", status_code=400)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.accepted_plan_id)
        self.assertFalse(TrainingPlan.objects.exists())

    def test_finite_zero_duration_preserves_zero(self) -> None:
        row = draft(self.owner, self.duration("0"))
        result = accept_proposal(self.owner, row.pk)
        self.assertTrue(TrainingPlan.objects.filter(pk=result.pk).exists())

    def test_cancelled_to_scheduled_is_visible_and_not_reported_as_unchanged(self) -> None:
        accepted = accept_proposal(self.owner, draft(self.owner, self.content).pk)
        old = PlannedSession.objects.get(plan_id=accepted.pk)
        cancelled = planning().change_session(
            ChangeScheduledSession(
                AccountId(self.owner.pk),
                PlannedSessionId(old.pk),
                Revision(old.revision),
                "Cancelación explícita del atleta",
                ScheduleStatus.CANCELLED,
            )
        )
        base = TrainingPlan.objects.get(pk=cancelled.plan)
        row = draft(self.owner, self.content, base)
        changes = comparison(self.owner, row, self.content)
        label, before, after = changes[-1]
        self.assertEqual(label, "Sesiones y prescripciones")
        self.assertIn("Cancelada", before)
        self.assertIn("Programada", after)
        self.assertNotEqual(before, after)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("proposal-review", args=[row.pk]))
        self.assertContains(response, "Cancelada")
        self.assertContains(response, "Programada")
        self.assertFalse(TrainingPlan.objects.filter(previous=base).exists())
