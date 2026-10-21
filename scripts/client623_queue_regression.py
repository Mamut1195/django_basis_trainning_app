"""Isolated real-browser regression for CLIENT623-R1; no production configuration."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast
from urllib.request import urlopen
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page, Request, Route, StorageState

    from basis.modules.training.adapters.models import Session


class SourceBinding(TypedDict):
    files: dict[str, str]
    aggregate: str


class StrengthSnapshot(TypedDict, total=False):
    id: int
    source: int | None
    actual_reps: int | None
    actual_kg: str | None
    target_reps: int | None
    target_kg: str | None
    actual_load_type: str | None
    adaptation_reason: str


class BlockSnapshot(TypedDict, total=False):
    id: int
    source: int | None
    sets: list[StrengthSnapshot]


class SessionSnapshot(TypedDict):
    id: str
    title: str
    revision: int
    planned: int | None
    status: str
    blocks: list[BlockSnapshot]
    duration_seconds: int | None
    reported_rpe: str | None


class Mutation(TypedDict):
    account: str
    mutation_id: str
    created: int
    session: SessionSnapshot
    delivery: NotRequired[str]


class LocalRecord(TypedDict, total=False):
    session: SessionSnapshot
    operations: list[Mutation]


class RequestRecord(TypedDict):
    context: str
    payload: Mutation


class LostResponse(TypedDict):
    request: Mutation
    receipt: dict[str, object]


type CheckDetails = dict[str, bool | str | int]


class CheckResult(TypedDict, total=False):
    name: str
    status: str
    details: CheckDetails
    traceback: str


class RunResult(TypedDict, total=False):
    output: str
    python: str
    interpreter: str
    checks: list[CheckResult]
    pageerrors: list[str]
    external_blocked: list[str]
    post_requests: list[RequestRecord]
    origin: str
    browser: str
    browser_stopped: bool
    receipt_count: int
    fatal: str
    authored_before: str
    authored_after: str
    source_changes_during_run: list[str]
    client_js_unchanged: bool
    script_unchanged: bool
    handoff_unchanged: bool
    server_stopped: bool
    status: str


def number(value: object) -> float:
    assert isinstance(value, (str, int, float)), "Expected a recorded numeric value"
    return float(value)


def mutation_from(value: object) -> Mutation:
    assert isinstance(value, dict), "Expected a queued mutation object"
    return cast(Mutation, value)


ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(r"C:\Users\Jonnathan\Mamut system\django-basis-trainning-app")
CHROME = Path(
    r"C:\Users\Jonnathan\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe"
)
JS = "basis/adapters/web/static/basis/js/offline.js"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding() -> SourceBinding:
    names = (
        subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    files = {p: digest(ROOT / p) for p in sorted(set(filter(None, names))) if (ROOT / p).is_file()}
    return {
        "files": files,
        "aggregate": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def main() -> int:
    parent = ROOT / ".cache"
    assert parent.is_dir() and CHROME.is_file()
    out = parent / ("client623-queue-" + uuid4().hex)
    out.mkdir()

    def save(name: str, value: object) -> None:
        (out / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    before = binding()
    save("sources-before.json", before)
    handoff = digest(MAIN / "docs/HANDOFF_PRESENTATION_2026-10-19.md")
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "PATHEXT",
            "COMSPEC",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PROGRAMDATA",
            "TEMP",
            "TMP",
        }
    }
    env.update(
        DJANGO_SETTINGS_MODULE="config.test_settings",
        DJANGO_DEBUG="1",
        DJANGO_SECRET_KEY="public-client623-queue-regression",
        DATABASE_URL="sqlite:///" + (out / "client.sqlite3").as_posix(),
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        AI_ENABLED="0",
        BASIS_DEVELOPMENT_ACCESS="0",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
        PYTHONPATH=str(ROOT),
    )
    os.environ.clear()
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    import django

    django.setup()
    from django.core.management import call_command
    from django.db import connections
    from playwright.sync_api import sync_playwright

    from basis.modules.sync.adapters.models import SyncReceipt
    from basis.modules.training.adapters.actions import start_session
    from basis.modules.training.adapters.planning_actions import build_plan
    from scripts.browser_smoke import (
        json_body,
        login,
        seed_stale_local_mutation,
        service_worker_ready,
        wait_for_outbox,
    )
    from scripts.browser_smoke import (
        outbox as read_outbox,
    )
    from tests.regression.contracts import ScheduledDocument
    from tests.regression.factories import account, exercise, proposal

    with (out / "setup.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
        call_command("migrate", interactive=False, verbosity=1)
        user = account("client623queue")
        ex = exercise()
        document = proposal(user)
        documents: list[ScheduledDocument] = []
        for n in range(25):
            scheduled = copy.deepcopy(document["sessions"][0])
            scheduled["title"] = f"Queue {n:02}"
            scheduled["blocks"] = [
                {
                    "sport": "strength",
                    "title": "Fuerza original",
                    "sets": [
                        {"exercise": ex.pk, "target_reps": 5, "target_kg": "80"},
                        {"exercise": ex.pk, "target_reps": 8, "target_kg": "60"},
                        {"exercise": ex.pk, "target_reps": 6, "target_kg": "40"},
                    ],
                }
            ]
            documents.append(scheduled)
        sessions: list[Session] = []
        for start in (0, 13):
            document["sessions"] = documents[start : start + 13]
            plan = build_plan(user, document)
            assert plan is not None
            sessions.extend(start_session(user, p) for p in plan.sessions.all())
    connections.close_all()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    result: RunResult = {
        "output": str(out),
        "python": sys.version,
        "interpreter": sys.executable,
        "checks": [],
        "pageerrors": [],
        "external_blocked": [],
        "post_requests": [],
        "origin": origin,
    }
    server_log = (out / "server.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-B", "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT,
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    browser: Browser | None = None
    contexts: list[tuple[str, BrowserContext]] = []
    auth_state: StorageState | None = None

    def check(name: str, fn: Callable[[], CheckDetails]) -> None:
        try:
            details = fn()
            result["checks"].append({"name": name, "status": "VERIFIED", "details": details})
        except Exception:
            result["checks"].append(
                {"name": name, "status": "FAILED", "traceback": traceback.format_exc()}
            )
        save("result.json", result)
        print(name + ": " + result["checks"][-1]["status"], flush=True)

    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if urlopen(origin + "/health/", timeout=1).status == 200:
                    break
            except Exception:
                time.sleep(0.1)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=str(CHROME))
            result["browser"] = browser.version

            def setup(name: str, width: int = 390) -> tuple[BrowserContext, Page]:
                nonlocal auth_state
                assert browser is not None
                ctx = browser.new_context(
                    viewport={"width": width, "height": 900}, storage_state=auth_state
                )
                ctx.set_default_timeout(10000)
                ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
                contexts.append((name, ctx))

                def guard(route: Route) -> None:
                    if route.request.url.startswith(origin + "/"):
                        route.continue_()
                    else:
                        result["external_blocked"].append(route.request.url)
                        route.abort()

                ctx.route("**/*", guard)
                ctx.on(
                    "page",
                    lambda page: page.on(
                        "pageerror", lambda e: result["pageerrors"].append(str(e))
                    ),
                )

                def record_request(request: Request) -> None:
                    if request.method == "POST" and request.url.endswith("/api/sync/"):
                        result["post_requests"].append(
                            {"context": name, "payload": mutation_from(request.post_data_json)}
                        )

                ctx.on("request", record_request)
                page = ctx.new_page()
                if auth_state is None:
                    login(page, origin, user.username, "Example-password-824!")
                    auth_state = ctx.storage_state()
                else:
                    page.goto(origin + "/")
                service_worker_ready(page)
                served = page.request.get(origin + "/static/basis/js/offline.js").body()
                assert hashlib.sha256(served).hexdigest() == before["files"][JS]
                return ctx, page

            def outbox(page: Page) -> list[Mutation]:
                return [mutation_from(value) for value in read_outbox(page)]

            def snapshot(page: Page, sid: UUID | str) -> SessionSnapshot:
                response = page.request.get(origin + f"/api/sessions/{sid}/snapshot/")
                assert response.status == 200
                value = json_body(response)["session"]
                assert isinstance(value, dict), "Expected a server session snapshot"
                return cast(SessionSnapshot, value)

            def download(page: Page, session: Session) -> None:
                page.goto(origin + f"/sessions/{session.pk}/")
                page.locator("[data-download-session]").click()
                page.wait_for_function(
                    "document.querySelector('#global-status')?.textContent.includes('Sesión guardada')"
                )
                page.goto(origin + "/offline/")

            def open_editor(page: Page, session: Session) -> None:
                page.locator(".offline-row").filter(
                    has=page.get_by_role("heading", name=session.title, exact=True)
                ).get_by_role("button", name="Abrir sesión", exact=True).click()

            def fill(page: Page, reps: str = "4", kg: str = "75") -> None:
                page.locator("#offline-blocks-0-sets-0-actual_reps").fill(reps)
                page.locator("#offline-blocks-0-sets-0-actual_kg").fill(kg)

            def adapt(page: Page, reason: str | None = None) -> None:
                page.get_by_text(
                    "Adaptación real opcional · conserva la prescripción", exact=True
                ).first.click()
                page.get_by_label("Carga realizada", exact=True).first.select_option("assisted")
                if reason is not None:
                    page.get_by_label("Motivo de adaptación", exact=True).first.fill(reason)

            def store(page: Page, name: str) -> list[LocalRecord]:
                value: object = page.evaluate(
                    """async name=>{const d=await new Promise(r=>{const q=indexedDB.open('basis-offline-v1',1);q.onsuccess=()=>r(q.result)});return await new Promise(r=>{const q=d.transaction(name).objectStore(name).getAll();q.onsuccess=()=>r(q.result)})}""",
                    name,
                )
                assert isinstance(value, list), "Expected IndexedDB rows"
                return cast(list[LocalRecord], value)

            def finish(name: str, ctx: BrowserContext) -> None:
                ctx.tracing.stop(path=str(out / (name + ".zip")))
                ctx.close()
                contexts.remove((name, ctx))

            def correction(width: int, index: int) -> CheckDetails:
                name = f"recovery-{width}"
                ctx, page = setup(name, width)
                item, unrelated = sessions[index : index + 2]
                baseline = snapshot(page, item.pk)
                download(page, item)
                download(page, unrelated)
                ctx.set_offline(True)
                open_editor(page, item)
                fill(page)
                page.locator("#offline-blocks-0-sets-1-actual_reps").fill("0")
                page.locator("#offline-blocks-0-sets-1-actual_kg").fill("0")
                adapt(page)
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 1)
                original = outbox(page)[0]
                open_editor(page, unrelated)
                fill(page, "3", "72.5")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 2)
                other = next(r for r in outbox(page) if r["session"]["id"] == str(unrelated.pk))
                page.reload()
                assert page.evaluate(
                    "!navigator.onLine && navigator.serviceWorker.controller !== null"
                )
                open_editor(page, item)
                adapt(page, "Equipo tras recarga " + str(width))
                page.get_by_role("button", name="Completar sesión", exact=True).click()
                wait_for_outbox(page, 2)
                corrected = next(r for r in outbox(page) if r["session"]["id"] == str(item.pk))
                assert corrected["mutation_id"] != original["mutation_id"]
                assert corrected["session"]["revision"] == baseline["revision"]
                assert (
                    next(r for r in outbox(page) if r["session"]["id"] == str(unrelated.pk))
                    == other
                )
                assert page.evaluate("window.basisPending()") == 2
                assert (
                    store(page, "archive")[0]["operations"][0]["mutation_id"]
                    == original["mutation_id"]
                )
                page.screenshot(path=str(out / (name + "-offline.png")), full_page=True)
                ctx.set_offline(False)
                wait_for_outbox(page, 0)
                page.locator("[data-sync-now]").click()
                page.locator("[data-sync-now]").click()
                closed = snapshot(page, item.pk)
                assert (
                    closed["revision"] == baseline["revision"] + 1
                    and closed["status"] == "completed"
                )
                row, zero, unknown = closed["blocks"][0]["sets"]
                assert row["actual_reps"] == 4 and number(row["actual_kg"]) == 75
                assert zero["actual_reps"] == 0 and number(zero["actual_kg"]) == 0
                assert unknown["actual_reps"] is None and unknown["actual_kg"] is None
                assert row["target_reps"] == 5 and number(row["target_kg"]) == 80
                assert row["id"] == baseline["blocks"][0]["sets"][0]["id"]
                assert snapshot(page, unrelated.pk)["revision"] == 2
                page.goto(origin + f"/sessions/{item.pk}/")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
                page.screenshot(path=str(out / (name + "-accepted.png")), full_page=True)
                save(
                    name + ".json",
                    {
                        "original": original,
                        "corrected": corrected,
                        "unrelated": other,
                        "closed": closed,
                    },
                )
                finish(name, ctx)
                return {
                    "UI_only": True,
                    "same_uuid": True,
                    "canonical_revision": True,
                    "null_zero_and_unrelated_preserved": True,
                }

            check(
                "UI_missing_reason_offline_reload_correct_reconnect_390", lambda: correction(390, 0)
            )
            check(
                "UI_missing_reason_offline_reload_correct_reconnect_1440",
                lambda: correction(1440, 2),
            )

            def rejected(legacy: bool = False) -> CheckDetails:
                name = "legacy-400" if legacy else "real-400"
                ctx, page = setup(name)
                item = sessions[5 if legacy else 4]
                baseline = snapshot(page, item.pk)
                download(page, item)
                if legacy:
                    body = copy.deepcopy(baseline)
                    row = body["blocks"][0]["sets"][0]
                    row["actual_load_type"] = "assisted"
                    row["actual_reps"] = 4
                    row["actual_kg"] = "75"
                    account_id = page.locator("body").get_attribute("data-account")
                    seed_stale_local_mutation(
                        page,
                        {
                            "mutation_id": str(uuid4()),
                            "account": account_id,
                            "created": int(time.time() * 1000),
                            "session": body,
                        },
                    )
                    page.locator("[data-sync-now]").click()
                else:
                    open_editor(page, item)
                    fill(page)
                    adapt(page)
                    page.get_by_role("button", name="Completar sesión", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#offline-status').textContent.includes('Una adaptación requiere un motivo')"
                )
                pending = outbox(page)[0]
                assert pending["delivery"] == "rejected_validation"
                assert snapshot(page, item.pk) == baseline
                page.screenshot(path=str(out / (name + "-rejected.png")), full_page=True)
                ctx.set_offline(True)
                page.reload()
                open_editor(page, item)
                assert page.locator("#offline-blocks-0-sets-0-actual_kg").is_enabled()
                assert page.locator("#offline-blocks-0-sets-0-actual_kg").input_value() == "75"
                adapt(page, "Motivo corregido en UI")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 1)
                corrected = outbox(page)[0]
                assert (
                    corrected["mutation_id"] != pending["mutation_id"]
                    and corrected["session"]["revision"] == 1
                )
                ctx.set_offline(False)
                wait_for_outbox(page, 0)
                saved = snapshot(page, item.pk)
                assert saved["revision"] == 2
                assert (
                    saved["blocks"][0]["sets"][0]["adaptation_reason"] == "Motivo corregido en UI"
                )
                save(
                    name + ".json",
                    {
                        "rejected": pending,
                        "corrected": corrected,
                        "accepted": saved,
                        "archive": store(page, "archive"),
                    },
                )
                finish(name, ctx)
                return {
                    "HTTP400_definitive": True,
                    "legacy_ambiguous_first_replayed": legacy,
                    "closed_local_draft_editable": not legacy,
                }

            check("real_400_closed_local_draft_recoverable", rejected)
            check("legacy_unknown_delivery_real_400_UI_recovery", lambda: rejected(True))

            def midflight(invalid: bool = False) -> CheckDetails:
                name = "midflight-400" if invalid else "midflight-success"
                ctx, page = setup(name)
                item = sessions[7 if invalid else 6]
                download(page, item)
                held: list[Route] = []
                page.route("**/api/sync/", lambda route: held.append(route), times=1)
                open_editor(page, item)
                fill(page, "4", "70")
                if invalid:
                    adapt(page)
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                page.wait_for_timeout(200)
                assert len(held) == 1 and outbox(page)[0]["delivery"] == "attempted"
                original = copy.deepcopy(outbox(page)[0])
                open_editor(page, item)
                fill(page, "4", "75")
                if invalid:
                    adapt(page, "Corrección durante envío")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 2)
                assert (
                    next(r for r in outbox(page) if r["mutation_id"] == original["mutation_id"])
                    == original
                )
                held[0].continue_()
                wait_for_outbox(page, 0)
                saved = snapshot(page, item.pk)
                assert saved["revision"] == (2 if invalid else 3)
                assert number(saved["blocks"][0]["sets"][0]["actual_kg"]) == 75
                save(
                    name + ".json",
                    {
                        "original_attempt": original,
                        "server": saved,
                        "archive": store(page, "archive"),
                    },
                )
                finish(name, ctx)
                return {
                    "inflight_not_discarded": True,
                    "correction_sent_after_definitive_outcome": True,
                }

            check("midflight_valid_edit_keeps_first_request_then_successor", midflight)
            check("midflight_invalid_edit_waits_for_real400_then_repairs", lambda: midflight(True))

            def timeout_and_dom() -> CheckDetails:
                name = "timeout-applied"
                ctx, page = setup(name)
                item = sessions[8]
                download(page, item)
                captured: list[LostResponse] = []

                def applied_then_lost(route: Route) -> None:
                    response = route.fetch()
                    assert response.status == 200
                    captured.append(
                        {
                            "request": mutation_from(route.request.post_data_json),
                            "receipt": json_body(response),
                        }
                    )
                    route.abort("timedout")

                page.route("**/api/sync/", applied_then_lost, times=1)
                open_editor(page, item)
                fill(page, "4", "70")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#offline-status').textContent.includes('Sin conexión')"
                )
                assert len(outbox(page)) == 1 and outbox(page)[0]["delivery"] == "attempted"
                assert snapshot(page, item.pk)["revision"] == 2
                original = outbox(page)[0]
                # Replay its immutable key while the editor remains open and dirty.
                open_editor(page, item)
                fill(page, "4", "75")
                held: list[Route] = []
                page.route("**/api/sync/", lambda r: held.append(r), times=1)
                page.locator("[data-sync-now]").click()
                page.wait_for_timeout(200)
                assert len(held) == 1
                held[0].continue_()
                wait_for_outbox(page, 0)
                assert page.locator("#offline-blocks-0-sets-0-actual_kg").input_value() == "75"
                assert snapshot(page, item.pk)["revision"] == 2
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 0)
                saved = snapshot(page, item.pk)
                assert (
                    saved["revision"] == 3
                    and number(saved["blocks"][0]["sets"][0]["actual_kg"]) == 75
                )
                requests = [r["payload"] for r in result["post_requests"] if r["context"] == name]
                assert (
                    requests[0]["mutation_id"]
                    == requests[1]["mutation_id"]
                    == original["mutation_id"]
                )
                assert requests[0]["session"] == requests[1]["session"]
                save(
                    name + ".json",
                    {
                        "lost_response": captured,
                        "original": original,
                        "requests": requests,
                        "server": saved,
                    },
                )
                finish(name, ctx)
                return {
                    "applied_response_lost": True,
                    "same_key_receipt_replay": True,
                    "dirty_DOM_survives_ack": True,
                    "own_ack_revision_used": True,
                }

            check("applied_timeout_same_key_retry_dirty_editor_survives", timeout_and_dom)

            def failure_state(code: int, index: int) -> CheckDetails:
                name = f"transient-{code}"
                ctx, page = setup(name)
                item = sessions[index]
                download(page, item)
                page.route(
                    "**/api/sync/",
                    lambda r: r.fulfill(
                        status=code,
                        content_type="text/html" if code == 400 else "application/json",
                        body="Rejected transport"
                        if code == 400
                        else '{"detail":"Owned injected failure"}',
                    ),
                )
                open_editor(page, item)
                fill(page, "4", "70")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                page.wait_for_function(
                    "/No se pudo sincronizar|No hay acceso activo/.test(document.querySelector('#offline-status').textContent)"
                )
                first = copy.deepcopy(outbox(page)[0])
                assert first["delivery"] == "attempted"
                open_editor(page, item)
                fill(page, "4", "75")
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 2)
                assert (
                    next(r for r in outbox(page) if r["mutation_id"] == first["mutation_id"])
                    == first
                )
                assert snapshot(page, item.pk)["revision"] == 1
                assert "Todos los registros" not in page.locator("#offline-status").inner_text()
                pending = outbox(page)
                page.unroute("**/api/sync/")
                page.locator("[data-sync-now]").click()
                wait_for_outbox(page, 0)
                assert snapshot(page, item.pk)["revision"] == 3
                save(
                    name + ".json",
                    {
                        "injected_failure_status": code,
                        "pending_unchanged_prefix": pending,
                        "server_after_real_retry": snapshot(page, item.pk),
                    },
                )
                finish(name, ctx)
                return {
                    "failure_injection": code,
                    "no_reset_or_discard": True,
                    "real_retry_revision": 3,
                }

            for offset, code in enumerate((401, 403, 429, 500, 400)):

                def run_failure(c: int = code, n: int = 9 + offset) -> CheckDetails:
                    return failure_state(c, n)

                check(
                    f"HTTP{code}_preserves_ambiguous_prefix",
                    run_failure,
                )

            def consumers() -> CheckDetails:
                name = "two-consumers"
                ctx, page = setup(name)
                item = sessions[14]
                download(page, item)
                ctx.set_offline(True)
                open_editor(page, item)
                fill(page)
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(page, 1)
                worker = ctx.new_page()
                worker.goto(origin + "/offline/")
                ctx.set_offline(False)
                page.locator("[data-sync-now]").click()
                worker.locator("[data-sync-now]").click()
                wait_for_outbox(page, 0)
                assert snapshot(page, item.pk)["revision"] == 2
                assert page.evaluate("navigator.locks !== undefined")
                save(
                    name + ".json",
                    {
                        "server": snapshot(page, item.pk),
                        "requests": [r for r in result["post_requests"] if r["context"] == name],
                    },
                )
                finish(name, ctx)
                return {"two_live_pages_web_locks": True, "one_server_mutation": True}

            check("two_consumers_serialize_same_queue", consumers)

            def real_conflict() -> CheckDetails:
                name = "real409"
                ctx, page = setup(name)
                item = sessions[15]
                baseline = snapshot(page, item.pk)
                download(page, item)
                remote = ctx.new_page()
                remote.goto(origin + f"/sets/{baseline['blocks'][0]['sets'][0]['id']}/edit/")
                remote.locator("[name=actual_reps]").fill("8")
                remote.locator("[name=actual_kg]").fill("70")
                remote.locator("form[data-form-submit] button[type=submit]").click()
                remote.wait_for_url(origin + f"/sessions/{item.pk}/")
                open_editor(page, item)
                fill(page)
                page.get_by_role("button", name="Guardar registro", exact=True).click()
                page.wait_for_function("document.querySelector('#sync-conflict').open")
                queued = copy.deepcopy(outbox(page))
                assert len(queued) == 1 and queued[0]["session"]["revision"] == 1
                assert queued[0]["delivery"] == "attempted"
                assert snapshot(page, item.pk)["revision"] == 2
                page.locator("#sync-conflict [data-conflict=local]").click()
                wait_for_outbox(page, 0)
                saved = snapshot(page, item.pk)
                assert (
                    saved["revision"] == 3
                    and number(saved["blocks"][0]["sets"][0]["actual_kg"]) == 75
                )
                assert (
                    store(page, "archive")[0]["operations"][0]["mutation_id"]
                    == queued[0]["mutation_id"]
                )
                save(
                    name + ".json",
                    {"conflicting_pending_before_choice": queued, "after_explicit_choice": saved},
                )
                finish(name, ctx)
                return {"real409_no_automatic_reset": True, "only_explicit_choice_rebases": True}

            check("real409_preserved_until_explicit_choice", real_conflict)

            def identity_guard(new_uuid: bool = False) -> CheckDetails:
                name = "new-uuid-mapping" if new_uuid else "foreign-child-guard"
                ctx, page = setup(name)
                item = sessions[16 if new_uuid else 17]
                baseline = snapshot(page, item.pk)
                page.goto(origin + "/offline/")
                body = copy.deepcopy(baseline)
                if new_uuid:
                    body["id"] = str(uuid4())
                    body["revision"] = 0
                    body["planned"] = None
                    for block in body["blocks"]:
                        block.pop("id", None)
                        block.pop("source", None)
                        for row in block["sets"]:
                            row.pop("id", None)
                            row.pop("source", None)
                else:
                    body["blocks"][0]["sets"][0]["id"] = snapshot(page, sessions[0].pk)["blocks"][
                        0
                    ]["sets"][0]["id"]
                mutation: dict[str, object] = {
                    "account": page.locator("body").get_attribute("data-account"),
                    "mutation_id": str(uuid4()),
                    "created": int(time.time() * 1000),
                    "session": body,
                }
                seed_stale_local_mutation(page, mutation)
                if new_uuid:
                    ctx.set_offline(True)
                    page.reload()
                    open_editor(page, item)
                    fill(page)
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    wait_for_outbox(page, 2)
                    ctx.set_offline(False)
                    wait_for_outbox(page, 0)
                    saved = snapshot(page, body["id"])
                    local = store(page, "sessions")[0]["session"]
                    assert local == saved and saved["revision"] == 2
                    assert (
                        saved["blocks"][0]["sets"][0]["id"]
                        != baseline["blocks"][0]["sets"][0]["id"]
                    )
                    assert snapshot(page, item.pk) == baseline
                else:
                    page.locator("[data-sync-now]").click()
                    page.wait_for_function(
                        "document.querySelector('#offline-status').textContent.includes('Registro sin sincronizar')"
                    )
                    open_editor(page, item)
                    fill(page, "4", "77.5")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    page.wait_for_function(
                        "document.querySelector('#offline-status').textContent.includes('Registro sin sincronizar')"
                    )
                    assert (
                        outbox(page)[0]["session"]["blocks"][0]["sets"][0]["id"]
                        == body["blocks"][0]["sets"][0]["id"]
                    )
                    assert outbox(page)[0]["delivery"] == "rejected_validation"
                    assert snapshot(page, item.pk) == baseline
                    saved = baseline
                save(
                    name + ".json",
                    {"original_mutation": mutation, "server": saved, "outbox": outbox(page)},
                )
                finish(name, ctx)
                return {"new_uuid": new_uuid, "ids_never_stripped_to_bypass_validation": True}

            check("new_UUID_idless_legacy_prefix_receipt_mapping", lambda: identity_guard(True))
            check("foreign_child_ID_stays_400_after_UI_result_correction", identity_guard)

            def fill_close_values(page: Page, kg: str = "77.5") -> None:
                fill(page, "4", kg)
                page.locator("#offline-blocks-0-sets-1-actual_reps").fill("0")
                page.locator("#offline-blocks-0-sets-1-actual_kg").fill("0")
                page.locator("#offline-duration_seconds").fill("600")
                page.locator("#offline-reported_rpe").fill("5")

            def assert_close_values(state: SessionSnapshot) -> None:
                actual, zero, unknown = state["blocks"][0]["sets"]
                assert actual["actual_reps"] == 4 and number(actual["actual_kg"]) == 77.5
                assert zero["actual_reps"] == 0 and number(zero["actual_kg"]) == 0
                assert unknown["actual_reps"] is None and unknown["actual_kg"] is None
                assert state["duration_seconds"] == 600 and number(state["reported_rpe"]) == 5

            def assert_preserved_children(local: SessionSnapshot, actual: SessionSnapshot) -> None:
                # The wire codec serializes Decimal kg with two places; compare
                # the entire child snapshot after only that known representation.
                expected = copy.deepcopy(local["blocks"])
                for block in expected:
                    for row in block["sets"]:
                        if row["actual_kg"] is not None:
                            row["actual_kg"] = f"{number(row['actual_kg']):.2f}"
                assert actual["blocks"] == expected

            def pending_close(page: Page, sid: str) -> Mutation:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    found = [row for row in outbox(page) if row["session"]["id"] == sid]
                    if len(found) == 1 and found[0]["session"]["status"] == "completed":
                        return found[0]
                    page.wait_for_timeout(50)
                raise AssertionError("Expected one locally completed draft")

            def await_closed(page: Page, sid: str) -> SessionSnapshot:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    state = snapshot(page, sid)
                    if state["status"] == "completed":
                        wait_for_outbox(page, 0)
                        return state
                    page.wait_for_timeout(50)
                raise AssertionError("Expected actual server acknowledgement of completion")

            def close_receipt(sid: str) -> SessionSnapshot:
                # Read-only observation, safe while Playwright's event loop is active.
                with sqlite3.connect(
                    (out / "client.sqlite3").as_uri() + "?mode=ro", uri=True
                ) as db:
                    rows = db.execute(
                        "SELECT result FROM basis_sync_syncreceipt WHERE json_extract(result, '$.id') = ?",
                        (sid,),
                    ).fetchall()
                assert len(rows) == 1, "Completion must have exactly one accepted receipt"
                value: object = json.loads(rows[0][0])
                assert isinstance(value, dict)
                return cast(SessionSnapshot, value)

            def readonly_capture(page: Page, item: Session, name: str) -> None:
                page.goto(origin + f"/sessions/{item.pk}/")
                assert not page.locator("a[href^='/sets/'][href$='/edit/']").count()
                assert page.get_by_role("button", name="Completar sesión", exact=True).count() == 0
                page.screenshot(path=str(out / (name + "-readonly.png")), full_page=True)

            def stale_close(width: int, index: int) -> CheckDetails:
                name = f"stale-close-{width}"
                ctx, editor = setup(name, width)
                item, unrelated = sessions[index : index + 2]
                baseline = snapshot(editor, item.pk)
                download(editor, item)
                download(editor, unrelated)
                stale = ctx.new_page()
                stale.goto(origin + f"/sessions/{item.pk}/")
                ctx.set_offline(True)
                open_editor(editor, item)
                fill_close_values(editor)
                editor.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(editor, 1)
                original = outbox(editor)[0]
                open_editor(editor, unrelated)
                fill(editor, "3", "72.5")
                editor.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(editor, 2)
                other = next(
                    row for row in outbox(editor) if row["session"]["id"] == str(unrelated.pk)
                )
                stale.get_by_role("button", name="Completar sesión", exact=True).click()
                completed = pending_close(editor, str(item.pk))
                assert (
                    next(row for row in outbox(editor) if row["session"]["id"] == str(unrelated.pk))
                    == other
                )
                save(
                    name + "-queued.json",
                    {"original": original, "completed": completed, "unrelated": other},
                )
                ctx.set_offline(False)
                actual = await_closed(editor, str(item.pk))
                receipt = close_receipt(str(item.pk))
                readonly_capture(stale, item, name)
                save(
                    name + ".json",
                    {
                        "baseline": baseline,
                        "original": original,
                        "completed": completed,
                        "actual_server": actual,
                        "receipt_readonly": receipt,
                        "unrelated_server": snapshot(editor, unrelated.pk),
                    },
                )
                assert_close_values(actual)
                assert receipt == actual
                assert_preserved_children(original["session"], actual)
                assert actual["revision"] == baseline["revision"] + 1
                assert snapshot(editor, unrelated.pk)["blocks"][0]["sets"][0]["actual_reps"] == 3
                finish(name, ctx)
                return {
                    "two_tabs_UI_only": True,
                    "latest_numbers_zero_null_duration_rpe_preserved": True,
                    "one_receipt": True,
                    "unrelated_uuid_unchanged": True,
                }

            check("stale_HTML_close_390_preserves_latest_draft", lambda: stale_close(390, 18))
            check("stale_HTML_close_1440_preserves_latest_draft", lambda: stale_close(1440, 20))

            def observe_writes(page: Page) -> None:
                page.evaluate("""() => {
                    window.__client623Writes = 0;
                    const original = IDBDatabase.prototype.transaction;
                    IDBDatabase.prototype.transaction = function(stores, mode, ...rest) {
                        const tx = original.call(this, stores, mode, ...rest);
                        const names = typeof stores === 'string' ? [stores] : Array.from(stores);
                        if(mode === 'readwrite' && names.includes('outbox') && names.includes('sessions')) window.__client623Writes++;
                        return tx;
                    };
                }""")

            def hold_idb(page: Page) -> None:
                page.evaluate("""() => {
                    window.__client623Held = false;
                    window.__client623Released = false;
                    const source = `
                        let release = false;
                        onmessage = () => { release = true; };
                        const opening = indexedDB.open('basis-offline-v1', 1);
                        opening.onsuccess = () => {
                            const db = opening.result;
                            const tx = db.transaction(['sessions','outbox','archive'], 'readwrite');
                            tx.oncomplete = () => { postMessage('released'); db.close(); };
                            let held = false;
                            function keepActive() {
                                const request = tx.objectStore('outbox').get('__read_only_barrier__');
                                request.onsuccess = () => {
                                    if(!held) { held=true; postMessage('held'); }
                                    if(!release) keepActive();
                                };
                            }
                            keepActive();
                        };
                    `;
                    window.__client623WorkerURL = URL.createObjectURL(new Blob([source], {type:'application/javascript'}));
                    const worker = window.__client623Worker = new Worker(window.__client623WorkerURL);
                    worker.onmessage = event => {
                        if(event.data === 'held') window.__client623Held = true;
                        if(event.data === 'released') window.__client623Released = true;
                    };
                    window.__client623BarrierTimeout = setTimeout(() => worker.postMessage('release'), 10000);
                }""")
                page.wait_for_function("window.__client623Held === true")

            def release_idb(page: Page) -> None:
                # Release is a Worker message, never an IDB read waiting on its own lock.
                page.evaluate("window.__client623Worker.postMessage('release')")
                page.wait_for_function("window.__client623Released === true")
                page.evaluate("""() => {
                    clearTimeout(window.__client623BarrierTimeout);
                    window.__client623Worker.terminate();
                    URL.revokeObjectURL(window.__client623WorkerURL);
                }""")

            def close_edit_race(edit_first: bool) -> CheckDetails:
                name = "race-edit-then-close" if edit_first else "race-close-then-edit"
                ctx, editor = setup(name)
                item = sessions[22 if edit_first else 23]
                download(editor, item)
                stale = ctx.new_page()
                stale.goto(origin + f"/sessions/{item.pk}/")
                ctx.set_offline(True)
                open_editor(editor, item)
                fill_close_values(editor, "70")
                editor.get_by_role("button", name="Guardar registro", exact=True).click()
                wait_for_outbox(editor, 1)
                original = outbox(editor)[0]
                open_editor(editor, item)
                fill_close_values(editor)
                observe_writes(editor)
                observe_writes(stale)
                hold_idb(stale)
                if edit_first:
                    editor.get_by_role("button", name="Guardar registro", exact=True).click()
                    editor.wait_for_function("window.__client623Writes === 1")
                    stale.get_by_role("button", name="Completar sesión", exact=True).click()
                    stale.wait_for_function("window.__client623Writes === 1")
                else:
                    stale.get_by_role("button", name="Completar sesión", exact=True).click()
                    stale.wait_for_function("window.__client623Writes === 1")
                    editor.get_by_role("button", name="Guardar registro", exact=True).click()
                    editor.wait_for_function("window.__client623Writes === 1")
                # Only synchronous transaction-creation signals were awaited while held.
                release_idb(stale)
                pending = pending_close(editor, str(item.pk))
                if not edit_first:
                    editor.wait_for_function(
                        "document.querySelector('#offline-status').textContent.includes('La copia local cambió')"
                    )
                    assert (
                        editor.locator("#offline-blocks-0-sets-0-actual_kg").input_value() == "77.5"
                    )
                    assert pending["session"]["blocks"] == original["session"]["blocks"]
                    editor.screenshot(
                        path=str(out / (name + "-retained-input.png")), full_page=True
                    )
                    # The user reviews the now-current local draft and finishes entirely in UI.
                    open_editor(editor, item)
                    assert (
                        editor.locator("#offline-blocks-0-sets-0-actual_kg").input_value() == "70"
                    )
                    fill_close_values(editor)
                    editor.get_by_role("button", name="Completar sesión", exact=True).click()
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        pending = pending_close(editor, str(item.pk))
                        if number(pending["session"]["blocks"][0]["sets"][0]["actual_kg"]) == 77.5:
                            break
                        editor.wait_for_timeout(50)
                assert_close_values(pending["session"])
                ctx.set_offline(False)
                actual = await_closed(editor, str(item.pk))
                receipt = close_receipt(str(item.pk))
                assert_close_values(actual)
                assert receipt == actual and actual["revision"] == 2
                assert_preserved_children(pending["session"], actual)
                readonly_capture(stale, item, name)
                save(
                    name + ".json",
                    {
                        "order": name,
                        "barrier": "Worker IDB lock; release via independent postMessage",
                        "original": original,
                        "pending": pending,
                        "actual_server": actual,
                        "receipt_readonly": receipt,
                    },
                )
                finish(name, ctx)
                return {
                    "deterministic_IDB_order": True,
                    "no_circular_wait": True,
                    "latest_actuals_preserved": True,
                    "UI_review_if_edit_loses_race": not edit_first,
                }

            check("IDB_barrier_edit_then_close_preserves_latest", lambda: close_edit_race(True))
            check(
                "IDB_barrier_close_then_edit_retains_inputs_and_UI_review",
                lambda: close_edit_race(False),
            )

            def fresh_close() -> CheckDetails:
                name = "fresh-single-tab-close"
                ctx, page = setup(name)
                item = sessions[24]
                baseline = snapshot(page, item.pk)
                assert not store(page, "sessions")
                page.goto(origin + f"/sets/{baseline['blocks'][0]['sets'][0]['id']}/edit/")
                page.locator("[name=actual_reps]").fill("4")
                page.locator("[name=actual_kg]").fill("77.5")
                page.locator("form[data-form-submit] button[type=submit]").click()
                page.wait_for_url(origin + f"/sessions/{item.pk}/")
                actual_before = snapshot(page, item.pk)
                page.get_by_role("button", name="Completar sesión", exact=True).click()
                actual = await_closed(page, str(item.pk))
                assert actual["blocks"] == actual_before["blocks"]
                assert actual["revision"] == actual_before["revision"] + 1
                assert close_receipt(str(item.pk)) == actual
                readonly_capture(page, item, name)
                save(name + ".json", {"before": actual_before, "actual_server": actual})
                finish(name, ctx)
                return {
                    "fresh_HTML_without_local_copy": True,
                    "single_tab_close_acknowledged": True,
                }

            check("fresh_single_tab_completion_preserves_results", fresh_close)
            browser.close()
            result["browser_stopped"] = not browser.is_connected()
            browser = None
        result["receipt_count"] = SyncReceipt.objects.count()
        assert result["receipt_count"] == 32, result["receipt_count"]
    except Exception:
        result["fatal"] = traceback.format_exc()
    finally:
        for name, ctx in contexts:
            with contextlib.suppress(Exception):
                ctx.tracing.stop(path=str(out / (name + ".zip")))
                ctx.close()
        if browser:
            with contextlib.suppress(Exception):
                browser.close()
        server.terminate()
        server.wait(timeout=10)
        server_log.close()
        connections.close_all()
        after = binding()
        save("sources-after.json", after)
        result["authored_before"] = before["aggregate"]
        result["authored_after"] = after["aggregate"]
        result["source_changes_during_run"] = [
            p
            for p in set(before["files"]) | set(after["files"])
            if before["files"].get(p) != after["files"].get(p)
        ]
        result["client_js_unchanged"] = before["files"][JS] == after["files"][JS]
        result["script_unchanged"] = before["files"].get(
            "scripts/client623_queue_regression.py"
        ) == after["files"].get("scripts/client623_queue_regression.py")
        result["handoff_unchanged"] = handoff == digest(
            MAIN / "docs/HANDOFF_PRESENTATION_2026-10-19.md"
        )
        result["server_stopped"] = server.poll() is not None
        result["status"] = (
            "VERIFIED"
            if not result.get("fatal")
            and result["checks"]
            and all(c["status"] == "VERIFIED" for c in result["checks"])
            and not result["pageerrors"]
            else "FAILED"
        )
        save("result.json", result)
        save(
            "evidence-sha256.json",
            {p.name: digest(p) for p in out.iterdir() if p.is_file() and p.suffix != ".sqlite3"},
        )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"post_requests", "external_blocked"}},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
