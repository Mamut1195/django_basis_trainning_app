"""Frozen job budgets reach the actual HTTP request through an isolated transport."""

import json
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.coach.adapters.actions import request_body as preview_body
from basis.modules.coach.adapters.context_wire import encode_context
from basis.modules.coach.adapters.jobs import DjangoJobsRepository
from basis.modules.coach.adapters.models import AIJob, UsagePeriod
from basis.modules.coach.adapters.provider import DeepSeekProvider
from basis.modules.coach.application.jobs import CoachConfiguration, Enqueue, Jobs
from basis.modules.coach.domain.jobs import (
    HISTORICAL_PRICING,
    LIMITS,
    CoachInvalid,
    PricingPolicy,
    Reconcile,
    TokenUsage,
)
from basis.shared.identifiers import AccountId, AIRequestKey
from tests_architecture.test_coach_jobs import CONTEXT, NOW, Ports, Profiles

MODEL = "deepseek-v4-flash"


class FrozenProviderPolicyTests(TestCase):
    def setUp(self) -> None:
        self.owner = AccountId(get_user_model().objects.create_user(username="frozen-provider").pk)
        self.requests: list[dict[str, object]] = []

        def respond(request: httpx.Request) -> httpx.Response:
            self.requests.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "model": MODEL,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                    "choices": [{"finish_reason": "stop", "message": {"content": "fixture"}}],
                },
            )

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(respond), timeout=timeout)

        ports = Ports()
        self.service = Jobs(
            DjangoJobsRepository(),
            DjangoAccountLocks(),
            ports,
            Profiles(),
            ports,
            DeepSeekProvider("synthetic-not-a-credential", client),
            ports,
            ports,
            DjangoUnitOfWork,
            CoachConfiguration(True, True, MODEL),
        )
        body = preview_body("short", "question", encode_context(CONTEXT), MODEL)
        body["max_tokens"] = 100
        self.expected_body = body
        self.exact_input_bound = len(json.dumps(body, ensure_ascii=False).encode()) + 128

    def policy(self, input_bound: int) -> PricingPolicy:
        return replace(
            HISTORICAL_PRICING,
            version="synthetic-frozen-transport",
            short_limits=(input_bound, 100),
        )

    def test_quarantined_worker_response_cannot_follow_a_released_reconciliation(self) -> None:
        job = self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))
        command = Reconcile(
            job.id, "late-response", "admin:test", "ledger:fixture", "synthetic", "no_charge", True
        )
        outcomes: list[str] = []

        def respond(request: httpx.Request) -> httpx.Response:
            AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
            self.service.quarantine_stale_jobs()
            outcomes.append(self.service.reconcile(command, apply=True).outcome)
            return httpx.Response(
                200,
                json={
                    "model": MODEL,
                    "usage": {"prompt_tokens": 10**40, "completion_tokens": False},
                    "choices": [{"finish_reason": "stop", "message": {"content": "fixture"}}],
                },
            )

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(respond), timeout=timeout)

        self.service.provider = DeepSeekProvider("synthetic", client)
        self.assertTrue(self.service.process_one())
        row = AIJob.objects.get(pk=job.id)
        with self.subTest("reconciliation before response"):
            self.assertEqual(outcomes, ["retained"])
        with self.subTest("late evidence and block"):
            self.assertEqual(row.status, "uncertain")
            self.assertIs(row.invalid_usage_observed, True)
            self.assertTrue(self.service.repo.blocked())

    def test_quarantined_worker_records_malformed_response_before_reconciliation(self) -> None:
        job = self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))

        def respond(request: httpx.Request) -> httpx.Response:
            AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
            self.service.quarantine_stale_jobs()
            return httpx.Response(
                200,
                json={
                    "model": MODEL,
                    "usage": {"prompt_tokens": 10**40, "completion_tokens": False},
                    "choices": [{"finish_reason": "stop", "message": {"content": "fixture"}}],
                },
            )

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(respond), timeout=timeout)

        self.service.provider = DeepSeekProvider("synthetic", client)
        self.assertTrue(self.service.process_one())
        row = AIJob.objects.get(pk=job.id)
        self.assertEqual(row.status, "uncertain")
        self.assertIs(row.invalid_usage_observed, True)
        self.assertTrue(self.service.repo.blocked())

    def test_worker_decodes_mixed_invalid_usage_and_reconciliation_retains_it(self) -> None:
        calls: list[int] = []

        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(
                200,
                json={
                    "model": MODEL,
                    "usage": {
                        "prompt_tokens": 10**40,
                        "completion_tokens": False,
                    },
                    "choices": [{"finish_reason": "stop", "message": {"content": "fixture"}}],
                },
            )

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(respond), timeout=timeout)

        self.service.provider = DeepSeekProvider("synthetic", client)
        first = self.service.enqueue(
            Enqueue(self.owner, "short", "question", AIRequestKey(uuid4()))
        )
        second = self.service.enqueue(
            Enqueue(self.owner, "short", "question", AIRequestKey(uuid4()))
        )
        self.assertTrue(self.service.process_one())
        job = self.service.repo.job(first.id)
        self.assertEqual((job.status, job.cost), ("uncertain", None))
        before = self.service.repo.usage(job.usage_period)
        for charged in (False, True):
            command = Reconcile(
                job.id,
                f"decision-{charged}",
                "admin:test",
                "ledger:fixture",
                "synthetic evidence",
                "usage" if charged else "no_charge",
                not charged,
                MODEL if charged else "",
                TokenUsage(1, 0, 0) if charged else None,
            )
            record = self.service.reconcile(command, apply=True)
            self.assertEqual((record.outcome, record.cost), ("retained", None))
            self.assertEqual(self.service.reconcile(command, apply=True), record)
        self.assertIs(AIJob.objects.get(pk=first.id).invalid_usage_observed, True)
        self.assertEqual(self.service.repo.usage(job.usage_period), before)
        self.assertFalse(
            self.service.process_one()
        )  # Existing service block requires human action.
        self.assertEqual(self.service.repo.job(second.id).status, "pending")
        self.assertEqual(len(calls), 1)

    def test_enqueue_worker_uses_frozen_output_and_input_bounds_despite_current_policy(
        self,
    ) -> None:
        self.service.config = replace(
            self.service.config, pricing=self.policy(self.exact_input_bound)
        )
        job = self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))
        self.service.config = replace(
            self.service.config,
            pricing=replace(
                HISTORICAL_PRICING,
                version="synthetic-later",
                short_limits=(1, 1),
            ),
        )
        self.assertTrue(self.service.process_one())
        self.assertEqual(self.requests, [self.expected_body])
        self.assertEqual(self.requests[0]["max_tokens"], 100)
        self.assertEqual(self.service.repo.job(job.id).status, "succeeded")
        self.assertEqual(job.pricing.input_limit if job.pricing else None, self.exact_input_bound)

    def test_global_limit_change_between_enqueue_and_call_cannot_change_frozen_request(
        self,
    ) -> None:
        self.service.config = replace(
            self.service.config, pricing=self.policy(self.exact_input_bound)
        )
        job = self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))
        with patch.dict(LIMITS, {"short": (1, 1)}):
            self.assertTrue(self.service.process_one())
        self.assertEqual(self.requests, [self.expected_body])
        self.assertEqual(self.service.repo.job(job.id).status, "succeeded")

    def test_enqueue_rejects_one_byte_over_frozen_input_budget_and_rolls_back(self) -> None:
        self.service.config = replace(
            self.service.config, pricing=self.policy(self.exact_input_bound - 1)
        )
        with self.assertRaisesRegex(CoachInvalid, "presupuesto"):
            self.service.enqueue(Enqueue(self.owner, "short", "question", AIRequestKey(uuid4())))
        self.assertFalse(AIJob.objects.exists())
        self.assertFalse(UsagePeriod.objects.exists())
        self.assertEqual(self.requests, [])
