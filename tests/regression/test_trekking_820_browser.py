"""Opt-in local HTML smoke for trekking stage correction."""

import os
from pathlib import Path
from unittest import skipUnless
from urllib.parse import urlparse

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from basis.modules.training.adapters.models import TrekStage, TrekTrip

from .factories import account, session


@skipUnless(os.getenv("BASIS_TREK_BROWSER") == "1", "opt-in browser smoke")
class TrekkingBrowserSmoke(StaticLiveServerTestCase):
    def test_edit_and_render(self) -> None:
        owner = account("trek-browser820")
        item = session(owner, sport="hiking")
        trip = TrekTrip.objects.create(owner=owner, title="Recorrido ficticio")
        stage = TrekStage.objects.create(trip=trip, session=item, order=1)
        output = Path(os.environ["BASIS_TREK_OUTPUT"])
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
            )
            context = browser.new_context(
                viewport={"width": 390, "height": 844}, service_workers="block"
            )
            context.route(
                "**/*",
                lambda route: (
                    route.continue_()
                    if urlparse(route.request.url).netloc == urlparse(self.live_server_url).netloc
                    else route.abort()
                ),
            )
            page = context.new_page()
            errors = []
            static_status = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "response",
                lambda response: (
                    static_status.append(response.status) if "/static/" in response.url else None
                ),
            )
            page.goto(self.live_server_url + "/accounts/login/")
            page.locator("input[name=username]").fill(owner.username)
            page.locator("input[name=password]").fill("Example-password-824!")
            page.locator("form button[type=submit]").click()
            page.wait_for_url(self.live_server_url + "/")
            response = page.goto(
                f"{self.live_server_url}/trekking/{trip.pk}/stages/{stage.pk}/edit/"
            )
            assert response is not None
            self.assertEqual(response.status, 200)
            page.locator("[name=overnight_altitude_m]").fill("2350.25")
            page.locator("[name=recovery_notes]").fill("Descanso ficticio")
            page.locator("form button[type=submit]").click()
            page.wait_for_url(f"{self.live_server_url}/trekking/{trip.pk}/")
            self.assertTrue(page.get_by_text("Descanso ficticio").is_visible())
            page.screenshot(path=str(output / "trekking-mobile.png"), full_page=False)
            page.get_by_text("Descanso ficticio").scroll_into_view_if_needed()
            page.screenshot(path=str(output / "trekking-stage-mobile.png"), full_page=False)
            self.assertTrue(static_status)
            self.assertTrue(all(status == 200 for status in static_status), static_status)
            self.assertFalse(errors, errors)
            context.close()
            browser.close()
