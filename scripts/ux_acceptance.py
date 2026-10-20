"""BASIS UX task/viewport evidence on an owned temporary database; no provider calls."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import timedelta
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import Page, sync_playwright

from scripts.acceptance_browser import (
    ROOT,
    child_environment,
    choose_port,
    execute,
    ready,
    source_binding,
)
from scripts.browser_smoke import create_session, login, mapping, no_overflow


def fixture(output: Path) -> None:
    import django

    django.setup()
    from django.contrib.auth.models import User
    from django.utils import timezone

    from basis.adapters.django.acceptance_fixture import prepare
    from basis.modules.coach.adapters.models import AIJob, PlanProposal, UsagePeriod
    from basis.modules.training.adapters.models import (
        Block,
        Cycle,
        Goal,
        PlannedSession,
        TrainingPlan,
    )

    # prepare verifies engine, exact database identity and repository-local cache.
    prepare()
    owner = User.objects.get(username="owner@browser.test")
    start = timezone.localdate()
    end = start + timedelta(days=6)
    goal = Goal.objects.create(owner=owner, title="Objetivo UX ficticio", sport="hiking")
    plan = TrainingPlan.objects.create(
        owner=owner, goal=goal, title="Semana UX ficticia", start_date=start, end_date=end
    )
    parent: Cycle | None = None
    for kind in ("macro", "meso", "micro"):
        parent = Cycle.objects.create(
            plan=plan,
            parent=parent,
            kind=kind,
            title="Ciclo UX " + kind,
            start_date=start,
            end_date=end,
        )
    assert parent is not None
    scheduled = PlannedSession.objects.create(
        owner=owner, plan=plan, cycle=parent, title="Caminata UX ficticia", date=start
    )
    Block.objects.create(
        planned=scheduled,
        sport="hiking",
        title="Prescripción ficticia",
        target={"distance_m": 5000, "duration_seconds": 3600},
    )
    period = UsagePeriod.objects.create(owner=owner, key="ux-fixture")
    job = AIJob.objects.create(
        owner=owner,
        usage_period=period,
        kind="plan",
        prompt="PROPUESTA FICTICIA: sin proveedor",
        reservation=0,
        requested_model="fixture-not-provider",
        context={"fixture": "SYNTHETIC_FIXTURE_NOT_PROVIDER"},
        status="completed",
    )
    content: dict[str, object] = {
        "title": "Propuesta UX ficticia",
        "goal_id": goal.pk,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "notes": "Datos ficticios para revisar la interfaz. Sin generación de proveedor.",
        "cycles": [
            {
                "key": kind,
                "parent": previous,
                "kind": kind,
                "title": "Propuesta " + kind,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
            for kind, previous in (("macro", None), ("meso", "macro"), ("micro", "meso"))
        ],
        "sessions": [
            {
                "title": "Caminata de propuesta",
                "date": start.isoformat(),
                "cycle_key": "micro",
                "blocks": [
                    {"sport": "hiking", "title": "Suave", "target": {"duration_seconds": 1800}}
                ],
            }
        ],
    }
    review = PlanProposal.objects.create(owner=owner, job=job, content=content)
    (output / "fixture.json").write_text(
        json.dumps(
            {
                "scheduled": scheduled.pk,
                "plan": plan.pk,
                "proposal": review.pk,
                "job": str(job.pk),
                "rescheduled_date": (start + timedelta(days=1)).isoformat(),
                "source": "SYNTHETIC_FIXTURE_NOT_PROVIDER",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


AUDIT = r"""async () => {
  await document.fonts.ready;
  await new Promise(requestAnimationFrame);
  await Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().endTime<=1000)
    .map(a=>a.finished.catch(()=>{})));
  const visible = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e);
    return r.width>0 && r.height>0 && s.visibility==='visible' && s.display!=='none'
      && !e.closest('[inert]')
      && e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}); };
  const rgb = c => (c.match(/[\d.]+/g)||[]).map(Number);
  const rgba = c => c.length===3?[...c,1]:c;
  const over = (f,b) => { const fg=rgba(f), bg=rgba(b), a=fg[3]+bg[3]*(1-fg[3]);
    return [...[0,1,2].map(i=>a?(fg[i]*fg[3]+bg[i]*bg[3]*(1-fg[3]))/a:0),a]; };
  // Composite the group opacity as well as background/color alpha, inside out.
  const paint = (e,fg=[0,0,0,0]) => { for(let n=e;n;n=n.parentElement) {
    const s=getComputedStyle(n); fg=over(fg,rgb(s.backgroundColor)); fg[3]*=Number(s.opacity);
    } return over(fg,[255,255,255]); };
  const complex = e => { for(let n=e;n;n=n.parentElement) { const s=getComputedStyle(n);
    if(s.backgroundImage!=='none'||s.filter!=='none'||s.mixBlendMode!=='normal'
      ||s.backdropFilter!=='none')return true; } return false; };
  const lum = c => c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
    .slice(0,3).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const ratio = (fg,bg) => { const l=[lum(fg),lum(bg)].sort((a,b)=>b-a);
    return (l[0]+.05)/(l[1]+.05); };
  const selector = e => { const parts=[]; for(let n=e;n;n=n.parentElement) {
    if(n.id){parts.unshift('#'+CSS.escape(n.id));break;}
    parts.unshift(n.localName+':nth-of-type('+([...n.parentElement?.children||[]]
      .filter(x=>x.localName===n.localName).indexOf(n)+1)+')');
    } return parts.join(' > '); };
  const describe = e => ({selector:selector(e),text:(e.textContent||e.getAttribute('aria-label')
    ||e.name||e.tagName).trim().slice(0,90)});
  const contrast=[], contrast_review=[];
  // Audit the actual text owner, including small/span/td, not its container's color.
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  for(let node;node=walker.nextNode();) {
    const e=node.parentElement;
    if(!node.textContent.trim()||!visible(e)||e.closest('script,style,svg,noscript,template')
      ||e.closest(':disabled,[aria-disabled="true"]'))continue;
    const item={...describe(e),text:node.textContent.trim().slice(0,90)};
    if(complex(e)){contrast_review.push({...item,reason:'complex-background'});continue;}
    const s=getComputedStyle(e), value=ratio(paint(e,rgb(s.color)),paint(e));
    const large=parseFloat(s.fontSize)>=24 || (parseFloat(s.fontSize)>=18.66&&Number(s.fontWeight)>=700);
    const threshold=large?3:4.5;
    if(value<threshold)contrast.push({...item,ratio:+value.toFixed(2),threshold});
  }
  const targets=[];
  for(const e of document.querySelectorAll('.actions a,.actions button,.nav a,input:not([type=hidden]),select,textarea,summary')) {
    if(!visible(e)||e.disabled)continue;
    const target=e.matches('[type=checkbox],[type=radio]')?(e.labels?.[0]||e):e;
    const r=target.getBoundingClientRect();
    if(r.width<24||r.height<24)targets.push({text:(e.textContent||e.getAttribute('aria-label')||e.name||e.tagName).trim().slice(0,80),width:+r.width.toFixed(1),height:+r.height.toFixed(1)});
  }
  const focus=[], focus_review=[], focus_checked=[];
  const original=document.activeElement, scroll=[scrollX,scrollY];
  const state = e => { const s=getComputedStyle(e); return {outlineStyle:s.outlineStyle,
    outlineWidth:s.outlineWidth,outlineColor:s.outlineColor,outlineOffset:s.outlineOffset,
    boxShadow:s.boxShadow,backgroundColor:s.backgroundColor,borderColor:s.borderColor}; };
  const settle = async e => {
    await new Promise(requestAnimationFrame);
    const animations=e.getAnimations();
    const bounded=animations.filter(a=>a.effect?.getComputedTiming().endTime<=1000);
    await Promise.all(bounded.map(a=>a.finished.catch(()=>{})));
    await new Promise(requestAnimationFrame);
    return animations.length===bounded.length;
  };
  try {
  for(const e of document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex],[contenteditable="true"]')) {
    if(!visible(e)||e.disabled||e.tabIndex<0)continue;
    e.blur(); await settle(e); const before=state(e);
    e.focus({preventScroll:true}); const settled=await settle(e), after=state(e);
    const item={...describe(e),before,after,focusVisible:e.matches(':focus-visible')};
    const indicators=[], unsupported=[];
    const s=getComputedStyle(e), parent=e.parentElement;
    const against=paint(parent);
    const measure = color => { const fg=rgba(rgb(color)); fg[3]*=Number(s.opacity);
      return ratio(paint(parent,fg),against); };
    if(after.outlineStyle!=='none'&&parseFloat(after.outlineWidth)>0
      &&rgba(rgb(after.outlineColor))[3]>0
      &&['outlineStyle','outlineWidth','outlineColor','outlineOffset'].some(k=>before[k]!==after[k])) {
      indicators.push({kind:'outline',ratio:measure(after.outlineColor)});
    }
    if(after.boxShadow!=='none'&&after.boxShadow!==before.boxShadow) {
      // A zero-blur, positive-spread OUTER ring can indicate focus. An unchanged
      // decoration, inset shadow or blurred elevation cannot prove that by color alone.
      for(const shadow of after.boxShadow.split(/,(?![^()]*\))/)) {
        const color=shadow.match(/rgba?\([^)]+\)/)?.[0];
        const lengths=(shadow.replace(/rgba?\([^)]+\)/g,'').match(/-?[\d.]+px/g)||[]).map(parseFloat);
        if(color&&!shadow.includes('inset')&&lengths.length===4&&lengths[0]===0
          &&lengths[1]===0&&lengths[2]===0&&lengths[3]>0) {
          indicators.push({kind:'solid-outer-shadow',ratio:measure(color)});
        } else unsupported.push(shadow.trim());
      }
    }
    item.indicators=indicators;
    const pass=indicators.some(i=>i.ratio>=3);
    let reason=null;
    if(!settled)reason='unsettled-animation';
    else if(!item.focusVisible||document.activeElement!==e)reason='focus-visible-not-reached';
    else if(complex(e))reason='complex-background';
    else if(!pass&&unsupported.length)reason='unmeasured-shadow';
    else if(!pass&&!indicators.length&&['backgroundColor','borderColor'].some(k=>before[k]!==after[k]))
      reason='unmeasured-style-indicator';
    if(reason){item.status='REVIEW';focus_review.push({...item,reason,unsupported});}
    else if(!pass){item.status='FAILED';focus.push({...item,
      reason:indicators.length?'low-contrast-indicator':'missing-indicator',threshold:3});}
    else item.status='VERIFIED';
    focus_checked.push(item);
    e.blur();
  }
  } finally {
    if(original instanceof HTMLElement){original.focus({preventScroll:true});await settle(original);}
    scrollTo(...scroll);
  }
  return {contrast,contrast_review,targets,focus,focus_review,focus_checked,
    methodology:'DOM solid-color screening; keyboard modality; settled focus styles; not WCAG certification',
    theme:document.documentElement.classList.contains('dark')?'dark':'light',
    tokens:{accent:getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
      surface:getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()},
    landmarks:{main:document.querySelectorAll('main').length,nav:document.querySelectorAll('nav[aria-label]').length}};
}"""


def records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("Audit records must be a JSON array")
    return [mapping(item) for item in value]


def expand_details(page: Page) -> None:
    # Keep the locator set stable as [open] changes; .all() on :not([open])
    # produces lazy nth locators that skip items when the matching list shrinks.
    for detail in page.locator("details").all():
        if detail.get_attribute("open") is None:
            detail.locator(":scope > summary").focus()
            page.keyboard.press("Enter")
            assert detail.get_attribute("open") is not None


def dom_checks(output: Path, executable: str) -> dict[str, object]:
    """Exercise the measurement with installed CSS and adversarial DOM; no Django/DB/port."""
    audits: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path=executable, headless=True)
        context = instance.new_context(viewport={"width": 1440, "height": 1000})
        context.route("**/*", lambda route: route.abort())
        page = context.new_page()
        try:
            cotton_css = str(
                files("django_cotton_ui").joinpath("static/django_cotton_ui/cotton-ui.css")
            )
            for width in (390, 768, 1440):
                for theme in ("light", "dark"):
                    page.set_viewport_size({"width": width, "height": 1000})
                    # Representative markup uses the installed button's classes, not a
                    # replacement component. This fixture is not a real application route.
                    page.set_content("""<html><body><main id="main" class="content stack">
                      <section class="hero stack-sm"><p class="eyebrow">Hoy cuenta</p>
                        <h2>Entrena con intención</h2><p class="muted">Contexto visible</p>
                        <div class="actions">
                          <a id="cta" href="#main" class="bg-accent text-accent-foreground
                            hover:bg-accent-content border border-transparent inline-block
                            rounded-button text-sm py-2 px-4 font-medium transition focus-ring">
                            Registrar entrenamiento</a>
                          <a id="hero-link" href="#main" style="color:inherit">Ver mi plan</a>
                        </div></section>
                      <button id="cotton" class="bg-white text-ink-800 border border-ink-200
                        dark:bg-ink-400/30 dark:text-ink-300 dark:border-ink-300/20 shadow
                        text-sm py-2 px-4 font-medium transition focus-ring">Cotton</button>
                      <label for="notes">Notas</label><textarea id="notes"></textarea>
                      <details><summary id="summary">Detalle</summary>Contenido</details>
                      </main><nav class="nav" aria-label="Principal">
                        <a id="navigation" href="#main">Hoy</a></nav></body></html>""")
                    for css in (
                        cotton_css,
                        str(ROOT / "basis/adapters/web/static/basis/css/tokens.css"),
                        str(ROOT / "basis/adapters/web/static/basis/css/app.css"),
                    ):
                        page.add_style_tag(path=css)
                    page.evaluate(
                        "theme => document.documentElement.classList.toggle('dark',theme==='dark')",
                        theme,
                    )
                    page.keyboard.press("Tab")
                    audit = mapping(page.evaluate(AUDIT))
                    (output / "dom-last-audit.json").write_text(
                        json.dumps(audit, indent=2), encoding="utf-8"
                    )
                    assert not any(
                        audit[key]
                        for key in (
                            "focus",
                            "focus_review",
                            "contrast",
                            "contrast_review",
                            "targets",
                        )
                    ), audit
                    assert len(records(audit["focus_checked"])) == 6, audit
                    no_overflow(page)
                    audit.update({"width": width, "theme": theme, "case": "installed-css"})
                    audits.append(audit)
                    page.locator("#hero-link").focus()
                    page.screenshot(
                        path=str(output / f"dom-hero-{width}-{theme}.png"),
                        animations="disabled",
                        full_page=True,
                    )
            # Positive controls must fail the audit, so that a clean matrix cannot
            # be achieved just by skipping outline:none or all box-shadows.
            page.set_content("""<style>
              body { background:white;color:black; } button { outline:none; }
              #transparent:focus-visible { outline:3px solid transparent; }
              #ring:focus-visible { box-shadow:0 0 0 3px rgb(0,0,0); }
              #bad-ring:focus-visible { box-shadow:0 0 0 3px rgb(238,238,238); }
              #decoration { box-shadow:0 0 0 3px black; }
              #blur:focus-visible { box-shadow:0 0 5px 3px black; }
              #inset:focus-visible { box-shadow:inset 0 0 0 3px black; }
              #bad-outline:focus-visible { outline:3px solid #eee; }
              #near-threshold:focus-visible { outline:3px solid rgb(148.9,148.9,148.9); }
              #gradient { background:linear-gradient(white,black); }
              #transparent-text { opacity:0; }
              </style><main>
              <button id="missing">Missing</button><button id="transparent">Transparent</button>
              <button id="ring">Ring</button><button id="bad-ring">Low contrast ring</button>
              <button id="decoration">Unchanged decoration</button><button id="blur">Blurred</button>
              <button id="inset">Inset</button><button id="bad-outline">Low outline</button>
              <button id="near-threshold">Below 3 before rounding</button>
              <button id="disabled" disabled>Disabled</button>
              <div inert><button id="inert">Inert</button></div>
              <button id="hidden" hidden>Hidden</button>
              <p id="gradient">Needs image review</p><p id="opacity" style="opacity:.2">Faded text</p>
              <p>Parent black <span id="leaf" style="color:#eee">Low contrast leaf</span></p>
              <p id="transparent-text">Invisible</p>
              <details open><summary id="closed-summary">Collapsed after layout</summary>
                <input id="closed-input"><p style="color:#eee">Hidden low contrast</p></details>
              </main>""")
            # Chromium can retain nonzero rectangles after collapsing details.
            page.locator("#closed-input").bounding_box()
            page.locator("details").evaluate("e => e.open=false")
            page.add_style_tag(content="#closed-summary:focus-visible { outline:3px solid black; }")
            page.keyboard.press("Tab")
            audit = mapping(page.evaluate(AUDIT))
            (output / "dom-last-audit.json").write_text(
                json.dumps(audit, indent=2), encoding="utf-8"
            )
            failures = {item["selector"]: item["reason"] for item in records(audit["focus"])}
            assert failures == {
                "#missing": "missing-indicator",
                "#transparent": "missing-indicator",
                "#bad-ring": "low-contrast-indicator",
                "#decoration": "missing-indicator",
                "#bad-outline": "low-contrast-indicator",
                "#near-threshold": "low-contrast-indicator",
            }, failures
            assert {item["selector"] for item in records(audit["focus_review"])} == {
                "#blur",
                "#inset",
            }
            assert {item["selector"] for item in records(audit["contrast"])} == {
                "#opacity",
                "#leaf",
            }
            assert {item["selector"] for item in records(audit["contrast_review"])} == {"#gradient"}
            checked = records(audit["focus_checked"])
            assert len(checked) == 10
            assert not any(item["selector"] == "#closed-input" for item in checked)
            ring = next(item for item in checked if item["selector"] == "#ring")
            assert ring["status"] == "VERIFIED" and records(ring["indicators"])[0]["ratio"] == 21
            audit["case"] = "intentional-failures-and-review-controls"
            audits.append(audit)
            (output / "dom-audits.json").write_text(json.dumps(audits, indent=2), encoding="utf-8")
            page.set_content("""<details open><summary>Already open</summary></details>
              <details><summary>One</summary><input></details>
              <details><summary>Two</summary><input></details>
              <details><summary>Three</summary><input></details>""")
            expand_details(page)
            assert page.locator("details[open]").count() == 4
            result: dict[str, object] = {
                "status": "VERIFIED",
                "scope": "LOCAL_DOM_REGRESSION_NOT_APPLICATION_ACCEPTANCE",
                "browser": instance.version,
                "matrix_pages": 0,
                "dom_cases": len(audits),
                "keyboard_expand_repeated_details": "VERIFIED",
                "screen_reader": "NOT RUN",
                "owner_acceptance": "PENDING",
            }
        finally:
            context.close()
            instance.close()
    result["browser_closed"] = True
    return result


def submit(page: Page) -> None:
    page.locator("form[data-form-submit] button[type=submit]").click()
    page.wait_for_load_state("domcontentloaded")


def browser(origin: str, output: Path, executable: str) -> dict[str, object]:
    parsed = urlparse(origin)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path:
        raise ValueError("UX browser requires the owned loopback HTTP origin")
    data = mapping(json.loads((output / "fixture.json").read_text(encoding="utf-8")))
    pages = {
        "today": "/",
        "plans": "/plans/",
        "progress": "/progress/",
        "coach": "/coach/",
        "profile": "/profile/",
        "preferences": "/profile/preferences/",
        "billing": "/billing/",
        "scheduled": "/scheduled/" + str(data["scheduled"]) + "/",
        "proposal": "/coach/proposals/" + str(data["proposal"]) + "/",
        "offline": "/offline/",
    }
    audits: list[dict[str, object]] = []
    errors: list[str] = []
    tasks: list[str] = []
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path=executable, headless=True)
        context = instance.new_context(viewport={"width": 1440, "height": 1000})
        # Only loopback HTTP assets; generated data is never sent to a provider.
        context.route(
            "**/*",
            lambda route: (
                route.continue_() if route.request.url.startswith(origin + "/") else route.abort()
            ),
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(origin + "/accounts/signup/")
            assert page.locator("form").count() >= 1
            tasks.append("signup_form_real_route")
            login(page, origin, "owner@browser.test", os.environ["BASIS_E2E_PASSWORD"])
            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                for theme in ("light", "dark"):
                    page.evaluate("value => localStorage.setItem('basis-theme', value)", theme)
                    for name, path in pages.items():
                        response = page.goto(origin + path)
                        assert response is not None and response.status == 200, (
                            path,
                            response.status if response else None,
                        )
                        page.wait_for_function(
                            "value => document.documentElement.classList.contains('dark') === (value === 'dark')",
                            arg=theme,
                        )
                        no_overflow(page)
                        page.keyboard.press("Tab")
                        audit = mapping(page.evaluate(AUDIT))
                        audit.update({"page": name, "width": width, "theme": theme})
                        audits.append(audit)
                        page.screenshot(
                            path=str(output / f"{name}-{width}-{theme}.png"),
                            full_page=True,
                            animations="disabled",
                        )
                        if name == "proposal":
                            expand_details(page)
                            assert page.locator("details:not([open])").count() == 0
                            expanded = mapping(page.evaluate(AUDIT))
                            expanded.update(
                                {"page": "proposal-expanded", "width": width, "theme": theme}
                            )
                            audits.append(expanded)
                            page.screenshot(
                                path=str(output / f"proposal-expanded-{width}-{theme}.png"),
                                full_page=True,
                                animations="disabled",
                            )
            tasks.append("viewport_theme_matrix_60_pages_and_6_expanded_proposal_states")
            page.goto(origin + "/")
            page.keyboard.press("Tab")
            assert page.locator(".skip-link").evaluate("node => node === document.activeElement")
            page.keyboard.press("Enter")
            assert page.url.endswith("#main")
            toggle = page.locator("[data-theme-toggle]:visible").first
            toggle.focus()
            outline = toggle.evaluate(
                "node => ({style:getComputedStyle(node).outlineStyle,width:getComputedStyle(node).outlineWidth})"
            )
            assert mapping(outline)["style"] != "none"
            page.keyboard.press("Enter")
            tasks.append("keyboard_skip_theme_focus")
            page.goto(origin + pages["scheduled"] + "reschedule/")
            page.locator("input[name=date]").fill(str(data["rescheduled_date"]))
            submit(page)
            assert page.url.endswith(pages["scheduled"])
            page.goto(origin + pages["scheduled"] + "reschedule/")
            assert page.locator("input[name=date]").input_value() == data["rescheduled_date"]
            tasks.append("reschedule_real_post_and_persisted_date")
            session_url = create_session(page, origin, "Sesión UX ficticia")
            assert "/sessions/" in session_url
            tasks.append("manual_training_real_post")
            page.goto(origin + "/progress/")
            assert "completadas ?" not in page.locator("main").inner_text()
            tasks.append("progress_real_route_and_separator")
            page.goto(origin + "/coach/jobs/" + str(data["job"]) + "/")
            for _ in range(3):
                page.evaluate(
                    """async url => {
                  await htmx.ajax('GET',url,{target:'#job-result',swap:'outerHTML'});
                }""",
                    origin + "/coach/jobs/" + str(data["job"]) + "/",
                )
                assert page.locator("#job-result").count() == 1
                assert page.get_by_role("link", name="Revisar propuesta").count() == 1
            tasks.append("three_real_htmx_fragment_swaps_single_result")
            page.get_by_role("link", name="Revisar propuesta").click()
            page.locator("button[name=decision][value=accept]").click()
            page.wait_for_url("**/plans/*/")
            assert "Propuesta UX ficticia" in page.locator("main").inner_text()
            tasks.append("synthetic_proposal_real_review_acceptance_and_plan")
            assert not errors, errors
            findings = [
                a
                for a in audits
                if any(
                    a[key]
                    for key in ("contrast", "contrast_review", "targets", "focus", "focus_review")
                )
            ]
            return {
                "status": "VERIFIED_WITH_FINDINGS" if findings else "VERIFIED",
                "browser": instance.version,
                "matrix_pages": len(audits),
                "route_matrix_pages": 60,
                "expanded_proposal_states": 6,
                "tasks": tasks,
                "audits": audits,
                "findings": findings,
                "javascript_errors": errors,
                "screen_reader": "NOT RUN",
                "owner_acceptance": "PENDING",
                "fixture": "SYNTHETIC_FIXTURE_NOT_PROVIDER",
                "browser_closed": True,
            }
        finally:
            context.close()
            instance.close()
            (output / "browser-closed.json").write_text(
                json.dumps({"browser_closed": True}), encoding="utf-8"
            )


def run(output: Path, executable: str, *, dom_only: bool = False) -> int:
    output = output.resolve()
    cache = ROOT / ".cache"
    if cache.is_symlink() or cache.resolve() != cache or not output.is_relative_to(cache):
        raise ValueError("UX artifacts require the repository-owned cache")
    output.mkdir(parents=True, exist_ok=False)
    before = source_binding()
    (output / "source-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    password, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    environment = child_environment(output / "ux.sqlite3", password, secret)
    server: subprocess.Popen[str] | None = None
    server_log: TextIO | None = None
    result: dict[str, object] = {
        "status": "FAILED",
        "scope": "LOCAL_DOM_REGRESSION" if dom_only else "APPLICATION_UX_ACCEPTANCE",
        "provider_calls": "DISABLED",
        "smtp": "DISABLED",
        "toolchain": {
            "python": sys.version.split()[0],
            "playwright": version("playwright"),
            "django_cotton_ui": version("django-cotton-ui"),
        },
    }
    try:
        if dom_only:
            result.update(dom_checks(output, executable))
        else:
            execute(
                [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "0"],
                environment,
                output / "migrate.log",
            )
            execute(
                [
                    sys.executable,
                    "-m",
                    "scripts.ux_acceptance",
                    "--fixture",
                    "--output",
                    str(output),
                ],
                environment,
                output / "fixture.log",
            )
            origin = "http://127.0.0.1:" + str(choose_port(0))
            result["origin"] = origin
            result["database"] = str(output / "ux.sqlite3")
            server_log = (output / "server.log").open("w", encoding="utf-8")
            server = subprocess.Popen(
                [
                    sys.executable,
                    "manage.py",
                    "runserver",
                    origin.removeprefix("http://"),
                    "--noreload",
                ],
                cwd=ROOT,
                env=environment,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            result["server_pid"] = server.pid
            ready(server, origin)
            execute(
                [
                    sys.executable,
                    "-m",
                    "scripts.ux_acceptance",
                    "--worker",
                    "--origin",
                    origin,
                    "--output",
                    str(output),
                    "--browser-executable",
                    executable,
                ],
                environment,
                output / "browser.log",
                timeout=480,
            )
            result.update(
                mapping(json.loads((output / "browser-result.json").read_text(encoding="utf-8")))
            )
    except Exception as error:
        result["error"] = str(error).replace(password, "[REDACTED]").replace(secret, "[REDACTED]")
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if server_log is not None:
            server_log.close()
        result["server_stopped"] = server is None or server.poll() is not None
        if (output / "browser-closed.json").is_file():
            result.update(
                mapping(json.loads((output / "browser-closed.json").read_text(encoding="utf-8")))
            )
        after = source_binding()
        (output / "source-after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
        result["source_sha256"] = before["aggregate_sha256"]
        result["source_unchanged"] = before == after
        if before != after:
            result.update(
                {"status": "FAILED", "error": "Authored runtime changed during UX acceptance"}
            )
        for log in output.glob("*.log"):
            content = log.read_text(encoding="utf-8", errors="replace")
            log.write_text(
                content.replace(password, "[REDACTED]").replace(secret, "[REDACTED]"),
                encoding="utf-8",
            )
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "receipt": str(output / "result.json"),
                "server_stopped": result["server_stopped"],
            }
        )
    )
    return (
        0
        if result["status"] in ("VERIFIED", "VERIFIED_WITH_FINDINGS") and result["server_stopped"]
        else 1
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".cache" / "ux-acceptance" / uuid4().hex
    )
    parser.add_argument("--browser-executable")
    parser.add_argument("--origin")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument(
        "--dom-only",
        action="store_true",
        help="Run local measurement regressions without a DB/server",
    )
    args = parser.parse_args()
    output = Path(args.output).resolve()
    cache = ROOT / ".cache"
    if cache.is_symlink() or cache.resolve() != cache or not output.is_relative_to(cache):
        parser.error("UX artifacts require the repository-owned cache")
    if args.fixture:
        fixture(output)
        return 0
    if args.worker:
        result = browser(str(args.origin), output, str(args.browser_executable))
        (output / "browser-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    if not args.browser_executable or not Path(args.browser_executable).is_file():
        parser.error("--browser-executable must identify an installed Chromium executable")
    return run(output, str(args.browser_executable), dom_only=args.dom_only)


if __name__ == "__main__":
    raise SystemExit(main())
