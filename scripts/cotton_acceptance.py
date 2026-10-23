"""Real loopback Cotton/HTMX/Alpine/CSRF/public-cache evidence; no providers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Route, sync_playwright

from scripts.acceptance_browser import (
    ROOT,
    child_environment,
    choose_port,
    execute,
    ready,
    source_binding,
)
from scripts.browser_smoke import login, mapping, no_overflow, service_worker_ready
from scripts.ux_acceptance import AUDIT as UX_AUDIT
from scripts.ux_acceptance import records

# Scoped adaptation only: the shared auditor's numeric-channel regex mistakes
# OKLCH lightness/chroma/hue for sRGB channels. Let the browser's CSS Color engine
# convert computed solid paints to explicit sRGB, preserving fractional channels
# and alpha (no 8-bit canvas quantization). Reject unsupported/ambiguous paints.
COLOR_NORMALIZER = r"""
  const rgb = color => {
    if(typeof color!=='string')throw Error('Unknown solid paint: '+String(color));
    const number='[+-]?(?:\\d*\\.\\d+|\\d+\\.?\\d*)(?:e[+-]?\\d+)?';
    const legacy=new RegExp('^rgba?\\(('+number+'),?\\s+('+number+'),?\\s+('
      +number+')(?:\\s*[,/]\\s*('+number+'))?\\)$','i');
    const old=color.match(legacy);
    if(old) {
      const values=[+old[1],+old[2],+old[3],old[4]===undefined?1:+old[4]];
      if(values.some(v=>!Number.isFinite(v))||values.slice(0,3).some(v=>v<0||v>255)
        ||values[3]<0||values[3]>1)throw Error('Invalid sRGB paint: '+color);
      return values;
    }
    if(!/^(?:oklch|oklab|lab|lch|color|color-mix|rgb|rgba|hsl|hsla)\(/i.test(color)
      ||/\b(?:none|currentcolor|var|env)\b/i.test(color))throw Error('Unknown solid paint: '+color);
    const relative='color(from '+color+' srgb r g b / alpha)';
    if(!CSS.supports('color',relative))throw Error('Unsupported solid paint conversion: '+color);
    const probe=document.createElement('span');
    probe.style.setProperty('color',relative,'important');
    probe.style.setProperty('display','none','important');
    document.documentElement.append(probe);
    let converted;
    try { converted=getComputedStyle(probe).color; } finally { probe.remove(); }
    const match=converted.match(new RegExp('^color\\(srgb\\s+('+number+')\\s+('
      +number+')\\s+('+number+')(?:\\s*/\\s*('+number+'))?\\)$','i'));
    if(!match)throw Error('Unresolved solid paint conversion: '+color+' => '+converted);
    const values=[+match[1],+match[2],+match[3],match[4]===undefined?1:+match[4]];
    if(values.some(v=>!Number.isFinite(v))||values.slice(0,3).some(v=>v<-.0001||v>1.0001)
      ||values[3]<0||values[3]>1)
      throw Error('Out-of-gamut solid paint needs review: '+color+' => '+converted);
    return [...values.slice(0,3).map(v=>Math.min(1,Math.max(0,v))*255),values[3]];
  };
"""
_LEGACY_RGB = "  const rgb = c => (c.match(/[\\d.]+/g)||[]).map(Number);"
if UX_AUDIT.count(_LEGACY_RGB) != 1:
    raise RuntimeError("Shared auditor color parser changed; scoped adaptation needs review")
AUDIT = UX_AUDIT.replace(_LEGACY_RGB, COLOR_NORMALIZER)

# One overall deadline, never renewed by a chained transition. Keep the existing
# 1000ms finite-effect limit and require four consecutive animation-free RAFs.
# A chained transition can start two RAFs after the previous one ends; two
# quiet frames cut such a chain off early (MAM-627 R2 reproduction).
# Observe again after every batch: Alpine may start its next transition later.
SETTLE = r"""async () => {
  const deadline=performance.now()+1500;
  let timer, expired=false;
  try {
    await Promise.race([
      (async () => {
        await document.fonts.ready;
        let quietFrames=0;
        while(!expired && quietFrames<4) {
          await new Promise(requestAnimationFrame);
          if(expired)return;
          if(performance.now()>=deadline)throw Error('Unsettled animation');
          const animations=document.getAnimations();
          for(const a of animations) {
            const t=a.effect?.getComputedTiming();
            if(!t || !Number.isFinite(t.endTime) || t.endTime>1000
              || a.playState==='paused' || !Number.isFinite(a.playbackRate)
              || a.playbackRate<=0 || t.endTime/a.playbackRate>1000)
              throw Error('Unbounded or unsupported animation');
          }
          const active=animations.filter(a=>a.playState==='running'||a.pending);
          if(active.length) {
            quietFrames=0;
            await Promise.all(active.map(a=>a.finished.catch(()=>{})));
          } else {
            quietFrames++;
          }
        }
      })(),
      new Promise((_,reject)=>{timer=setTimeout(()=>{
        expired=true;reject(Error('Unsettled animation'));
      },1500);})
    ]);
  } finally { expired=true;clearTimeout(timer); }
}"""

BORDERS = (
    "() => {\n"
    + COLOR_NORMALIZER
    + r"""
  const lum = c => rgb(c).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
    .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
  const ratio = (a,b) => (Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
  return [...document.querySelectorAll('input:not([type=hidden]):not(:disabled)')].map(e=>{
    const s=getComputedStyle(e), bg=s.backgroundColor;
    if(rgb(bg)[3]!==1)throw Error('Translucent control background needs review');
    return {id:e.id,ratios:['Top','Right','Bottom','Left'].map(side=>{
      if(s['border'+side+'Style']!=='solid'||parseFloat(s['border'+side+'Width'])<1)
        throw Error('Unsupported control border');
      if(rgb(s['border'+side+'Color'])[3]!==1)throw Error('Translucent control border needs review');
      return ratio(s['border'+side+'Color'],bg);
    })};
  });
}"""
)

# Record only presentation values; never form values, cookies, headers or secrets.
PAINTS = (
    "() => {\n"
    + COLOR_NORMALIZER
    + r"""
  return [...document.querySelectorAll('[role="alert"]')].map(e=>{
    const s=getComputedStyle(e);
    return {classes:e.className,color:s.color,background:s.backgroundColor,
      srgb:rgb(s.color),background_srgb:rgb(s.backgroundColor)};
  });
}"""
)

TOKEN_STATE = """selector => {
  const card=document.querySelector(selector), s=getComputedStyle(card);
  // Titled cards pad an inner body (last child); untitled cards pad the card itself.
  const pad=e=>getComputedStyle(e).padding;
  const cardPadding=[card,card.lastElementChild].filter(Boolean).map(pad).find(v=>v!=='0px')||pad(card);
  const input=document.querySelector('input:not([type=hidden])');
  const button=document.querySelector('.focus-ring');
  const body=getComputedStyle(document.body);
  return {font:body.fontFamily,bodySize:body.fontSize,
    radius:s.borderTopLeftRadius,padding:cardPadding,
    background:body.backgroundColor,
    inputRadius:input?getComputedStyle(input).borderTopLeftRadius:null,
    inputFont:input?getComputedStyle(input).fontFamily:null,
    inputSize:input?getComputedStyle(input).fontSize:null,
    buttonFont:button?getComputedStyle(button).fontFamily:null,
    buttonSize:button?getComputedStyle(button).fontSize:null};
}"""

FOCUSABLE = r"""() => {
  const all=[...document.querySelectorAll('*')];
  return [...document.querySelectorAll(
    'a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex],[contenteditable="true"]'
  )].filter(e=>e.tabIndex>=0 && !e.matches(':disabled') && !e.closest('[inert]')
    && e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})
    && e.getClientRects().length).map(e=>{
      if(e.tabIndex>0)throw Error('Positive tabindex requires explicit ordering review');
      return e.tagName+':'+all.indexOf(e);
    });
}"""

# Allowlisted structural/boolean diagnostics only: no DOM text, input values,
# arbitrary attributes, URLs, error messages, storage, cookies or headers.
DIALOG_STATE = r"""() => {
  const overlay=document.querySelector('[x-bind="overlay"]');
  const panel=document.querySelector('[x-bind="dialog"]');
  const trigger=document.querySelector('#open-dialog');
  const visible=e=>!!e&&e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
  let show=null;
  if(overlay&&window.Alpine) {
    const value=window.Alpine.$data(overlay).show;
    if(typeof value==='boolean')show=value;
  }
  return {
    overlays:document.querySelectorAll('[x-bind="overlay"]').length,
    panels:document.querySelectorAll('[x-bind="dialog"]').length,
    kit_show:show,overlay_visible:visible(overlay),panel_visible:visible(panel),
    inner_role_dialog:panel?.getAttribute('role')==='dialog',
    root_role_dialog:document.querySelector('#catalog-dialog')?.getAttribute('role')==='dialog',
    aria_modal:panel?.getAttribute('aria-modal')==='true',
    close_label_cerrar:document.querySelector('[x-bind="closeButton"]')
      ?.getAttribute('aria-label')==='Cerrar',
    focus_in_panel:!!panel&&panel.contains(document.activeElement),
    focus_on_trigger:!!trigger&&trigger===document.activeElement
  };
}"""


def binding() -> dict[str, object]:
    return {
        "runtime": source_binding(),
        "verification": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "scripts/cotton_acceptance.py",
                "tests/regression/test_components.py",
                "mypy-django.ini",
                "docs/COMPONENTS.md",
                "docs/COTTON-VERIFICATION.md",
            )
        },
    }


def mark_stage(
    result: dict[str, object], output: Path, phase: str, filename: str = "browser-result.json"
) -> None:
    """Persist the active phase before work, including on later assertion failure."""
    result["stage"] = phase
    history = result.setdefault("stages", [])
    if not isinstance(history, list):
        raise TypeError("Stage history must be a list")
    history.append(phase)
    (output / filename).write_text(json.dumps(result, indent=2), encoding="utf-8")


def active_key(page: Page) -> str:
    return str(
        page.evaluate("""() => {const e=document.activeElement;return e===document.body
      ? 'BODY' : e.tagName+':'+[...document.querySelectorAll('*')].indexOf(e);}""")
    )


def keyboard(page: Page) -> list[str]:
    """Real Tab cycle, body sentinel allowed once at wrap, exact eligible-stop coverage."""
    expected = page.evaluate(FOCUSABLE)
    assert isinstance(expected, list) and expected
    page.keyboard.press("Tab")
    assert page.locator(".skip-link").evaluate("e=>e===document.activeElement")
    stops: list[str] = []
    bodies = 0
    for _ in range(len(expected) + 3):
        key = active_key(page)
        if key == "BODY":
            bodies += 1
            assert bodies == 1 and set(stops) == set(expected), (stops, expected)
            page.keyboard.press("Tab")
            continue
        if key in stops:
            assert key == stops[0], ("Nonconsecutive keyboard trap", key)
            break
        page.evaluate(SETTLE)
        item = mapping(
            page.evaluate("""() => {
          const e=document.activeElement,s=getComputedStyle(e);
          return {visible:e.matches(':focus-visible'),width:parseFloat(s.outlineWidth),
            style:s.outlineStyle,offset:parseFloat(s.outlineOffset),disabled:e.matches(':disabled'),
            eligible:!e.closest('[inert]')&&e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})};
        }""")
        )
        assert item == {
            "visible": True,
            "width": 3,
            "style": "solid",
            "offset": 3,
            "disabled": False,
            "eligible": True,
        }, (key, item)
        stops.append(key)
        page.keyboard.press("Tab")
    else:
        raise AssertionError("Keyboard traversal did not complete")
    assert len(stops) == len(expected) and set(stops) == set(expected), (stops, expected)
    for key in reversed(stops):
        page.keyboard.press("Shift+Tab")
        if active_key(page) == "BODY":
            page.keyboard.press("Shift+Tab")
        assert active_key(page) == key, (key, active_key(page))
    return stops


def token_mutation(page: Page, selector: str) -> dict[str, object]:
    page.evaluate(SETTLE)
    original = page.locator("html").get_attribute("style")
    before = mapping(page.evaluate(TOKEN_STATE, selector))
    diagnostic: dict[str, object] = {
        "selector": selector,
        "button_selector": ".focus-ring",
        "input_selector": "input:not([type=hidden])",
        "before": before,
        "after": None,
    }
    try:
        # app.css body owns --font-md; its unlayered control font:inherit wins
        # over layered Tailwind text-sm. Mutate both canonical sizes, not a
        # downstream utility or per-control override, to test actual authority.
        page.evaluate("""() => {
          const s=document.documentElement.style;
          s.setProperty('--font-body','monospace');
          s.setProperty('--font-md','19px');
          s.setProperty('--font-sm','19px');
          s.setProperty('--space-1','6px');
          s.setProperty('--radius-lg','30px');
          s.setProperty('--radius-sm','18px');
          s.setProperty('--basis-brand-background','#f6f0ff');
        }""")
        page.evaluate(SETTLE)
        after = mapping(page.evaluate(TOKEN_STATE, selector))
        diagnostic["after"] = after
        assert before["font"] != after["font"] and after["font"] == "monospace", (
            "Body canonical font-family did not change to monospace",
            diagnostic,
        )
        assert before["bodySize"] != after["bodySize"] and after["bodySize"] == "19px", (
            "Body canonical font-size did not change to 19px",
            diagnostic,
        )
        assert before["radius"] != after["radius"] and after["radius"] == "30px", (
            "Card canonical radius did not change to 30px",
            diagnostic,
        )
        assert before["padding"] != after["padding"], (
            "Card canonical spacing did not change computed padding",
            diagnostic,
        )
        assert before["background"] != after["background"], (
            "Canonical brand background did not change body paint",
            diagnostic,
        )
        assert before["buttonFont"] != after["buttonFont"] and after["buttonFont"] == "monospace", (
            "Kit button canonical font-family did not change to monospace",
            diagnostic,
        )
        assert before["buttonSize"] != after["buttonSize"] and after["buttonSize"] == "19px", (
            "Kit button canonical font-size did not change to 19px",
            diagnostic,
        )
        if before["inputRadius"] is not None:
            assert after["inputRadius"] == "18px", (
                "Input canonical radius did not resolve to 18px",
                diagnostic,
            )
            assert (
                before["inputFont"] != after["inputFont"] and after["inputFont"] == "monospace"
            ), (
                "Input canonical font-family did not change to monospace",
                diagnostic,
            )
            assert before["inputSize"] != after["inputSize"] and after["inputSize"] == "19px", (
                "Input canonical font-size did not change to 19px",
                diagnostic,
            )
    finally:
        page.evaluate(
            """style => {if(style===null)document.documentElement.removeAttribute('style');
          else document.documentElement.setAttribute('style',style);}""",
            original,
        )
        page.evaluate(SETTLE)
    restored_style = page.locator("html").get_attribute("style")
    assert restored_style == original, (
        "Original html style attribute was not restored exactly",
        {**diagnostic, "original_style": original, "restored_style": restored_style},
    )
    restored = mapping(page.evaluate(TOKEN_STATE, selector))
    assert restored == before, (
        "Computed presentation did not return to pre-mutation state",
        {**diagnostic, "restored": restored},
    )
    return {
        "before": before,
        "after": after,
        "restored": restored,
        "original_style_preserved": True,
    }


def measurement_regressions(page: Page) -> dict[str, object]:
    # Analytical sRGB/OKLab references, independent of production tokens. For
    # neutral OKLab L=.5, linear RGB=L^3=.125; sRGB=0.388572859*255.
    # Reference-only channel tolerance: 0.05 on the 0..255 scale (0.05/255
    # normalized). Directed pinned-Chromium observation of OKLab/OKLCH white
    # yields [254.967105,255,255], a 0.032895 conversion/serialization deviation.
    # The bound covers that precision difference without 8-bit rounding. Alpha
    # retains 0.00001. Neither tolerance is used by AUDIT or contrast thresholds;
    # measured fractional channels and the below-threshold focus control remain.
    conversion = page.evaluate(
        "() => {\n"
        + COLOR_NORMALIZER
        + r"""
      const channelTolerance=.05, alphaTolerance=.00001;
      const cases=[['rgb(0, 0, 0)',[0,0,0,1]],
        ['rgb(148.9, 148.9, 148.9)',[148.9,148.9,148.9,1]],
        ['oklch(0 0 0)',[0,0,0,1]],['oklab(1 0 0)',[255,255,255,1]],
        ['oklch(1 0 0)',[255,255,255,1]],['color(srgb 1 1 1)',[255,255,255,1]],
        ['oklab(0.5 0 0 / 0.25)',[99.086079,99.086079,99.086079,.25]],
        ['color(srgb 0.2 0.4 0.6 / 0.5)',[51,102,153,.5]],
        ['color-mix(in oklab, black 50%, white)',[99.086079,99.086079,99.086079,1]]];
      const results=cases.map(([paint,expected])=>{
        const actual=rgb(paint);
        if(actual.some((v,i)=>Math.abs(v-expected[i])>(i===3?alphaTolerance:channelTolerance)))
          throw Error('Analytical color reference mismatch: '+paint);
        return {paint,actual,expected,channelTolerance,alphaTolerance};
      });
      for(const paint of ['unknown(1 2 3)','currentColor','var(--missing)',
        'oklch(none 0 0)','linear-gradient(black,white)','color(srgb 2 0 0)']) {
        let rejected=false;try{rgb(paint);}catch(_){rejected=true;}
        if(!rejected)throw Error('Unknown/ambiguous paint accepted: '+paint);
      }
      return results;
    }"""
    )
    # Low/high contrast plus alpha compositing in modern color spaces.
    for paint, fails in (
        ("#eee", True),
        ("black", False),
        ("oklch(0.95 0 0)", True),
        ("oklch(0 0 0)", False),
        ("oklab(0 0 0 / .1)", True),
        ("color-mix(in oklab, black 50%, white)", False),
    ):
        page.set_content(f'<p style="color:{paint};background:white">Reference</p>')
        audit = mapping(page.evaluate(AUDIT))
        assert bool(records(audit["contrast"])) == fails, (paint, audit)
        assert not audit["contrast_review"]
    # Keep thresholds unrounded, and retain focus positive/negative controls.
    page.set_content("""<style>body{background:white;color:black}
      button:focus-visible{outline:3px solid oklch(0 0 0)}
      #bad:focus-visible{outline-color:oklch(.95 0 0)}
      #near:focus-visible{outline-color:rgb(148.9,148.9,148.9)}</style>
      <button id="good">Good</button><button id="bad">Bad</button>
      <button id="near">Below threshold before rounding</button>""")
    page.keyboard.press("Tab")
    audit = mapping(page.evaluate(AUDIT))
    assert {item["selector"] for item in records(audit["focus"])} == {"#bad", "#near"}, audit
    assert not audit["focus_review"], audit
    good = next(item for item in records(audit["focus_checked"]) if item["selector"] == "#good")
    assert records(good["indicators"])[0]["ratio"] == 21, good
    page.set_content("""<style>:focus-visible{outline:3px solid black;outline-offset:3px;}
      #hidden{display:none}</style><a class="skip-link" href="#main">Saltar</a>
      <main id="main"><button>Uno</button><button disabled>No</button>
      <button id="hidden">Oculto</button><div inert><button>Inerte</button></div>
      <details><summary>Detalle</summary><input aria-label="Oculto en detalle"></details>
      <input type="hidden"><input aria-label="Último"></main>""")
    stops = keyboard(page)
    assert len(stops) == 4, stops
    page.set_content("""<style>@keyframes forever{to{opacity:.5}}
      p{animation:forever 1s infinite}</style><p>Infinite must fail</p>""")
    try:
        page.evaluate(SETTLE)
    except PlaywrightError as error:
        assert "Unbounded or unsupported animation" in str(error)
    else:
        raise AssertionError("Infinite animation was silently skipped")
    for declaration in ("animation:bounded 1001ms", "animation:bounded 80ms paused"):
        page.set_content(
            "<style>@keyframes bounded{to{opacity:.5}}p{"
            + declaration
            + "}</style><p>Unsupported must fail</p>"
        )
        try:
            page.evaluate(SETTLE)
        except PlaywrightError as error:
            assert "Unbounded or unsupported animation" in str(error)
        else:
            raise AssertionError("Long or paused animation was silently skipped")
    page.set_content("""<style>p{transition:color 80ms;color:black}</style><p>Finite settles</p>""")
    page.locator("p").evaluate("e=>{getComputedStyle(e).color;e.style.color='rgb(20, 20, 20)';}")
    page.evaluate(SETTLE)
    assert page.locator("p").evaluate("e=>getComputedStyle(e).color") == "rgb(20, 20, 20)"
    # Independent CSS fixture, not production self-comparison: each end event
    # starts the next finite transition two RAFs later, as Alpine can do.
    page.set_content("""<style>p{opacity:1;transform:translateX(0);color:black;
      transition:opacity 80ms,transform 80ms,color 80ms}</style><p>Chained finite</p>""")
    page.locator("p").evaluate("""e=>{
      e.dataset.ended='0';
      e.addEventListener('transitionend',event=>{
        e.dataset.ended=String(Number(e.dataset.ended)+1);
        requestAnimationFrame(()=>requestAnimationFrame(()=>{
          if(event.propertyName==='opacity')e.style.transform='translateX(10px)';
          if(event.propertyName==='transform')e.style.color='rgb(20, 20, 20)';
        }));
      });
      getComputedStyle(e).opacity;e.style.opacity='.5';
    }""")
    page.evaluate(SETTLE)
    chained = mapping(
        page.locator("p").evaluate("""e=>{
          const s=getComputedStyle(e);
          return {ended:Number(e.dataset.ended),opacity:s.opacity,transform:s.transform,
            color:s.color,active:document.getAnimations().filter(a=>a.playState==='running'||a.pending).length};
        }""")
    )
    assert chained == {
        "ended": 3,
        "opacity": "0.5",
        "transform": "matrix(1, 0, 0, 1, 10, 0)",
        "color": "rgb(20, 20, 20)",
        "active": 0,
    }, chained
    # An endless chain of individually finite effects must hit the SAME overall
    # deadline, not receive another 1500ms allowance for every new animation.
    page.set_content("""<style>p{opacity:1;transition:opacity 80ms}</style><p>Never quiet</p>""")
    page.locator("p").evaluate("""e=>{
      e.addEventListener('transitionend',()=>requestAnimationFrame(()=>{
        e.style.opacity=e.style.opacity==='0.5'?'1':'0.5';
      }));
      getComputedStyle(e).opacity;e.style.opacity='.5';
    }""")
    try:
        page.evaluate(SETTLE)
    except PlaywrightError as error:
        assert "Unsettled animation" in str(error)
    else:
        raise AssertionError("Endless finite chain bypassed the overall deadline")
    # Replace only the synthetic negative fixture; never cancel real UI effects.
    page.set_content("<p>Animation regression fixtures complete</p>")
    return {
        "color_analytical_references": conversion,
        "unknown_ambiguous_out_of_gamut_rejected": True,
        "text_reference_controls": True,
        "focus_reference_controls": True,
        "keyboard_hidden_inert_closed_details": len(stops),
        "infinite_animation_rejected": True,
        "long_and_paused_animation_rejected": True,
        "finite_transition_settled": True,
        "chained_finite_transitions_settled": chained,
        "endless_finite_chain_deadline_rejected": True,
        "settle_overall_deadline_ms": 1500,
        "settle_max_effect_duration_ms": 1000,
        "settle_quiet_frames": 4,
    }


def browser(origin: str, output: Path, executable: str) -> dict[str, object]:
    audits: list[dict[str, object]] = []
    errors: list[str] = []
    blocked: list[str] = []
    swaps: list[str] = []
    result: dict[str, object] = {"status": "FAILED"}
    mark_stage(result, output, "browser_launch")
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path=executable, headless=True)
        context = instance.new_context(viewport={"width": 1440, "height": 1000})

        def local_only(route: Route) -> None:
            if route.request.url.startswith(origin + "/"):
                route.continue_()
            else:
                blocked.append(route.request.url.split("?", 1)[0])
                route.abort()

        context.route("**/*", local_only)
        page = context.new_page()
        # Error classes/counts diagnose JS failures without logging arbitrary
        # messages, which can contain form values or other sensitive content.
        page.on("pageerror", lambda error: errors.append(type(error).__name__))
        page.on(
            "request",
            lambda request: (
                swaps.append(request.url) if request.url.endswith("/fragment/") else None
            ),
        )
        try:
            mark_stage(result, output, "measurement_regressions")
            result["measurement_regressions"] = measurement_regressions(page)
            for width in (390, 768, 1440):
                for theme in ("light", "dark"):
                    mark_stage(result, output, f"catalog_matrix:{width}:{theme}")
                    page.set_viewport_size({"width": width, "height": 1000})
                    response = page.goto(origin + "/ui/components/")
                    assert response is not None and response.status == 200
                    page.evaluate(
                        "t=>document.documentElement.classList.toggle('dark',t==='dark')", theme
                    )
                    page.wait_for_function(
                        "document.querySelector('#component-fragment')._x_dataStack"
                    )
                    page.evaluate(SETTLE)
                    # Diagnose real computed paints before making contrast claims.
                    paints = page.evaluate(PAINTS)
                    (output / f"paints-{width}-{theme}.json").write_text(
                        json.dumps(paints, indent=2), encoding="utf-8"
                    )
                    no_overflow(page)
                    stops = keyboard(page)
                    assert len(stops) > 50
                    audit = mapping(page.evaluate(AUDIT))
                    borders = records(page.evaluate(BORDERS))
                    audit.update({"width": width, "theme": theme, "keyboard_stops": stops})
                    audit["control_borders"] = borders
                    audits.append(audit)
                    (output / "audits.json").write_text(
                        json.dumps(audits, indent=2), encoding="utf-8"
                    )
                    failure_keys = (
                        "contrast",
                        "contrast_review",
                        "focus",
                        "focus_review",
                        "targets",
                    )
                    assert not any(audit[key] for key in failure_keys), {
                        "width": width,
                        "theme": theme,
                        "failures": {key: audit[key] for key in failure_keys if audit[key]},
                    }
                    assert borders
                    for border in borders:
                        ratios = border["ratios"]
                        assert isinstance(ratios, list)
                        assert all(float(str(value)) >= 3 for value in ratios), border
                    page.screenshot(
                        path=str(output / f"catalog-{width}-{theme}.png"),
                        full_page=True,
                        animations="disabled",
                    )
            mark_stage(result, output, "token_mutation:catalog")
            page.goto(origin + "/ui/components/")
            page.evaluate("document.documentElement.classList.remove('dark')")
            tokens: dict[str, object] = {"catalog": token_mutation(page, "#token-card")}
            result["tokens"] = tokens
            mark_stage(result, output, "csrf_real_http")
            csrf = page.locator("input[name=csrfmiddlewaretoken]").input_value()
            assert (
                context.request.post(origin + "/ui/components/", form={"nombre": "x"}).status == 403
            )
            assert (
                context.request.post(
                    origin + "/ui/components/", form={"csrfmiddlewaretoken": "x" * 64}
                ).status
                == 403
            )
            accepted = context.request.post(
                origin + "/ui/components/",
                form={
                    "csrfmiddlewaretoken": csrf,
                    "nombre": "Ficticio",
                    "correo": "x@example.test",
                },
            )
            assert accepted.status == 200 and 'id="catalog-accepted"' in accepted.text()
            mark_stage(result, output, "form_error_summary_keyboard")
            page.locator("form[data-form-submit]").evaluate("e=>e.noValidate=true")
            page.locator("form button[type=submit]").click()
            summary = page.locator("[data-error-summary]")
            summary.wait_for()
            assert summary.evaluate("e=>e===document.activeElement")
            summary.locator("a").first.focus()
            page.keyboard.press("Enter")
            assert page.locator("#id_nombre").evaluate("e=>e===document.activeElement")
            page.screenshot(path=str(output / "catalog-errors.png"), full_page=True)
            mark_stage(result, output, "htmx_alpine_repeated_swaps")
            page.locator("#parent-counter").click()
            assert page.locator("#parent-value").inner_text() == "1"
            for index in range(3):
                mark_stage(result, output, f"htmx_alpine_swap:{index + 1}")
                page.locator("#child-counter").click()
                page.wait_for_function("document.querySelector('#child-value').textContent==='1'")
                with page.expect_response(
                    lambda r: r.url.endswith("/fragment/") and r.status == 200
                ):
                    page.locator("#swap-fragment").click()
                page.wait_for_function("document.querySelector('#child-value').textContent==='0'")
                assert page.locator("#component-fragment").count() == 1
                assert page.locator("#parent-value").inner_text() == "1"
                page.get_by_role("button", name="Detalle del fragmento").click()
                page.get_by_text("Contenido ficticio desplegable.", exact=True).wait_for()
                page.evaluate(SETTLE)
            page.locator("#child-counter").click()
            page.wait_for_function("document.querySelector('#child-value').textContent==='1'")
            assert len(swaps) == 3, swaps
            mark_stage(result, output, "csrf_origin_guard")
            csrf_guard = mapping(
                page.evaluate("""() => {
              const run=path=>{const detail={path,headers:{}};
                const e=new CustomEvent('htmx:configRequest',{bubbles:true,cancelable:true,detail});
                document.body.dispatchEvent(e);
                return {cancelled:e.defaultPrevented,token:!!detail.headers['X-CSRFToken']};};
              return {local:run('/ui/components/fragment/'),external:run('https://example.invalid/')};
            }""")
            )
            assert mapping(csrf_guard["local"]) == {"cancelled": False, "token": True}
            assert mapping(csrf_guard["external"]) == {"cancelled": True, "token": False}
            mark_stage(result, output, "dialog_keyboard_escape_focus_return")
            closed_state = mapping(page.evaluate(DIALOG_STATE))
            result["dialog_before_open"] = closed_state
            assert closed_state["overlays"] == 1 and closed_state["panels"] == 1, closed_state
            assert closed_state["kit_show"] is False, closed_state
            assert closed_state["overlay_visible"] is False, closed_state
            assert closed_state["panel_visible"] is False, closed_state
            assert closed_state["inner_role_dialog"] is True, closed_state
            assert closed_state["root_role_dialog"] is False, closed_state
            page.locator("#open-dialog").focus()
            page.keyboard.press("Enter")
            # First prove opening independently of role semantics. Keep the role
            # lookup below: visible markup alone does not prove accessibility.
            page.locator('[x-bind="overlay"]').wait_for(state="visible")
            page.wait_for_function(
                "window.Alpine.$data(document.querySelector('[x-bind=overlay]')).show===true"
            )
            page.evaluate(SETTLE)
            opened_state = mapping(page.evaluate(DIALOG_STATE))
            result["dialog_after_open"] = opened_state
            assert opened_state["kit_show"] is True, opened_state
            assert opened_state["overlay_visible"] is True, opened_state
            assert opened_state["panel_visible"] is True, opened_state
            assert opened_state["aria_modal"] is True, opened_state
            # Minor (a): Alpine must not overwrite the composed role/aria-label
            # on the open dialog (app.js sets them on DOMContentLoaded, Alpine binds
            # :aria-modal/:aria-labelledby on the same panel).
            assert opened_state["inner_role_dialog"] is True, opened_state
            assert opened_state["close_label_cerrar"] is True, opened_state
            dialog = page.get_by_role("dialog")
            dialog.wait_for()
            assert dialog.count() == 1
            assert dialog.evaluate("e=>e.matches('[x-bind=dialog]')")
            assert page.get_by_role("button", name="Cerrar", exact=True).count() == 1
            for key in ("Tab", "Shift+Tab"):
                for _ in range(4):
                    page.keyboard.press(key)
                    assert dialog.evaluate("e=>e.contains(document.activeElement)")
            page.screenshot(path=str(output / "catalog-dialog.png"), full_page=True)
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden")
            assert page.locator("#open-dialog").evaluate("e=>e===document.activeElement")
            escaped_state = mapping(page.evaluate(DIALOG_STATE))
            result["dialog_after_escape"] = escaped_state
            assert escaped_state["kit_show"] is False, escaped_state
            assert escaped_state["overlay_visible"] is False, escaped_state
            assert escaped_state["focus_on_trigger"] is True, escaped_state
            assert escaped_state["inner_role_dialog"] is True, escaped_state
            assert escaped_state["close_label_cerrar"] is True, escaped_state
            mark_stage(result, output, "primary_pages_login")
            login(page, origin, "owner@browser.test", os.environ["BASIS_E2E_PASSWORD"])
            for path in ("/", "/plans/", "/progress/", "/coach/", "/profile/"):
                mark_stage(result, output, f"token_mutation:primary:{path}")
                page.goto(origin + path)
                page.evaluate("document.documentElement.classList.remove('dark')")
                selector = ".basis-card"
                if page.locator(selector).count():
                    tokens[path] = token_mutation(page, selector)
                no_overflow(page)
            assert set(tokens) == {
                "catalog",
                "/",
                "/plans/",
                "/progress/",
                "/coach/",
                "/profile/",
            }, tokens
            mark_stage(result, output, "service_worker_ready")
            page.goto(origin + "/")
            readiness = service_worker_ready(page)
            assert context.request.get(origin + "/api/csrf/").status == 200
            mark_stage(result, output, "public_cache_inventory")
            cached = mapping(
                page.evaluate("""async () => {
              const result={};for(const key of await caches.keys()) {
                const cache=await caches.open(key);
                result[key]=(await cache.keys()).map(r=>new URL(r.url).pathname);
              }return result;
            }""")
            )
            paths: list[str] = []
            for key, values in cached.items():
                assert key.startswith("basis-shell-") and isinstance(values, list), cached
                paths.extend(str(value) for value in values)
            assert len(paths) == 19 and "/offline/" in paths, paths
            assert all(path == "/offline/" or path.startswith("/static/") for path in paths)
            digest_script = """async paths => {
              const results={};for(const path of paths){
                const response=await fetch(path);if(!response.ok)throw Error(path);
                const digest=await crypto.subtle.digest('SHA-256',await response.arrayBuffer());
                results[path]=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
              }return results;
            }"""
            public_paths = [path for path in paths if path != "/offline/"]
            mark_stage(result, output, "public_resource_online_digests")
            online = mapping(page.evaluate(digest_script, public_paths))
            mark_stage(result, output, "public_resource_offline_digests")
            context.set_offline(True)
            offline = mapping(page.evaluate(digest_script, public_paths))
            assert online == offline and len(offline) == 18
            mark_stage(result, output, "private_api_and_navigation_offline")
            assert page.evaluate("""async () => {
              try {await fetch('/api/csrf/');return false;}catch(_){return true;}
            }""")
            page.goto(origin + "/ui/components/")
            assert page.locator("#offline-sessions").count() == 1
            assert page.locator("#component-catalog").count() == 0
            assert "Browser Owner" not in page.locator("body").inner_text()
            page.screenshot(path=str(output / "offline-public-shell.png"), full_page=True)
            context.set_offline(False)
            mark_stage(result, output, "final_browser_checks")
            assert not errors, errors
            assert not blocked, blocked
            result.update(
                {
                    "status": "VERIFIED",
                    "browser": instance.version,
                    "matrix": audits,
                    "tokens": tokens,
                    "csrf_real_http": [403, 403, accepted.status],
                    "htmx_real_swaps": len(swaps),
                    "alpine_parent_retained_child_single_listener": True,
                    "dialog_keyboard_escape_focus_return": True,
                    "csrf_origin_guard": csrf_guard,
                    "service_worker": readiness,
                    "cache_paths": cached,
                    "offline_resource_sha256": offline,
                    "private_api_offline_rejected": True,
                    "private_navigation_not_cached": True,
                    "javascript_errors": errors,
                    "blocked_external_requests": blocked,
                    "screen_reader": "NOT RUN",
                    "physical_device": "NOT RUN",
                    "owner_acceptance": "PENDING",
                }
            )
            mark_stage(result, output, "browser_complete")
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)[:5900]
            result["javascript_errors"] = errors
            try:
                result["dialog_failure_state"] = mapping(page.evaluate(DIALOG_STATE))
            except Exception as diagnostic_error:
                result["dialog_failure_state"] = {
                    "unavailable": True,
                    "error_class": type(diagnostic_error).__name__,
                }
            raise RuntimeError(result["error"]) from None
        finally:
            context.close()
            instance.close()
            result["browser_closed"] = True
            result["screenshot_sha256"] = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.glob("*.png"))
            }
            result["audit_sha256"] = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.glob("*.json"))
                if path.name == "audits.json" or path.name.startswith("paints-")
            }
            (output / "browser-result.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
    return result


def run(output: Path, executable: str) -> int:
    # The coordinator supplies an evidence directory OUTSIDE the worktree. The
    # fixture's independent DB guard still requires a fresh repository-owned DB.
    output = output.absolute()
    if output.is_symlink() or output.resolve() != output:
        raise ValueError("Evidence must not redirect through symlinks")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Evidence directory must be fresh and empty")
    cache = ROOT / ".cache"
    if cache.is_symlink() or cache.resolve() != cache:
        raise ValueError("Fixture cache must not redirect outside the repository")
    owned = cache / ("mam627-" + uuid4().hex)
    owned.mkdir(parents=True, exist_ok=False)
    database = owned / "cotton.sqlite3"
    before = binding()
    password, secret = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    environment = child_environment(database, password, secret)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    server: subprocess.Popen[str] | None = None
    log: TextIO | None = None
    result: dict[str, object] = {
        "status": "FAILED",
        "provider_calls": "DISABLED",
        "smtp": "DISABLED",
        "database": str(database),
        "evidence": str(output),
        "toolchain": {
            "python": sys.version.split()[0],
            "playwright": version("playwright"),
            "django": version("django"),
            "django_cotton": version("django-cotton"),
            "django_cotton_ui": version("django-cotton-ui"),
        },
    }
    try:
        mark_stage(result, output, "database_migrate", "result.json")
        execute(
            [sys.executable, "manage.py", "migrate", "--noinput", "--verbosity", "0"],
            environment,
            output / "migrate.log",
        )
        mark_stage(result, output, "fixture_prepare", "result.json")
        execute(
            [sys.executable, "-m", "scripts.cotton_acceptance", "--fixture"],
            environment,
            output / "fixture.log",
        )
        origin = "http://127.0.0.1:" + str(choose_port(0))
        result["origin"] = origin
        mark_stage(result, output, "loopback_server_start", "result.json")
        log = (output / "server.log").open("w", encoding="utf-8")
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
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        result["server_pid"] = server.pid
        ready(server, origin)
        mark_stage(result, output, "browser_worker", "result.json")
        execute(
            [
                sys.executable,
                "-m",
                "scripts.cotton_acceptance",
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
        result["error"] = (
            str(error).replace(password, "[REDACTED]").replace(secret, "[REDACTED]")[:6000]
        )
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        if log is not None:
            log.close()
        result["server_stopped"] = server is None or server.poll() is not None
        worker_result = output / "browser-result.json"
        if worker_result.is_file():
            worker = mapping(json.loads(worker_result.read_text(encoding="utf-8")))
            result["browser_closed"] = worker.get("browser_closed", False)
            for key in (
                "error",
                "audit_sha256",
                "measurement_regressions",
                "stage",
                "stages",
                "tokens",
                "javascript_errors",
                "dialog_before_open",
                "dialog_after_open",
                "dialog_after_escape",
                "dialog_failure_state",
            ):
                if key in worker:
                    result["browser_error" if key == "error" else key] = worker[key]
        result["screenshot_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.glob("*.png"))
        }
        after = binding()
        result.update(
            {"source_before": before, "source_after": after, "source_unchanged": before == after}
        )
        if before != after:
            result["status"] = "FAILED"
        for path in [*output.glob("*.log"), *output.glob("*.json")]:
            text = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(
                text.replace(password, "[REDACTED]").replace(secret, "[REDACTED]"), encoding="utf-8"
            )
        # Keep evidence AND the owned fixture DB. Cleanup only the processes we started.
        (output / "result.json").write_text(
            json.dumps(result, indent=2)
            .replace(password, "[REDACTED]")
            .replace(secret, "[REDACTED]"),
            encoding="utf-8",
        )
    print(json.dumps({"status": result["status"], "receipt": str(output / "result.json")}))
    # Only allowlisted measurement/assertion details, never raw HTTP or form data.
    print(
        "SUMMARY "
        + json.dumps(
            {
                "status": result["status"],
                "stage": result.get("stage", ""),
                "browser_error": result.get("browser_error", ""),
                "matrix_pages": len(audits)
                if (audits := result.get("matrix")) and isinstance(audits, list)
                else 0,
                "measurement_regressions": bool(result.get("measurement_regressions")),
                "screenshots": list(mapping(result["screenshot_sha256"])),
                "source_unchanged": result["source_unchanged"],
                "server_stopped": result["server_stopped"],
                "browser_closed": result.get("browser_closed", False),
            }
        )
    )
    return 0 if result["status"] == "VERIFIED" and result["server_stopped"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--browser-executable")
    parser.add_argument("--origin")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.fixture:
        import django

        django.setup()
        from basis.adapters.django.acceptance_fixture import prepare

        prepare()
        return 0
    if args.output is None or args.browser_executable is None:
        parser.error("--output and an installed --browser-executable are required")
    if args.worker:
        parsed = urlsplit(str(args.origin))
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            parser.error("Only the owned loopback origin is permitted")
        browser(str(args.origin), Path(args.output), str(args.browser_executable))
        return 0
    return run(Path(args.output), str(args.browser_executable))


if __name__ == "__main__":
    raise SystemExit(main())
