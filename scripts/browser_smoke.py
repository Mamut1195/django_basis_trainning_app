"""Real browser checks for an explicitly isolated loopback acceptance server."""

from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import APIResponse, Error, Page, Route, sync_playwright
from playwright.sync_api import Response as BrowserResponse


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("Expected JSON object")
    return cast(dict[str, object], value)


def json_body(response: APIResponse) -> dict[str, object]:
    return mapping(response.json())


def login(page: Page, origin: str, email: str, password: str) -> None:
    page.goto(origin + "/accounts/login/")
    page.locator("input[name=username]").fill(email)
    page.locator("input[name=password]").fill(password)
    page.locator("form button[type=submit]").click()
    page.wait_for_url(origin + "/")


def create_session(page: Page, origin: str, title: str) -> str:
    page.goto(origin + "/sessions/new/")
    page.locator("input[name=title]").fill(title)
    page.locator("input[name=duration_seconds]").fill("3600")
    page.locator("input[name=reported_rpe]").fill("5")
    page.locator("select[name=block-sport]").select_option("hiking")
    page.locator("input[name=block-title]").fill("Browser hiking")
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/sessions/*/")
    return page.url


def outbox(page: Page) -> list[dict[str, object]]:
    value: object = page.evaluate("""async () => {
      const db = await new Promise((resolve,reject) => { const req=indexedDB.open('basis-offline-v1',1); req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error); });
      return await new Promise((resolve,reject) => { const req=db.transaction('outbox').objectStore('outbox').getAll(); req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error); });
    }""")
    if not isinstance(value, list):
        raise AssertionError("Expected IndexedDB outbox")
    return [mapping(row) for row in value]


def download_session(page: Page, origin: str) -> None:
    page.locator("[data-download-session]").click()
    page.wait_for_function(
        "document.querySelector('#global-status')?.textContent.includes('Sesión guardada')"
    )
    page.goto(origin + "/offline/")
    page.get_by_role("button", name="Abrir sesión", exact=True).last.click()


def no_overflow(page: Page) -> None:
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (
        "Horizontal overflow"
    )


def run(origin: str, output: Path, executable: str | None, password: str) -> dict[str, object]:
    parsed = urlparse(origin)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise ValueError("Browser acceptance requires the owned loopback server")
    output.mkdir(parents=True, exist_ok=True)
    checks: list[str] = []
    errors: list[str] = []
    external_requests: list[dict[str, str]] = []
    external_responses: list[dict[str, str | int]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})

            def local_only(route: Route) -> None:
                destination = urlparse(route.request.url)
                if (destination.scheme, destination.netloc) == (parsed.scheme, parsed.netloc):
                    route.continue_()
                else:
                    request = route.request
                    try:
                        frame = urlparse(request.frame.url)
                        frame_path = frame.path
                        frame_origin = frame.scheme + "://" + frame.netloc
                    except Error:
                        frame_path = "worker"
                        frame_origin = "worker"
                    external_requests.append(
                        {
                            "host": urlparse(request.url).netloc,
                            "resource_type": request.resource_type,
                            "frame_path": frame_path,
                            "frame_origin": frame_origin,
                        }
                    )
                    route.abort()

            context.route("**/*", local_only)

            def external_response(response: BrowserResponse) -> None:
                parsed_response = urlparse(response.url)
                if parsed_response.scheme in ("http", "https") and (
                    parsed_response.scheme,
                    parsed_response.netloc,
                ) != (parsed.scheme, parsed.netloc):
                    external_responses.append(
                        {"host": parsed_response.netloc, "status": response.status}
                    )

            context.on("response", external_response)
            page = context.new_page()

            def record_error(error: Error) -> None:
                errors.append(str(error).replace(password, "[REDACTED]"))

            page.on("pageerror", record_error)
            login(page, origin, "owner@browser.test", password)
            page.wait_for_function("navigator.serviceWorker.controller !== null")
            page.screenshot(path=str(output / "today-desktop.png"), full_page=True)
            no_overflow(page)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "today-mobile.png"), full_page=True)
            no_overflow(page)
            for path in ("/plans/", "/progress/", "/coach/", "/profile/", "/billing/"):
                response = page.goto(origin + path)
                assert response is not None and response.status == 200, path
                no_overflow(page)
            checks.append("desktop_mobile_navigation")
            session_url = create_session(page, origin, "Browser offline hiking")
            download_session(page, origin)
            page.locator("#offline-blocks-0-actual-distance_m").fill("5500.5")
            page.locator("#offline-blocks-0-actual-pack_kg").fill("7.25")
            context.set_offline(True)
            page.locator("button[name=mode][value=draft]").click()
            page.wait_for_function(
                "document.querySelector('#offline-status').textContent.includes('Pendiente')"
            )
            page.reload()
            assert page.evaluate("!navigator.onLine"), "Reload must actually occur offline"
            page.get_by_role("button", name="Abrir sesión", exact=True).last.click()
            assert page.locator("#offline-blocks-0-actual-pack_kg").input_value() == "7.25"
            page.locator("button[name=mode][value=complete]").click()
            page.wait_for_function(
                "window.basisPending && window.basisPending().then(count => count === 2)"
            )
            queued = sorted(
                outbox(page), key=lambda row: int(str(mapping(row["session"])["revision"]))
            )
            assert len(queued) == 2
            context.set_offline(False)
            page.locator("[data-sync-now]").click()
            page.wait_for_function(
                "document.querySelector('#offline-status').textContent.includes('Todos los registros')"
            )
            snapshot_url = session_url.replace("/sessions/", "/api/sessions/") + "snapshot/"
            snapshot = json_body(page.request.get(snapshot_url))
            result = mapping(snapshot["session"])
            assert result["status"] == "completed"
            blocks = cast(list[object], result["blocks"])
            actual = mapping(mapping(blocks[0])["actual"])
            assert actual["pack_kg"] == "7.25" and actual["distance_m"] == "5500.5"
            assert result["revision"] == 3 and len(outbox(page)) == 0
            checks.extend(
                (
                    "real_offline_reload",
                    "fractional_result_persisted",
                    "ordered_two_operation_outbox",
                    "completed_revision_three",
                )
            )
            page.screenshot(path=str(output / "offline-synced-mobile.png"), full_page=True)
            token = str(json_body(page.request.get(origin + "/api/csrf/"))["token"])
            headers = {"X-CSRFToken": token}
            replay = page.request.post(origin + "/api/sync/", data=queued[0], headers=headers)
            assert replay.status == 200
            replay_state = mapping(json_body(replay)["session"])
            assert replay_state["revision"] == 2 and replay_state["status"] == "in_progress"
            assert mapping(json_body(page.request.get(snapshot_url))["session"])["revision"] == 3
            stale = dict(queued[0])
            stale["mutation_id"] = str(uuid4())
            conflict = page.request.post(origin + "/api/sync/", data=stale, headers=headers)
            assert conflict.status == 409
            assert mapping(json_body(conflict)["current"])["revision"] == 3
            no_csrf = page.request.post(origin + "/api/sync/", data=stale)
            assert no_csrf.status == 403
            checks.extend(
                ("idempotent_replay_historical_snapshot", "stale_revision_409", "csrf_403")
            )
            observer = context.new_page()
            observer.on("pageerror", record_error)
            observer.goto(origin + "/profile/")
            page.goto(origin + "/profile/")
            with page.expect_request(
                lambda request: (
                    request.url == origin + "/accounts/logout/" and request.method == "POST"
                )
            ) as logout_request:
                page.locator("form[data-logout] button[type=submit]").click()
            assert logout_request.value.method == "POST"
            page.wait_for_url(origin + "/accounts/login/")
            observer.wait_for_url(origin + "/accounts/login/")
            logout_response = page.request.get(origin + "/api/csrf/", max_redirects=0)
            assert logout_response.status == 302, (
                "Logout left the server session authenticated: " + str(logout_response.status)
            )
            assert page.evaluate("localStorage.getItem('basis-account')") is None, (
                "Logout retained local account scope"
            )
            login(page, origin, "other@browser.test", password)
            page.goto(origin + "/offline/")
            assert page.get_by_role("button", name="Abrir sesión", exact=True).count() == 0
            assert page.request.get(snapshot_url).status == 404
            other_token = str(json_body(page.request.get(origin + "/api/csrf/"))["token"])
            assert (
                page.request.post(
                    origin + "/api/sync/", data=queued[0], headers={"X-CSRFToken": other_token}
                ).status
                == 403
            )
            checks.extend(
                (
                    "real_csrf_logout_post",
                    "other_tab_logout_redirect",
                    "logout_clears_local_account",
                    "account_switch_hides_sessions",
                    "foreign_snapshot_404",
                    "foreign_queue_403",
                )
            )
            assert not errors, "Uncaught JavaScript errors"
            assert not external_responses, "External HTTP delivery is forbidden"
            environment_injected = [
                request
                for request in external_requests
                if request["host"] == "me.kis.v2.scr.kaspersky-labs.com"
                and request["resource_type"] == "script"
                and request["frame_origin"] == origin
            ]
            unexpected_requests = [
                request for request in external_requests if request not in environment_injected
            ]
            assert not unexpected_requests, "Unexpected external browser requests: " + json.dumps(
                unexpected_requests
            )
            summary: dict[str, object] = {
                "status": "VERIFIED",
                "browser": browser.version,
                "desktop": "1440x1000",
                "mobile": "390x844",
                "checks": checks,
                "completed_revision": result["revision"],
                "javascript_errors": errors,
                "blocked_external_requests": external_requests,
                "environment_injected_blocked": {
                    "classification": "ENVIRONMENT_INJECTED_BLOCKED",
                    "exact_host": "me.kis.v2.scr.kaspersky-labs.com",
                    "attempts": len(environment_injected),
                    "resources": sorted(
                        {request["resource_type"] for request in environment_injected}
                    ),
                    "assumption": "Antivirus scripts attached to local frames, absent application source; every outside-origin request remains aborted.",
                },
                "external_responses": external_responses,
            }
            (output / "browser-result.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            return summary
        finally:
            (output / "completed-checks.json").write_text(
                json.dumps(checks, indent=2), encoding="utf-8"
            )
            (output / "external-requests.json").write_text(
                json.dumps(external_requests), encoding="utf-8"
            )
            (output / "external-responses.json").write_text(
                json.dumps(external_responses), encoding="utf-8"
            )
            browser.close()
            (output / "browser-closed.json").write_text(
                json.dumps({"browser_closed": True}), encoding="utf-8"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable")
    args = parser.parse_args()
    password = os.environ["BASIS_E2E_PASSWORD"]
    try:
        result = run(str(args.origin), Path(args.output), args.browser_executable, password)
        print(json.dumps(result))
        return 0
    except Exception as error:
        failure = {
            "status": "FAILED",
            "error": str(error).replace(password, "[REDACTED]"),
            "traceback": traceback.format_exc().replace(password, "[REDACTED]"),
        }
        (Path(args.output) / "browser-result.json").write_text(
            json.dumps(failure, indent=2), encoding="utf-8"
        )
        print(json.dumps(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
