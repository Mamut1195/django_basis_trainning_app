"""Opt-in Chromium acceptance of lost response and two independent offline clients."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import cast
from unittest import skipUnless
from uuid import UUID

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.models import Session

from . import test_pwa_browser as browser_helpers
from .factories import account, session


@skipUnless(os.environ.get("BASIS_PWA_BROWSER") == "1", "opt-in BASIS_PWA_BROWSER=1")
class OfflineDeliveryBrowserTests(StaticLiveServerTestCase):
    def login(self, page: Page, username: str) -> None:
        browser_helpers.PwaBrowserTests.login(
            cast(browser_helpers.PwaBrowserTests, self), page, username
        )

    def wait_async(self, page: Page, expression: str) -> None:
        browser_helpers.PwaBrowserTests.wait_async(
            cast(browser_helpers.PwaBrowserTests, self), page, expression
        )

    def local_records(self, page: Page) -> list[list[object]]:
        return browser_helpers.PwaBrowserTests.local_records(
            cast(browser_helpers.PwaBrowserTests, self), page
        )

    def database_state(self, session_id: UUID, mutation: str) -> tuple[int, int, int | None, int]:
        def read() -> tuple[int, int, int | None, int]:
            try:
                item = Session.objects.get(pk=session_id)
                return (
                    SyncReceipt.objects.filter(mutation_id=mutation).count(),
                    SyncReceipt.objects.count(),
                    item.duration_seconds,
                    item.revision,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(read).result()

    def prepare(self, browser: Browser, user: User, item: Session) -> tuple[BrowserContext, Page]:
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.set_default_timeout(15000)
        page = context.new_page()
        self.login(page, user.username)
        page.evaluate("() => navigator.serviceWorker.ready")
        page.reload()
        page.wait_for_function("navigator.serviceWorker.controller !== null")
        page.goto(f"{self.live_server_url}/sessions/{item.pk}/")
        page.evaluate("() => window.basisOfflineReady")
        page.locator("[data-download-session]").click()
        page.wait_for_function(
            "document.querySelector('#global-status').textContent.includes('Sesión guardada')"
        )
        context.set_offline(True)
        page.goto(self.live_server_url + "/offline/")
        return context, page

    def edit(self, page: Page, duration: int) -> None:
        page.get_by_role("button", name="Abrir sesión", exact=True).click()
        page.locator("#offline-duration_seconds").fill(str(duration))
        page.get_by_role("button", name="Guardar registro", exact=True).click()
        self.wait_async(page, "async () => (await window.basisPending()) === 1")

    def test_lost_response_retry_and_conflict_between_independent_contexts(self) -> None:
        user = account("mam632-two-clients")
        item = session(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
            )
            a, first = self.prepare(browser, user, item)
            b, second = self.prepare(browser, user, item)
            try:
                self.edit(first, 650)
                self.edit(second, 660)
                delivered: list[tuple[str, int]] = []

                def lose_response(route: Route) -> None:
                    response = route.fetch()
                    body = route.request.post_data
                    assert body is not None
                    delivered.append((body, response.status))
                    route.abort()

                a.route("**/api/sync/", lose_response)
                with first.expect_event(
                    "requestfailed", predicate=lambda req: req.url.endswith("/api/sync/")
                ):
                    a.set_offline(False)
                self.wait_async(first, "async () => !window.basisSyncing()")
                self.assertEqual(len(delivered), 1)
                self.assertEqual(delivered[0][1], 200)
                self.assertEqual(first.evaluate("() => window.basisPending()"), 1)
                mutation = json.loads(delivered[0][0])["mutation_id"]
                self.assertEqual(self.database_state(item.pk, mutation)[0], 1)
                a.unroute("**/api/sync/")
                first.locator("[data-sync-now]").click()
                self.wait_async(first, "async () => (await window.basisPending()) === 0")
                self.assertEqual(self.database_state(item.pk, mutation)[0], 1)
                _, _, duration, revision = self.database_state(item.pk, mutation)
                self.assertEqual(duration, 650)
                b.set_offline(False)
                second.locator("#sync-conflict[open]").wait_for()
                self.assertIn("660", second.locator("#conflict-local").inner_text())
                self.assertIn("650", second.locator("#conflict-remote").inner_text())
                self.assertEqual(second.evaluate("() => window.basisPending()"), 1)
                second.locator("[data-conflict=server]").click()
                self.wait_async(second, "async () => (await window.basisPending()) === 0")
                records = self.local_records(second)
                self.assertTrue(records[2])
                _, count, duration, final_revision = self.database_state(item.pk, mutation)
                self.assertEqual((duration, final_revision), (650, revision))
                self.assertEqual(count, 1)
            finally:
                a.close()
                b.close()
                browser.close()

    def test_abort_before_server_keeps_export_and_retry_is_single(self) -> None:
        user = account("mam632-abort")
        item = session(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
            )
            context, page = self.prepare(browser, user, item)
            try:
                self.edit(page, 710)
                attempted: list[dict[str, object]] = []

                def abort_before_server(route: Route) -> None:
                    body = route.request.post_data
                    assert body is not None
                    attempted.append(json.loads(body))
                    route.abort()

                context.route("**/api/sync/", abort_before_server)
                with page.expect_event(
                    "requestfailed", predicate=lambda req: req.url.endswith("/api/sync/")
                ):
                    context.set_offline(False)
                self.wait_async(page, "async () => !window.basisSyncing()")
                self.assertEqual(len(attempted), 1)
                mutation = attempted[0]["mutation_id"]
                assert isinstance(mutation, str)
                self.assertEqual(self.database_state(item.pk, mutation)[0], 0)
                self.assertEqual(page.evaluate("() => window.basisPending()"), 1)
                with page.expect_download() as info:
                    page.locator("[data-export-local]").click()
                exported = json.loads(info.value.path().read_text(encoding="utf-8"))
                self.assertEqual(exported["schema"], "basis-local-v1")
                self.assertEqual(exported["pending"][0]["mutation_id"], mutation)
                self.assertEqual(exported["pending"][0]["session"]["duration_seconds"], 710)
                self.assertEqual(exported["account"], attempted[0]["account"])
                context.unroute("**/api/sync/")
                page.locator("[data-sync-now]").click()
                self.wait_async(page, "async () => (await window.basisPending()) === 0")
                self.assertEqual(self.database_state(item.pk, mutation)[0], 1)
                self.assertEqual(self.database_state(item.pk, mutation)[2], 710)
            finally:
                context.close()
                browser.close()

    def test_conflict_can_send_local_version_after_review(self) -> None:
        user = account("mam632-choose-local")
        item = session(user)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
            )
            a, first = self.prepare(browser, user, item)
            b, second = self.prepare(browser, user, item)
            try:
                self.edit(first, 720)
                self.edit(second, 730)
                a.set_offline(False)
                self.wait_async(first, "async () => (await window.basisPending()) === 0")
                b.set_offline(False)
                second.locator("#sync-conflict[open]").wait_for()
                self.assertIn("730", second.locator("#conflict-local").inner_text())
                self.assertIn("720", second.locator("#conflict-remote").inner_text())
                second.locator("[data-conflict=local]").click()
                self.wait_async(second, "async () => (await window.basisPending()) === 0")
                _, count, duration, revision = self.database_state(
                    item.pk, "00000000-0000-0000-0000-000000000000"
                )
                self.assertEqual((count, duration, revision), (2, 730, 3))
                self.assertTrue(self.local_records(second)[2])
            finally:
                a.close()
                b.close()
                browser.close()
