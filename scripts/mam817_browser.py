"""MAM817 real Edge/loopback acceptance; synthetic owned data, no provider calls.

All artifacts go to the explicitly authorized external --output directory. Mutable
SQLite and browser profile state stay in a unique worktree .cache directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread
from typing import TextIO, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT.parent.parent / "basis-runs"
DELTA = (
    "basis/modules/billing/adapters/templates/billing/subscription.html",
    "tests/regression/test_billing_entitlements.py",
    "tests_architecture/test_entitlements.py",
    "scripts/mam817_browser.py",
    "docs/ENTITLEMENTS_MAM817.md",
    "mypy-django.ini",
)

# The subprocess receives only a scrubbed environment and never accepts a DB path
# from an HTTP request. Every ORM observation/mutation rechecks the exact owned DB.
ORM = """
import json, os
from datetime import timedelta
from pathlib import Path
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.utils import timezone
from django.utils.formats import date_format
from basis.modules.billing.adapters.models import BillingAccount
expected = Path(os.environ['BASIS_ACCEPTANCE_DATABASE']).resolve()
cache = settings.BASE_DIR / '.cache'
assert not cache.is_symlink() and cache.resolve() == cache
assert expected.is_relative_to(cache.resolve()) and expected.is_file()
assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
assert Path(settings.DATABASES['default']['NAME']).resolve() == expected
assert not settings.DEVELOPMENT_ACCESS and not settings.AI_ENABLED
assert not settings.POLAR_ACCESS_TOKEN and not settings.DEEPSEEK_API_KEY
owner = BillingAccount.objects.get(owner__username='owner@browser.test')
if os.environ['MAM817_ORM_ACTION'] == 'expire':
    assert owner.entitled
    assert BillingAccount.objects.filter(pk=owner.pk).update(
        period_end=timezone.now() - timedelta(seconds=1)) == 1
    owner.refresh_from_db()
    assert not owner.entitled
rows = {}
for label in ('basis_training', 'basis_sync'):
    for model in apps.get_app_config(label).get_models():
        rows[model._meta.label_lower] = json.loads(serializers.serialize(
            'json', model.objects.order_by('pk')))
