"""Backend omission/reclassification races in independent PG processes."""

import json
import time
from copy import deepcopy
from unittest import skipUnless
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from basis.modules.sync.adapters.models import SyncReceipt

from .contracts import SessionDocument, session_snapshot
from .test_adaptation_updates import ADAPTATION_KEYS, BackendAdaptationFixture
from .test_planning_revision import HTTPWorker


@skipUnless(connection.vendor == "postgresql", "Requires PG process lock observations")
class BackendAdaptationProcessTests(BackendAdaptationFixture, TransactionTestCase):
    def setUp(self) -> None:
        self.make_adapted()

    def legacy(self) -> SessionDocument:
        payload = session_snapshot(self.item)
        payload["notes"] = "Legacy metadata at revision2"
        for block in payload["blocks"]:
            for row in block["sets"]:
                for key in ADAPTATION_KEYS:
                    row.pop(key, None)
        return payload

    def fresh(self) -> SessionDocument:
        payload = session_snapshot(self.item)
        payload["blocks"][0]["sets"][0].update(
            actual_exercise=self.exercise.pk,
            actual_load_type="external",
            actual_kind="work",
            adaptation_reason="Observed unassisted working set now",
        )
        return payload

    def spec(self, payload: SessionDocument, pause: str = "") -> dict[str, object]:
        db = dict(connection.settings_dict)
        db["TEST"] = {}
        return {
            "database": db,
            "owner": self.owner.pk,
            "action": "sync",
            "pause": pause,
            "planned": self.plan.sessions.get().pk,
            "head": self.plan.pk,
            "target": self.plan.pk,
            "instant": timezone.now().isoformat(),
            "body": {
                "account": str(self.owner.athlete.public_id),
                "mutation_id": str(uuid4()),
                "session": payload,
            },
        }

    def pair(self, first: dict[str, object], second: dict[str, object]) -> tuple[int, int]:
        workers: list[HTTPWorker] = []
        try:
            one = HTTPWorker(first)
            workers.append(one)
            two = HTTPWorker(second)
            workers.append(two)
            self.assertNotEqual(one.ready["pid"], two.ready["pid"])
            self.assertNotEqual(one.ready["process"], two.ready["process"])
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
                    wait and wait[0] == "Lock", "Observe native account/aggregate lock wait"
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
                "BACKEND623_ADAPTATION_PROCESS "
                + json.dumps(
                    {"processes": [w.ready for w in workers], "wait": wait, "results": results},
                    default=str,
                ),
                flush=True,
            )
            return int(str(results[0]["status"])), int(str(results[1]["status"]))
        finally:
            for worker in workers:
                worker.close()

    def test_legacy_notes_then_reclassification_rejects_stale_change(self) -> None:
        self.assertEqual(
            self.pair(self.spec(self.legacy(), "sync"), self.spec(self.fresh())), (200, 409)
        )
        self.row.refresh_from_db()
        self.assertEqual((self.row.actual_load_type, self.row.actual_kind), ("assisted", "failed"))
        self.assertIsNone(self.row.external_volume_kg)
        self.assertIsNone(self.row.estimated_1rm)
        self.assertEqual(SyncReceipt.objects.count(), 2)

    def test_reclassification_then_legacy_current_snapshot_is_stale_not_a_clear(self) -> None:
        self.assertEqual(
            self.pair(self.spec(self.fresh(), "sync"), self.spec(self.legacy())), (200, 409)
        )
        self.row.refresh_from_db()
        self.assertEqual((self.row.actual_load_type, self.row.actual_kind), ("external", "work"))
        self.assertEqual(str(self.row.external_volume_kg), "300.00")
        self.assertEqual(str(self.row.estimated_1rm), "85.00")

    def test_rejected_clear_rolls_back_before_waiting_legacy_notes(self) -> None:
        bad = self.fresh()
        bad["blocks"][0]["sets"][0]["actual_load_type"] = None
        self.assertEqual(self.pair(self.spec(bad, "sync"), self.spec(self.legacy())), (400, 200))
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_load_type, "assisted")
        self.assertEqual(self.row.adaptation_reason, "Observed assistance")
        self.assertEqual(SyncReceipt.objects.count(), 2)

    def test_replay_with_omitted_fields_keeps_one_new_receipt(self) -> None:
        first, second = self.spec(self.legacy(), "sync"), self.spec(self.legacy())
        second["body"] = deepcopy(first["body"])
        self.assertEqual(self.pair(first, second), (200, 200))
        self.assertEqual(SyncReceipt.objects.count(), 2)
        self.item.refresh_from_db()
        self.assertEqual(self.item.revision, 3)
        self.row.refresh_from_db()
        self.assertIsNone(self.row.external_volume_kg)

    def test_manual_numeric_omission_then_sync_reclassification_conflicts(self) -> None:
        first = self.spec(self.legacy(), "metrics")
        first.update(
            action="set",
            row=self.row.pk,
            body={"revision": 2, "actual_reps": 0, "actual_kg": "75", "actual_rpe": "10"},
        )
        self.assertEqual(self.pair(first, self.spec(self.fresh())), (302, 409))
        self.row.refresh_from_db()
        self.assertEqual(self.row.actual_reps, 0)
        self.assertEqual(self.row.actual_kind, "failed")
        self.assertEqual(self.row.actual_load_type, "assisted")
        self.assertEqual(SyncReceipt.objects.count(), 1)
