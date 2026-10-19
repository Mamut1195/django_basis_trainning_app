"""Real owner projections, proposal transactions and isolated HTTP contracts."""

import copy
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from basis.bootstrap.coach import contexts, proposal_definition, proposals
from basis.bootstrap.planning import build_proposal, revise
from basis.modules.coach.adapters.context_wire import decode_context, encode_context, mapping, rows
from basis.modules.coach.adapters.provider import DeepSeekProvider, decode_reply, request_body
from basis.modules.coach.application.proposals import CreateProposal
from basis.modules.coach.domain.jobs import ProviderAmbiguous, ProviderRejected
from basis.shared.identifiers import AccountId, JobId
from daily_trainning_app.models import Classification, Exercise
from daily_trainning_app.models import User as Athlete
from training.ai import enqueue, process_one
from training.models import (
    AthleteSettings,
    BillingAccount,
    Goal,
    PlanProposal,
    SportProfile,
    TrainingPlan,
    Wellness,
)
from training.proposals import accept_proposal, edit_and_accept_proposal, reject_proposal


def account(name: str = "athlete") -> User:
    user = get_user_model().objects.create_user(
        username=name + "@example.test", email=name + "@example.test"
    )
    Athlete.objects.create(
        account=user,
        nombre=name,
        email=user.email,
        fecha_inicio=timezone.localdate(),
        email_verified=True,
        edad=25,
    )
    AthleteSettings.objects.create(owner=user, availability=[1, 3, 5])
    BillingAccount.objects.create(
        owner=user,
        polar_customer_id="customer-" + name,
        status="active",
        period_start=timezone.now() - timedelta(days=1),
        period_end=timezone.now() + timedelta(days=29),
    )
    return user


def exercise() -> Exercise:
    classification, _ = Classification.objects.get_or_create(nombre="Strength")
    return Exercise.objects.create(nombre="Squat", classification=classification)


def proposal(owner: User) -> dict[str, object]:
    goal = Goal.objects.create(owner=owner, title="Consistency", sport="running")
    start, end = (
        timezone.localdate().isoformat(),
        (timezone.localdate() + timedelta(days=6)).isoformat(),
    )
    return {
        "title": "Week",
        "goal_id": goal.pk,
        "start_date": start,
        "end_date": end,
        "cycles": [
            {
                "key": key,
                "parent": parent,
                "kind": kind,
                "title": key,
                "start_date": start,
                "end_date": end,
            }
            for key, parent, kind in (
                ("ma", None, "macro"),
                ("me", "ma", "meso"),
                ("mi", "me", "micro"),
            )
        ],
        "sessions": [
            {
                "title": "Run",
                "date": start,
                "cycle_key": "mi",
                "blocks": [
                    {"sport": "running", "title": "Easy", "target": {"duration_seconds": 1800}}
                ],
            }
        ],
    }


