"""Opt-in local Chromium acceptance; never launched by the default Django suite."""

import json
import os
import re
from pathlib import Path
from unittest import skipUnless
from urllib.parse import urlparse

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from playwright.sync_api import Page, Route, sync_playwright

from .factories import account


@skipUnless(os.environ.get("BASIS_RUNNING_BROWSER") == "1", "opt-in BASIS_RUNNING_BROWSER=1")
class RunningBrowserTests(StaticLiveServerTestCase):
    def setUp(self) -> None:
        # Deliberately fictitious disposable account; the shared factory owns access setup.
        self.owner = account("fictitious-browser-running812")

    def submit(self, page: Page) -> None:
        page.locator("form button[type=submit]").click()
        page.wait_for_url("**/sessions/*/")

    def test_manual_running_block_and_interval_responsive(self) -> None:
        output = Path(os.environ["BASIS_RUNNING_OUTPUT"])
        output.mkdir(parents=True, exist_ok=True)
        checks: list[str] = []
        errors: list[str] = []
        blocked: list[str] = []
        findings: list[str] = []
        report: dict[str, object] = {"status": "FAILED", "checks": checks, "UI_findings": findings}
        origin = self.live_server_url

        def local_only(route: Route) -> None:
            if urlparse(route.request.url).netloc == urlparse(origin).netloc:
                route.continue_()
            else:
                blocked.append(urlparse(route.request.url).netloc)
                route.abort()

        try:
            with sync_playwright() as playwright:
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
                try:
                    page.goto(origin + "/accounts/login/")
                    page.locator("input[name=username]").fill(self.owner.username)
                    page.locator("input[name=password]").fill("Example-password-824!")
                    page.locator("form button[type=submit]").click()
                    page.wait_for_url(origin + "/")
                    checks.append("Real HTTP login with fictitious factory credentials")
                    page.goto(origin + "/sessions/new/")
                    page.locator("input[name=title]").fill("Running manual ficticio 812")
                    page.locator("input[name=date]").fill(timezone.localdate().isoformat())
                    page.locator("select[name=block-sport]").select_option("running")
                    page.locator("input[name=block-title]").fill("Rodaje ficticio")
                    self.submit(page)
                    detail = page.url
                    self.assertIn("— s/km", page.locator("main").inner_text())
                    checks.append("Empty actual pace is unknown, not zero")
                    page.get_by_role("link", name="Registrar variables", exact=True).click()
                    for name, value in (
                        ("duration_seconds", "1800"),
                        ("distance_m", "5000"),
                        ("pause_seconds", "120"),
                        ("ascent_m", "0"),
                        ("descent_m", "0"),
                        ("surface", "Pista ficticia"),
                        ("session_type", "Rodaje manual"),
                    ):
                        page.locator(f"input[name={name}]").fill(value)
                    self.assertEqual(page.locator("input[name=heart_rate_bpm]").input_value(), "")
                    self.assertEqual(page.locator("input[name=cadence_spm]").input_value(), "")
                    self.submit(page)
                    self.assertEqual(
                        page.locator("dd").filter(has_text=re.compile(r"360[.,]00 s/km")).count(), 1
                    )
                    checks.append(
                        "Block elapsed pace 360.00 s/km; pause120 not subtracted; HR absent"
                    )
                    page.get_by_role("link", name="Añadir intervalo +", exact=True).click()
                    page.locator("input[name=repetitions]").fill("2")
                    page.locator("input[name=rest_seconds]").fill("0")
                    page.locator("input[name=target-duration_seconds]").fill("60")
                    page.locator("input[name=target-distance_m]").fill("400")
                    self.submit(page)
                    interval = page.locator(".card-line").filter(has_text="Intervalo 1")
                    self.assertIn("— s/km", interval.inner_text())
                    self.assertEqual(interval.locator("pre").count(), 0)
                    checks.append(
                        "Interval target does not fill actual; readable metrics, no raw JSON"
                    )
                    interval.get_by_role("link", name="Registrar resultado", exact=True).click()
                    for name, value in (
                        ("metrics-duration_seconds", "60"),
                        ("metrics-distance_m", "400"),
                        ("metrics-pause_seconds", "0"),
                        ("metrics-cadence_spm", "0"),
                        ("actual_rest_seconds", "0"),
                    ):
                        page.locator(f"input[name={name}]").fill(value)
                    self.submit(page)
                    self.assertEqual(
                        interval.locator("dd")
                        .filter(has_text=re.compile(r"150[.,]00 s/km"))
                        .count(),
                        2,
                    )
                    checks.append(
                        "Real HTTP interval edit: target and actual150.00; observed zeros kept"
                    )
                    for width, height in ((390, 844), (1440, 1000)):
                        page.set_viewport_size({"width": width, "height": height})
                        page.goto(detail)
                        # Stable selector: opening one details must not renumber the next locator.
                        for summary in page.locator("details > summary").all():
                            summary.click()
                        page.evaluate("document.fonts.ready")
                        self.assertFalse(
                            page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        )
                        text = page.locator("main").inner_text()
                        for label in (
                            "Objetivo / prescripción",
                            "Resultado real · registro manual",
                            "Ritmo derivado transcurrido",
                            "s/km",
                            "pasos/min",
                            "no se restan",
                        ):
                            self.assertIn(label, text)
                        self.assertNotIn("None", text)
                        self.assertIn("0 pasos/min", text)
                        self.assertIn("0 m", text)
                        page.screenshot(path=str(output / f"running-{width}.png"), full_page=True)
                        checks.append(
                            f"{width}px: no horizontal overflow; labels, units, null/zero"
                        )
                    self.assertFalse(errors, errors)
                    # All nonlocal requests are aborted, including environment-injected scripts.
                    report.update(
                        status="VERIFIED",
                        javascript_errors=errors,
                        blocked_external_hosts=blocked,
                        external_requests_delivered=0,
                    )
                    findings.append(
                        "390/1440px DOM and screenshots observed; objective and manual actual distinct. "
                        "No screenreader, device, GPS, sensor or offline-browser acceptance claimed."
                    )
                finally:
                    context.close()
                    browser.close()
        finally:
            (output / "browser-report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
