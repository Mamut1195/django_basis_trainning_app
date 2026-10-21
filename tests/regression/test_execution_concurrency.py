"""Two independent processes, real PG waits and actual manual/sync HTTP routes."""

import json
import time
from dataclasses import replace
from typing import cast
from unittest import skipUnless
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.actions import start_session
from basis.modules.training.adapters.django import block_state
from basis.modules.training.adapters.models import Session
from basis.modules.training.adapters.wire import encode_block

from .contracts import required, session_snapshot
from .test_execution_records import ExecutionFixture
from .test_planning_revision import HTTPWorker


@skipUnless(connection.vendor == "postgresql", "Requires real PG process locks")
class ExecutionProcessTests(ExecutionFixture, TransactionTestCase):
    def setUp(self) -> None:
        self.make_prescription()

    def spec(self, action: str, payload: object, pause: str = "") -> dict[str, object]:
        database = dict(connection.settings_dict)
        database["TEST"] = {}
        return {
            "instant": timezone.now().isoformat(),
            "database": database,
            "owner": self.owner.pk,
            "action": action,
            "pause": pause,
            "planned": self.planned.pk,
            "head": self.plan.pk,
            "target": self.plan.pk,
            "body": {
                "account": str(self.owner.athlete.public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
        }

    def run_pair(self, first: dict[str, object], second: dict[str, object]) -> tuple[int, int]:
        workers: list[HTTPWorker] = []
        try:
            one, two = HTTPWorker(first), HTTPWorker(second)
            workers.extend((one, two))
            self.assertNotEqual(one.ready["process"], two.ready["process"])
            self.assertNotEqual(one.ready["pid"], two.ready["pid"])
            one.send("go")
            one.expect("locked")
            two.send("go")
            wait = None
            try:
                deadline = time.monotonic() + 7
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT wait_event_type, pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid=%s",
                            [int(str(two.ready["pid"]))],
                        )
                        wait = cursor.fetchone()
                    if wait and wait[0] == "Lock":
                        break
                    time.sleep(0.02)
                self.assertTrue(
                    wait and wait[0] == "Lock", "Competitor must wait on a real product lock"
                )
            finally:
                one.send("release")
            results = one.expect("result"), two.expect("result")
            for worker, result in zip(workers, results, strict=True):
                self.assertEqual(worker.process.wait(timeout=10), 0)
                self.assertIsNone(result["error"])
                self.assertIsNone(result["sqlstate"])
                self.assertNotEqual(result["status"], 500)
            print(
                "MAM623_PROCESS "
                + json.dumps(
                    {"ready": [w.ready for w in workers], "wait": wait, "results": results},
                    default=str,
                ),
                flush=True,
            )
            return int(str(results[0]["status"])), int(str(results[1]["status"]))
        finally:
            for worker in workers:
                worker.close()

    def initial(self) -> dict[str, object]:
        source = block_state(self.planned.blocks.get())
        source = replace(source, id=None, sets=tuple(replace(s, id=None) for s in source.sets))
        return {
            "id": str(uuid4()),
            "revision": 0,
            "planned": self.planned.pk,
            "blocks": [encode_block(source)],
        }

    def test_start_then_canonical_sync_has_one_execution_no_phantom_receipt(self) -> None:
        self.assertEqual(
            self.run_pair(self.spec("start", {}, "start"), self.spec("sync", self.initial())),
            (302, 400),
        )
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_canonical_sync_then_start_reuses_same_execution(self) -> None:
        self.assertEqual(
            self.run_pair(self.spec("sync", self.initial(), "sync"), self.spec("start", {})),
            (200, 302),
        )
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(SyncReceipt.objects.count(), 1)

    def test_edit_then_close_stale_revision_preserves_actual_and_ids(self) -> None:
        item = start_session(self.owner, self.planned)
        row = required(item.blocks.get().sets.first())
        finish = session_snapshot(item)
        finish["status"] = "completed"
        manual = self.spec("set", {}, "metrics")
        manual.update(row=row.pk, body={"revision": 1, "actual_reps": 4, "actual_kg": "75"})
        self.assertEqual(self.run_pair(manual, self.spec("sync", finish)), (302, 409))
        row.refresh_from_db()
        self.assertEqual(row.actual_reps, 4)
        self.assertEqual(required(item.blocks.get().sets.first()).pk, row.pk)
        self.assertEqual(SyncReceipt.objects.count(), 0)

    def test_close_then_edit_cannot_reopen_or_invent_pending_results(self) -> None:
        item = start_session(self.owner, self.planned)
        row = required(item.blocks.get().sets.first())
        finish = session_snapshot(item)
        finish["status"] = "completed"
        manual = self.spec("set", {})
        manual.update(row=row.pk, body={"revision": 1, "actual_reps": 4, "actual_kg": "75"})
        self.assertEqual(self.run_pair(self.spec("sync", finish, "sync"), manual), (200, 409))
        row.refresh_from_db()
        self.assertIsNone(row.actual_reps)
        item.refresh_from_db()
        self.assertEqual(item.status, "completed")

    def test_same_key_two_processes_replays_one_receipt(self) -> None:
        item = start_session(self.owner, self.planned)
        payload = session_snapshot(item)
        first, second = self.spec("sync", payload, "sync"), self.spec("sync", payload)
        second["body"] = dict(cast(dict[str, object], first["body"]))
        self.assertEqual(self.run_pair(first, second), (200, 200))
        self.assertEqual(SyncReceipt.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.revision, 2)

    def test_two_keys_same_revision_conflict_without_overwrite(self) -> None:
        item = start_session(self.owner, self.planned)
        payload = session_snapshot(item)
        self.assertEqual(
            self.run_pair(self.spec("sync", payload, "sync"), self.spec("sync", payload)),
            (200, 409),
        )
        self.assertEqual(SyncReceipt.objects.count(), 1)