@override_settings(AI_ENABLED=True, DEEPSEEK_API_KEY="test-not-a-credential")
class CoachEdgeTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account(), account("other")

    def test_frozen_wire_roundtrip_preserves_dates_decimals_zero_and_order(self) -> None:
        AthleteSettings.objects.filter(owner=self.owner).update(
            availability=[1, 3], equipment="e" * 600
        )
        SportProfile.objects.create(
            owner=self.owner,
            sport="running",
            experience="beginner",
            threshold=Decimal("160"),
            threshold_unit="bpm",
            measured_on=timezone.localdate(),
            method="test",
        )
        Goal.objects.create(
            owner=self.owner,
            title="Owned",
            sport="running",
            target_value=0,
            target_unit="m",
            priority="secondary",
        )
        Wellness.objects.create(owner=self.owner, sleep_hours=0, pain_score=0, stress=1)
        Goal.objects.create(owner=self.other, title="SECRET-OTHER", sport="running")
        exercise()
        context = contexts().snapshot(AccountId(self.owner.pk), "plan", None)
        encoded = encode_context(context)
        roundtrip = encode_context(decode_context(encoded))
        self.assertEqual(
            json.dumps(encoded, ensure_ascii=False), json.dumps(roundtrip, ensure_ascii=False)
        )
        self.assertNotIn("SECRET-OTHER", json.dumps(encoded))
        self.assertNotIn(self.owner.email, json.dumps(encoded))
        prefs = mapping(encoded["preferences"])
        self.assertEqual(len(str(prefs["equipment"])), 500)
        self.assertIsNone(mapping(encoded["wellness_latest"])["soreness"])
        self.assertEqual(mapping(encoded["wellness_latest"])["sleep_hours"], "0.0")

    def test_provider_one_call_and_exact_payload_without_network(self) -> None:
        context = contexts().snapshot(AccountId(self.owner.pk), "short", None)
        requests: list[httpx.Request] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "model": "reported",
                    "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
                },
            )

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(handle), timeout=timeout)

        result = DeepSeekProvider("test-not-a-credential", client).call(
            "short", "Hi", context, "deepseek-flash"
        )
        self.assertEqual(len(requests), 1)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.answer, "answer")
        self.assertEqual(
            json.loads(requests[0].content), request_body("short", "Hi", context, "deepseek-flash")
        )

    def test_timeout_is_ambiguous_and_provider_rejection_definitive(self) -> None:
        context = contexts().snapshot(AccountId(self.owner.pk), "short", None)
        for code in (429, 500):
            with self.subTest(code=code):

                def handle(request: httpx.Request) -> httpx.Response:
                    return httpx.Response(code, text="private provider response")

                def client(*, timeout: httpx.Timeout) -> httpx.Client:
                    return httpx.Client(transport=httpx.MockTransport(handle), timeout=timeout)

                with self.assertRaises(
                    ProviderRejected if code == 429 else ProviderAmbiguous
                ) as caught:
                    DeepSeekProvider("secret-test", client).call(
                        "short", "Hi", context, "deepseek-flash"
                    )
                self.assertNotIn("private", str(caught.exception))
                self.assertNotIn("secret", str(caught.exception))

    def test_decoder_preserves_partial_usage_when_choices_invalid(self) -> None:
        result = decode_reply(
            {"usage": {"prompt_tokens": 3, "completion_tokens": 4}, "choices": []}
        )
        assert result is not None and result.usage is not None
        self.assertEqual(result.usage.input_tokens, 3)
        self.assertFalse(result.choice_present)
        invalid = decode_reply({"usage": {"prompt_tokens": True, "completion_tokens": 4}})
        assert invalid is not None
        self.assertIsNone(invalid.usage)

    def _proposal(self) -> PlanProposal:
        source = proposal(self.owner)
        job = enqueue(self.owner, "plan", "Plan", uuid.uuid4())
        id = proposals(source).create(
            CreateProposal(
                AccountId(self.owner.pk), JobId(job.pk), proposal_definition(source), None
            )
        )
        row = PlanProposal.objects.get(pk=id)
        self.assertEqual(row.content, source)
        return row

    def test_proposal_acceptance_is_idempotent_and_owner_scoped(self) -> None:
        row = self._proposal()
        with self.assertRaises(PlanProposal.DoesNotExist):
            accept_proposal(self.other, row.pk)
        plan = accept_proposal(self.owner, row.pk)
        self.assertEqual(accept_proposal(self.owner, row.pk).pk, plan.pk)
        self.assertEqual(TrainingPlan.objects.count(), 1)
        self.assertEqual(plan.owner_id, self.owner.pk)

    def test_edit_and_accept_preserves_source_and_rollback_on_stale_version(self) -> None:
        row = self._proposal()
        source = copy.deepcopy(row.content)
        source["title"] = "Edited"
        plan = edit_and_accept_proposal(self.owner, row.pk, source)
        row.refresh_from_db()
        self.assertEqual(row.content, source)
        self.assertEqual(plan.title, "Edited")
        with self.assertRaises(ValidationError):
            edit_and_accept_proposal(self.owner, row.pk, source)
        self.assertEqual(TrainingPlan.objects.count(), 1)

    def test_reject_preserves_content_and_never_creates_plan(self) -> None:
        row = self._proposal()
        original = row.content
        reject_proposal(self.owner, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, "rejected")
        self.assertEqual(row.content, original)
        with self.assertRaises(ValidationError):
            accept_proposal(self.owner, row.pk)
        self.assertFalse(TrainingPlan.objects.exists())

    @patch("training.ai.httpx.Client")
    def test_plan_question_does_not_create_proposal(self, client: object) -> None:
        from unittest.mock import Mock

        assert isinstance(client, Mock)
        job = enqueue(self.owner, "plan", "Plan", uuid.uuid4())
        response = client.return_value.__enter__.return_value.post.return_value
        response.status_code = 200
        response.json.return_value = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "choices": [{"finish_reason": "stop", "message": {"content": '{"question":"Goal?"}'}}],
        }
        self.assertTrue(process_one())
        job.refresh_from_db()
        self.assertEqual(job.status, "succeeded")
        self.assertFalse(PlanProposal.objects.exists())

    def test_stale_base_edit_rolls_back_content_and_plan_creation(self) -> None:
        source = proposal(self.owner)
        base = build_proposal(self.owner.pk, source)
        assert base is not None
        job = enqueue(self.owner, "plan", "Plan", uuid.uuid4(), base.pk)
        row = PlanProposal.objects.create(owner=self.owner, job=job, content=source, base_plan=base)
        revise(self.owner.pk, base.pk)
        edited = copy.deepcopy(source)
        edited["title"] = "Must rollback"
        with self.assertRaises(ValidationError):
            edit_and_accept_proposal(self.owner, row.pk, edited)
        row.refresh_from_db()
        self.assertEqual(row.content, source)
        self.assertEqual(row.status, "pending")
        self.assertIsNone(row.accepted_plan_id)
        self.assertEqual(TrainingPlan.objects.count(), 2)

    @patch("training.ai.httpx.Client")
    def test_successful_provider_plan_is_pending_exact_json_and_has_no_execution(
        self, client: object
    ) -> None:
        from unittest.mock import Mock

        assert isinstance(client, Mock)
        source = proposal(self.owner)
        source["notes"] = "Keep optional shape"
        block = mapping(rows(mapping(rows(source["sessions"])[0])["blocks"])[0])
        block["target"] = {"duration_seconds": "1800"}
        job = enqueue(self.owner, "plan", "Plan", uuid.uuid4())
        response = client.return_value.__enter__.return_value.post.return_value
        response.status_code = 200
        response.json.return_value = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(source)}}],
        }
        self.assertTrue(process_one())
        row = PlanProposal.objects.get(job=job)
        self.assertEqual(row.status, "pending")
        self.assertEqual(row.content, source)
        self.assertFalse(TrainingPlan.objects.exists())

    @patch("training.ai.httpx.Client")
    def test_invalid_usage_blocks_future_calls_and_retains_reservation(
        self, client: object
    ) -> None:
        from unittest.mock import Mock

        from training.models import AIServiceState

        assert isinstance(client, Mock)
        job = enqueue(self.owner, "short", "Help", uuid.uuid4())
        response = client.return_value.__enter__.return_value.post.return_value
        response.status_code = 200
        response.json.return_value = {"usage": {"prompt_tokens": True, "completion_tokens": 10}}
        self.assertTrue(process_one())
        self.assertFalse(process_one())
        job.refresh_from_db()
        job.usage_period.refresh_from_db()
        self.assertEqual(job.status, "uncertain")
        self.assertEqual(job.usage_period.reserved, job.reservation)
        self.assertTrue(AIServiceState.objects.get().blocked)
        self.assertEqual(client.return_value.__enter__.return_value.post.call_count, 1)

    def test_unexpected_truthy_top_level_provider_payload_retains_legacy_escape(self) -> None:
        for value in ([1], True, "invalid", 1):
            with self.subTest(value=value), self.assertRaises(AttributeError):
                decode_reply(value)
        empty_values: tuple[object, ...] = ([], {}, False, 0, "")
        for empty_value in empty_values:
            self.assertIsNone(decode_reply(empty_value))

    def test_reject_and_accepted_replay_do_not_revalidate_stored_content(self) -> None:
        row = self._proposal()
        PlanProposal.objects.filter(pk=row.pk).update(content={"malformed": True})
        reject_proposal(self.owner, row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, "rejected")
        source = proposal(self.owner)
        job = enqueue(self.owner, "plan", "Another", uuid.uuid4())
        id = proposals(source).create(
            CreateProposal(
                AccountId(self.owner.pk), JobId(job.pk), proposal_definition(source), None
            )
        )
        accepted = accept_proposal(self.owner, id)
        PlanProposal.objects.filter(pk=id).update(content={"malformed": True})
        self.assertEqual(accept_proposal(self.owner, id).pk, accepted.pk)
