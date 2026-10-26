"""Opt-in local Chromium swimming flow; artifacts belong to the scoped runner output."""

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


@skipUnless(os.environ.get("BASIS_SWIMMING_BROWSER") == "1", "opt-in BASIS_SWIMMING_BROWSER=1")
class SwimmingBrowserTests(StaticLiveServerTestCase):
    def setUp(self) -> None:
        self.owner = account("fictitious-browser-swimming814")

    def submit(self, page: Page) -> None:
        page.locator("form button[type=submit]").click()
        page.wait_for_url("**/sessions/*/")

    def test_manual_swimming_block_and_interval_responsive(self) -> None:
        # The bounded runner expands {OUTPUT}; do not hardcode or invent an evidence directory.
        output = Path(os.environ["BASIS_SWIMMING_OUTPUT"])
        output.mkdir(parents=True, exist_ok=True)
        checks: list[str] = []
        errors: list[str] = []
        blocked: list[str] = []
        report: dict[str, object] = {
            "status": "FAILED",
            "checks": checks,
            "javascript_errors": errors,
            "blocked_external_hosts": blocked,
            "external_requests_delivered": 0,
        }
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
                    checks.append("Real local HTTP login, fictitious factory account")
                    page.goto(origin + "/sessions/new/")
                    page.locator("input[name=title]").fill("Natación manual ficticia 814")
                    page.locator("input[name=date]").fill(timezone.localdate().isoformat())
                    page.locator("select[name=block-sport]").select_option("swimming")
                    page.locator("input[name=block-title]").fill("Piscina ficticia")
                    self.submit(page)
                    detail = page.url
                    self.assertIn("— s/100 m", page.locator("main").inner_text())
                    checks.append("Created swimming session: absent actual pace is unknown")
                    page.get_by_role("link", name="Registrar variables", exact=True).click()
                    for name, value in (
                        ("duration_seconds", "1200"),
                        ("distance_m", "800"),
                        ("pool_length_m", "25"),
                        ("laps", "31"),
                        ("strokes", "0"),
                        ("stroke", "Crol propio"),
                        ("drill", "Remadas ficticias"),
                    ):
                        page.locator(f"input[name={name}]").fill(value)
                    self.assertEqual(page.locator("input[name=heart_rate_bpm]").input_value(), "")
                    self.submit(page)
                    self.assertEqual(
                        page.locator("dd")
                        .filter(has_text=re.compile(r"150[.,]00 s/100 m"))
                        .count(),
                        1,
                    )
                    checks.append(
                        "Block 1200s/800m =150.00; 31 laps do not override distance; HR absent"
                    )
                    page.get_by_role("link", name="Añadir intervalo +", exact=True).click()
                    for name, value in (
                        ("repetitions", "4"),
                        ("rest_seconds", "60"),
                        ("target-duration_seconds", "100"),
                        ("target-distance_m", "50"),
                    ):
                        page.locator(f"input[name={name}]").fill(value)
                    self.submit(page)
                    interval = page.locator(".card-line").filter(has_text="Intervalo 1")
                    self.assertIn("— s/100 m", interval.inner_text())
                    self.assertEqual(interval.locator("pre").count(), 0)
                    checks.append("Interval target does not fill unknown actual; no raw JSON")
                    interval.get_by_role("link", name="Registrar resultado", exact=True).click()
                    for name, value in (
                        ("metrics-duration_seconds", "120"),
                        ("metrics-distance_m", "50"),
                        ("metrics-strokes", "0"),
                        ("actual_rest_seconds", "30"),
                    ):
                        page.locator(f"input[name={name}]").fill(value)
                    self.submit(page)
                    self.assertEqual(
                        interval.locator("dd")
                        .filter(has_text=re.compile(r"240[.,]00 s/100 m"))
                        .count(),
                        1,
                    )
                    checks.append("Interval actual 120s/50m =240.00; rest30 not subtracted")
                    # Reopen through HTTP to check persisted values, not only submitted DOM state.
                    interval.get_by_role("link", name="Registrar resultado", exact=True).click()
                    for name, value in (
                        ("metrics-duration_seconds", "120"),
                        ("metrics-strokes", "0"),
                        ("rest_seconds", "60"),
                        ("actual_rest_seconds", "30"),
                    ):
                        self.assertEqual(page.locator(f"input[name={name}]").input_value(), value)
                    self.assertEqual(
                        page.locator("input[name=metrics-heart_rate_bpm]").input_value(), ""
                    )
                    checks.append(
                        "Reopened persisted interval: distinct rests60/30, zero strokes, HR blank"
                    )
                    for width, height in ((390, 844), (1440, 1000)):
                        page.set_viewport_size({"width": width, "height": height})
                        page.goto(detail)
                        for summary in page.locator("details > summary").all():
                            summary.click()
                        page.evaluate("document.fonts.ready")
                        self.assertFalse(
                            page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        )
                        for expected in ("150", "200", "240"):
                            self.assertEqual(
                                page.locator("dd")
                                .filter(has_text=re.compile(rf"{expected}[.,]00 s/100 m"))
                                .count(),
                                1,
                            )
                        text = page.locator("main").inner_text()
                        for label in (
                            "Objetivo / prescripción",
                            "Resultado real · registro manual",
                            "Ritmo derivado transcurrido",
                            "no se restan",
                            "totales del bloque son autoritativos",
                            "no se suman de nuevo",
                            "No se infiere distancia",
                            "0",
                            "4 repeticiones",
                        ):
                            self.assertIn(label, text)
                        self.assertNotIn("None", text)
                        page.screenshot(path=str(output / f"swimming-{width}.png"), full_page=True)
                        checks.append(
                            f"{width}px: separate block/interval target/actual pace; no overflow"
                        )
                    self.assertFalse(errors, errors)
                    report.update(
                        status="VERIFIED",
                        UI_findings=[
                            "390/1440 DOM and screenshots captured; manual target/actual and units distinct. "
                            "Screenshots require independent visual review; no screenreader or device seal."
                        ],
                    )
                finally:
                    context.close()
                    browser.close()
        finally:
            (output / "browser-report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
