"""Opt-in local browser: hiking editing while disconnected and real IndexedDB outbox."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless
from urllib.parse import urlparse

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from playwright.sync_api import Route, sync_playwright

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.models import Block

from .factories import account, session
from .test_hiking import hiking_observations


@skipUnless(os.environ.get("BASIS_HIKING_BROWSER") == "1", "opt-in BASIS_HIKING_BROWSER=1")
class HikingBrowserTests(StaticLiveServerTestCase):
    def assert_database(self, block_id: int, *, saved: bool) -> None:
        # Playwright runs an event loop; keep synchronous ORM checks in another thread.
        try:
            block = Block.objects.get(pk=block_id)
            self.assertEqual(SyncReceipt.objects.count(), 1 if saved else 0)
            if not saved:
                self.assertEqual(block.actual, {})
                return
            self.assertEqual(set(block.actual), set(hiking_observations()))
            for key, value in hiking_observations().items():
                if key.startswith("difficulty_") or key == "terrain":
                    self.assertEqual(block.actual[key], value)
                else:
                    self.assertEqual(Decimal(block.actual[key]), Decimal(value))
        finally:
            connections.close_all()

    def test_disconnected_edit_queue_rejection_correction_and_acknowledgement(self) -> None:
        owner = account("fictitious-browser-hiking819")
        item = session(owner, sport="hiking")
        block = item.blocks.get()
        output = Path(os.environ["BASIS_HIKING_OUTPUT"])
        output.mkdir(parents=True, exist_ok=True)
        checks: list[str] = []
        errors: list[str] = []
        blocked: list[str] = []
        delivered_external: list[str] = []
        report: dict[str, object] = {
            "status": "FAILED",
            "checks": checks,
            "javascript_errors": errors,
            "blocked_external_hosts": blocked,
            "delivered_external_responses": delivered_external,
        }
        origin = self.live_server_url

        def local_only(route: Route) -> None:
            if urlparse(route.request.url).netloc == urlparse(origin).netloc:
                route.continue_()
            else:
                blocked.append(urlparse(route.request.url).netloc)
                route.abort()

        try:
            with ThreadPoolExecutor(max_workers=1) as executor, sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
                )
                report["browser_version"] = browser.version
                context = browser.new_context(
                    viewport={"width": 390, "height": 844}, service_workers="block"
                )
                context.route("**/*", local_only)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "response",
                    lambda response: (
                        delivered_external.append(response.url)
                        if urlparse(response.url).netloc != urlparse(origin).netloc
                        else None
                    ),
                )
                try:
                    page.goto(origin + "/accounts/login/")
                    page.locator("input[name=username]").fill(owner.username)
                    page.locator("input[name=password]").fill("Example-password-824!")
                    page.locator("form button[type=submit]").click()
                    page.wait_for_url(origin + "/")
                    page.goto(f"{origin}/sessions/{item.pk}/")
                    page.evaluate("() => window.basisOfflineReady")
                    page.locator("[data-download-session]").click()
                    page.wait_for_function(
                        "document.querySelector('#global-status').textContent.includes('Sesión guardada')"
                    )
                    page.goto(origin + "/offline/")
                    page.evaluate("() => window.basisOfflineReady")
                    page.get_by_role("button", name="Abrir sesión", exact=True).wait_for()
                    context.set_offline(True)
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    page.locator("details.offline-details > summary").click()
                    for key, value in hiking_observations().items():
                        page.locator(f'input[data-path=\'["blocks",0,"actual","{key}"]\']').fill(
                            value
                        )
                    pack = page.locator("#offline-blocks-0-actual-pack_kg")
                    self.assertEqual(pack.get_attribute("step"), "any")
                    # A cross-field error is retained locally until the server can validate it.
                    page.locator("#offline-blocks-0-actual-descent_m").fill("700.14")
                    page.get_by_role("button", name="Guardar registro", exact=True).click()
                    page.wait_for_function(
                        "document.querySelector('#offline-sessions').textContent.includes('Pendiente de sincronizar')"
                    )
                    executor.submit(self.assert_database, block.pk, saved=False).result()
                    checks.append(
                        "Disconnected edit saved to IndexedDB; no server write or receipt"
                    )
                    context.set_offline(False)
                    page.locator("[data-sync-now]").click()
                    page.wait_for_function(
                        "document.querySelector('#offline-sessions').textContent.includes('Ascenso menos descenso')"
                    )
                    executor.submit(self.assert_database, block.pk, saved=False).result()
                    checks.append(
                        "Reconnection rejects inconsistent elevation and preserves pending edit"
                    )
                    page.get_by_role("button", name="Abrir sesión", exact=True).click()
                    self.assertEqual(pack.input_value(), "6.25")
                    page.locator("#offline-blocks-0-actual-descent_m").fill("700.15")
                    with page.expect_response(
                        lambda response: (
                            response.url == origin + "/api/sync/" and response.status == 200
                        )
                    ):
                        page.get_by_role("button", name="Guardar registro", exact=True).click()
                    page.wait_for_function(
                        "!document.querySelector('#offline-sessions').textContent.includes('Pendiente de sincronizar')"
                    )
                    executor.submit(self.assert_database, block.pk, saved=True).result()
                    checks.append(
                        "Corrected queued data acknowledged once; decimal pack and all fields persisted"
                    )
                    self.assertFalse(errors, errors)
                    # Host antivirus may inject requests; the route must deliver none externally.
                    self.assertFalse(delivered_external, delivered_external)
                    report["status"] = "VERIFIED"
                finally:
                    context.close()
                    browser.close()
        finally:
            (output / "browser-report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
