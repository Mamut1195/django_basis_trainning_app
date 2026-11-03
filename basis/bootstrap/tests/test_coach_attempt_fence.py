"""Real worker, HTTP decoder, ledger and PostgreSQL attempt fencing."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Event
from time import monotonic, sleep
from typing import Callable
from unittest.mock import patch
from uuid import uuid4

import httpx
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature

from basis.adapters.django.transactions import DjangoUnitOfWork
from basis.modules.accounts.adapters.coach import DjangoAccountLocks
from basis.modules.coach.adapters.jobs import DjangoJobsRepository
from basis.modules.coach.adapters.models import AIJob, AIReconciliation, AIServiceState, TrialFund
from basis.modules.coach.adapters.provider import DeepSeekProvider
from basis.modules.coach.application.jobs import CoachConfiguration, Enqueue, Jobs
from basis.modules.coach.domain.jobs import (
    Job,
    ProviderReply,
    Reconcile,
    Reconciliation,
    TokenUsage,
)
from basis.shared.identifiers import AccountId, AIRequestKey, JobId
from tests_architecture.test_coach_jobs import NOW, Ports, Profiles

MODEL = "deepseek-v4-flash"


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class AttemptFenceTests(TransactionTestCase):
    def service(self, trial: bool, handler: Callable[[httpx.Request], httpx.Response]) -> Jobs:
        ports = Ports()
        ports.state = replace(ports.state, status="trialing" if trial else "active")

        def client(*, timeout: httpx.Timeout) -> httpx.Client:
            return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout)

        return Jobs(
            DjangoJobsRepository(),
            DjangoAccountLocks(),
            ports,
            Profiles(),
            ports,
            DeepSeekProvider("synthetic", client),
            ports,
            ports,
            DjangoUnitOfWork,
            CoachConfiguration(True, True, MODEL),
        )

    def test_worker_late_matrix_preserves_reservations_and_replay(self) -> None:
        for trial in (False, True):
            for invalid in (False, True):
                for before in (False, True):
                    for charged in (False, True):
                        with self.subTest(
                            trial=trial, invalid=invalid, before=before, charged=charged
                        ):
                            AIServiceState.objects.update(blocked=False)
                            entered, resume = Event(), Event()
                            calls = []

                            def handler(request: httpx.Request) -> httpx.Response:
                                calls.append(1)
                                entered.set()
                                self.assertTrue(resume.wait(10))
                                usage = (
                                    {"prompt_tokens": 10**40, "completion_tokens": False}
                                    if invalid
                                    else {"prompt_tokens": 1, "completion_tokens": 0}
                                )
                                return httpx.Response(
                                    200,
                                    json={
                                        "model": MODEL,
                                        "usage": usage,
                                        "choices": [
                                            {
                                                "finish_reason": "stop",
                                                "message": {"content": "fixture"},
                                            }
                                        ],
                                    },
                                )

                            service = self.service(trial, handler)
                            owner = AccountId(
                                get_user_model().objects.create_user(username=f"fence-{uuid4()}").pk
                            )
                            job = service.enqueue(
                                Enqueue(owner, "short", "question", AIRequestKey(uuid4()))
                            )
                            original_usage = service.repo.usage(job.usage_period)
                            original_fund = (
                                service.repo.fund(job.trial_fund) if job.trial_fund else None
                            )
                            command = Reconcile(
                                job.id,
                                "decision",
                                "admin:test",
                                "fixture",
                                "synthetic",
                                "usage" if charged else "no_charge",
                                not charged,
                                MODEL if charged else "",
                                TokenUsage(1, 0, 0) if charged else None,
                            )

                            def run_worker() -> bool:
                                close_old_connections()
                                try:
                                    return service.process_one()
                                finally:
                                    connections.close_all()

                            with ThreadPoolExecutor(max_workers=1) as pool:
                                future = pool.submit(run_worker)
                                try:
                                    self.assertTrue(entered.wait(10))
                                    opened = service.repo.job(job.id)
                                    self.assertIsNotNone(opened.attempt_id)
                                    AIJob.objects.filter(pk=job.id).update(
                                        started_at=NOW - timedelta(minutes=11)
                                    )
                                    service.quarantine_stale_jobs()
                                    # Neither uncredentialed nor wrong-attempt settlement can close it.
                                    service.settle(job.id, definitive=True)
                                    service.settle(job.id, definitive=True, attempt_id=uuid4())
                                    self.assertEqual(
                                        service.repo.job(job.id).attempt_id, opened.attempt_id
                                    )
                                    if before:
                                        self.assertEqual(
                                            service.reconcile(command).outcome, "retained"
                                        )
                                        self.assertFalse(
                                            AIReconciliation.objects.filter(job_id=job.id).exists()
                                        )
                                        record = service.reconcile(command, apply=True)
                                        self.assertEqual(record.outcome, "retained")
                                        self.assertEqual(
                                            service.reconcile(command, apply=True), record
                                        )
                                finally:
                                    resume.set()
                                self.assertTrue(future.result(timeout=15))

                            closed = service.repo.job(job.id)
                            self.assertEqual(
                                (closed.status, closed.cost, closed.attempt_id),
                                ("uncertain", None, None),
                            )
                            self.assertIs(closed.invalid_usage_observed, invalid)
                            if not invalid:
                                self.assertEqual(
                                    (
                                        closed.reported_model,
                                        closed.input_tokens,
                                        closed.output_tokens,
                                        closed.cache_hit_tokens,
                                    ),
                                    (MODEL, 1, 0, 0),
                                )
                            self.assertEqual(service.repo.usage(job.usage_period), original_usage)
                            if original_fund:
                                self.assertEqual(service.repo.fund(original_fund.id), original_fund)
                            self.assertEqual(
                                service.settle(job.id, attempt_id=opened.attempt_id), closed
                            )
                            if before:
                                self.assertEqual(service.reconcile(command, apply=True), record)
                            final_command = replace(command, key="after") if before else command
                            later_fund = None
                            if trial:
                                later_fund, _ = TrialFund.objects.get_or_create(month="2026-12")
                                later_balance = (later_fund.reserved, later_fund.spent)
                            with patch.object(
                                service.clock, "now", return_value=NOW + timedelta(days=45)
                            ):
                                final_record = service.reconcile(final_command, apply=True)
                            if later_fund:
                                later_fund.refresh_from_db()
                                self.assertEqual(
                                    (later_fund.reserved, later_fund.spent), later_balance
                                )
                            self.assertEqual(
                                final_record.outcome,
                                "retained" if invalid else ("charged" if charged else "released"),
                            )
                            self.assertEqual(
                                service.reconcile(final_command, apply=True), final_record
                            )
                            self.assertEqual(calls, [1])
                            self.assertEqual(
                                AIReconciliation.objects.filter(job_id=job.id).count(),
                                2 if before else 1,
                            )
                            if invalid:
                                self.assertTrue(service.repo.blocked())
                                self.assertEqual(
                                    service.repo.usage(job.usage_period), original_usage
                                )
                                if original_fund:
                                    self.assertEqual(
                                        service.repo.fund(original_fund.id), original_fund
                                    )
                            else:
                                usage = service.repo.usage(job.usage_period)
                                cost = Decimal("0.00000030") if charged else Decimal(0)
                                self.assertEqual((usage.reserved, usage.spent), (Decimal(0), cost))
                                if original_fund:
                                    fund = service.repo.fund(original_fund.id)
                                    self.assertEqual(
                                        (fund.reserved, fund.spent),
                                        (
                                            original_fund.reserved - job.reservation,
                                            original_fund.spent + cost,
                                        ),
                                    )

    def test_late_valid_plan_does_not_create_proposal(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                AIServiceState.objects.update(blocked=False)
                service = self.service(trial, lambda request: httpx.Response(500))
                owner = AccountId(
                    get_user_model().objects.create_user(username=f"plan-{uuid4()}").pk
                )
                job = service.enqueue(Enqueue(owner, "plan", "question", AIRequestKey(uuid4())))
                baseline = service.repo.usage(job.usage_period)

                def handler(request: httpx.Request) -> httpx.Response:
                    AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
                    service.quarantine_stale_jobs()
                    return httpx.Response(
                        200,
                        json={
                            "model": MODEL,
                            "usage": {"prompt_tokens": 1, "completion_tokens": 0},
                            "choices": [
                                {"finish_reason": "stop", "message": {"content": "fixture"}}
                            ],
                        },
                    )

                service.provider = self.service(trial, handler).provider
                with patch.object(service.proposals, "complete") as complete:
                    self.assertTrue(service.process_one())
                    complete.assert_not_called()
                self.assertEqual(service.repo.job(job.id).status, "uncertain")
                self.assertEqual(service.repo.usage(job.usage_period), baseline)

    def test_postgres_lock_orders_return_and_reconciliation(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                AIServiceState.objects.update(blocked=False)
                entered, resume, worker_pid_ready, reconcile_pid_ready = (Event() for _ in range(4))
                pids = {}

                def handler(request: httpx.Request) -> httpx.Response:
                    entered.set()
                    self.assertTrue(resume.wait(10))
                    return httpx.Response(
                        200,
                        json={
                            "model": MODEL,
                            "usage": {"prompt_tokens": 10**40, "completion_tokens": False},
                        },
                    )

                service = self.service(trial, handler)
                owner = AccountId(
                    get_user_model().objects.create_user(username=f"lock-{uuid4()}").pk
                )
                job = service.enqueue(Enqueue(owner, "short", "question", AIRequestKey(uuid4())))
                baseline = service.repo.usage(job.usage_period)
                original_fund = service.repo.fund(job.trial_fund) if job.trial_fund else None
                command = Reconcile(
                    job.id, "lock", "admin:test", "fixture", "synthetic", "no_charge", True
                )

                def run_worker() -> bool:
                    close_old_connections()
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_backend_pid()")
                            pids["worker"] = cursor.fetchone()[0]
                        worker_pid_ready.set()
                        return service.process_one()
                    finally:
                        connections.close_all()

                def reconcile() -> Reconciliation:
                    close_old_connections()
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_backend_pid()")
                            pids["reconcile"] = cursor.fetchone()[0]
                        reconcile_pid_ready.set()
                        return service.reconcile(command, apply=True)
                    finally:
                        connections.close_all()

                def wait_blocked(pid: int, blocker: int) -> None:
                    deadline = monotonic() + 8
                    while monotonic() < deadline:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                            if blocker in cursor.fetchone()[0]:
                                return
                        sleep(0.02)
                    self.fail(f"PostgreSQL backend {pid} did not block")

                with ThreadPoolExecutor(max_workers=2) as pool:
                    worker = pool.submit(run_worker)
                    self.assertTrue(worker_pid_ready.wait(10))
                    self.assertTrue(entered.wait(10))
                    AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
                    service.quarantine_stale_jobs()
                    try:
                        with transaction.atomic():
                            AIJob.objects.select_for_update().get(pk=job.id)
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT pg_backend_pid()")
                                main_pid = cursor.fetchone()[0]
                            resume.set()
                            wait_blocked(pids["worker"], main_pid)
                            admin = pool.submit(reconcile)
                            self.assertTrue(reconcile_pid_ready.wait(10))
                            wait_blocked(pids["reconcile"], pids["worker"])
                    finally:
                        resume.set()
                    self.assertTrue(worker.result(timeout=15))
                    self.assertEqual(admin.result(timeout=15).outcome, "retained")
                row = service.repo.job(job.id)
                self.assertEqual(
                    (row.status, row.invalid_usage_observed, row.attempt_id),
                    ("uncertain", True, None),
                )
                self.assertEqual(service.repo.usage(job.usage_period), baseline)
                if original_fund:
                    self.assertEqual(service.repo.fund(original_fund.id), original_fund)
                self.assertEqual(service.reconcile(command, apply=True).outcome, "retained")

    def test_postgres_reconciliation_holds_locks_before_late_return(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                AIServiceState.objects.update(blocked=False)
                entered, return_http, admin_locked, release_admin = (Event() for _ in range(4))
                pids: dict[str, int] = {}

                def handler(request: httpx.Request) -> httpx.Response:
                    entered.set()
                    self.assertTrue(return_http.wait(10))
                    return httpx.Response(
                        200,
                        json={
                            "model": MODEL,
                            "usage": {"prompt_tokens": 10**40, "completion_tokens": False},
                        },
                    )

                worker_service = self.service(trial, handler)
                admin_service = self.service(trial, handler)
                owner = AccountId(
                    get_user_model().objects.create_user(username=f"reverse-{uuid4()}").pk
                )
                job = worker_service.enqueue(
                    Enqueue(owner, "short", "question", AIRequestKey(uuid4()))
                )
                usage = worker_service.repo.usage(job.usage_period)
                fund = worker_service.repo.fund(job.trial_fund) if job.trial_fund else None
                command = Reconcile(
                    job.id, "reverse", "admin:test", "fixture", "synthetic", "no_charge", True
                )
                original_lock = admin_service.repo.lock_job

                def hold_lock(job_id: JobId) -> Job:
                    locked = original_lock(job_id)
                    admin_locked.set()
                    self.assertTrue(release_admin.wait(10))
                    return locked

                def run_worker() -> bool:
                    close_old_connections()
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_backend_pid()")
                            pids["worker"] = cursor.fetchone()[0]
                        return worker_service.process_one()
                    finally:
                        connections.close_all()

                def run_admin() -> Reconciliation:
                    close_old_connections()
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_backend_pid()")
                            pids["admin"] = cursor.fetchone()[0]
                        return admin_service.reconcile(command, apply=True)
                    finally:
                        connections.close_all()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    worker = pool.submit(run_worker)
                    self.assertTrue(entered.wait(10))
                    AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
                    worker_service.quarantine_stale_jobs()
                    try:
                        with patch.object(admin_service.repo, "lock_job", side_effect=hold_lock):
                            admin = pool.submit(run_admin)
                            self.assertTrue(admin_locked.wait(10))
                            return_http.set()
                            deadline = monotonic() + 8
                            while monotonic() < deadline:
                                with connection.cursor() as cursor:
                                    cursor.execute("SELECT pg_blocking_pids(%s)", [pids["worker"]])
                                    if pids["admin"] in cursor.fetchone()[0]:
                                        break
                                sleep(0.02)
                            else:
                                self.fail("worker did not wait on reconciliation")
                            release_admin.set()
                            self.assertEqual(admin.result(timeout=15).outcome, "retained")
                            self.assertTrue(worker.result(timeout=15))
                    finally:
                        return_http.set()
                        release_admin.set()
                row = worker_service.repo.job(job.id)
                self.assertEqual(
                    (row.status, row.attempt_id, row.invalid_usage_observed),
                    ("uncertain", None, True),
                )
                self.assertEqual(worker_service.repo.usage(job.usage_period), usage)
                if fund:
                    self.assertEqual(worker_service.repo.fund(fund.id), fund)
                self.assertEqual(admin_service.reconcile(command, apply=True).outcome, "retained")

    def test_late_missing_usage_ambiguous_and_definitive_errors_close_only_on_return(self) -> None:
        for trial in (False, True):
            for scenario in ("missing", "ambiguous", "definitive"):
                with self.subTest(trial=trial, scenario=scenario):
                    AIServiceState.objects.update(blocked=False)
                    service = self.service(trial, lambda request: httpx.Response(500))
                    owner = AccountId(
                        get_user_model().objects.create_user(username=f"error-{uuid4()}").pk
                    )
                    job = service.enqueue(
                        Enqueue(owner, "short", "question", AIRequestKey(uuid4()))
                    )
                    baseline = service.repo.usage(job.usage_period)
                    original_fund = service.repo.fund(job.trial_fund) if job.trial_fund else None
                    calls = []

                    def handler(request: httpx.Request) -> httpx.Response:
                        calls.append(1)
                        AIJob.objects.filter(pk=job.id).update(
                            started_at=NOW - timedelta(minutes=11)
                        )
                        service.quarantine_stale_jobs()
                        if scenario == "ambiguous":
                            raise httpx.ReadTimeout("synthetic", request=request)
                        if scenario == "definitive":
                            return httpx.Response(400)
                        return httpx.Response(200, json={"model": MODEL})

                    service.provider = self.service(trial, handler).provider
                    self.assertTrue(service.process_one())
                    row = service.repo.job(job.id)
                    self.assertEqual(
                        (row.status, row.attempt_id, row.invalid_usage_observed),
                        ("uncertain", None, False),
                    )
                    self.assertEqual(service.repo.usage(job.usage_period), baseline)
                    if original_fund:
                        self.assertEqual(service.repo.fund(original_fund.id), original_fund)
                    self.assertEqual(calls, [1])
                    command = Reconcile(
                        job.id, "error", "admin:test", "fixture", "synthetic", "no_charge", True
                    )
                    self.assertEqual(
                        service.reconcile(command, apply=True).outcome,
                        "retained" if scenario == "missing" else "released",
                    )

    def test_attempt_closure_and_invalid_marker_roll_back_together(self) -> None:
        for trial in (False, True):
            with self.subTest(trial=trial):
                AIServiceState.objects.update(blocked=False)
                service = self.service(trial, lambda request: httpx.Response(500))
                owner = AccountId(
                    get_user_model().objects.create_user(username=f"rollback-{uuid4()}").pk
                )
                job = service.enqueue(Enqueue(owner, "short", "question", AIRequestKey(uuid4())))
                with DjangoUnitOfWork() as work:
                    claimed = service.repo.claim(NOW)
                    work.commit()
                assert claimed is not None
                AIJob.objects.filter(pk=job.id).update(started_at=NOW - timedelta(minutes=11))
                service.quarantine_stale_jobs()
                previous = service.repo.job(job.id)
                usage = service.repo.usage(job.usage_period)
                original_fund = service.repo.fund(job.trial_fund) if job.trial_fund else None
                save = service.repo.save_job

                def save_then_fail(changed: Job) -> None:
                    save(changed)
                    raise RuntimeError("synthetic rollback")

                reply = ProviderReply(None, MODEL, invalid_usage_observed=True)
                with patch.object(service.repo, "save_job", side_effect=save_then_fail):
                    with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
                        service.settle(job.id, reply, attempt_id=claimed.attempt_id)
                self.assertEqual(service.repo.job(job.id), previous)
                self.assertEqual(service.repo.usage(job.usage_period), usage)
                self.assertFalse(service.repo.blocked())
                if original_fund:
                    self.assertEqual(service.repo.fund(original_fund.id), original_fund)
                closed = service.settle(job.id, reply, attempt_id=claimed.attempt_id)
                self.assertEqual((closed.attempt_id, closed.invalid_usage_observed), (None, True))
                self.assertEqual(
                    service.settle(job.id, reply, attempt_id=claimed.attempt_id), closed
                )


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class AttemptFenceMigrationTests(TransactionTestCase):
    def test_legacy_active_and_uncertain_are_fenced_and_downgrade_rejected(self) -> None:
        old = [("basis_coach", "0002_frozen_pricing_reconciliation")]
        new = [("basis_coach", "0003_open_attempt_fence")]
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        owner = get_user_model().objects.create_user(username=f"legacy-{uuid4()}")
        usage = apps.get_model("basis_coach", "UsagePeriod").objects.create(
            owner_id=owner.pk, key="legacy"
        )
        job_model = apps.get_model("basis_coach", "AIJob")
        ids = {}
        for status in ("pending", "running", "uncertain", "succeeded", "failed"):
            job = job_model.objects.create(
                id=uuid4(),
                owner_id=owner.pk,
                request_key=uuid4(),
                kind="short",
                prompt="fixture",
                context={},
                status=status,
                usage_period_id=usage.pk,
                reservation="0.003",
                requested_model=MODEL,
            )
            ids[status] = job.pk
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            migrated = executor.loader.project_state(new).apps.get_model("basis_coach", "AIJob")
            attempts = {
                status: migrated.objects.get(pk=pk).attempt_id for status, pk in ids.items()
            }
            self.assertIsNotNone(attempts["running"])
            self.assertIsNotNone(attempts["uncertain"])
            self.assertNotEqual(attempts["running"], attempts["uncertain"])
            for status in ("pending", "succeeded", "failed"):
                self.assertIsNone(attempts[status])
            with self.assertRaises(IrreversibleError):
                MigrationExecutor(connection).migrate(old)
            self.assertEqual(
                migrated.objects.get(pk=ids["uncertain"]).attempt_id, attempts["uncertain"]
            )
        finally:
            MigrationExecutor(connection).migrate(new)
