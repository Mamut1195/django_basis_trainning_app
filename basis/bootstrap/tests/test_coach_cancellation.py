"""PostgreSQL parity, authenticated HTTP and deterministic cancellation races."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from threading import Event
from time import monotonic
from typing import Callable, TypeVar
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.test import (
    Client,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.urls import reverse
from django.utils import timezone

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.bootstrap.coach import jobs
from basis.bootstrap.tests.test_coach_edges import account, proposal
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.coach.adapters.actions import cancel, enqueue, process_one
from basis.modules.coach.adapters.jobs import DjangoJobsRepository
from basis.modules.coach.adapters.models import AIJob, PlanProposal, TrialFund, UsagePeriod
from basis.modules.coach.application.jobs import CoachConfiguration, Enqueue, Jobs
from basis.modules.coach.domain.jobs import CancellationConflict, Job
from basis.modules.training.adapters.models import Session, TrainingPlan
from basis.modules.training.adapters.planning_actions import build_proposal
from basis.shared.identifiers import AccountId, AIRequestKey
from tests_architecture.coach_cancellation_contract import CancellationContract
from tests_architecture.test_coach_jobs import NOW, Ports, Profiles

T = TypeVar("T")


class LaterPorts(Ports):
    def now(self) -> datetime:
        return NOW + timedelta(days=35)


def service(trial: bool = False) -> Jobs:
    ports = Ports()
    ports.state = replace(ports.state, status="trialing" if trial else "active")
    return Jobs(
        DjangoJobsRepository(),
        DjangoAccountLocks(),
        ports,
        Profiles(),
        ports,
        ports,
        ports,
        ports,
        DjangoUnitOfWork,
        CoachConfiguration(True, True, "deepseek-v4-flash"),
    )


class ORMCancellationTests(CancellationContract, TestCase):
    def setUp(self) -> None:
        self.owner = AccountId(get_user_model().objects.create_user(username="cancel-owner").pk)
        self.other = AccountId(get_user_model().objects.create_user(username="cancel-other").pk)
        self.service = service()


@override_settings(
    AI_ENABLED=True, DEEPSEEK_API_KEY="synthetic-only", DEEPSEEK_MODEL="deepseek-flash"
)
class CancellationHTTPTests(TestCase):
    def setUp(self) -> None:
        self.owner, self.other = account("cancel-http"), account("cancel-foreign")
        self.client.force_login(self.owner)

    def test_post_twice_reopen_replay_and_worker_never_dispatches_or_proposes(self) -> None:
        for trial in (False, True):
            BillingAccount.objects.filter(owner=self.owner).update(
                status="trialing" if trial else "active"
            )
            for kind in ("short", "plan"):
                key = uuid4()
                job = enqueue(self.owner, kind, "Synthetic cancellation", key)
                detail = reverse("job-detail", args=[job.pk])
                url = reverse("job-cancel", args=[job.pk])
                self.assertContains(self.client.get(detail), "Cancelar consulta")
                for _ in range(2):
                    self.assertRedirects(self.client.post(url), detail)
                for hx in (False, True):
                    page = self.client.get(detail, headers={"HX-Request": "true"} if hx else {})
                    self.assertContains(page, "Cancelada")
                    self.assertContains(page, "Costo calculado: USD 0,00000000")
                    self.assertNotContains(page, 'hx-trigger="every 3s"')
                    self.assertNotContains(page, "Cancelar consulta")
                with patch("basis.modules.coach.adapters.actions.httpx.Client") as client:
                    self.assertEqual(
                        enqueue(self.owner, kind, "Synthetic cancellation", key).pk, job.pk
                    )
                    self.assertFalse(process_one())
                    client.assert_not_called()
                self.assertFalse(PlanProposal.objects.filter(job=job).exists())
                self.assertEqual(AIJob.objects.filter(owner=self.owner, request_key=key).count(), 1)

    def test_auth_method_owner_and_csrf_are_enforced_without_leaks(self) -> None:
        job = enqueue(self.owner, "short", "Private cancellation prompt", uuid4())
        url = reverse("job-cancel", args=[job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.other)
        foreign = self.client.post(url)
        self.assertEqual(foreign.status_code, 404)
        self.assertNotContains(foreign, job.prompt, status_code=404)
        self.assertEqual(self.client.post(reverse("job-cancel", args=[uuid4()])).status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url).status_code, 403)
        csrf.get(reverse("job-detail", args=[job.pk]))
        self.assertEqual(csrf.post(url, {"csrfmiddlewaretoken": "invalid"}).status_code, 403)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(
            csrf.post(url, {"csrfmiddlewaretoken": csrf.cookies["csrftoken"].value}).status_code,
            302,
        )

    def test_expired_account_can_cancel_with_ai_disabled(self) -> None:
        job = enqueue(self.owner, "plan", "Expired owner", uuid4())
        BillingAccount.objects.filter(owner=self.owner).update(
            period_end=timezone.now() - timedelta(days=1)
        )
        with override_settings(AI_ENABLED=False, DEEPSEEK_API_KEY=""):
            self.assertEqual(
                self.client.post(reverse("job-cancel", args=[job.pk])).status_code, 302
            )
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")

    def test_concurrent_claim_returns_409_and_real_state_with_reserve_intact(self) -> None:
        job = enqueue(self.owner, "short", "Claim race", uuid4())
        original_cancel = cancel

        def claim_first(*args: object) -> AIJob:
            with DjangoUnitOfWork() as work:
                jobs().repo.claim(timezone.now())
                work.commit()
            return original_cancel(self.owner, job.pk)

        with patch("basis.modules.coach.adapters.web.views.cancel", side_effect=claim_first):
            page = self.client.post(reverse("job-cancel", args=[job.pk]))
        self.assertContains(page, "running", status_code=409)
        self.assertContains(page, "ya comenzó", status_code=409)
        self.assertContains(page, "Reserva pendiente:", status_code=409)
        self.assertContains(page, 'hx-trigger="every 3s"', status_code=409)
        self.assertNotContains(page, "Cancelar consulta", status_code=409)
        job.refresh_from_db()
        self.assertEqual((job.status, job.usage_period.reserved), ("running", job.reservation))

    def test_manual_training_and_current_plan_survive_cancellation(self) -> None:
        plan = build_proposal(self.owner.pk, proposal(self.owner))
        assert plan is not None
        before = list(TrainingPlan.objects.filter(owner=self.owner).values())
        job = enqueue(self.owner, "plan", "Cancel adaptation", uuid4(), base_plan_id=plan.pk)
        self.client.post(reverse("job-cancel", args=[job.pk]))
        result = self.client.post(
            reverse("session-new"),
            {
                "title": "Manual after cancellation",
                "date": timezone.localdate().isoformat(),
                "duration_protocol": "elapsed",
                "block-sport": "running",
                "block-title": "Run",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertTrue(
            Session.objects.filter(owner=self.owner, title="Manual after cancellation").exists()
        )
        self.assertEqual(list(TrainingPlan.objects.filter(owner=self.owner).values()), before)


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class CancellationConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.owner = AccountId(get_user_model().objects.create_user(username="cancel-race").pk)

    def threaded(self, action: Callable[[], T], ready: Event, pids: list[int]) -> T:
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            ready.set()
            return action()
        finally:
            connections.close_all()

    def blocked_by(self, pid: int, blocker: int) -> None:
        deadline = monotonic() + 6
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                if blocker in cursor.fetchone()[0]:
                    return
        self.fail(f"PostgreSQL did not report expected blocker {blocker} for {pid}")

    def main_pid(self) -> int:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            return int(cursor.fetchone()[0])

    def pending(self, trial: bool) -> tuple[Jobs, Job]:
        instance = service(trial)
        return instance, instance.enqueue(
            Enqueue(self.owner, "short", "race", AIRequestKey(uuid4()))
        )

    def test_claim_first_cancel_waits_on_job_then_conflicts(self) -> None:
        for trial in (False, True):
            instance, job = self.pending(trial)
            ready = Event()
            pids: list[int] = []

            def cancellation() -> str:
                try:
                    service(trial).cancel(self.owner, job.id)
                except CancellationConflict:
                    return "conflict"
                return "unexpected cancellation"

            with ThreadPoolExecutor(max_workers=1) as pool:
                with transaction.atomic():
                    claimed = instance.repo.claim(NOW)
                    assert claimed is not None
                    future = pool.submit(self.threaded, cancellation, ready, pids)
                    self.assertTrue(ready.wait(5))
                    self.blocked_by(pids[0], self.main_pid())
                self.assertEqual(future.result(timeout=10), "conflict")
            self.assertEqual(instance.repo.usage(job.usage_period).reserved, job.reservation)
            self.assertEqual(instance.repo.job(job.id).attempt_id, claimed.attempt_id)
            # Close this fixture's attempt through the matching818 path, without HTTP.
            instance.settle(job.id, definitive=True, attempt_id=claimed.attempt_id)

    def test_cancel_first_worker_skips_locked_row_and_never_sends_after_commit(self) -> None:
        for trial in (False, True):
            instance, job = self.pending(trial)
            ready = Event()
            pids: list[int] = []
            with ThreadPoolExecutor(max_workers=1) as pool:
                with transaction.atomic():
                    instance.cancel(self.owner, job.id)
                    # claim deliberately uses SKIP LOCKED: it must NOT wait on cancellation.
                    future = pool.submit(self.threaded, service(trial).process_one, ready, pids)
                    self.assertTrue(ready.wait(5))
                    self.assertFalse(future.result(timeout=10))
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pids[0]])
                        self.assertEqual(cursor.fetchone()[0], [])
            with patch.object(instance.provider, "call") as call:
                self.assertFalse(instance.process_one())
                call.assert_not_called()
            self.assertEqual(instance.repo.job(job.id).status, "cancelled")
            self.assertEqual(instance.repo.usage(job.usage_period).reserved, 0)

    def test_cancel_then_enqueue_same_account_blocks_without_cycle_original_and_later_month(
        self,
    ) -> None:
        for trial in (False, True):
            for later_month in (False, True):
                instance, job = self.pending(trial)
                other = service(trial)
                if later_month:
                    other.clock = replace_clock = LaterPorts()
                    replace_clock.state = replace(
                        replace_clock.state, period_end=NOW + timedelta(days=60)
                    )
                    other.billing = replace_clock
                ready = Event()
                pids: list[int] = []
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with transaction.atomic():
                        instance.cancel(self.owner, job.id)
                        future = pool.submit(
                            self.threaded,
                            lambda: other.enqueue(
                                Enqueue(
                                    self.owner, "short", "concurrent enqueue", AIRequestKey(uuid4())
                                )
                            ),
                            ready,
                            pids,
                        )
                        self.assertTrue(ready.wait(5))
                        self.blocked_by(pids[0], self.main_pid())
                    created = future.result(timeout=10)
                usage = instance.repo.usage(created.usage_period)
                self.assertEqual((usage.reserved, usage.short_count), (created.reservation, 1))
                self.assertEqual(instance.repo.job(job.id).status, "cancelled")
                instance.cancel(self.owner, created.id)
                self.assertFalse(UsagePeriod.objects.filter(reserved__lt=0).exists())
                self.assertFalse(TrialFund.objects.filter(reserved__lt=0).exists())

    def test_enqueue_first_cancel_waits_and_preserves_new_job_reserve(self) -> None:
        for trial in (False, True):
            instance, job = self.pending(trial)
            ready = Event()
            pids: list[int] = []
            with ThreadPoolExecutor(max_workers=1) as pool:
                with transaction.atomic():
                    created = instance.enqueue(
                        Enqueue(self.owner, "short", "enqueue first", AIRequestKey(uuid4()))
                    )
                    future = pool.submit(
                        self.threaded,
                        lambda: service(trial).cancel(self.owner, job.id),
                        ready,
                        pids,
                    )
                    self.assertTrue(ready.wait(5))
                    self.blocked_by(pids[0], self.main_pid())
                self.assertEqual(future.result(timeout=10).status, "cancelled")
            usage = instance.repo.usage(job.usage_period)
            self.assertEqual((usage.reserved, usage.short_count), (created.reservation, 1))
            if created.trial_fund:
                self.assertEqual(
                    instance.repo.fund(created.trial_fund).reserved, created.reservation
                )
            instance.cancel(self.owner, created.id)

    def test_simultaneous_cancellation_waits_then_replays_without_double_adjustment(self) -> None:
        for trial in (False, True):
            instance, job = self.pending(trial)
            ready = Event()
            pids: list[int] = []
            with ThreadPoolExecutor(max_workers=1) as pool:
                with transaction.atomic():
                    result = instance.cancel(self.owner, job.id)
                    future = pool.submit(
                        self.threaded,
                        lambda: service(trial).cancel(self.owner, job.id),
                        ready,
                        pids,
                    )
                    self.assertTrue(ready.wait(5))
                    self.blocked_by(pids[0], self.main_pid())
                self.assertEqual(future.result(timeout=10), result)
            usage = instance.repo.usage(job.usage_period)
            self.assertEqual((usage.reserved, usage.short_count), (0, 0))
            if job.trial_fund:
                self.assertEqual(instance.repo.fund(job.trial_fund).reserved, 0)
