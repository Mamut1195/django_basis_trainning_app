"""Local HTTP-to-worker acceptance with synthetic accounts and no provider traffic."""

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from basis.bootstrap.tests.test_coach_edges import account, proposal
from basis.modules.coach.adapters.models import AIJob, PlanProposal, UsagePeriod
from basis.modules.coach.adapters.web.forms import ProposalReviewForm
from basis.modules.training.adapters.models import Block, PlannedSession, Session, TrainingPlan
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
            page = self.client.get(url)
            self.assertContains(page, 'hx-trigger="every 3s"')
            self.assertContains(page, 'id="coach-job-update-status"')
            self.assertContains(page, 'aria-live="polite"')
            self.assertContains(page, "basis/js/coach-job.js")
            fragment = self.client.get(url, HTTP_HX_REQUEST="true")
            self.assertContains(fragment, "pending")
            self.assertNotContains(fragment, 'id="coach-job-update-status"')
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

    def test_adaptation_of_existing_plan_preserves_history(self) -> None:
        content = proposal(self.owner)
        base = build_proposal(self.owner.pk, content)
        assert base is not None
        scheduled = PlannedSession.objects.get(plan=base)
        execution = Session.objects.create(
            owner=self.owner,
            planned=scheduled,
            title="Histórico sintético",
            date=scheduled.date,
            status="completed",
            duration_seconds=1400,
        )
        Block.objects.create(
            session=execution,
            order=1,
            sport="running",
            title="Resultado sintético",
            actual={"duration_seconds": 1400},
        )
        before_plan = list(TrainingPlan.objects.filter(pk=base.pk).values())
        before_scheduled = list(PlannedSession.objects.filter(pk=scheduled.pk).values())
        before_execution = list(Session.objects.filter(pk=execution.pk).values())
        before_blocks = list(Block.objects.filter(session=execution).values())
        content["title"] = "Adaptación sintética"
        job = self.enqueue("plan", base=base)
        self.worker(self.reply(json.dumps(content)))
        row = PlanProposal.objects.get(job=job, base_plan=base)
        url = reverse("proposal-review", args=[row.pk])
        self.assertContains(
            self.client.get(reverse("job-detail", args=[job.pk])), "Revisar propuesta"
        )
        page = self.client.get(url)
        self.assertContains(page, "Qué cambia")
        form = ProposalReviewForm(content=content, owner=self.owner)
        fields = {key: value if value is not None else "" for key, value in form.initial.items()}
        fields.update(decision="preview", constraints_reviewed="on")
        preview = self.client.post(url, fields)
        self.assertContains(preview, "Aceptar esta comparación")
        fields.update(decision="accept", review_token=preview.context["review_token"])
        self.assertEqual(self.client.post(url, fields).status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, "accepted")
        assert row.accepted_plan_id is not None
        successor = TrainingPlan.objects.get(pk=row.accepted_plan_id)
        self.assertEqual(
            (successor.title, successor.version), ("Adaptación sintética", base.version + 1)
        )
        self.assertEqual(list(TrainingPlan.objects.filter(pk=base.pk).values()), before_plan)
        self.assertEqual(
            list(PlannedSession.objects.filter(pk=scheduled.pk).values()), before_scheduled
        )
        self.assertEqual(list(Session.objects.filter(pk=execution.pk).values()), before_execution)
        self.assertEqual(list(Block.objects.filter(session=execution).values()), before_blocks)
        self.assertEqual(len(self.calls), 1)

    def test_per_job_usage_distinguishes_unknown_reserved_and_zero(self) -> None:
        job = self.enqueue()
        url = reverse("job-detail", args=[job.pk])
        pending = self.client.get(url)
        self.assertContains(pending, "Costo aún no disponible")
        self.assertContains(pending, "Reserva pendiente:")
        self.assertNotContains(pending, "Costo calculado:")
        self.assertNotContains(pending, "Tokens de entrada:")
        self.worker(self.reply("Respuesta sintética"))
        page = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertContains(page, "Costo calculado: USD")
        self.assertContains(page, "Tokens de entrada: 20")
        self.assertContains(page, "Tokens de salida: 10")
        self.assertNotContains(page, "Reserva pendiente:")
        AIJob.objects.filter(pk=job.pk).update(cost=Decimal(0), input_tokens=0, output_tokens=0)
        zero = self.client.get(url)
        self.assertContains(zero, "Costo calculado: USD 0,00000000")
        self.assertContains(zero, "Tokens de entrada: 0")
        self.assertContains(zero, "Tokens de salida: 0")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_ambiguous_usage_shows_retained_reservation_not_zero_cost(self) -> None:
        job = self.enqueue()
        self.worker(httpx.Response(500, text="PRIVATE-PROVIDER-DETAIL"))
        page = self.client.get(reverse("job-detail", args=[job.pk]))
        self.assertContains(page, "Costo aún no disponible")
        self.assertContains(page, "Reserva retenida:")
        self.assertNotContains(page, "Costo calculado:")
        self.assertNotContains(page, "PRIVATE-PROVIDER-DETAIL")
