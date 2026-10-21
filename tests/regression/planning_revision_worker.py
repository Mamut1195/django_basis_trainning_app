"""Isolated-process HTTP worker for the 622 lock/read revision regressions.

stdin/stdout coordinate the controller, not product threads or lock ownership.
The worker pauses only after a real repository call; the controller observes PG
blocking then releases it BEFORE waiting for either transaction to finish.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import patch


def emit(data: dict[str, object]) -> None:
    print(json.dumps(data, default=str), flush=True)


def main() -> None:
    spec = cast(dict[str, object], json.loads(sys.stdin.readline()))
    from django.conf import settings

    database = cast(dict[str, object], spec["database"])
    # Bind the worker to the parent's TEST database, never to DATABASE_URL's
    # non-test name. Explicit fields also work when the runner did not set PG*.
    settings.DATABASES["default"]["ENGINE"] = str(database["ENGINE"])
    settings.DATABASES["default"]["NAME"] = str(database["NAME"])
    settings.DATABASES["default"]["HOST"] = str(database["HOST"])
    settings.DATABASES["default"]["PORT"] = str(database["PORT"])
    settings.DATABASES["default"]["USER"] = str(database["USER"])
    settings.DATABASES["default"]["PASSWORD"] = str(database["PASSWORD"])
    settings.DATABASES["target"] = settings.DATABASES["default"].copy()
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection, connections
    from django.test import Client

    from basis.modules.training.adapters.django import DjangoSessionRepository
    from basis.modules.training.adapters.manual_repository import DjangoManualRepository
    from basis.modules.training.adapters.planning import DjangoPlanRepository
    from basis.modules.training.application.manual import BlockContext
    from basis.modules.training.domain.execution import Prescription, SessionState
    from basis.modules.training.domain.manual import ParentRef
    from basis.modules.training.domain.planning import PlanSnapshot
    from basis.shared.identifiers import (
        AccountId,
        BlockId,
        PlanId,
        PlannedSessionId,
        Revision,
        SessionId,
    )

    owner = int(str(spec["owner"]))
    user = get_user_model().objects.get(pk=owner)
    client = Client(raise_request_exception=False)
    # Login writes last_login/auth FKs. Finish it before either business request
    # starts so a wait cannot be mistaken for a login-vs-writer lock.
    client.force_login(user)
    worker_connection = (
        connections["target"] if str(spec["action"]).startswith("alias_") else connection
    )
    with worker_connection.cursor() as cursor:
        cursor.execute("SET lock_timeout = '12s'")
        cursor.execute("SET statement_timeout = '20s'")
        cursor.execute("SELECT pg_backend_pid()")
        pid = cursor.fetchone()[0]
    emit({"phase": "ready", "pid": pid, "process": os.getpid()})
    if sys.stdin.readline().strip() != "go":
        raise AssertionError("Controller did not start the request")

    paused = False
    contexts: list[object] = []

    def pause(hook: str) -> None:
        nonlocal paused
        if spec.get("pause") == hook and not paused:
            paused = True
            emit({"phase": "locked", "hook": hook, "pid": pid})
            if sys.stdin.readline().strip() != "release":
                raise AssertionError("Controller did not release the request")

    original_prescription = DjangoSessionRepository.prescription
    original_snapshot = DjangoPlanRepository.snapshot
    original_get = DjangoSessionRepository.get
    original_advance = DjangoManualRepository.advance
    original_block = DjangoManualRepository.block

    def prescribed(
        repo: DjangoSessionRepository, account: AccountId, planned: PlannedSessionId
    ) -> Prescription:
        result = original_prescription(repo, account, planned)
        pause("start")
        return result

    def snapshot(
        repo: DjangoPlanRepository, account: AccountId, plan: PlanId, *, lock: bool
    ) -> PlanSnapshot:
        result = original_snapshot(repo, account, plan, lock=lock)
        if lock:
            pause("plan")
        return result

    def get(
        repo: DjangoSessionRepository,
        session: SessionId,
        *,
        lock: bool,
        owner: AccountId | None = None,
    ) -> SessionState | None:
        result = original_get(repo, session, lock=lock, owner=owner)
        if lock:
            pause("sync")
        return result

    def advance(repo: DjangoManualRepository, ref: ParentRef, revision: Revision) -> None:
        original_advance(repo, ref, revision)
        pause("metrics")

    def block(repo: DjangoManualRepository, id: BlockId) -> BlockContext | None:
        result = original_block(repo, id)
        if result is not None:
            contexts.append([(metric.name.value, str(metric.value)) for metric in result.target])
        return result

    try:
        if str(spec["action"]).startswith("alias_"):
            from basis.modules.accounts.adapters.coach import DjangoAccountLocks
            from basis.modules.training.adapters.locking import TrainingUnitOfWork, lock_plan

            with TrainingUnitOfWork(using="target") as work:
                if spec["action"] in {"alias_account", "alias_rollback"}:
                    DjangoAccountLocks(using="target").lock(AccountId(owner))
                else:
                    lock_plan(int(str(spec["head"])), alias="target")
                pause("alias")
                atomic = {
                    "default": connections["default"].in_atomic_block,
                    "target": connections["target"].in_atomic_block,
                }
                if spec["action"] == "alias_rollback":
                    from basis.modules.training.adapters.models import Goal

                    Goal.objects.using("target").create(
                        owner_id=owner, title="Rollback target alias 622", sport="running"
                    )
                else:
                    work.commit()
            emit(
                {
                    "phase": "result",
                    "action": spec["action"],
                    "status": 200,
                    "pid": pid,
                    "process": os.getpid(),
                    "error": None,
                    "sqlstate": None,
                    "body": atomic,
                    "contexts": [],
                }
            )
            return
        instant = (
            datetime.fromisoformat(str(spec["instant"]))
            if spec.get("instant")
            else datetime(2026, 10, 19, 17, tzinfo=timezone.utc)
        )
        with (
            patch("django.utils.timezone.now", return_value=instant),
            patch.object(DjangoSessionRepository, "prescription", prescribed),
            patch.object(DjangoPlanRepository, "snapshot", snapshot),
            patch.object(DjangoSessionRepository, "get", get),
            patch.object(DjangoManualRepository, "advance", advance),
            patch.object(DjangoManualRepository, "block", block),
        ):
            action = str(spec["action"])
            planned = int(str(spec["planned"]))
            head = int(str(spec["head"]))
            reason = "622 revision regression " + action
            if action == "sync":
                response = client.post(
                    "/api/sync/", json.dumps(spec["body"]), content_type="application/json"
                )
            elif action == "start":
                response = client.post(f"/scheduled/{planned}/start/")
            elif action == "move":
                response = client.post(
                    f"/scheduled/{planned}/reschedule/",
                    {
                        "revision": spec["revision"],
                        "reason": reason,
                        "date": (instant.date() + timedelta(days=3)).isoformat(),
                    },
                )
            elif action == "revise":
                response = client.post(f"/plans/{head}/revise/", {"reason": reason})
            elif action == "restore":
                response = client.post(
                    f"/plans/{head}/restore/{spec['target']}/", {"reason": reason}
                )
            elif action == "cancel":
                response = client.post(
                    f"/scheduled/{planned}/change/",
                    {"action": "cancelled", "reason": reason, "revision": spec["revision"]},
                )
            elif action == "metrics":
                response = client.post(
                    f"/blocks/{spec['block']}/metrics/",
                    {"revision": spec["revision"], "duration_seconds": spec["duration"]},
                )
            elif action == "set":
                response = client.post(
                    f"/sets/{spec['row']}/edit/", cast(dict[str, object], spec["body"])
                )
            else:
                raise AssertionError("Unknown worker action")
            info = getattr(response, "exc_info", None)
            error = info[1] if response.status_code == 500 and info else None
            sqlstate = getattr(getattr(error, "__cause__", None), "sqlstate", None)
            body: object = (
                response.json()
                if response.headers.get("Content-Type", "").startswith("application/json")
                else None
            )
            emit(
                {
                    "phase": "result",
                    "action": action,
                    "status": response.status_code,
                    "pid": pid,
                    "process": os.getpid(),
                    "error": type(error).__name__ if error else None,
                    "sqlstate": sqlstate,
                    "body": body,
                    "contexts": contexts,
                }
            )
    finally:
        connections.close_all()


if __name__ == "__main__":
    main()
