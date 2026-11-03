"""Opt-in multisport offline wire recovery against the local Django server."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import cast
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from playwright.sync_api import Page, sync_playwright

from basis.modules.sync.adapters.models import SyncReceipt
from basis.modules.training.adapters.models import (
    Block,
    Interval,
    Session,
    StrengthSet,
    TrekStage,
    TrekTrip,
)
from basis.modules.training.domain.sports import VARIABLES

from . import test_pwa_browser as helpers
from .contracts import session_snapshot
from .factories import account, exercise, session


@skipUnless(os.environ.get("BASIS_PWA_BROWSER") == "1", "opt-in BASIS_PWA_BROWSER=1")
class MultisportOfflineTests(StaticLiveServerTestCase):
    def records(self, page: Page) -> list[list[object]]:
        return helpers.PwaBrowserTests.local_records(cast(helpers.PwaBrowserTests, self), page)

    def wait(self, page: Page, expression: str) -> None:
        helpers.PwaBrowserTests.wait_async(cast(helpers.PwaBrowserTests, self), page, expression)

    def test_multisport_recovery(self) -> None:
        owner, other = account("payload-owner"), account("payload-other")
        item = session(owner, sport="strength")
        first = item.blocks.get()
        ex = exercise()
        for order in (1, 2):
            StrengthSet.objects.create(
                block=first, exercise=ex, order=order, target_reps=10, target_kg=20
            )
        sports = ("cardio", "running", "cycling", "swimming", "hiking")
        for order, sport in enumerate(sports, 2):
            block = Block.objects.create(
                session=item,
                order=order,
                sport=sport,
                title=sport,
                target={"duration_seconds": "900"},
            )
            Interval.objects.create(
                block=block, repetitions=2, target={"duration_seconds": "60"}, rest_seconds=30
            )
        trip = TrekTrip.objects.create(owner=owner, title="Ruta ficticia")
        stage = TrekStage.objects.create(
            trip=trip, session=item, order=1, recovery_notes="Descanso ficticio"
        )
        values = {
            '["duration_seconds"]': "1800",
            '["reported_rpe"]': "0",
            '["blocks",0,"sets",0,"actual_reps"]': "8",
            '["blocks",0,"sets",0,"actual_kg"]': "0",
            '["blocks",0,"sets",0,"actual_rir"]': "0",
            '["blocks",0,"sets",1,"actual_reps"]': "7",
            '["blocks",0,"sets",1,"actual_kg"]': "22.5",
            '["blocks",1,"actual","duration_seconds"]': "600",
            '["blocks",1,"actual","session_type"]': "suave",
            '["blocks",2,"actual","distance_m"]': "5000",
            '["blocks",2,"actual","cadence_spm"]': "170",
            '["blocks",3,"actual","power_w"]': "0",
            '["blocks",3,"actual","environment"]': "indoor",
            '["blocks",4,"actual","strokes"]': "0",
            '["blocks",4,"actual","stroke"]': "crol",
            '["blocks",5,"actual","pack_kg"]': "6.25",
            '["blocks",5,"actual","terrain"]': "sendero",
            '["blocks",5,"intervals",0,"actual","duration_seconds"]': "45",
            '["blocks",5,"intervals",0,"actual_rest_seconds"]': "0",
        }

        # Exercise every block-level field declared by the current sport schema.
        samples = {
            "duration_seconds": "900",
            "moving_seconds": "700",
            "pause_seconds": "100",
            "distance_m": "1000",
            "heart_rate_bpm": "120",
            "max_heart_rate_bpm": "150",
            "ascent_m": "100",
            "descent_m": "100",
            "start_altitude_m": "2000",
            "max_altitude_m": "2050",
            "end_altitude_m": "2000",
            "pack_kg": "6.25",
            "environment": "indoor",
            "pool_length_m": "25",
            "laps": "20",
            "strokes": "0",
            "cadence_spm": "170",
            "cadence_rpm": "80",
            "power_w": "0",
        }
        for index, sport in enumerate(sports, 1):
            for key, spec in VARIABLES[sport].items():
                path = json.dumps(["blocks", index, "actual", key], separators=(",", ":"))
                values[path] = samples.get(key, "dato ficticio" if spec.kind == "text" else "1")
            # The offline editor exposes numeric interval metrics, not text or choices.
            for key, spec in VARIABLES[sport].items():
                if spec.kind not in ("text", "choice"):
                    path = json.dumps(
                        ["blocks", index, "intervals", 0, "actual", key], separators=(",", ":")
                    )
                    values[path] = samples.get(key, "1")
            values[
                json.dumps(["blocks", index, "intervals", 0, "actual_rpe"], separators=(",", ":"))
            ] = "0"
            values[
                json.dumps(
                    ["blocks", index, "intervals", 0, "actual_rest_seconds"], separators=(",", ":")
                )
            ] = "0"

        def db_read(mutation: str) -> tuple[object, int, str, int]:
            try:
                current = Session.objects.get(pk=item.pk, owner=owner)
                return (
                    session_snapshot(current),
                    SyncReceipt.objects.filter(mutation_id=mutation, owner=owner).count(),
                    TrekStage.objects.get(pk=stage.pk).recovery_notes,
                    Session.objects.filter(pk=item.pk, owner=other).count(),
                )
            finally:
                connections.close_all()

        with sync_playwright() as p, ThreadPoolExecutor(max_workers=1) as pool:
            browser = p.chromium.launch(
                executable_path=os.environ["BROWSER_EXECUTABLE"], headless=True
            )
            context = browser.new_context(viewport={"width": 390, "height": 844})
            page = context.new_page()
            page.set_default_timeout(15000)
            try:
                helpers.PwaBrowserTests.login(
                    cast(helpers.PwaBrowserTests, self), page, owner.username
                )
                page.evaluate("() => navigator.serviceWorker.ready")
                page.reload()
                page.wait_for_function("navigator.serviceWorker.controller !== null")
                page.goto(f"{self.live_server_url}/sessions/{item.pk}/")
                page.evaluate("() => window.basisOfflineReady")
                page.locator("[data-download-session]").click()
                page.wait_for_function(
                    "document.querySelector('#global-status').textContent.includes('Sesión guardada')"
                )
                original = cast(
                    dict[str, object], cast(dict[str, object], self.records(page)[0][0])["session"]
                )
                context.set_offline(True)
                page.goto(self.live_server_url + "/offline/")
                page.get_by_role("button", name="Abrir sesión", exact=True).click()
                for path, value in values.items():
                    field = page.locator(f"[data-path='{path}']")
                    if field.evaluate("e => e.tagName") == "SELECT":
                        field.select_option(value)
                    else:
                        field.fill(value)
                page.get_by_role("button", name="Completar sesión", exact=True).click()
                self.wait(page, "async () => (await window.basisPending()) === 1")
                records = self.records(page)
                saved = cast(dict[str, object], records[0][0])
                queued = cast(dict[str, object], records[1][0])
                self.assertEqual(saved["session"], queued["session"])
                self.assertEqual(saved["account"], queued["account"])
                mutation = cast(str, queued["mutation_id"])
                self.assertEqual(
                    pool.submit(db_read, mutation).result()[1:], (0, "Descanso ficticio", 0)
                )
                page.reload()
                page.get_by_role("button", name="Abrir sesión", exact=True).click()
                for path, value in values.items():
                    self.assertEqual(page.locator(f"[data-path='{path}']").input_value(), value)
                self.assertEqual(self.records(page)[0][0], saved)
                sent: list[dict[str, object]] = []
                page.on(
                    "request",
                    lambda req: (
                        sent.append(json.loads(req.post_data or "{}"))
                        if req.url.endswith("/api/sync/") and req.method == "POST"
                        else None
                    ),
                )
                context.set_offline(False)
                self.wait(page, "async () => (await window.basisPending()) === 0")
                self.assertEqual(sent[0]["mutation_id"], mutation)
                self.assertEqual(sent[0]["session"], queued["session"])
                current, count, notes, foreign = pool.submit(db_read, mutation).result()
                self.assertEqual((count, notes, foreign), (1, "Descanso ficticio", 0))
                self.assertEqual(
                    cast(dict[str, object], self.records(page)[0][0])["session"], current
                )
                self.assertEqual(cast(dict[str, object], current)["status"], "completed")

                def compare_wire(expected: object, actual: object, path: str = "") -> None:
                    if isinstance(expected, dict):
                        self.assertIsInstance(actual, dict, path)
                        assert isinstance(actual, dict)
                        self.assertEqual(expected.keys(), actual.keys(), path)
                        for key in expected:
                            if key != "revision":
                                compare_wire(expected[key], actual[key], f"{path}/{key}")
                    elif isinstance(expected, list):
                        self.assertIsInstance(actual, list, path)
                        assert isinstance(actual, list)
                        self.assertEqual(len(expected), len(actual), path)
                        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
                            compare_wire(left, right, f"{path}/{index}")
                    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
                        self.assertEqual(Decimal(str(expected)), Decimal(str(actual)), path)
                    else:
                        self.assertEqual(expected, actual, path)

                compare_wire(queued["session"], current)
                self.assertEqual(
                    cast(int, cast(dict[str, object], current)["revision"]),
                    cast(int, cast(dict[str, object], queued["session"])["revision"]) + 1,
                )
                sets = cast(
                    list[dict[str, object]],
                    cast(list[dict[str, object]], cast(dict[str, object], current)["blocks"])[0][
                        "sets"
                    ],
                )
                self.assertIsNone(sets[1]["actual_rir"])
                self.assertEqual(sets[0]["actual_rir"], 0)
                self.assertEqual(
                    cast(list[dict[str, object]], original["blocks"])[1]["target"],
                    cast(list[dict[str, object]], cast(dict[str, object], current)["blocks"])[1][
                        "target"
                    ],
                )
                result = page.evaluate(
                    """async body => { const token = (await (await fetch('/api/csrf/')).json()).token; const r = await fetch('/api/sync/', {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':token},body:JSON.stringify(body)}); return {status:r.status, body:await r.json()}; }""",
                    sent[0],
                )
                self.assertEqual(result["status"], 200)
                self.assertEqual(result["body"]["session"], current)
                self.assertEqual(pool.submit(db_read, mutation).result()[1], 1)
                foreign_context = browser.new_context()
                try:
                    foreign_page = foreign_context.new_page()
                    helpers.PwaBrowserTests.login(
                        cast(helpers.PwaBrowserTests, self), foreign_page, other.username
                    )
                    response = foreign_page.goto(f"{self.live_server_url}/sessions/{item.pk}/")
                    assert response is not None
                    self.assertEqual(response.status, 404)
                finally:
                    foreign_context.close()
                context.set_offline(True)
                page.reload()
                page.get_by_role("button", name="Abrir sesión", exact=True).click()
                for path, value in values.items():
                    field = page.locator(f"[data-path='{path}']")
                    if field.get_attribute("type") == "number":
                        self.assertEqual(Decimal(field.input_value()), Decimal(value))
                    else:
                        self.assertEqual(field.input_value(), value)
                    self.assertTrue(field.is_disabled())
                output = Path(os.environ["BASIS_PWA_OUTPUT"])
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / "multisport-completed.png"), full_page=True)
                (output / "multisport-wire.json").write_text(
                    json.dumps(
                        {
                            "download": original,
                            "queued": queued,
                            "sent": sent[0],
                            "persisted": current,
                            "replay": result,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            finally:
                context.close()
                browser.close()
