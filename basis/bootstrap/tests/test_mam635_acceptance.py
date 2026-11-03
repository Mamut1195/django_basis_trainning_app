"""Local HTTP-to-worker acceptance with synthetic accounts and no provider traffic."""

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from basis.bootstrap.tests.test_coach_edges import account, proposal
from basis.modules.coach.adapters.models import AIJob, PlanProposal, UsagePeriod
from basis.modules.coach.adapters.web.forms import ProposalReviewForm
from basis.modules.training.adapters.models import Session, TrainingPlan
from basis.modules.training.adapters.planning_actions import build_proposal


@override_settings(
    AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-only", DEEPSEEK_MODEL="deepseek-flash"
)
class CoachAcceptance635Tests(TestCase):
    def setUp(self) -> None:
        self.owner = account("accept635")
        self.other = account("other635")
        self.client.force_login(self.owner)
        self.calls: list[httpx.Request] = []

    def enqueue(self, kind: str = "short", base: TrainingPlan | None = None) -> AIJob:
        response = self.client.post(
            reverse("coach-ask"),
            {
                "kind": kind,
                "prompt": "Consulta sintética",
                "request_key": str(uuid.uuid4()),
                "base_plan": base.pk if base else "",
            },
        )
        self.assertEqual(response.status_code, 302)
        job = AIJob.objects.get(owner=self.owner, kind=kind)
        self.assertEqual(response["Location"], reverse("job-detail", args=[job.pk]))
        return job

    def worker(self, response: httpx.Response) -> None:
        real_client = httpx.Client

        def handle(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            return response

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return real_client(transport=httpx.MockTransport(handle), timeout=timeout)

        with patch("basis.modules.coach.adapters.actions.httpx.Client", side_effect=client):
            call_command("process_ai_jobs", once=True)

    @staticmethod
    def reply(content: str) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            },
        )

    def test_reopen_poll_and_owner_isolation_do_not_enqueue(self) -> None:
        job = self.enqueue()
        url = reverse("job-detail", args=[job.pk])
        for _ in range(2):
            self.assertContains(self.client.get(url), 'hx-trigger="every 3s"')
            self.assertContains(self.client.get(url, HTTP_HX_REQUEST="true"), "pending")
        self.assertEqual(AIJob.objects.count(), 1)
        self.assertEqual(len(self.calls), 0)
        self.worker(self.reply("Respuesta sintética"))
        self.assertContains(self.client.get(url, HTTP_HX_REQUEST="true"), "Respuesta sintética")
        self.assertNotContains(self.client.get(url), 'hx-trigger="every 3s"')
        job.refresh_from_db()
        self.assertEqual(
            (job.status, job.reported_model, job.input_tokens), ("succeeded", "deepseek-flash", 20)
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(len(self.calls), 1)

    def test_provider_failure_is_ambiguous_no_retry_or_private_error(self) -> None:
        base = build_proposal(self.owner.pk, proposal(self.owner))
        assert base is not None
        before = list(TrainingPlan.objects.filter(owner=self.owner).values())
        job = self.enqueue("plan", base=base)
        self.worker(httpx.Response(500, text="PRIVATE-PROVIDER-DETAIL"))
        job.refresh_from_db()
        self.assertEqual(job.status, "uncertain")
        self.assertIsNone(job.cost)
        self.assertGreater(job.usage_period.reserved, 0)
        page = self.client.get(reverse("job-detail", args=[job.pk]))
        self.assertContains(page, "No reintentaremos automáticamente")
        self.assertNotContains(page, "PRIVATE-PROVIDER-DETAIL")
        self.assertNotContains(page, "synthetic-only")
        self.worker(self.reply("must not be sent"))
        self.assertEqual(len(self.calls), 1)
        result = self.client.post(
            reverse("session-new"),
            {
                "title": "Registro sintético",
                "date": timezone.localdate().isoformat(),
                "duration_protocol": "elapsed",
                "block-sport": "running",
                "block-title": "Carrera",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            Session.objects.filter(owner=self.owner, title="Registro sintético").exists()
        )
        self.assertEqual(list(TrainingPlan.objects.filter(owner=self.owner).values()), before)

    def test_stale_running_job_is_quarantined_without_another_call(self) -> None:
        job = self.enqueue()
        AIJob.objects.filter(pk=job.pk).update(
            status="running", started_at=timezone.now() - timedelta(minutes=11)
        )
        self.worker(self.reply("must not be sent"))
        job.refresh_from_db()
        self.assertEqual(job.status, "uncertain")
        self.assertGreater(job.usage_period.reserved, 0)
        self.assertEqual(len(self.calls), 0)

    def test_limit_is_reported_without_another_job(self) -> None:
        job = self.enqueue()
        UsagePeriod.objects.filter(pk=job.usage_period_id).update(short_count=200)
        response = self.client.post(
            reverse("coach-ask"),
            {
                "kind": "short",
                "prompt": "Otra consulta",
                "request_key": str(uuid.uuid4()),
            },
            follow=True,
        )
        self.assertContains(response, "Has usado las acciones IA disponibles")
        self.assertEqual(AIJob.objects.count(), 1)
        self.assertEqual(len(self.calls), 0)

    def test_invalid_plan_is_not_exposed_or_applied(self) -> None:
        job = self.enqueue("plan")
        self.worker(self.reply(json.dumps({"title": "incomplete"})))
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertFalse(PlanProposal.objects.filter(job=job).exists())
        self.assertFalse(TrainingPlan.objects.filter(owner=self.owner).exists())
        self.assertContains(
            self.client.get(reverse("job-detail", args=[job.pk])), "No se aplicó ningún cambio"
        )

    def test_generated_plan_can_be_reviewed_and_rejected(self) -> None:
        content = proposal(self.owner)
        job = self.enqueue("plan")
        self.worker(self.reply(json.dumps(content)))
        row = PlanProposal.objects.get(job=job)
        url = reverse("proposal-review", args=[row.pk])
        self.assertContains(
            self.client.get(reverse("job-detail", args=[job.pk])), "Revisar propuesta"
        )
        page = self.client.get(url)
        self.assertContains(page, "Qué cambia")
        result = self.client.post(
            url, {"decision": "reject", "review_token": page.context["review_token"]}
        )
        self.assertEqual(result.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, "rejected")
        self.assertFalse(TrainingPlan.objects.filter(owner=self.owner).exists())

    def test_generated_plan_can_be_compared_and_accepted(self) -> None:
        content = proposal(self.owner)
        job = self.enqueue("plan")
        self.worker(self.reply(json.dumps(content)))
        row = PlanProposal.objects.get(job=job)
        url = reverse("proposal-review", args=[row.pk])
        form = ProposalReviewForm(content=content, owner=self.owner)
        fields = {key: value if value is not None else "" for key, value in form.initial.items()}
        fields.update(decision="preview", constraints_reviewed="on")
        preview = self.client.post(url, fields)
        self.assertEqual(preview.status_code, 200)
        fields.update(decision="accept", review_token=preview.context["review_token"])
        self.assertEqual(self.client.post(url, fields).status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, "accepted")
        self.assertIsNotNone(row.accepted_plan_id)
