"""Independent processes exercise account/FK locks and authoritative root reads."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import cast
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from basis.modules.athletes.adapters.identity import public_id
from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import session_snapshot, start_session
from basis.modules.training.adapters.models import Goal, PlannedSession, Session, TrainingPlan
from basis.modules.training.public import RevisePlan
from tests.regression.test_planning_versioning import PlanningFixture

ROOT = Path(__file__).resolve().parents[2]


class HTTPWorker:
    def __init__(self, spec: dict[str, object]) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "tests.regression.planning_revision_worker"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
        )
        self.events: Queue[dict[str, object]] = Queue()
        self.messages: list[dict[str, object]] = []
        self.errors: list[str] = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.stderr_reader = threading.Thread(target=self._read_errors, daemon=True)
        self.reader.start()
        self.stderr_reader.start()
        self.send(json.dumps(spec))
        self.ready = self.expect("ready")

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            data = cast(dict[str, object], json.loads(line))
            self.messages.append(data)
            self.events.put(data)

    def _read_errors(self) -> None:
        assert self.process.stderr is not None
        self.errors.extend(self.process.stderr)

    def send(self, text: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def expect(self, phase: str) -> dict[str, object]:
        try:
            item = self.events.get(timeout=22)
        except Empty as error:
            raise AssertionError(
                "Worker did not emit " + phase + ": " + "".join(self.errors)
            ) from error
        if item.get("phase") != phase:
            raise AssertionError((phase, item, self.errors))
        return item

    def close(self) -> None:
        try:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=5)
        finally:
            self.reader.join(timeout=2)
            self.stderr_reader.join(timeout=2)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream is not None:
                    stream.close()


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL lock waits")
class PlanningRevisionProcessTests(PlanningFixture, TransactionTestCase):
    def setUp(self) -> None:
        # Deliberately de-align auth IDs and athlete IDs. Account locks must use
        # the real AUTH_USER_MODEL row, not profile.pk or a submitted actor field.
        get_user_model().objects.create_user(username="auth-slot-without-profile-622")
        super().setUp()
        self.assertNotEqual(self.user.pk, self.user.athlete.pk)
        self.executed = start_session(
            self.user, PlannedSession.objects.get(plan_id=self.header.id, title="executed")
        )

    def spec(self, action: str, pause: str = "") -> dict[str, object]:
        db = dict(connection.settings_dict)
        db["TEST"] = {}
        body: dict[str, object] = {
            "account": str(public_id(self.user.pk)),
            "mutation_id": str(uuid4()),
            "session": session_snapshot(self.executed),
        }
        return {
            "database": db,
            "owner": self.user.pk,
            "action": action,
            "pause": pause,
            "planned": self.future.pk,
            "head": self.header.id,
            "target": self.header.id,
            "revision": self.future.revision,
            "body": body,
        }

    def run_pair(
        self, first: dict[str, object], second: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, object]]:
        workers: list[HTTPWorker] = []
        observations: dict[str, object] = {
            "first_action": first["action"],
            "second_action": second["action"],
        }
        try:
            one = HTTPWorker(first)
            workers.append(one)
            two = HTTPWorker(second)
            workers.append(two)
            self.assertNotEqual(one.ready["process"], two.ready["process"])
            self.assertNotEqual(one.ready["pid"], two.ready["pid"])
            one.send("go")
            one.expect("locked")
            two.send("go")
            try:
                deadline = time.monotonic() + 7
                waiting = None
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT wait_event_type, wait_event, pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid=%s",
                            [int(str(two.ready["pid"]))],
                        )
                        state = cursor.fetchone()
                    if state and state[0] == "Lock":
                        waiting = state
                        break
                    time.sleep(0.02)
                self.assertIsNotNone(waiting, "The second process must wait on a real product lock")
                observations["wait"] = waiting
            finally:
                one.send("release")
            a, b = one.expect("result"), two.expect("result")
            observations["outcomes"] = [a, b]
            for worker, result in ((one, a), (two, b)):
                self.assertEqual(worker.process.wait(timeout=10), 0, worker.errors)
                self.assertIsNone(result["error"], worker.errors)
                self.assertIsNone(result["sqlstate"], worker.errors)
                self.assertNotEqual(result["status"], 500, worker.errors)
                self.assertFalse(any("deadlock detected" in error for error in worker.errors))
            print("R622_PROCESS " + json.dumps(observations, default=str), flush=True)
            return a, b
        finally:
            for worker in workers:
                worker.close()

    def test_move_then_sync_other_execution_commits_both_without_fk_deadlock(self) -> None:
        a, b = self.run_pair(self.spec("move", "plan"), self.spec("sync"))
        self.assertEqual((a["status"], b["status"]), (302, 200))
        self.assertEqual(TrainingPlan.objects.count(), 2)
        self.assertEqual(SyncReceipt.objects.count(), 1)

    def test_sync_then_move_other_execution_commits_both_without_fk_deadlock(self) -> None:
        a, b = self.run_pair(self.spec("sync", "sync"), self.spec("move"))
        self.assertEqual((a["status"], b["status"]), (200, 302))

    def test_start_then_sync_other_execution_commits_both(self) -> None:
        a, b = self.run_pair(self.spec("start", "start"), self.spec("sync"))
        self.assertEqual((a["status"], b["status"]), (302, 200))
        self.assertEqual(Session.objects.filter(owner=self.user).count(), 2)

    def test_sync_then_start_other_execution_commits_both(self) -> None:
        a, b = self.run_pair(self.spec("sync", "sync"), self.spec("start"))
        self.assertEqual((a["status"], b["status"]), (200, 302))

    def test_start_then_new_linked_sync_has_no_second_execution_or_receipt(self) -> None:
        second = self.spec("sync")
        payload = session_snapshot(self.executed)
        payload.update(id=str(uuid4()), planned=self.future.pk, revision=0)
        body = cast(dict[str, object], second["body"])
        body["session"] = payload
        a, b = self.run_pair(self.spec("start", "start"), second)
        self.assertEqual((a["status"], b["status"]), (302, 400))
        self.assertEqual(Session.objects.filter(planned=self.future).count(), 1)
        self.assertFalse(SyncReceipt.objects.exists())

    def test_new_linked_sync_then_start_reuses_execution_and_replay_is_unchanged(self) -> None:
        first = self.spec("sync", "sync")
        payload = session_snapshot(self.executed)
        payload.update(id=str(uuid4()), planned=self.future.pk, revision=0)
        # Initialize from this prescription, not a snapshot/IDs of a different
        # execution. MAM623 freezes the intention shared by both entry paths.
        payload["blocks"] = [
            {
                "sport": block.sport,
                "title": block.title,
                "target": block.target,
                "actual": {},
                "sets": [],
                "intervals": [],
            }
            for block in self.future.blocks.all()
        ]
        body = cast(dict[str, object], first["body"])
        body["session"] = payload
        a, b = self.run_pair(first, self.spec("start"))
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.assertEqual(Session.objects.filter(planned=self.future).count(), 1)
        replay = self.client.post("/api/sync/", json.dumps(body), content_type="application/json")
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), a["body"])
        self.assertEqual(SyncReceipt.objects.count(), 1)

    def test_account_lock_uses_target_alias_and_auth_pk_not_profile_pk(self) -> None:
        a, b = self.run_pair(self.spec("alias_account", "alias"), self.spec("start"))
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.assertEqual(a["body"], {"default": False, "target": True})

    def test_lineage_lock_and_uow_use_the_same_nondefault_alias(self) -> None:
        a, b = self.run_pair(self.spec("alias_plan", "alias"), self.spec("start"))
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.assertEqual(a["body"], {"default": False, "target": True})

    def test_nondefault_uow_rolls_back_on_target_and_retains_outer_lock_until_exit(self) -> None:
        a, b = self.run_pair(self.spec("alias_rollback", "alias"), self.spec("start"))
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.assertEqual(a["body"], {"default": False, "target": True})
        self.assertFalse(Goal.objects.filter(title="Rollback target alias 622").exists())

    def test_foreign_execution_is_rejected_without_locking_its_account(self) -> None:
        one, two = HTTPWorker(self.spec("move", "plan")), None
        try:
            second = self.spec("sync")
            second["owner"] = self.other.pk
            body = cast(dict[str, object], second["body"])
            body["account"] = str(public_id(self.other.pk))
            two = HTTPWorker(second)
            one.send("go")
            one.expect("locked")
            two.send("go")
            result = None
            foreign_wait = False
            try:
                deadline = time.monotonic() + 7
                while time.monotonic() < deadline:
                    try:
                        result = two.events.get(timeout=0.05)
                        break
                    except Empty:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                                [int(str(two.ready["pid"]))],
                            )
                            state = cursor.fetchone()
                        if state and state[0] == "Lock":
                            foreign_wait = True
                            break
            finally:
                one.send("release")
            first = one.expect("result")
            result = result or two.expect("result")
            self.assertFalse(
                foreign_wait, "An unauthorized execution must not acquire the victim's account lock"
            )
            self.assertEqual((first["status"], result["status"]), (302, 400))
            print(
                "R622_FOREIGN "
                + json.dumps(
                    {
                        "foreign_account_wait": foreign_wait,
                        "victim_process": one.ready,
                        "actor_process": two.ready,
                        "outcomes": [first, result],
                    },
                    default=str,
                ),
                flush=True,
            )
            self.assertFalse(SyncReceipt.objects.exists())
            self.executed.refresh_from_db()
            self.assertEqual(self.executed.revision, 1)
        finally:
            one.close()
            if two:
                two.close()

    def test_cancel_then_sync_other_execution_keeps_cancellation(self) -> None:
        a, b = self.run_pair(self.spec("cancel", "plan"), self.spec("sync"))
        self.assertEqual((a["status"], b["status"]), (302, 200))
        self.assertEqual(PlannedSession.objects.get(origin=self.future).status, "cancelled")

    def test_sync_then_cancel_keeps_both_writes(self) -> None:
        a, b = self.run_pair(self.spec("sync", "sync"), self.spec("cancel"))
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.assertEqual(PlannedSession.objects.get(origin=self.future).status, "cancelled")

    def test_revise_then_sync_other_execution_keeps_both_writes(self) -> None:
        a, b = self.run_pair(self.spec("revise", "plan"), self.spec("sync"))
        self.assertEqual((a["status"], b["status"]), (302, 200))

    def test_sync_then_revise_other_execution_keeps_both_writes(self) -> None:
        a, b = self.run_pair(self.spec("sync", "sync"), self.spec("revise"))
        self.assertEqual((a["status"], b["status"]), (200, 302))

    def test_restore_then_sync_other_execution_keeps_history(self) -> None:
        head = self.service.revise(
            RevisePlan(self.owner, self.header.id, "Base de restore concurrente")
        )
        first, second = self.spec("restore", "plan"), self.spec("sync")
        first["head"] = head.id
        a, b = self.run_pair(first, second)
        self.assertEqual((a["status"], b["status"]), (302, 200))
        self.executed.refresh_from_db()
        self.assertEqual(
            self.executed.planned_id,
            PlannedSession.objects.get(plan_id=self.header.id, title="executed").pk,
        )

    def test_sync_then_restore_keeps_both_writes_and_historical_fk(self) -> None:
        head = self.service.revise(
            RevisePlan(self.owner, self.header.id, "Base de restore inverso")
        )
        second = self.spec("restore")
        second["head"] = head.id
        a, b = self.run_pair(self.spec("sync", "sync"), second)
        self.assertEqual((a["status"], b["status"]), (200, 302))
        self.executed.refresh_from_db()
        self.assertEqual(
            self.executed.planned_id,
            PlannedSession.objects.get(plan_id=self.header.id, title="executed").pk,
        )

    def test_replayed_sync_waits_for_account_and_does_not_add_receipt_or_revision(self) -> None:
        spec = self.spec("sync")
        initial = self.client.post(
            "/api/sync/", json.dumps(spec["body"]), content_type="application/json"
        )
        self.assertEqual(initial.status_code, 200)
        a, b = self.run_pair(self.spec("move", "plan"), spec)
        self.assertEqual((a["status"], b["status"]), (302, 200))
        self.assertEqual(b["body"], initial.json())
        self.assertEqual(SyncReceipt.objects.count(), 1)
        self.executed.refresh_from_db()
        self.assertEqual(self.executed.revision, 2)

    def test_metrics_anticipated_revision_rechecks_targets_inside_lock(self) -> None:
        block = self.future.blocks.get()
        block.target = {}
        block.save()
        first, second = self.spec("metrics", "metrics"), self.spec("metrics")
        first.update(block=block.pk, duration="1800", revision=1)
        second.update(block=block.pk, duration="999", revision=2)
        a, b = self.run_pair(first, second)
        self.assertEqual((a["status"], b["status"]), (302, 400))
        self.assertEqual(b["contexts"], [[], [["duration_seconds", "1800"]]])
        self.future.refresh_from_db()
        block.refresh_from_db()
        self.assertEqual((block.target, self.future.revision), ({"duration_seconds": "1800"}, 2))
        self.assertEqual(TrainingPlan.objects.count(), 1)
        print(
            "R622_ROOT_STATE "
            + json.dumps(
                {
                    "http": [a["status"], b["status"]],
                    "target": block.target,
                    "revision": self.future.revision,
                    "version_count": TrainingPlan.objects.count(),
                }
            ),
            flush=True,
        )
        current = self.service.revise(
            RevisePlan(self.owner, self.header.id, "Cambiar objetivos con motivo")
        )
        copy = PlannedSession.objects.get(plan_id=current.id, origin=self.future)
        response = self.client.post(
            f"/blocks/{copy.blocks.get().pk}/metrics/",
            {"revision": copy.revision, "duration_seconds": "999"},
        )
        self.assertEqual(response.status_code, 302)
        block.refresh_from_db()
        self.assertEqual(block.target, {"duration_seconds": "1800"})
