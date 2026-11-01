"""MAM-629 real headless acceptance on a disposable loopback WSGI server.

Run as a module. No Python child runner, providers, SMTP or real account data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from wsgiref.simple_server import make_server

from playwright.sync_api import Page, Route, expect, sync_playwright

from scripts.acceptance_browser import source_binding
from scripts.browser_smoke import login, no_overflow

ROOT = Path(__file__).resolve().parents[2]


def database_call[T](operation: Callable[[], T]) -> T:
    """Fixture reads stay outside Playwright's event loop; Django guards remain on."""

    def invoke() -> T:
        from django.db import connections

        try:
            return operation()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(invoke).result()


def submit(page: Page) -> None:
    page.get_by_role("button", name="Guardar cambio", exact=True).click()


def fill_dates(page: Page, start: str, end: str) -> None:
    page.locator("[name=start_date]").fill(start)
    page.locator("[name=end_date]").fill(end)


def run(output: Path, executable: str) -> int:
    from django import setup

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    database = (
        ROOT.parent.parent / "basis-runs/MAM-629/codex1" / ("browser-" + uuid4().hex + ".sqlite3")
    )
    os.environ.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.test_settings",
            "BASIS_DATABASE_PATH": str(database),
            "AI_ENABLED": "0",
            "DEEPSEEK_API_KEY": "",
            "POLAR_ACCESS_TOKEN": "",
            "POLAR_PRODUCT_ID": "",
            "POLAR_WEBHOOK_SECRET": "",
            "DJANGO_DEBUG": "1",
        }
    )
    os.environ.pop("DATABASE_URL", None)
    setup()
    from dataclasses import replace

    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from django.db import connections
    from django.utils import timezone

    from basis.bootstrap.planning import planning
    from basis.modules.training.adapters.actions import session_snapshot, start_session
    from basis.modules.training.adapters.models import Goal, PlannedSession, TrainingPlan
    from basis.modules.training.public import CreatePlan
    from basis.shared.identifiers import AccountId, GoalId
    from tests.regression.factories import account
    from tests_architecture.test_planning import TODAY, definition

    before = source_binding()
    checkpoints: list[str] = []
    errors: list[str] = []
    external: list[str] = []
    result: dict[str, object] = {
        "status": "FAILED",
        "checkpoints": checkpoints,
        "server_stopped": False,
        "providers": "NOT RUN",
        "smtp": "NOT RUN",
    }
    server = None
    thread = None
    try:
        with (output / "migrate.txt").open("w", encoding="utf-8") as stream:
            call_command("migrate", interactive=False, stdout=stream, stderr=stream)
        user, other = account("calendar-ficticio-629"), account("calendar-otro-ficticio-629")
        today = timezone.localdate()
        goal = Goal.objects.create(
            owner=user, title="Objetivo ficticio de aceptación", sport="running"
        )
        original = definition(GoalId(goal.pk))
        delta = today - TODAY
        data = replace(
            original,
            title="Plantilla privada ficticia",
            start_date=original.start_date + delta,
            end_date=original.end_date + delta,
            cycles=tuple(
                replace(c, start_date=c.start_date + delta, end_date=c.end_date + delta)
                for c in original.cycles
            ),
            sessions=tuple(replace(s, date=s.date + delta) for s in original.sessions),
        )
        source = planning().create(CreatePlan(AccountId(user.pk), data))
        executed = start_session(
            user, PlannedSession.objects.get(plan_id=source.id, title="executed")
        )
        block = executed.blocks.get()
        block.actual = {"distance_m": "1234"}
        block.save()
        frozen = session_snapshot(executed)
        foreign_goal = Goal.objects.create(
            owner=other, title="Objetivo secreto ficticio", sport="running"
        )
        foreign = TrainingPlan.objects.create(
            owner=other,
            goal=foreign_goal,
            title="Plan ajeno ficticio",
            start_date=today,
            end_date=today,
        )
        connections.close_all()
        server = make_server("127.0.0.1", 0, StaticFilesHandler(get_wsgi_application()))
        origin = "http://127.0.0.1:" + str(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    is_mobile=True,
                    has_touch=True,
                    service_workers="block",
                )

                def route(request: Route) -> None:
                    if request.request.url.startswith(origin + "/"):
                        request.continue_()
                    else:
                        external.append(request.request.url.split("?")[0])
                        request.abort()

                context.route("**/*", route)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                login(page, origin, user.email, "Example-password-824!")

                # Build the entire empty hierarchy through ordinary browser forms.
                page.goto(origin + "/plans/new/")
                page.locator("[name=title]").fill("Bloque desde cero ficticio")
                page.locator("[name=goal]").select_option(str(goal.pk))
                end = (today + timedelta(days=14)).isoformat()
                fill_dates(page, today.isoformat(), end)
                page.locator("form button[type=submit]").click()
                page.wait_for_url(re.compile(r"/plans/\d+/$"))
                manual = database_call(
                    lambda: TrainingPlan.objects.get(title="Bloque desde cero ficticio")
                )
                page.get_by_role("link", name="Calendario semanal y editor", exact=True).click()
                for kind in ("macro", "meso", "micro"):
                    page.get_by_role("link", name="Añadir ciclo", exact=True).click()
                    page.locator("[name=title]").fill("Ciclo " + kind)
                    page.locator("[name=kind]").select_option(kind)
                    if kind != "macro":
                        parent = database_call(
                            lambda: manual.cycles.get(kind="macro" if kind == "meso" else "meso")
                        )
                        page.locator("[name=parent]").select_option(str(parent.pk))
                    fill_dates(page, today.isoformat(), end)
                    submit(page)
                    expect(page.locator("#plan-board")).to_be_visible()
                page.get_by_role("link", name="Programar sesión", exact=True).click()
                page.locator("[name=cycle]").select_option(
                    str(database_call(lambda: manual.cycles.get(kind="micro").pk))
                )
                page.locator("[name=title]").fill("Sesión concreta ficticia")
                page.locator("[name=date]").fill((today + timedelta(days=1)).isoformat())
                submit(page)
                expect(
                    page.get_by_role("heading", name="Sesión concreta ficticia", exact=True)
                ).to_be_visible()
                checkpoints.append("crear_plan_macro_meso_micro_sesion_por_formularios")

                # Cycle validation beside the action, then an actual versioned edit.
                page.goto(origin + f"/plans/{manual.pk}/calendar/")
                page.get_by_role("link", name="Editar ciclo Ciclo micro", exact=True).click()
                page.locator("[name=reason]").fill("Ajuste ficticio del enfoque")
                page.locator("[name=end_date]").fill((today - timedelta(days=1)).isoformat())
                submit(page)
                expect(page.locator("[data-error-summary]")).to_be_visible()
                page.screenshot(path=str(output / "cycle-error-390.png"), full_page=True)
                page.locator("[name=end_date]").fill(end)
                page.locator("[name=focus]").fill("Enfoque ficticio editado")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                head = database_call(lambda: TrainingPlan.objects.get(previous=manual))
                assert (
                    database_call(lambda: head.cycles.get(kind="micro").focus)
                    == "Enfoque ficticio editado"
                )
                checkpoints.append("editar_ciclo_error_local_y_version_con_borrador")

                # Private template copy includes an executed intent, never its results.
                page.goto(origin + "/plans/")
                page.get_by_role("link", name="Crear desde plantilla privada", exact=True).click()
                page.locator("[name=source]").select_option(str(source.id))
                page.locator("[name=goal]").select_option(str(goal.pk))
                page.locator("[name=title]").fill("Bloque copiado ficticio")
                page.locator("[name=start_date]").fill(today.isoformat())
                page.locator("[name=reason]").fill("Nuevo período ficticio")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                copied = database_call(
                    lambda: TrainingPlan.objects.get(title="Bloque copiado ficticio")
                )
                assert copied.lineage != source.lineage
                assert database_call(
                    lambda: all(
                        not s.executions.exists() and not b.actual
                        for s in copied.sessions.all()
                        for b in s.blocks.all()
                    )
                )
                checkpoints.append("crear_desde_plantilla_privada_sin_resultados")

                # Keyboard activates real HTMX navigation; no document reload.
                page.evaluate("window.mam629Marker='kept'")
                next_week = page.get_by_role("link", name="Semana siguiente", exact=True)
                next_week.focus()
                page.keyboard.press("Enter")
                expect(page).to_have_url(re.compile(r"week="))
                expect(page.locator("#plan-board")).to_be_visible()
                assert page.evaluate("window.mam629Marker") == "kept"
                expect(page.locator("#calendar-next")).to_be_focused()
                page.goto(origin + f"/plans/{copied.pk}/calendar/?week={today.isoformat()}")
                no_overflow(page)
                for _ in range(12):
                    page.keyboard.press("Tab")
                    assert page.evaluate("document.activeElement !== document.body")
                page.keyboard.press("Shift+Tab")
                page.screenshot(path=str(output / "calendar-390.png"), full_page=True)
                checkpoints.append("movil_390_sin_overflow_tab_shift_tab_enter_htmx")

                page.get_by_role("link", name="Editar plan", exact=True).click()
                expect(page.get_by_text("Impacto al guardar", exact=True)).to_be_visible()
                page.locator("[name=title]").fill("Bloque editado ficticio")
                page.locator("[name=reason]").fill("Cambiar nombre ficticio")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                head = database_call(lambda: TrainingPlan.objects.get(previous=copied))
                future = database_call(lambda: head.sessions.get(title="future"))
                page.goto(origin + f"/scheduled/{future.pk}/editor/move/")
                page.locator("[name=date]").fill((future.date + timedelta(days=1)).isoformat())
                page.locator("[name=reason]").fill("Viaje ficticio")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                moved = database_call(lambda: PlannedSession.objects.get(supersedes=future))
                assert moved.date == future.date + timedelta(days=1)
                page.goto(origin + f"/scheduled/{moved.pk}/editor/change/")
                page.locator("[name=action]").select_option("skipped")
                page.locator("[name=reason]").fill("Descanso ficticio")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                skipped = database_call(lambda: PlannedSession.objects.get(supersedes=moved))
                assert skipped.status == "skipped"
                page.goto(origin + f"/scheduled/{skipped.pk}/editor/change/")
                page.locator("[name=action]").select_option("replace")
                page.locator("[name=replacement]").select_option(
                    str(
                        database_call(
                            lambda: PlannedSession.objects.get(plan_id=source.id, title="past").pk
                        )
                    )
                )
                page.locator("[name=reason]").fill("Sustitución ficticia")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                replaced = database_call(lambda: PlannedSession.objects.get(supersedes=skipped))
                assert (
                    replaced.origin_id == (future.origin_id or future.pk)
                    and replaced.status == "scheduled"
                )
                page.locator("[name=compare]").select_option(str(copied.pk))
                page.get_by_role("button", name="Comparar versiones", exact=True).click()
                expect(page.get_by_role("heading", name=re.compile("Antes: v1"))).to_be_visible()
                no_overflow(page)
                page.screenshot(path=str(output / "versions-390.png"), full_page=True)
                checkpoints.append("editar_plan_reprogramar_omitir_sustituir_comparar_versiones")

                # Execution relation and actual values survive edits of their source plan.
                page.goto(origin + f"/plans/{source.id}/edit/")
                page.locator("[name=title]").fill("Fuente editada ficticia")
                page.locator("[name=reason]").fill("Conservar resultado ficticio")
                submit(page)
                expect(page.locator("#plan-board")).to_be_visible()
                expect(
                    page.get_by_text(re.compile("Conservada en v1")).filter(has_text="executed")
                ).to_be_visible()
                database_call(executed.refresh_from_db)
                assert database_call(lambda: session_snapshot(executed)) == frozen
                response = page.goto(origin + f"/scheduled/{executed.planned_id}/editor/move/")
                assert response is not None and response.status == 200
                page.locator("[name=reason]").fill("Intento ficticio rechazado")
                submit(page)
                expect(page.locator("[data-error-summary]")).to_be_visible()
                checkpoints.append("coherencia_plan_resultado_y_guardia_de_ejecucion")

                # No-JS fallback and independent second account browser context.
                fallback = browser.new_context(
                    java_script_enabled=False, viewport={"width": 390, "height": 844}
                )
                fallback.add_cookies(
                    [
                        {"name": c["name"], "value": c["value"], "url": origin}
                        for c in context.cookies()
                    ]
                )
                plain = fallback.new_page()
                plain.goto(origin + f"/plans/{replaced.plan_id}/calendar/")
                plain.get_by_role("link", name="Semana siguiente", exact=True).click()
                expect(plain).to_have_url(re.compile("week="))
                fallback.close()
                second = browser.new_context(viewport={"width": 390, "height": 844})
                second_page = second.new_page()
                login(second_page, origin, other.email, "Example-password-824!")
                second_page.goto(origin + "/plans/")
                expect(
                    second_page.get_by_text("Bloque editado ficticio", exact=True)
                ).to_have_count(0)
                for url in (
                    f"/plans/{replaced.plan_id}/calendar/",
                    f"/plans/{source.id}/edit/",
                    f"/scheduled/{future.pk}/editor/move/",
                    f"/plans/{foreign.pk}/calendar/?compare={source.id}",
                ):
                    response = second_page.goto(origin + url)
                    assert response is not None and response.status == 404
                second.close()
                checkpoints.append("fallback_sin_js_y_aislamiento_entre_cuentas")
                assert not errors, errors
                assert not external, external
                result.update(
                    {
                        "status": "VERIFIED",
                        "browser": browser.version,
                        "javascript_errors": errors,
                        "external_requests": external,
                    }
                )
                context.close()
            finally:
                browser.close()
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        connections.close_all()
        result["server_stopped"] = thread is None or not thread.is_alive()
        after = source_binding()
        result["source_before"] = before
        result["source_after"] = after
        result["source_unchanged"] = before == after
        result["screenshots"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.png")
        }
        result["auditor_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if not result["source_unchanged"] or not result["server_stopped"]:
            result["status"] = "FAILED"
        (output / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "status": result["status"],
                "checkpoints": checkpoints,
                "server_stopped": result["server_stopped"],
            }
        )
    )
    return 0 if result["status"] == "VERIFIED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--browser-executable", required=True)
    args = parser.parse_args()
    return run(args.output, args.browser_executable)


if __name__ == "__main__":
    raise SystemExit(main())