print(json.dumps({
    'rows': rows,
    'billing': json.loads(serializers.serialize('json', BillingAccount.objects.order_by('pk'))),
    'start': date_format(timezone.localtime(owner.period_start), 'j M Y H:i'),
    'end': date_format(timezone.localtime(owner.period_end), 'j M Y H:i'),
    'entitled': owner.entitled,
}))
"""


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("Expected a JSON object")
    return cast(dict[str, object], value)


def rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise AssertionError("Expected JSON rows")
    return [mapping(row) for row in value]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(output: Path, name: str, value: object) -> None:
    (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def binding() -> dict[str, object]:
    from scripts.acceptance_browser import source_binding

    files = dict(mapping(source_binding()["files"]))
    files.update({name: digest(ROOT / name) for name in DELTA})
    aggregate = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"algorithm": "sha256", "aggregate_sha256": aggregate, "files": files}


def owned_orm(
    environment: dict[str, str], output: Path, name: str, action: str
) -> dict[str, object]:
    from scripts.acceptance_browser import execute

    child = dict(environment, MAM817_ORM_ACTION=action)
    path = output / (name + ".json")
    execute([sys.executable, "-B", "-c", ORM], child, path)
    return mapping(json.loads(path.read_text(encoding="utf-8")))


def local_data(page: Page) -> dict[str, object]:
    value: object = page.evaluate("""async () => {
      const db = await new Promise((resolve, reject) => {
        const req = indexedDB.open('basis-offline-v1', 1);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
      try {
        const result = {};
        for (const name of ['sessions', 'outbox', 'archive']) {
          result[name] = await new Promise((resolve, reject) => {
            const req = db.transaction(name).objectStore(name).getAll();
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
          });
        }
        return result;
      } finally { db.close(); }
    }""")
    return mapping(value)


def wire(item: dict[str, object]) -> dict[str, object]:
    # Delivery metadata may change from unsent to attempted. Transport identity,
    # timestamp and the ENTIRE session payload must not change on a 403.
    return {key: item[key] for key in ("mutation_id", "account", "session", "created")}


def export_local(page: Page, output: Path, name: str, account: str) -> dict[str, object]:
    before = local_data(page)
    expected = {
        "schema": "basis-local-v1",
        "account": account,
        "sessions": [row for row in rows(before["sessions"]) if row["account"] == account],
        "pending": [row for row in rows(before["outbox"]) if row["account"] == account],
        "archive": [row for row in rows(before["archive"]) if row["account"] == account],
    }
    with page.expect_download() as pending:
        page.locator("[data-export-local]").click()
    download = pending.value
    assert download.suggested_filename == "basis-registros-locales.json"
    assert download.failure() is None
    path = output / name
    download.save_as(path)
    actual = mapping(json.loads(path.read_text(encoding="utf-8")))
    assert actual == expected, "Downloaded JSON must exactly match account-scoped IndexedDB"
    assert local_data(page) == before, "Export must not remove or rewrite local data"
    return actual


def browser_flow(
    context: BrowserContext,
    origin: str,
    output: Path,
    environment: dict[str, str],
    result: dict[str, object],
    checks: list[str],
) -> None:
    from scripts.browser_smoke import (
        create_session,
        download_session,
        json_body,
        login,
        no_overflow,
        outbox,
        service_worker_ready,
        wait_for_outbox,
    )

    blocked: list[dict[str, str]] = []
    external_responses: list[str] = []
    errors: list[str] = []
    sent: list[dict[str, object]] = []
    result["blocked_external_requests"] = blocked
    result["external_responses"] = external_responses
    result["javascript_errors"] = errors

    def local_only(route: Route) -> None:
        target = urlsplit(route.request.url)
        if target.scheme + "://" + target.netloc == origin:
            route.continue_()
        else:
            blocked.append({"host": target.netloc, "resource_type": route.request.resource_type})
            route.abort()

    context.route("**/*", local_only)
    context.on(
        "response",
        lambda response: (
            external_responses.append(urlsplit(response.url).netloc)
            if urlsplit(response.url).scheme in ("http", "https")
            and not response.url.startswith(origin + "/")
            else None
        ),
    )
    context.on("weberror", lambda error: errors.append(str(error.error)))
    page = context.new_page()
    login(page, origin, "owner@browser.test", environment["BASIS_E2E_PASSWORD"])
    result["service_worker"] = service_worker_ready(page)
    metadata = owned_orm(environment, output, "db-initial", "read")
    assert metadata["entitled"] is True
    checks.append("owned_fixture_active_without_development_bypass")
    for size, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        response = page.goto(origin + "/billing/")
        assert response is not None and response.status == 200
        initial = page.locator("p").filter(has_text="Inicio del período:")
        final = page.locator("p").filter(has_text="Próxima renovación:")
        assert initial.count() == 1 and initial.is_visible()
        assert final.count() == 1 and final.is_visible()
        assert initial.locator("strong").inner_text() == metadata["start"]
        assert final.locator("strong").inner_text() == metadata["end"]
        for paragraph in (initial, final):
            assert paragraph.evaluate("""node => {
              const r = node.getBoundingClientRect();
              return r.left >= 0 && r.right <= innerWidth && node.scrollWidth <= node.clientWidth;
            }"""), "Date text must fit the viewport"
        no_overflow(page)
        page.screenshot(path=str(output / ("billing-" + size + ".png")), full_page=True)
        checks.append("billing_dates_visible_no_overflow_" + str(width))

    session_url = create_session(page, origin, "MAM817 historial sintético privado")
    snapshot_url = session_url.replace("/sessions/", "/api/sessions/") + "snapshot/"
    downloaded = page.request.get(snapshot_url)
    assert downloaded.status == 200
    baseline = json_body(downloaded)
    account = str(baseline["account"])
    server_session = mapping(baseline["session"])
    download_session(page, origin)
    context.set_offline(True)
    page.locator("#offline-blocks-0-actual-distance_m").fill("5500.5")
    page.locator("#offline-blocks-0-actual-pack_kg").fill("7.25")
    page.locator("button[name=mode][value=draft]").click()
    wait_for_outbox(page, 1)
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('Pendiente')"
    )
    before_reload = local_data(page)
    queued = outbox(page)[0]
    UUID(str(queued["mutation_id"]))
    assert queued["account"] == account
    actual = mapping(rows(mapping(queued["session"])["blocks"])[0]["actual"])
    assert actual["distance_m"] == 5500.5 and actual["pack_kg"] == 7.25
    page.reload()
    assert page.evaluate("!navigator.onLine && navigator.serviceWorker.controller !== null")
    assert local_data(page) == before_reload
    page.get_by_role("button", name="Abrir sesión", exact=True).click()
    assert page.locator("#offline-blocks-0-actual-distance_m").input_value() == "5500.5"
    assert page.locator("#offline-blocks-0-actual-pack_kg").input_value() == "7.25"
    checks.append("real_offline_edit_reload_preserves_uuid_entire_payload_and_measurements")
    save(output, "queue-before-reconnect.json", before_reload)
    before = owned_orm(environment, output, "db-before-expiry", "read")
    expired = owned_orm(environment, output, "db-expired", "expire")
    assert expired["entitled"] is False and before["rows"] == expired["rows"]

    # Capture the actual UI fetch, never fulfill/mock/replace /api/sync/.
    context.on(
        "request",
        lambda request: (
            sent.append(mapping(request.post_data_json))
            if request.url == origin + "/api/sync/" and request.method == "POST"
            else None
        ),
    )
    with page.expect_response(
        lambda response: (
            response.url == origin + "/api/sync/" and response.request.method == "POST"
        ),
        timeout=15000,
    ) as denied:
        context.set_offline(False)
    ui_response = denied.value
    assert ui_response.status == 403
    ui_wire = mapping(ui_response.request.post_data_json)
    assert ui_wire == wire(queued)
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('No hay acceso activo')"
    )
    assert sent and all(item == wire(queued) for item in sent)
    ui_denial = {
        "status": ui_response.status,
        "request": ui_wire,
        "ui_status": page.locator("#offline-status").inner_text(),
    }
    save(output, "real-ui-403.json", ui_denial)
    checks.append("real_ui_403_same_queued_wire_and_denial_status")

    # Do not read/finish the ServiceWorker BrowserResponse body: it may never
    # complete after reconnect. Independently confirm the SAME operation against
    # the real backend via APIRequestContext, with bounded CSRF and POST requests.
    csrf = page.request.get(origin + "/api/csrf/", timeout=15000)
    assert csrf.status == 200
    token = str(json_body(csrf)["token"])
    confirmation = page.request.post(
        origin + "/api/sync/",
        data=ui_wire,
        headers={"X-CSRFToken": token},
        timeout=15000,
    )
    assert confirmation.status == 403
    denial = json_body(confirmation)
    assert "suscripción activa" in str(denial["detail"]), "Must be entitlement, not CSRF denial"
    direct_denial = {"status": confirmation.status, "body": denial, "request": ui_wire}
    save(output, "real-direct-403.json", direct_denial)
    checks.append("real_direct_http_entitlement_403_same_queued_wire")
    pending = outbox(page)
    assert len(pending) == 1 and wire(pending[0]) == wire(queued)
    assert pending[0]["delivery"] == "attempted"
    after_denial = local_data(page)
    assert after_denial["sessions"] == before_reload["sessions"]
    assert after_denial["archive"] == before_reload["archive"]
    assert json_body(page.request.get(snapshot_url))["session"] == server_session
    after = owned_orm(environment, output, "db-after-403", "read")
    assert after["rows"] == expired["rows"] and after["billing"] == expired["billing"]
    save(
        output,
        "real-403.json",
        {"ui": ui_denial, "direct_confirmation": direct_denial, "requests": sent},
    )
    save(output, "queue-after-403.json", after_denial)
    checks.append("real_entitlement_403_same_uuid_payload_local_data_and_server_unchanged")
    page.goto(origin + "/offline/")
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('No hay acceso activo')"
    )
    no_overflow(page)
    page.screenshot(path=str(output / "expired-pending.png"), full_page=True)
    online_export = export_local(page, output, "pending-expired.json", account)
    assert rows(online_export["pending"])[0] == outbox(page)[0]
    context.set_offline(True)
    page.reload()
    assert page.evaluate("!navigator.onLine")
    offline_export = export_local(page, output, "pending-offline.json", account)
    assert online_export == offline_export
    checks.append("exact_local_json_download_after_expiry_and_offline_without_data_loss")
    context.set_offline(False)
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('No hay acceso activo')"
    )
    history = page.request.get(session_url)
    assert history.status == 200 and str(server_session["title"]) in history.text()
    history_export = page.request.get(origin + "/export/")
    assert history_export.status == 200
    assert [row["pk"] for row in rows(json_body(history_export)["session"])] == [
        server_session["id"]
    ]
    checks.append("expired_owner_history_readable_and_exportable")

    # Clear authentication cookies ONLY, not application logout (which intentionally
    # deletes the old account's local data). This tests isolation with foreign rows
    # still physically present in the SAME IndexedDB/browser profile.
    retained = local_data(page)
    page.close()
    context.clear_cookies()
    other = context.new_page()
    login(other, origin, "other@browser.test", environment["BASIS_E2E_PASSWORD"])
    other.goto(origin + "/offline/")
    other.wait_for_function(
        "!document.querySelector('#offline-status').textContent.includes('Abriendo')"
    )
    assert other.get_by_role("button", name="Abrir sesión", exact=True).count() == 0
    assert str(server_session["title"]) not in other.locator("#offline-sessions").inner_text()
    other_account = other.locator("body").get_attribute("data-account")
    assert other_account and other_account != account
    assert local_data(other) == retained, "Foreign queue must remain present but inaccessible"
    other_export = export_local(other, output, "other-account.json", other_account)
    assert other_export == {
        "schema": "basis-local-v1",
        "account": other_account,
        "sessions": [],
        "pending": [],
        "archive": [],
    }
    context.set_offline(True)
    other.reload()
    assert other.evaluate("!navigator.onLine")
    assert export_local(other, output, "other-account-offline.json", other_account) == other_export
    context.set_offline(False)
    assert other.request.get(snapshot_url).status == 404
    assert other.request.get(session_url).status == 404
    foreign_history = other.request.get(origin + "/export/")
    assert foreign_history.status == 200
    assert json_body(foreign_history)["session"] == []
    assert str(server_session["title"]) not in foreign_history.text()
    token = str(json_body(other.request.get(origin + "/api/csrf/"))["token"])
    foreign_write = other.request.post(
        origin + "/api/sync/", data=wire(queued), headers={"X-CSRFToken": token}
    )
    assert foreign_write.status == 403
    assert json_body(foreign_write) == {"detail": "La cola pertenece a otra cuenta."}
    final_state = owned_orm(environment, output, "db-final", "read")
    assert final_state["rows"] == expired["rows"]
    assert final_state["billing"] == expired["billing"]
    assert local_data(other) == retained
    checks.append(
        "same_profile_other_account_cannot_view_export_or_submit_foreign_queue_or_history"
    )
    assert not errors, "Uncaught JavaScript error"
    assert not external_responses, "External HTTP delivery forbidden"
    checks.append("outside_origin_requests_aborted_no_external_responses")


def run(output: Path, executable: Path, expected_hash: str) -> int:
    from scripts.acceptance_browser import child_environment, choose_port, execute, ready

    output = output.absolute()
    authorized = EVIDENCE_ROOT.resolve()
    if output.resolve() != output or not output.is_relative_to(authorized):
        raise ValueError("Output must be an unredirected authorized basis-runs subdirectory")
    if output == authorized or output.is_relative_to(ROOT):
        raise ValueError("Evidence must be outside the worktree in a dedicated directory")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Refusing to overwrite a nonempty evidence directory")
    cache = ROOT / ".cache"
    if cache.is_symlink() or cache.resolve() != cache:
        raise ValueError("Worktree cache must not redirect")
    cache.mkdir(exist_ok=True)
    owned = cache / ("mam817-browser-" + uuid4().hex)
    owned.mkdir(exist_ok=False)
    database = owned / "browser.sqlite3"
    assert not database.exists()
    password, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    environment = child_environment(database, password, secret)
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(ROOT),
        BASIS_DEVELOPMENT_ACCESS="0",
        POLAR_ORGANIZATION_ID="",
    )
    before = binding()
    save(output, "source-before.json", before)
    checks: list[str] = []
    result: dict[str, object] = {
        "status": "FAILED",
        "checks": checks,
        "initial_source_snapshot_hash": (
            "dee173c28238955ad7b719cd906df701287dc1c2471ef234821e4ab0e0743989"
        ),
        "source_sha256": before["aggregate_sha256"],
        "python_version": sys.version,
        "python_executable_sha256": digest(Path(sys.executable)),
        "browser_expected_sha256": expected_hash.lower(),
        "database": str(database),
        "providers": "DISABLED",
        "smtp": "DISABLED",
        "server_stopped": False,
        "browser_stopped": False,
        "mutable_state_retained_in_owned_cache": True,
    }
    server: subprocess.Popen[str] | None = None
    server_log: TextIO | None = None
    try:
        executable = executable.resolve(strict=True)
        observed_hash = digest(executable)
        result["browser_executable_sha256"] = observed_hash
        if len(expected_hash) != 64 or observed_hash != expected_hash.lower():
            raise ValueError("Edge executable SHA256 mismatch; browser launch refused")
        checks.append("edge_executable_sha256_verified_before_launch")
        execute(
            [sys.executable, "-B", "manage.py", "migrate", "--noinput", "--verbosity", "0"],
            environment,
            output / "migrate.log",
        )
        execute(
            [
                sys.executable,
                "-B",
                "-c",
                "import django; django.setup(); "
                "from basis.adapters.django.acceptance_fixture import prepare; prepare()",
            ],
            environment,
            output / "fixture.log",
        )
        port = choose_port(0)
        origin = "http://127.0.0.1:" + str(port)
        result["origin"] = origin
        server_log = (output / "server.log").open("w", encoding="utf-8")
        server = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "manage.py",
                "runserver",
                "127.0.0.1:" + str(port),
                "--noreload",
            ],
            cwd=ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        result["server_pid"] = server.pid
        ready(server, origin)
        browser_env: dict[str, str | float | bool] = {
            key: value
            for key, value in environment.items()
            if key.upper()
            in {"SYSTEMROOT", "WINDIR", "PATH", "USERPROFILE", "LOCALAPPDATA", "APPDATA"}
        }
        browser_env.update(TEMP=str(owned), TMP=str(owned))
        flow_finished = Event()
        browser_cleanup: dict[str, object] = {"browser_stopped": False}

        def browser_worker() -> None:
            # Sync Playwright has no timeout argument for context/browser close.
            # Keep ALL Playwright calls on this one owner thread; the main thread
            # can bound teardown (including driver.stop) and still write a FAILED
            # receipt if it hangs. Never claim a timed-out browser was stopped.
            context: BrowserContext | None = None
            browser: Browser | None = None
            try:
                with sync_playwright() as playwright:
                    try:
                        # Recheck immediately before launch (migrations may take time).
                        assert digest(executable) == observed_hash
                        context = playwright.chromium.launch_persistent_context(
                            str(owned / "edge-profile"),
                            executable_path=str(executable),
                            headless=True,
                            accept_downloads=True,
                            downloads_path=str(owned / "downloads"),
                            viewport={"width": 1440, "height": 1000},
                            env=browser_env,
                            args=["--disable-background-networking", "--no-first-run"],
                        )
                        browser = context.browser
                        assert browser is not None
                        result["browser_version"] = browser.version
                        context.set_default_timeout(15000)
                        browser_flow(context, origin, output, environment, result, checks)
                        result["status"] = "VERIFIED"
                    except Exception as error:
                        result["error"] = type(error).__name__ + ": " + str(error)
                    finally:
                        flow_finished.set()
                        try:
                            if context is not None:
                                context.close()
                        finally:
                            if browser is not None:
                                browser.close()
                                browser_cleanup["browser_stopped"] = not browser.is_connected()
            except Exception as error:
                browser_cleanup["error"] = type(error).__name__ + ": " + str(error)
            finally:
                flow_finished.set()

        worker = Thread(target=browser_worker, name="mam817-owned-browser", daemon=True)
        worker.start()
        flow_finished.wait()
        worker.join(timeout=20)
        cleanup_finished = not worker.is_alive()
        result["browser_cleanup"] = dict(browser_cleanup)
        result["browser_cleanup_finished"] = cleanup_finished
        result["browser_stopped"] = cleanup_finished and browser_cleanup["browser_stopped"] is True
        if not cleanup_finished or "error" in browser_cleanup:
            result["status"] = "FAILED"
            result["browser_cleanup_error"] = (
                "Browser/driver teardown exceeded 20s; stop unconfirmed"
                if not cleanup_finished
                else browser_cleanup["error"]
            )
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
        result["status"] = "FAILED"
    finally:
        try:
            if server is None:
                result["server_stopped"] = True  # No owned server was launched.
            elif os.name == "nt":
                if server.poll() is not None:
                    # A dead wrapper alone cannot prove its children stopped.
                    result["server_cleanup_error"] = "Wrapper exited; subtree stop unconfirmed"
                else:
                    system_root = Path(os.environ["SystemRoot"])
                    if not system_root.is_absolute():
                        raise ValueError("SystemRoot must be absolute for owned taskkill")
                    stopped = subprocess.run(
                        [
                            str(system_root / "System32" / "taskkill.exe"),
                            "/PID",
                            str(server.pid),
                            "/T",
                            "/F",
                        ],
                        env=environment,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=15,
                        check=False,
                    )
                    result["server_taskkill"] = {
                        "pid": server.pid,
                        "returncode": stopped.returncode,
                        "stdout": stopped.stdout,
                        "stderr": stopped.stderr,
                    }
                    server.wait(timeout=10)
                    result["server_stopped"] = stopped.returncode == 0 and server.poll() is not None
            else:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
                result["server_stopped"] = server.poll() is not None
        except Exception as error:
            result["server_cleanup_error"] = type(error).__name__ + ": " + str(error)
            result["server_stopped"] = False
        finally:
            try:
                if server_log is not None:
                    server_log.close()
                after = binding()
                save(output, "source-after.json", after)
                result["source_unchanged"] = before == after
            except Exception as error:
                result["finalization_error"] = type(error).__name__ + ": " + str(error)
                result["source_unchanged"] = False
            result["cleanup"] = {
                "server_stopped": result["server_stopped"],
                "browser_stopped": result["browser_stopped"],
                "owned_database_retained": database.exists(),
                "no_shared_resources_deleted": True,
            }
            if not all(
                (result["server_stopped"], result["browser_stopped"], result["source_unchanged"])
            ):
                result["status"] = "FAILED"
            try:
                # Never print credentials, tracebacks with locals, request headers,
                # or subprocess environments. Redact logs/JSON on partial failure.
                for path in output.iterdir():
                    if path.suffix in (".log", ".json"):
                        text = path.read_text(encoding="utf-8", errors="replace")
                        path.write_text(
                            text.replace(password, "[REDACTED]").replace(secret, "[REDACTED]"),
                            encoding="utf-8",
                        )
                result["artifacts"] = {
                    path.name: digest(path) for path in sorted(output.iterdir()) if path.is_file()
                }
            except Exception as error:
                result["artifact_error"] = type(error).__name__ + ": " + str(error)
                result["status"] = "FAILED"
            finally:
                text = json.dumps(result, indent=2, ensure_ascii=False)
                (output / "result.json").write_text(
                    text.replace(password, "[REDACTED]").replace(secret, "[REDACTED]"),
                    encoding="utf-8",
                )
    print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}))
    return 0 if result["status"] == "VERIFIED" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path, required=True)
    parser.add_argument("--browser-sha256", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    return run(Path(args.output), Path(args.browser_executable), str(args.browser_sha256))


if __name__ == "__main__":
    raise SystemExit(main())
