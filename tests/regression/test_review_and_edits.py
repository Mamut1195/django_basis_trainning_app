from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import TestCase

from basis.modules.coach.adapters.actions import context_snapshot, request_body
from basis.modules.coach.adapters.web.forms import ProposalReviewForm
from basis.modules.training.adapters.actions import revise_plan, start_session
from basis.modules.training.adapters.models import StrengthSet
from basis.modules.training.adapters.planning_actions import validate_proposal

from .contracts import build_plan, progress_report, required, session_snapshot, sync_session
from .factories import account, exercise, proposal, session


class ReviewAndEditTests(TestCase):
    def setUp(self) -> None:
        self.owner = account()
        self.client.force_login(self.owner)

    def test_human_proposal_fields_roundtrip(self) -> None:
        content = proposal(self.owner)
        form = ProposalReviewForm(content=content, owner=self.owner)
        posted = {name: ("" if value is None else value) for name, value in form.initial.items()}
        edited = ProposalReviewForm(posted, content=content, owner=self.owner)
        self.assertTrue(edited.is_valid(), edited.errors)
        validate_proposal(self.owner, edited.to_content())

    def test_bounded_ai_body_fits_real_recent_context(self) -> None:
        context = context_snapshot(self.owner, "short")
        self.assertEqual(
            request_body("short", "Ayúdame con mi semana", context, "deepseek-flash")["max_tokens"],
            1500,
        )

    def test_fractional_json_values_are_not_binary_float_metrics(self) -> None:
        item = session(self.owner, "strength")
        StrengthSet.objects.create(
            block=required(item.blocks.first()), exercise=exercise(), target_reps=5
        )
        payload = session_snapshot(item)
        payload["reported_rpe"] = 5.5
        payload["blocks"][0]["sets"][0]["actual_kg"] = 0.3
        payload["blocks"][0]["sets"][0]["actual_reps"] = 5
        sync_session(self.owner, uuid.uuid4(), payload)
        self.assertEqual(StrengthSet.objects.get(block__session=item).actual_kg, Decimal("0.30"))

    def test_web_block_edits_use_optimistic_revision(self) -> None:
        item = session(self.owner, "running")
        block = required(item.blocks.first())
        response = self.client.post(
            f"/blocks/{block.pk}/metrics/", {"revision": 1, "distance_m": "5000"}
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            f"/blocks/{block.pk}/metrics/", {"revision": 1, "distance_m": "7000"}
        )
        self.assertEqual(response.status_code, 409)
        block.refresh_from_db()
        self.assertEqual(block.actual["distance_m"], "5000")

    def test_existing_prescribed_strength_set_can_record_actual(self) -> None:
        content = proposal(self.owner)
        content["sessions"][0]["blocks"] = [
            {
                "sport": "strength",
                "title": "Fuerza",
                "sets": [{"exercise": exercise().pk, "target_reps": 5, "target_kg": "20.25"}],
            }
        ]
        plan = build_plan(self.owner, content)
        item = start_session(self.owner, required(plan.sessions.first()))
        row = required(required(item.blocks.first()).sets.first())
        response = self.client.post(
            f"/sets/{row.pk}/edit/",
            {
                "revision": 1,
                "kind": "work",
                "load_type": "external",
                "side": "both",
                "target_reps": 99,
                "actual_reps": 5,
                "actual_kg": "20.25",
                "actual_rpe": "8.5",
            },
        )
        self.assertEqual(response.status_code, 302, response.content)
        row.refresh_from_db()
        self.assertEqual(row.target_reps, 5)
        self.assertEqual(row.actual_kg, Decimal("20.25"))

    def test_completed_prescription_not_duplicated_when_revising_plan(self) -> None:
        plan = build_plan(self.owner, proposal(self.owner))
        item = start_session(self.owner, required(plan.sessions.first()))
        item.status = "completed"
        item.save()
        new = revise_plan(self.owner, plan)
        self.assertEqual(new.sessions.count(), 0)
        report = progress_report(self.owner)
        self.assertEqual((report["scheduled_past"], report["completed_scheduled"]), (1, 1))
