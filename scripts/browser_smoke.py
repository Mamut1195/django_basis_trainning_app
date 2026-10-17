"""Run against the isolated demo database; never a deployed environment."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

origin = "http://127.0.0.1:8765"
output = Path("artifacts/browser")
output.mkdir(parents=True, exist_ok=True)
password = os.environ["BASIS_E2E_PASSWORD"]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.getenv("BROWSER_EXECUTABLE"), headless=True
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(origin + "/accounts/login/")
    page.locator("input[name=username]").fill(os.getenv("BASIS_E2E_EMAIL", "demo@basis.test"))
    page.locator("input[name=password]").fill(password)
    page.locator("form button[type=submit]").click()
    page.wait_for_url(origin + "/")
    page.wait_for_function("navigator.serviceWorker.controller !== null")
    page.screenshot(path=str(output / "today-desktop.png"), full_page=True)
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(output / "today-mobile.png"), full_page=True)
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    for path in ("/plans/", "/progress/", "/coach/", "/profile/", "/billing/"):
        response = page.goto(origin + path)
        assert response.status == 200, (path, response.status)
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), path
    page.goto(origin + "/sessions/new/")
    page.locator("input[name=title]").fill("Browser: salida de hiking")
    page.locator("input[name=duration_seconds]").fill("3600")
    page.locator("input[name=reported_rpe]").fill("5")
    page.locator("select[name=block-sport]").select_option("hiking")
    page.locator("input[name=block-title]").fill("Etapa uno")
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/sessions/*/")
    session_url = page.url
    page.locator("[data-download-session]").click()
    page.wait_for_function(
        "document.querySelector('#global-status')?.textContent.includes('Sesión guardada')"
    )
    page.goto(origin + "/offline/")
    page.get_by_role("button", name="Abrir sesión", exact=True).last.click()
    page.locator("#offline-blocks-0-actual-distance_m").fill("5500.5")
    page.locator("#offline-blocks-0-actual-pack_kg").fill("7.25")
    context.set_offline(True)
    page.locator("button[name=mode][value=draft]").click()
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('Pendiente')"
    )
    # The navigation must use the generic cached shell, without fetching private HTML.
    page.reload()
    page.get_by_role("button", name="Abrir sesión", exact=True).last.click()
    assert page.locator("#offline-blocks-0-actual-pack_kg").input_value() == "7.25"
    page.locator("button[name=mode][value=complete]").click()
    context.set_offline(False)
    page.locator("[data-sync-now]").click()
    page.wait_for_function(
        "document.querySelector('#offline-status').textContent.includes('Todos los registros')"
    )
    result = page.request.get(
        session_url.replace("/sessions/", "/api/sessions/") + "snapshot/"
    ).json()["session"]
    assert result["status"] == "completed", result
    assert result["blocks"][0]["actual"]["pack_kg"] == "7.25"
    assert result["revision"] == 3, result
    page.screenshot(path=str(output / "offline-synced-mobile.png"), full_page=True)
    assert not errors, errors
    summary = {
        "browser": "Chromium / Edge",
        "desktop": "1440x1000",
        "mobile": "390x844",
        "offline_reload": True,
        "fractional_pack": True,
        "ordered_outbox": True,
        "completed_revision": result["revision"],
        "javascript_errors": errors,
    }
    (output / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    browser.close()
