"""MAM-634: an owned RM is not an authorized source for a coach proposal."""

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from basis.bootstrap.coach import proposal_decoder, proposals
from basis.bootstrap.tests.test_mam634_proposals import account, draft, job_for, source
from basis.modules.athletes.adapters.models import User as Athlete
from basis.modules.athletes.adapters.models import UserExerciseRM
from basis.modules.catalog.adapters.models import Classification, Exercise
from basis.modules.coach.adapters.jobs import job_state
from basis.modules.coach.adapters.models import PlanProposal
from basis.modules.coach.adapters.proposal_actions import (
    accept_proposal,
    edit_and_accept_proposal,
    review_proposal,
)
from basis.modules.coach.adapters.proposals import DjangoProposalSink
from basis.modules.coach.application.proposals import CreateProposal
from basis.modules.coach.domain.jobs import CoachInvalid
from basis.modules.training.adapters.models import Block, Goal, PlannedSession, TrainingPlan
from basis.shared.identifiers import AccountId, JobId


class RMSource634Tests(TestCase):
    def setUp(self) -> None:
        self.owner = account("mam634-rm-source")
        goal = Goal.objects.create(owner=self.owner, title="Fuerza declarada", sport="strength")
        classification = Classification.objects.create(nombre="RM-source634")
        exercise = Exercise.objects.create(nombre="Sentadilla", classification=classification)
        self.rm = UserExerciseRM.objects.create(
            user=Athlete.objects.get(account=self.owner),
            exercise=exercise,
            peso_maximo_rm=Decimal(100),
            fecha_registro="2026-11-01",
        )
        self.content = source(goal)
        self.content["sessions"] = [
            {
                "title": "Fuerza",
                "date": "2027-01-04",
                "cycle_key": "micro",
                "blocks": [
                    {
                        "sport": "strength",
                        "title": "Serie",
                        "sets": [{"exercise": exercise.pk, "target_reps": 5}],
                    }
                ],
            }
        ]

    def with_rm(self, fields: Mapping[str, object] | None = None) -> dict[str, object]:
        definition = proposal_decoder()(self.content)
        content = copy.deepcopy(self.content)
        content["sessions"] = [
            {
                "title": "Fuerza",
                "date": "2027-01-04",
                "cycle_key": "micro",
                "blocks": [
                    {
                        "sport": "strength",
                        "title": "Serie",
                        "sets": [
                            {
                                "exercise": definition.sessions[0].blocks[0].sets[0].exercise,
                                "target_reps": 5,
                                **(
                                    fields
                                    if fields is not None
                                    else {"rm_reference": self.rm.pk, "target_percent_rm": 70}
                                ),
                            }
                        ],
                    }
                ],
            }
        ]
        return content

    def assert_no_calendar(self) -> None:
        self.assertFalse(TrainingPlan.objects.exists())
        self.assertFalse(PlannedSession.objects.exists())
        self.assertFalse(Block.objects.exists())

    def test_creation_checks_source_even_for_owned_existing_rm_and_zero_presence(self) -> None:
        for fields in (
            {"rm_reference": self.rm.pk},
            {"target_percent_rm": 70},
            {"rm_reference": 0},
            {"target_percent_rm": 0},
        ):
            with self.subTest(fields=fields):
                content = self.with_rm(fields)
                job = job_for(self.owner)
                self.assertIn("strength_rm_not_consulted", job.context["missing"])
                with self.assertRaisesRegex(CoachInvalid, "RM"):
                    proposals(content).create(
                        CreateProposal(
                            AccountId(self.owner.pk),
                            JobId(job.pk),
                            proposal_decoder()(content),
                            None,
                        )
                    )
                self.assertFalse(PlanProposal.objects.exists())
                self.assert_no_calendar()

    def test_sink_does_not_expose_or_apply_a_plan_with_unconsulted_rm(self) -> None:
        job = job_for(self.owner)
        answer = replace(job_state(job), answer=json.dumps(self.with_rm()))
        self.assertFalse(DjangoProposalSink(proposals, proposal_decoder()).complete(answer))
        self.assertFalse(PlanProposal.objects.exists())
        self.assert_no_calendar()

    def test_review_and_acceptance_revalidate_preexisting_invalid_draft(self) -> None:
        row = draft(self.owner, self.content)
        PlanProposal.objects.filter(pk=row.pk).update(content=self.with_rm())
        with self.assertRaisesRegex(ValidationError, "RM"):
            review_proposal(self.owner, row.pk)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("proposal-review", args=[row.pk]))
        self.assertContains(response, "RM", status_code=400)
        self.assertNotContains(response, "Nombre del plan", status_code=400)
        with self.assertRaisesRegex(ValidationError, "RM"):
            accept_proposal(self.owner, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.accepted_plan_id)
        self.assert_no_calendar()

    def test_edited_review_and_edit_acceptance_preserve_original_on_failure(self) -> None:
        row = draft(self.owner, self.content)
        with self.assertRaisesRegex(ValidationError, "RM"):
            review_proposal(self.owner, row.pk, self.with_rm())
        with self.assertRaisesRegex(ValidationError, "RM"):
            edit_and_accept_proposal(self.owner, row.pk, self.with_rm())
        row.refresh_from_db()
        self.assertEqual(row.content, self.content)
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.accepted_plan_id)
        self.assert_no_calendar()

    def test_null_rm_fields_remain_absent_and_plain_prescriptions_still_apply(self) -> None:
        content = self.with_rm({"rm_reference": None, "target_percent_rm": None})
        row = draft(self.owner, content)
        result = accept_proposal(self.owner, row.pk)
        self.assertTrue(TrainingPlan.objects.filter(pk=result.pk).exists())
