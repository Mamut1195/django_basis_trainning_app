"""Real PostgreSQL lock waits, not barriers waiting for mutually held locks."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from basis.bootstrap.planning import planning
from basis.bootstrap.training import training
from basis.modules.training.adapters.django import DjangoSessionRepository
from basis.modules.training.adapters.models import PlannedSession, Session, TrainingPlan
from basis.modules.training.adapters.planning import DjangoPlanRepository
from basis.modules.training.public import (
    ChangeScheduledSession,
    InvalidPlanning,
    PlanSnapshot,
    Prescription,
    RescheduleSession,
    RestorePlan,
    RevisePlan,
    ScheduleStatus,
    StartSession,
)
from basis.shared.identifiers import AccountId, PlanId, PlannedSessionId, Revision
from tests.regression.test_planning_versioning import PlanningFixture
from tests_architecture.test_planning import TODAY


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class PlanningConcurrencyTests(PlanningFixture, TransactionTestCase):
    def race(self, first: str, second: str) -> tuple[str, str]:
        captured, release, ready = threading.Event(), threading.Event(), threading.Event()
        second_pid: list[int] = []
        owner, head, target = self.owner, self.header.id, self.header.id
        session_id = PlannedSessionId(self.future.pk)
        revision = Revision(self.future.revision)
        if first == "restore":
            newer = self.service.revise(RevisePlan(owner, head, "Preparar restauración"))
            head = newer.id
            row = PlannedSession.objects.get(plan_id=head, origin=self.future)
            session_id, revision = PlannedSessionId(row.pk), Revision(row.revision)

        class PausedPlans(DjangoPlanRepository):
            def snapshot(inner, owner: AccountId, plan: PlanId, *, lock: bool) -> PlanSnapshot:
                result = super().snapshot(owner, plan, lock=lock)
                if lock and not captured.is_set():
                    captured.set()
                    if not release.wait(15):
                        raise AssertionError("Test controller did not release aggregate")
                return result

        class PausedSessions(DjangoSessionRepository):
            def prescription(inner, owner: AccountId, planned: PlannedSessionId) -> Prescription:
                result = super().prescription(owner, planned)
                captured.set()
                if not release.wait(15):
                    raise AssertionError("Test controller did not release aggregate")
                return result

        def operation(kind: str, paused: bool) -> str:
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                if not paused:
                    second_pid.append(pid)
                    ready.set()
                service = planning()
                execution = training()
                if paused:
                    service.repository = PausedPlans()
                    execution.repository = PausedSessions()
                try:
                    if kind == "start":
                        execution.start(StartSession(owner, session_id))
                    elif kind == "move":
                        service.reschedule(
                            RescheduleSession(
                                owner,
                                session_id,
                                TODAY + timedelta(days=2),
                                revision,
                                "Cambio concurrente",
                            )
                        )
                    elif kind == "cancel":
                        service.change_session(
                            ChangeScheduledSession(
                                owner,
                                session_id,
                                revision,
                                "Cancelar concurrente",
                                ScheduleStatus.CANCELLED,
                            )
                        )
                    elif kind == "restore":
                        service.restore(RestorePlan(owner, head, target, "Restaurar concurrente"))
                    else:
                        service.revise(RevisePlan(owner, head, "Revisión concurrente"))
                    return "accepted"
                except (InvalidPlanning, ValidationError):
                    return "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            winner = pool.submit(operation, first, True)
            try:
                self.assertTrue(captured.wait(8))
                loser = pool.submit(operation, second, False)
                self.assertTrue(ready.wait(8))
                # Observe the real database lock wait before releasing the winner.
                waiting = False
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                            [second_pid[0]],
                        )
                        state = cursor.fetchone()
                    if state and state[0] == "Lock":
                        waiting = True
                        break
                    time.sleep(0.02)
                self.assertTrue(waiting, "Second connection must wait on the shared aggregate lock")
            finally:
                release.set()
            outcomes = winner.result(timeout=12), loser.result(timeout=12)
        self.assertEqual(outcomes[0], "accepted")
        self.assertLessEqual(Session.objects.count(), 1)
        return outcomes

    def test_revise_move_rejects_stale_move(self) -> None:
        self.assertEqual(self.race("revise", "move"), ("accepted", "conflict"))

    def test_move_revise_rejects_stale_revision(self) -> None:
        self.assertEqual(self.race("move", "revise"), ("accepted", "conflict"))

    def test_revise_start_rejects_superseded_start(self) -> None:
        self.assertEqual(self.race("revise", "start"), ("accepted", "conflict"))
        self.assertFalse(Session.objects.exists())

    def test_start_revise_keeps_execution_and_does_not_clone_started_intent(self) -> None:
        self.assertEqual(self.race("start", "revise"), ("accepted", "accepted"))
        current = TrainingPlan.objects.get(previous_id=self.header.id)
        self.assertFalse(current.sessions.filter(origin=self.future).exists())
        self.assertEqual(Session.objects.get().planned_id, self.future.pk)

    def test_cancel_start_rejects_cancelled_or_superseded_start(self) -> None:
        self.assertEqual(self.race("cancel", "start"), ("accepted", "conflict"))

    def test_restore_move_rejects_stale_head(self) -> None:
        self.assertEqual(self.race("restore", "move"), ("accepted", "conflict"))

    def test_restore_restore_has_one_successor(self) -> None:
        self.assertEqual(self.race("restore", "restore"), ("accepted", "conflict"))
        self.assertEqual(TrainingPlan.objects.count(), 3)

    def test_start_start_returns_one_execution(self) -> None:
        self.assertEqual(self.race("start", "start"), ("accepted", "accepted"))
        self.assertEqual(Session.objects.count(), 1)
