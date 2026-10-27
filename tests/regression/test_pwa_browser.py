"""Opt-in real PWA lifecycle in Chromium; no providers or physical-device claims."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import cast
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse
from django.test import override_settings
from django.urls import URLPattern, URLResolver, include, path
from playwright.sync_api import Page, sync_playwright

GENERATION = 0


def versioned_worker(request: HttpRequest) -> HttpResponse:
    from basis.adapters.web.platform_views import service_worker

    response = service_worker(request)
    response.content = response.content.replace(
        b"basis-shell-", f"basis-shell-browser-{GENERATION}-".encode(), 1
    )
    return response


urlpatterns: list[URLPattern | URLResolver] = []


@skipUnless(os.environ.get("BASIS_PWA_BROWSER") == "1", "opt-in BASIS_PWA_BROWSER=1")
@override_settings(ROOT_URLCONF=__name__)
class PwaBrowserTests(StaticLiveServerTestCase):
    def wait_async(self, page: Page, expression: str) -> None:
        # Playwright's RAF predicate treats a Promise as truthy; await it explicitly.
        page.evaluate(
            """async expression => {
          const predicate = new Function('return (' + expression + ')')();
          const deadline = Date.now() + 15000;
          while (!(await predicate())) {
            if (Date.now() > deadline) throw Error('Async predicate timed out: ' + expression);
            await new Promise(resolve => setTimeout(resolve, 50));
          }
        }""",
            expression,
        )

    def blocked_update(self, page: Page) -> None:
        page.evaluate("""async () => {
          const registration = await navigator.serviceWorker.getRegistration();
          await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(Error('Update coordination timed out')), 10000);
            const listener = event => {
              if(event.data?.type !== 'RELEASE_UPDATE') return;
              clearTimeout(timeout);
              navigator.serviceWorker.removeEventListener('message', listener);
              resolve();
            };
            navigator.serviceWorker.addEventListener('message', listener);
            registration.waiting.postMessage({type:'ACTIVATE'});
          });
        }""")

    def login(self, page: Page, username: str) -> None:
        page.goto(self.live_server_url + "/accounts/login/")
        page.locator("input[name=username]").fill(username)
        page.locator("input[name=password]").fill("Example-password-824!")
        page.locator("form button[type=submit]").click()
        page.wait_for_url(self.live_server_url + "/")
        page.evaluate("() => window.basisOfflineReady")

    def local_records(self, page: Page) -> list[list[object]]:
        return cast(
            list[list[object]],
            page.evaluate("""async () => {
          const db = await new Promise((resolve, reject) => {
            const request = indexedDB.open('basis-offline-v1');
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
          });
          try {
            return await Promise.all(['sessions', 'outbox', 'archive'].map(name =>
              new Promise((resolve, reject) => {
                const request = db.transaction(name).objectStore(name).getAll();
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
              })));
          } finally { db.close(); }
        }"""),
        )

    def test_offline_reload_accounts_and_safe_multitab_update(self) -> None:
        global GENERATION, urlpatterns
        from .factories import account, session

        urlpatterns = [
            path("service-worker.js", versioned_worker),
            path("", include("config.urls")),
        ]
        GENERATION = 0
        first, other = account("pwa-browser-a"), account("pwa-browser-b")
        item = session(first)
        item.title = "Sesión privada ficticia A"
        item.save()
        other_item = session(other)
        extra_ids = [session(first).pk for _ in range(20)]
        output = Path(os.environ["BASIS_PWA_OUTPUT"])
        checks: list[str] = []
        errors: list[str] = []
        report: dict[str, object] = {"status": "FAILED", "checks": checks, "errors": errors}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
                )
                report["browser_version"] = browser.version
                context = browser.new_context(viewport={"width": 390, "height": 844})
                context.set_default_timeout(15000)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    self.login(page, first.username)
                    page.evaluate("() => navigator.serviceWorker.ready")
                    page.reload()
                    page.wait_for_function("navigator.serviceWorker.controller !== null")
                    page.goto(f"{self.live_server_url}/sessions/{item.pk}/")
                    page.evaluate("() => window.basisOfflineReady")
                    page.locator("[data-download-session]").click()
                    page.wait_for_function(
                        "document.querySelector('#global-status').textContent.includes('Sesión guardada')"
                    )
                    checks.append(
                        "Real login and explicit session download; local shell controlled"
                    )
                    # Exercise capacity through real HTTP downloads and UI deletion.
                    for extra_id in extra_ids:
                        page.goto(f"{self.live_server_url}/sessions/{extra_id}/")
                        page.evaluate("() => window.basisOfflineReady")
                        page.locator("[data-download-session]").click()
                        page.wait_for_function("""() => {
                          const text = document.querySelector('#global-status').textContent;
                          return text.includes('Sesión guardada') || text.includes('Límite local');
                        }""")
                    self.assertIn("Límite local", page.locator("#global-status").inner_text())
                    page.goto(self.live_server_url + "/offline/")
                    page.wait_for_function(
                        "document.querySelectorAll('.offline-row').length === 20"
                    )
                    for remaining in range(19, 0, -1):
                        page.locator(".offline-row").filter(
                            has_not_text=item.title
                        ).first.get_by_role("button", name="Eliminar copia descargada").click()
                        page.wait_for_function(
                            "n => document.querySelectorAll('.offline-row').length === n",
                            arg=remaining,
                        )
                    checks.append(
                        "20 real downloads accepted; 21st refused; synchronized copies removable"
                    )
                    await_cache = """async () => {
                      const keys = await caches.keys();
                      const urls = (await Promise.all(keys.map(async key =>
                        (await (await caches.open(key)).keys()).map(r => new URL(r.url).pathname)
                      ))).flat();
                      return urls.every(url => url.startsWith('/static/') || url === '/offline/');
                    }"""
                    self.assertTrue(page.evaluate(await_cache))
                    checks.append(
                        "CacheStorage contains public assets only, no private HTML or API"
                    )
                    context.set_offline(True)
                    page.goto(self.live_server_url + "/offline/")
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    page.locator("#offline-duration_seconds").fill("650")
                    page.locator("#offline-reported_rpe").fill("6")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    self.wait_async(page, "async () => (await window.basisPending()) === 1")
                    page.reload()
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    self.assertEqual(page.locator("#offline-duration_seconds").input_value(), "650")
                    # A real correction also gives archive content to protect at login.
                    page.locator("#offline-duration_seconds").fill("649")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    page.locator("#offline-duration_seconds").fill("650")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    self.wait_async(page, "async () => (await window.basisPending()) === 1")
                    page.screenshot(path=str(output / "offline-reloaded.png"), full_page=True)
                    checks.append(
                        "Network disabled: shell reload, edit, durable queue and restored value"
                    )
                    # Keep a pending operation while the real worker update installs.
                    context.route("**/api/sync/", lambda route: route.abort())
                    context.set_offline(False)
                    page.reload()
                    page.evaluate("() => window.basisOfflineReady")
                    self.wait_async(page, "async () => !window.basisSyncing()")
                    before_login = self.local_records(page)
                    self.assertTrue(all(before_login))
                    identity = page.evaluate("localStorage.getItem('basis-account')")
                    page.goto(self.live_server_url + "/accounts/login/")
                    page.evaluate("() => window.basisOfflineReady")
                    self.assertEqual(self.local_records(page), before_login)
                    self.assertEqual(
                        page.evaluate("localStorage.getItem('basis-account')"), identity
                    )
                    self.login(page, first.username)
                    self.wait_async(page, "async () => !window.basisSyncing()")
                    self.assertEqual(self.local_records(page), before_login)
                    checks.append(
                        "Pending sessions/outbox/archive survive login and same-account return"
                    )
                    context.clear_cookies()
                    page.goto(self.live_server_url + "/offline/")
                    page.evaluate("() => window.basisOfflineReady")
                    self.assertEqual(self.local_records(page), before_login)
                    self.assertEqual(
                        page.evaluate("localStorage.getItem('basis-account')"), identity
                    )
                    self.assertEqual(page.evaluate("() => window.basisPending()"), 0)
                    self.assertNotIn(item.title, page.locator("#offline-sessions").inner_text())
                    self.login(page, first.username)
                    self.wait_async(page, "async () => !window.basisSyncing()")
                    self.assertEqual(self.local_records(page), before_login)
                    checks.append(
                        "Expired session cookie preserves all stores without exposing them online"
                    )
                    page.goto(self.live_server_url + "/offline/")
                    page.evaluate("() => window.basisOfflineReady")
                    GENERATION = 1
                    page.evaluate("async () => (await navigator.serviceWorker.ready).update()")
                    self.wait_async(
                        page,
                        """async () => {
                          const registration = await navigator.serviceWorker.getRegistration();
                          return registration.waiting?.state === 'installed';
                        }""",
                    )
                    report["worker_before_update"] = page.evaluate("""async () => {
                      const r = await navigator.serviceWorker.getRegistration();
                      return {active:r.active?.state, waiting:r.waiting?.state,
                        installing:r.installing?.state, controller:!!navigator.serviceWorker.controller};
                    }""")
                    self.blocked_update(page)
                    self.assertEqual(page.evaluate("() => window.basisPending()"), 1)
                    self.assertTrue(
                        page.evaluate(
                            "async () => !!(await navigator.serviceWorker.getRegistration()).waiting"
                        )
                    )
                    checks.append("Waiting worker refuses activation with a durable pending record")
                    context.unroute("**/api/sync/")
                    page.locator("[data-sync-now]").click()
                    self.wait_async(page, "async () => (await window.basisPending()) === 0")
                    second = context.new_page()
                    second.on("pageerror", lambda error: errors.append(str(error)))
                    second.goto(self.live_server_url + "/offline/")
                    second.get_by_role("button", name="Abrir sesión", exact=True).click()
                    second.locator("#offline-duration_seconds").fill("651")
                    self.blocked_update(page)
                    self.assertEqual(
                        second.locator("#offline-duration_seconds").input_value(), "651"
                    )
                    self.assertTrue(
                        page.evaluate(
                            "async () => !!(await navigator.serviceWorker.getRegistration()).waiting"
                        )
                    )
                    checks.append("Another tab's open editor blocks update and keeps unsaved input")
                    second.close()
                    page.evaluate("localStorage.setItem('basis-timer', String(Date.now()+60000))")
                    self.blocked_update(page)
                    self.assertTrue(
                        page.evaluate(
                            "async () => !!(await navigator.serviceWorker.getRegistration()).waiting"
                        )
                    )
                    checks.append("Active rest timer blocks update")
                    page.evaluate("localStorage.removeItem('basis-timer')")
                    with page.expect_navigation():
                        page.evaluate(
                            "async () => (await navigator.serviceWorker.getRegistration()).waiting.postMessage({type:'ACTIVATE'})"
                        )
                    page.evaluate("() => window.basisOfflineReady")
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    self.assertEqual(page.locator("#offline-duration_seconds").input_value(), "650")
                    checks.append(
                        "Safe worker activation reloads and preserves the synchronized session"
                    )
                    context.route("**/api/sync/", lambda route: route.abort())
                    context.set_offline(True)
                    page.locator("#offline-duration_seconds").fill("652")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    self.wait_async(page, "async () => (await window.basisPending()) === 1")
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    page.locator("#offline-duration_seconds").fill("653")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    self.wait_async(page, "async () => (await window.basisPending()) === 1")
                    context.set_offline(False)
                    stale = context.new_page()
                    stale.goto(self.live_server_url + "/offline/")
                    stale.get_by_role("button", name="Abrir sesión", exact=True).click()
                    self.login(page, other.username)
                    stale.wait_for_url("**/accounts/login/")
                    page.goto(self.live_server_url + "/offline/")
                    page.evaluate("() => window.basisOfflineReady")
                    self.assertNotIn(item.title, page.locator("#offline-sessions").inner_text())
                    self.assertEqual(page.evaluate("() => window.basisPending()"), 0)
                    counts = page.evaluate("""async () => {
                      const db = await new Promise((resolve,reject) => {
                        const r=indexedDB.open('basis-offline-v1');
                        r.onsuccess=()=>resolve(r.result); r.onerror=()=>reject(r.error);
                      });
                      try {
                        return await Promise.all(['sessions','outbox','archive'].map(name =>
                          new Promise((resolve,reject)=> {
                            const r=db.transaction(name).objectStore(name).count();
                            r.onsuccess=()=>resolve(r.result); r.onerror=()=>reject(r.error);
                          })));
                      } finally {db.close();}
                    }""")
                    self.assertEqual(counts, [0, 0, 0])
                    checks.append(
                        "Account switch purges old data and invalidates an old account tab"
                    )
                    stale.close()
                    page.goto(f"{self.live_server_url}/sessions/{other_item.pk}/")
                    page.evaluate("() => window.basisOfflineReady")
                    page.locator("[data-download-session]").click()
                    page.wait_for_function(
                        "document.querySelector('#global-status').textContent.includes('Sesión guardada')"
                    )
                    context.set_offline(True)
                    page.goto(self.live_server_url + "/offline/")
                    for duration in ("660", "661"):
                        page.get_by_role("button", name="Abrir sesión", exact=True).click()
                        page.locator("#offline-duration_seconds").fill(duration)
                        page.get_by_role("button", name="Guardar registro", exact=True).click()
                        self.wait_async(page, "async () => (await window.basisPending()) === 1")
                    self.assertTrue(all(self.local_records(page)))
                    context.set_offline(False)
                    page.goto(self.live_server_url + "/profile/")
                    page.locator("[data-logout] button").click()
                    page.wait_for_url("**/accounts/login/")
                    page.evaluate("() => window.basisOfflineReady")
                    self.assertEqual(page.evaluate("localStorage.getItem('basis-account')"), "")
                    context.set_offline(True)
                    page.goto(self.live_server_url + "/offline/")
                    page.evaluate("() => window.basisOfflineReady")
                    self.assertNotIn(item.title, page.locator("#offline-sessions").inner_text())
                    checks.append(
                        "Logout followed by offline reload exposes no prior account session"
                    )
                    self.assertFalse(errors, errors)
                    report["status"] = "VERIFIED"
                finally:
                    context.close()
                    browser.close()
        finally:
            (output / "browser-report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )


if __name__ == "__main__":
    import django

    django.setup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=False)
    if not arguments.browser_executable.is_file():
        raise FileNotFoundError(arguments.browser_executable)
    os.environ["BASIS_PWA_BROWSER"] = "1"
    os.environ["BASIS_PWA_OUTPUT"] = str(arguments.output.resolve())
    os.environ["BROWSER_EXECUTABLE"] = str(arguments.browser_executable.resolve())
    call_command("test", "tests.regression.test_pwa_browser", interactive=False, verbosity=2)
