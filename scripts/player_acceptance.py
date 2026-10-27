"""MAM-628 mobile acceptance against a fresh local DB; no external services."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import threading
import traceback
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

from playwright.sync_api import Route, expect, sync_playwright

from scripts.acceptance_browser import ROOT, child_environment, execute, source_binding
from scripts.browser_smoke import login, no_overflow


def fixture() -> str:
    from django.contrib.auth.models import User

    from basis.adapters.django.acceptance_fixture import prepare
    from basis.modules.training.adapters.models import Block, Session, StrengthSet
    from tests.regression.factories import exercise

    prepare()
    owner = User.objects.get(username="owner@browser.test")
    item = Session.objects.create(owner=owner, title="Sesión ficticia MAM628")
    block = Block.objects.create(session=item, sport="strength", title="Fuerza ficticia")
    movement = exercise()
    for order in (1, 2):
        StrengthSet.objects.create(
            block=block,
            exercise=movement,
            order=order,
            target_reps=8,
            target_kg=40,
            target_rpe=7,
            rest_seconds=90,
        )
    return str(item.pk)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # No HTTP/session/header/form logging. Assertions and screenshots are evidence.
        pass


def run(output: Path, executable: str) -> int:
    output = output.resolve()
    allowed = ROOT.parent.parent / "basis-runs" / "MAM-628"
    if not output.is_relative_to(allowed.resolve()):
        raise ValueError("Evidence must stay in the authorized MAM-628 run")
    output.mkdir(exist_ok=False)
    cache = ROOT / ".cache" / ("mam628-browser-" + uuid4().hex)
    cache.mkdir(exist_ok=False)
    password, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    environment = child_environment(cache / "player.sqlite3", password, secret)
    before = source_binding()
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result: dict[str, object] = {
        "status": "FAILED",
        "providers": "DISABLED",
        "smtp": "DISABLED",
        "source_before": before,
        "script_sha256": script_hash,
        "python": sys.version.split()[0],
        "playwright": version("playwright"),
    }
    server_thread: threading.Thread | None = None
    try:
        execute(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "0"],
            environment,
            output / "migrate.log",
            timeout=90,
        )
        os.environ.update(environment)
        import django

        django.setup()
        session_id = fixture()
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.core.wsgi import get_wsgi_application

        app = StaticFilesHandler(get_wsgi_application())
        with make_server("127.0.0.1", 0, app, handler_class=QuietHandler) as server:
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            origin = f"http://127.0.0.1:{server.server_port}"
            try:
                with sync_playwright() as tool:
                    browser = tool.chromium.launch(
                        executable_path=executable, headless=True, timeout=15000
                    )
                    try:
                        result["chromium"] = browser.version
                        context = browser.new_context(
                            viewport={"width": 390, "height": 844}, service_workers="block"
                        )
                        context.set_default_timeout(10000)
                        context.set_default_navigation_timeout(15000)
                        result["stage"] = "login and today"
                        errors: list[str] = []
                        external: list[str] = []

                        def guard(route: Route) -> None:
                            if route.request.url.startswith(origin + "/"):
                                route.continue_()
                            else:
                                external.append(route.request.url.split("?")[0])
                                route.abort()

                        context.route("**/*", guard)
                        # Install before navigation so application timers use one clock.
                        context.clock.install()
                        page = context.new_page()
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("dialog", lambda dialog: dialog.accept())
                        login(page, origin, "owner@browser.test", password)
                        expect(
                            page.get_by_role("link", name="Continuar sesión", exact=True)
                        ).to_be_visible()
                        no_overflow(page)
                        page.screenshot(path=str(output / "today-390-light.png"), full_page=True)
                        page.get_by_role("link", name="Continuar sesión", exact=True).click()
                        quick = page.locator("[data-quick-set]").first
                        kg = quick.locator("[name=actual_kg]")
                        reps = quick.locator("[name=actual_reps]")
                        rpe = quick.locator("[name=actual_rpe]")
                        expect(kg).to_have_value("")
                        expect(reps).to_have_value("")
                        expect(rpe).to_have_value("")
                        result["stage"] = "autosave and reload"
                        kg.fill("37.25")
                        reps.fill("7")
                        rpe.fill("8.5")
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        page.reload()
                        expect(kg).to_have_value("37.25")
                        expect(reps).to_have_value("7")
                        kg.fill("38.5")
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        result["stage"] = "undo and validation"
                        quick.locator("[data-player-undo]").click()
                        expect(kg).to_have_value("37.25")
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        rpe.fill("11")
                        assert not rpe.evaluate("e => e.checkValidity()")
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Cambios pendientes de guardar."
                        )
                        rpe.fill("8.5")
                        kg.fill("0")
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        page.get_by_role("button", name="Siguiente", exact=True).click()
                        expect(page.locator("[data-player-row]").nth(1)).to_be_visible()
                        expect(
                            page.locator("[data-quick-set]").nth(1).locator("[name=actual_kg]")
                        ).to_have_value("")
                        page.get_by_role("button", name="Anterior", exact=True).click()
                        expect(kg).to_have_value("0.00")
                        # Timestamp oracle independent of the displayed countdown: advance wall clock.
                        result["stage"] = "timestamp suspension and reload"
                        # Python pause_at takes Unix seconds; Date.now() returns milliseconds.
                        page.clock.pause_at(page.evaluate("Date.now()") / 1000)
                        timer_now = page.evaluate("Date.now()")
                        account_key = page.locator("body").get_attribute("data-account")
                        assert account_key
                        timer_key = "basis-rest:" + account_key
                        quick.get_by_role(
                            "button", name="Iniciar descanso prescrito", exact=True
                        ).click()
                        expect(page.locator("[data-timer-output]")).to_have_text("01:30")
                        deadline = page.evaluate("key => localStorage.getItem(key)", timer_key)
                        assert deadline is not None
                        assert int(deadline) - timer_now == 90000
                        page.clock.fast_forward(31000)
                        assert page.evaluate("Date.now()") == timer_now + 31000
                        expect(page.locator("[data-timer-output]")).to_have_text("00:59")
                        page.reload()
                        assert page.locator("body").get_attribute("data-account") == account_key
                        assert page.evaluate("Date.now()") == timer_now + 31000
                        assert (
                            page.evaluate("key => localStorage.getItem(key)", timer_key) == deadline
                        )
                        expect(page.locator("[data-timer-output]")).to_have_text("00:59")
                        result["timer_reload"] = {
                            "status": "VERIFIED",
                            "elapsed_ms": 31000,
                            "remaining_seconds": 59,
                            "same_account_key_and_deadline": True,
                        }
                        # A fresh tab loses sessionStorage; localStorage must retain the deadline.
                        result["stage"] = "timer tab closure and reopen"
                        player_url = page.url
                        page.close()
                        page = context.new_page()
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("dialog", lambda dialog: dialog.accept())
                        page.goto(player_url)
                        assert page.locator("body").get_attribute("data-account") == account_key
                        assert page.evaluate("Date.now()") == timer_now + 31000
                        assert (
                            page.evaluate("key => localStorage.getItem(key)", timer_key) == deadline
                        )
                        expect(page.locator("[data-timer-output]")).to_have_text("00:59")
                        result["timer_reopen"] = {
                            "status": "VERIFIED",
                            "remaining_seconds": 59,
                            "same_account_key_and_deadline": True,
                        }
                        quick = page.locator("[data-quick-set]").first
                        kg = quick.locator("[name=actual_kg]")
                        reps = quick.locator("[name=actual_reps]")
                        rpe = quick.locator("[name=actual_rpe]")
                        page.clock.fast_forward(60000)
                        expect(page.locator("[data-timer-output]")).to_have_text("00:00")
                        # Focus and responsive screens, both themes, without recording credentials.
                        result["stage"] = "responsive themes and keyboard"
                        for width in (390, 768, 1440):
                            page.set_viewport_size({"width": width, "height": 900})
                            for theme in ("light", "dark"):
                                page.evaluate(
                                    "dark => document.documentElement.classList.toggle('dark', dark)",
                                    theme == "dark",
                                )
                                no_overflow(page)
                                kg.focus()
                                page.keyboard.press("Tab")
                                assert page.evaluate("document.activeElement.name") == "actual_rpe"
                                page.screenshot(
                                    path=str(output / f"player-{width}-{theme}.png"), full_page=True
                                )
                        page.set_viewport_size({"width": 390, "height": 844})

                        # Network failure is never a sync success; recovery is explicit and unsent.
                        def fail_save(route: Route) -> None:
                            route.abort()

                        result["stage"] = "network ambiguity and draft recovery"
                        page.route("**/player/sets/*/", fail_save)
                        kg.fill("12.34")
                        page.clock.fast_forward(1000)
                        expect(quick.locator("[data-row-status]")).to_contain_text("Sin confirmar")
                        page.unroute("**/player/sets/*/", fail_save)
                        page.reload()
                        expect(kg).to_have_value("0.00")
                        quick.get_by_role("button", name="Recuperar borrador", exact=False).click()
                        expect(kg).to_have_value("12.34")
                        expect(quick.locator("[data-row-status]")).to_contain_text("sin enviar")
                        quick.get_by_role("button", name="Guardar serie", exact=True).click()
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        # Two tabs: stale page must not overwrite a confirmed value.
                        result["stage"] = "stale revision conflict"
                        stale = context.new_page()
                        stale.goto(page.url)
                        kg.fill("13.34")
                        page.clock.fast_forward(1000)
                        expect(quick.locator("[data-row-status]")).to_have_text(
                            "Guardado confirmado por el servidor."
                        )
                        stale_form = stale.locator("[data-quick-set]").first
                        stale_form.locator("[name=actual_kg]").fill("99")
                        # The context clock is paused: fire this tab's 800 ms debounce.
                        stale.clock.fast_forward(1000)
                        expect(stale_form.locator("[data-row-status]")).to_contain_text(
                            "La sesión cambió"
                        )
                        stale.close()
                        page.reload()
                        result["stage"] = "partial close"
                        close = page.locator("#close-session")
                        close.locator("[name=confirm]").check()
                        close.get_by_role("button", name="Confirmar cierre de sesión").click()
                        expect(page.locator("#session-player")).to_have_count(0)
                        assert "Completada" in page.locator("main").inner_text()
                        expect(page.locator("[data-complete-session]")).to_have_count(0)
                        # Other account cannot reach the private execution.
                        result["stage"] = "account isolation"
                        other = browser.new_context(service_workers="block")
                        other.set_default_timeout(10000)
                        other.set_default_navigation_timeout(15000)
                        other.route("**/*", guard)
                        other_page = other.new_page()
                        login(other_page, origin, "other@browser.test", password)
                        forbidden = other_page.request.get(origin + f"/sessions/{session_id}/")
                        assert forbidden.status == 404
                        other.close()
                        assert not errors, errors
                        assert not external, external
                        result.update(
                            {
                                "status": "VERIFIED",
                                "stage": "complete",
                                "javascript_errors": errors,
                                "external_requests": external,
                                "matrix": "390/768/1440 x light/dark",
                                "checks": [
                                    "mobile complete flow",
                                    "server autosave and reload",
                                    "undo",
                                    "zero vs missing",
                                    "invalid input",
                                    "navigation",
                                    "timestamp suspension/reload",
                                    "timer tab closure/reopen with persistent deadline",
                                    "keyboard",
                                    "network ambiguity",
                                    "explicit draft recovery",
                                    "stale revision",
                                    "partial close",
                                    "account isolation",
                                ],
                            }
                        )
                        context.close()
                    finally:
                        browser.close()
                        result["browser_closed"] = True
            finally:
                server.shutdown()
                server_thread.join(timeout=10)
                result["server_stopped"] = not server_thread.is_alive()
    except Exception as error:
        result["traceback"] = (
            traceback.format_exc().replace(password, "[REDACTED]").replace(secret, "[REDACTED]")
        )
        result["error"] = (
            str(error).replace(password, "[REDACTED]").replace(secret, "[REDACTED]")[:4000]
        )
    after = source_binding()
    result.update(
        {
            "source_after": after,
            "source_unchanged": before == after,
            "screenshots": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.png")
            },
        }
    )
    if before != after:
        result["status"] = "FAILED"
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "error": result.get("error", ""),
                "receipt": str(output / "result.json"),
            }
        )
    )
    return 0 if result["status"] == "VERIFIED" and result.get("server_stopped") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable", required=True)
    args = parser.parse_args()
    return run(args.output, args.browser_executable)


if __name__ == "__main__":
    raise SystemExit(main())
