"""Bounded offline UX screening. Stdlib + installed Playwright; no server or pytest.

Requires a NEW --output directory. Does not install/download a browser. A zero exit
means only the named automated checks passed, never human/WCAG/product acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import unquote, urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page, Route


class Arguments(argparse.Namespace):
    output: Path
    browser_executable: str | None


class StaticChecks(TypedDict):
    logo_exact_bytes: bool
    local_assets: list[str]
    dark_tokens_only: bool
    component_colors_tokens_only: bool
    no_network_or_storage_apis: bool


class TextRecord(TypedDict):
    element: str
    text: str
    color: str
    background: list[float]
    ratio: float
    threshold: float
    size: float
    weight: int


class TargetRecord(TypedDict):
    element: str
    name: str
    width: float
    height: float


class BorderRecord(TypedDict):
    element: str
    side: str
    color: str
    style: str
    width: float
    background: list[float]
    adjacentBackground: list[float]
    backgroundRatio: float
    adjacentRatio: float
    threshold: float


class Issue(TypedDict, total=False):
    kind: str
    element: str
    error: str
    text: str
    color: str
    background: list[float]
    ratio: float
    threshold: float
    size: float
    weight: int
    name: str
    width: float
    height: float
    side: str
    style: str
    adjacentBackground: list[float]
    backgroundRatio: float
    adjacentRatio: float
    viewport: float


class AuditResult(TypedDict):
    problems: list[Issue]
    reviews: list[Issue]
    text: list[TextRecord]
    targets: list[TargetRecord]
    controlBorders: list[BorderRecord]
    controlCount: int


class FocusRect(TypedDict):
    x: float
    y: float
    width: float
    height: float


class FocusRecord(TypedDict, total=False):
    body: bool
    element: str
    controlIndex: int
    nativeDate: bool
    outline: str
    style: str
    width: float
    offset: float
    focusVisible: bool
    focusWithin: bool
    rect: FocusRect
    background: list[float]
    ratio: float
    geometryOK: bool
    navTop: float
    scrollMarginTop: float
    scrollMarginBottom: float
    ok: bool
    error: str


class SelfTestResult(TypedDict):
    status: str
    negative_kinds: list[str]
    gradient_review: bool
    black_white_ratio: float
    gray_white_ratio: float
    invisible_focus_rejected: bool
    alpha_oracle: list[float]
    keyboard_negative_focus: list[FocusRecord]
    faint_control_border_rejected: AuditResult
    native_date_traversal: list[FocusRecord]
    native_date_trap_rejected: list[FocusRecord]
    native_date_nonconsecutive_repeat_rejected: list[FocusRecord]
    large_text_rejected: bool
    small_label_rejected: bool
    disclosure_controls_checked: bool
    occluded_focus_rejected: list[FocusRecord]


class AuditEntry(AuditResult, total=False):
    width: int
    theme: str
    route: str
    state: str
    disclosure: str
    tokens: dict[str, str]
    keyboard: list[FocusRecord]
    status: str


class TimerMetrics(TypedDict):
    created: int
    cleared: int
    active: int
    trainingSubmits: int


class SessionGeometry(TypedDict):
    scrollY: float
    navTop: float
    sessionTop: float
    sessionBottom: float
    ctaTop: float
    ctaBottom: float
    ctaWidth: float
    contentWidth: float
    primaryCount: int
    toolsClosed: bool
    navVisible: bool


class Report(TypedDict, total=False):
    schema: int
    status: str
    scope: str
    started_at: str
    tools: dict[str, str]
    human_approval: str
    independent_review: str
    screen_reader: str
    physical_device: str
    external_validation: str
    limitations: list[str]
    source_before: dict[str, str]
    source_after: dict[str, str]
    static: StaticChecks
    network_attempts: list[str]
    javascript_errors: list[str]
    auditor_self_tests: SelfTestResult
    flows: list[str]
    session_geometry: dict[str, SessionGeometry]
    rest_timer: list[TimerMetrics]
    onboarding_input_audit: AuditResult
    keyboard_activation: list[str]
    audits: list[AuditEntry]
    audit_counts: dict[str, int]
    screenshots: list[str]
    browser_closed: bool
    artifacts: dict[str, str]
    error: str
    traceback: str
    finished_at: str


ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE = ROOT / "docs/design/prototipo"
CANONICAL_LOGO = ROOT / "basis/adapters/web/static/basis/brand/logo.svg"
SOURCE_PATHS = [
    PROTOTYPE / "index.html",
    PROTOTYPE / "styles.css",
    PROTOTYPE / "app.js",
    PROTOTYPE / "assets/logo.svg",
    ROOT / "docs/design/STYLE_GUIDE.md",
    ROOT / "docs/design/FLOWS.md",
    ROOT / "docs/UX-PLAN.md",
    Path(__file__).resolve(),
    CANONICAL_LOGO,
]
ROUTES = ("hoy", "entrenamiento", "plan", "progreso", "entrenador", "bienvenida", "registro")
STATES = ("normal", "empty", "loading", "error", "offline", "pending", "conflict")
SCREENSHOTS = {
    *(f"hoy-{width}-{theme}.png" for width in (390, 1440) for theme in ("light", "dark")),
    *(
        f"{route}-390-{theme}.png"
        for route in ("plan", "onboarding", "registro")
        for theme in ("light", "dark")
    ),
}

# Executed on the real DOM, not a palette-only surrogate. No remote dependencies.
# Backgrounds and alpha are composited in sRGB, then WCAG relative luminance uses
# the piecewise linearization. Unsupported paint produces a blocking review item.
AUDITOR = r"""() => {
  const problems = [], reviews = [], text = [], targets = [], controlBorders = [];
  const rgba = value => {
    const match = value.match(/^rgba?\(([^)]+)\)$/);
    if (!match) throw Error('Unsupported color: ' + value);
    const parts = match[1].split(',').map(Number);
    return [parts[0], parts[1], parts[2], parts.length === 4 ? parts[3] : 1];
  };
  const over = (front, back) => {
    const a = front[3] + back[3] * (1 - front[3]);
    if (a === 0) return [0,0,0,0];
    return [0,1,2].map(i => (front[i]*front[3] + back[i]*back[3]*(1-front[3]))/a).concat(a);
  };
  const luminance = color => color.slice(0,3).map(v => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, v, i) => sum + v * [0.2126,0.7152,0.0722][i], 0);
  const ratio = (a,b) => (Math.max(luminance(a),luminance(b)) + 0.05) /
    (Math.min(luminance(a),luminance(b)) + 0.05);
  const visible = el => el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) &&
    !el.closest('[hidden], [inert]') && el.getBoundingClientRect().width > 0;
  const id = el => el.id ? '#' + el.id : el.tagName.toLowerCase() +
    (el.getAttribute('href') || '') + ':' + el.textContent.trim().slice(0,55);
  const background = el => {
    const chain = [];
    for (let n=el; n; n=n.parentElement) chain.unshift(n);
    let bg = [255,255,255,1];
    for (const node of chain) {
      const s = getComputedStyle(node);
      if (s.backgroundImage !== 'none' || s.filter !== 'none' ||
          s.mixBlendMode !== 'normal' || Number(s.opacity) !== 1 ||
          s.backdropFilter !== 'none') throw Error('Unsupported paint at ' + id(node));
      bg = over(rgba(s.backgroundColor), bg);
    }
    return bg;
  };
  const checkText = (el, content) => {
    try {
      const s = getComputedStyle(el), bg = background(el);
      const fg = over(rgba(s.color), bg), measured = ratio(fg,bg);
      const size = parseFloat(s.fontSize), weight = parseInt(s.fontWeight,10);
      const threshold = 4.5; // R2: all text sizes, never the large-text exception.
      const item = {element:id(el), text:content.slice(0,100), color:s.color,
        background:bg, ratio:measured, threshold, size, weight};
      text.push(item);
      if (measured < threshold) problems.push({kind:'text-contrast', ...item});
    } catch (error) { reviews.push({kind:'text-paint', element:id(el), error:String(error)}); }
  };
  const checkControlBorder = el => {
    try {
      const s = getComputedStyle(el), bg = background(el), adjacent = background(el.parentElement);
      if (s.borderImageSource !== 'none') throw Error('Unsupported border image at ' + id(el));
      for (const side of ['Top','Right','Bottom','Left']) {
        const color = s['border' + side + 'Color'], border = over(rgba(color),bg);
        const style = s['border' + side + 'Style'], width = parseFloat(s['border' + side + 'Width']);
        const item = {element:id(el), side:side.toLowerCase(), color, style, width,
          background:bg, adjacentBackground:adjacent, backgroundRatio:ratio(border,bg),
          adjacentRatio:ratio(border,adjacent), threshold:3};
        controlBorders.push(item);
        if (style !== 'solid' || !(width > 0) ||
            item.backgroundRatio < 3 || item.adjacentRatio < 3) {
          problems.push({kind:'control-border', ...item});
        }
      }
    } catch (error) {
      reviews.push({kind:'control-border-paint', element:id(el), error:String(error)});
    }
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node=walker.currentNode, el=node.parentElement;
    if (!node.textContent.trim() || !el || el.closest('script,style,noscript,option') || !visible(el)) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    if (![...range.getClientRects()].some(r => r.width > 0 && r.bottom > 0 && r.right > 0)) continue;
    checkText(el, node.textContent.trim());
  }
  for (const label of document.querySelectorAll('label')) {
    if (visible(label) && parseFloat(getComputedStyle(label).fontSize) < 14) {
      problems.push({kind:'small-label',element:id(label),size:parseFloat(getComputedStyle(label).fontSize),threshold:14});
    }
  }
  const controls = [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex="0"]')]
    .filter(el => !el.disabled && (visible(el) || el.classList.contains('skip')));
  for (const el of controls) {
    const rect = el.getBoundingClientRect();
    const name = (el.getAttribute('aria-label') || el.labels && [...el.labels].map(x=>x.textContent).join(' ') ||
      el.textContent || '').trim();
    const item={element:id(el),name,width:rect.width,height:rect.height};
    targets.push(item);
    if (!name) problems.push({kind:'missing-label',...item});
    if (rect.width < 44 || rect.height < 44) problems.push({kind:'small-target',...item});
    if (el.matches('input,textarea') && el.value) {
      // Never put even a fictional password in input-value evidence.
      checkText(el,el.matches('input[type="password"]') ? '[REDACTED PASSWORD]' : el.value);
    }
    if (el.matches('select')) checkText(el,el.selectedOptions[0]?.textContent || '');
    if (el.matches('input,select') && visible(el)) checkControlBorder(el);
  }
  if (document.documentElement.scrollWidth > innerWidth + 1) problems.push({kind:'horizontal-overflow',
    width:document.documentElement.scrollWidth,viewport:innerWidth});
  window.__ux = {visible,id,background,ratio,rgba,over,controls};
  return {problems,reviews,text,targets,controlBorders,controlCount:controls.length};
}"""

FOCUS = r"""() => {
  const el=document.activeElement, u=window.__ux;
  if (!el || el === document.body) return {body:true};
  const s=getComputedStyle(el), r=el.getBoundingClientRect();
  const nav=document.querySelector('nav'), shell=nav?.closest('.sidebar');
  const fixedMobile=nav && shell && getComputedStyle(shell).position === 'fixed' &&
    shell.getBoundingClientRect().width >= innerWidth - 1;
  const navTop=fixedMobile ? shell.getBoundingClientRect().top : innerHeight;
  const limit=fixedMobile && !el.closest('nav') ? navTop : innerHeight;
  const marginTop=parseFloat(s.scrollMarginTop), marginBottom=parseFloat(s.scrollMarginBottom);
  // Inspect the native Tab scroll result; never repair it with scrollIntoView.
  const geometryOK=r.left >= 6 && r.top >= 6 && r.right <= innerWidth - 6 &&
    r.bottom <= limit - 6 && (!fixedMobile || el.closest('nav') ||
      (marginTop >= 6 && marginBottom >= 6));
  const item={element:u.id(el), controlIndex:u.controls.indexOf(el),
    nativeDate:el.matches('input[type="date"]'), outline:s.outlineColor, style:s.outlineStyle,
    width:parseFloat(s.outlineWidth), offset:parseFloat(s.outlineOffset),
    focusVisible:el.matches(':focus-visible'), focusWithin:el.matches(':focus-within'),
    rect:{x:r.x,y:r.y,width:r.width,height:r.height}, geometryOK:Boolean(geometryOK),
    navTop, scrollMarginTop:marginTop, scrollMarginBottom:marginBottom};
  try {
    const bg=u.background(el.parentElement), fg=u.over(u.rgba(s.outlineColor),bg);
    item.background=bg; item.ratio=u.ratio(fg,bg);
    item.ok=(item.focusVisible || (item.nativeDate && item.focusWithin)) &&
      item.width >= 3 && item.offset >= 3 && item.style === 'solid' &&
      u.rgba(s.outlineColor)[3] === 1 && item.ratio >= 3 && item.geometryOK;
  } catch(error) { item.ok=false; item.error=String(error); }
  return item;
}"""

# Test instrumentation only, never shipped to the prototype. Counts real timers
# and submit events so duplicate intervals and automatic submits cannot hide.
TIMER_OBSERVER = r"""(() => {
  const active=new Set();
  window.__restAudit={created:0,cleared:0,active:0,trainingSubmits:0};
  const originalSet=window.setInterval.bind(window), originalClear=window.clearInterval.bind(window);
  window.setInterval=(handler, delay, ...args) => {
    const handle=originalSet(handler,delay,...args);
    active.add(handle); window.__restAudit.created++; window.__restAudit.active=active.size;
    return handle;
  };
  window.clearInterval=handle => {
    if (active.delete(handle)) window.__restAudit.cleared++;
    window.__restAudit.active=active.size; return originalClear(handle);
  };
  document.addEventListener('submit',event => {
    if (event.target.id === 'training-form') window.__restAudit.trainingSubmits++;
  },true);
})();"""


def fingerprint() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SOURCE_PATHS
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def static_checks() -> StaticChecks:
    html = (PROTOTYPE / "index.html").read_text(encoding="utf-8")
    css = (PROTOTYPE / "styles.css").read_text(encoding="utf-8")
    js = (PROTOTYPE / "app.js").read_text(encoding="utf-8")
    require(
        (PROTOTYPE / "assets/logo.svg").read_bytes() == CANONICAL_LOGO.read_bytes(),
        "Logo must be an exact byte copy of the canonical SVG",
    )
    refs = re.findall(r'(?:src|href)="([^\"]+)"', html)
    for ref in refs:
        if ref.startswith("#"):
            continue
        require(not urlparse(ref).scheme and not ref.startswith("//"), f"Non-local asset: {ref}")
        asset = (PROTOTYPE / ref).resolve()
        require(
            asset.is_relative_to(PROTOTYPE) and asset.is_file(), f"Missing/escaped asset: {ref}"
        )
    require(
        'type="module"' not in html and "<style" not in html and "style=" not in html,
        "Use local classic JS and a single local stylesheet",
    )
    require(
        not re.search(
            r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|indexedDB|localStorage|sessionStorage)\b",
            js,
        ),
        "No network or persistent storage APIs in this in-memory demo",
    )
    require(
        "serviceWorker" not in js and "sendBeacon" not in js and "document.cookie" not in js,
        "No service worker, beacon or cookies",
    )
    require("@import" not in css and "url(" not in css, "No external CSS resources")
    dark_blocks = re.findall(r':root\[data-theme="dark"\]\s*\{([^}]+)\}', css)
    require(len(dark_blocks) == 1, "Exactly one dark token block")
    for declaration in dark_blocks[0].split(";"):
        if declaration.strip():
            require(
                re.match(r"\s*(--[\w-]+|color-scheme)\s*:", declaration) is not None,
                "Dark theme contains a component style",
            )
    require(css.count('[data-theme="dark"]') == 1, "No per-component dark rules")
    component_css = css[css.index("* {") :]
    require(
        not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", component_css),
        "Component color literals bypass tokens",
    )
    require(".style" not in js and "setProperty" not in js, "JS must not override styles/tokens")
    return {
        "logo_exact_bytes": True,
        "local_assets": refs,
        "dark_tokens_only": True,
        "component_colors_tokens_only": True,
        "no_network_or_storage_apis": True,
    }


def settle(page: Page) -> None:
    page.evaluate("() => document.fonts.ready")
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )


def keyboard_audit(
    page: Page, expected: int, records: list[FocusRecord] | None = None
) -> list[FocusRecord]:
    page.evaluate("""() => {
      document.body.setAttribute('tabindex','-1'); document.body.focus();
      document.body.removeAttribute('tabindex');
    }""")
    if records is None:
        records = []
    expected_order: list[str] = page.evaluate("() => window.__ux.controls.map(window.__ux.id)")
    require(len(expected_order) == expected, "Keyboard control count changed")
    max_date_stops = 4
    date_count: int = page.evaluate(
        "() => window.__ux.controls.filter(el => el.matches('input[type=\"date\"]')).length"
    )
    step_limit = expected + date_count * (max_date_stops - 1) + 4
    seen: set[int] = set()
    unique: list[FocusRecord] = []
    previous: int | None = None
    consecutive = 0
    completed = False
    for _ in range(step_limit):
        page.keyboard.press("Tab")
        item: FocusRecord = page.evaluate(FOCUS)
        records.append(item)
        if item.get("body"):
            if seen or expected == 0:
                completed = True
                break
            continue
        require(item["ok"], "Keyboard focus missing/low contrast/occluded; see audit")
        index = item["controlIndex"]
        require(0 <= index < expected, "Tab reached an unexpected DOM control")
        if index == previous:
            consecutive += 1
            require(item["nativeDate"], "Repeated non-date keyboard stop")
            require(consecutive <= max_date_stops, "Native date keyboard stop limit exceeded")
        else:
            require(index not in seen, "Nonconsecutive repeated keyboard control")
            seen.add(index)
            unique.append(item)
            previous = index
            consecutive = 1
    require(completed, "Keyboard traversal iteration limit exceeded")
    require(len(unique) == expected, f"Tab coverage: {len(unique)} / {expected}")
    require(
        [item["controlIndex"] for item in unique] == list(range(expected))
        and [item["element"] for item in unique] == expected_order,
        "Tab order differs from DOM order",
    )
    for _ in range(len(records)):
        page.keyboard.press("Shift+Tab")
    return records


def self_test(page: Page) -> SelfTestResult:
    page.set_content("""<!doctype html><html><head><style>
      body { background:#fff; color:#000; }
      button { width:60px; height:45px; background:#fff; color:#777; }
      button:focus-visible { outline:3px solid #fff; outline-offset:3px; }
      input { width:20px; height:20px; }
      .paint { background:linear-gradient(#fff,#000); }
      </style></head><body><p>Black on white</p><button>Bad contrast</button>
      <input /><p class="paint">Needs review</p><div hidden><button>Hidden</button></div>
      </body></html>""")
    audit: AuditResult = page.evaluate(AUDITOR)
    kinds = {item["kind"] for item in audit["problems"]}
    require(
        {"text-contrast", "missing-label", "small-target"}.issubset(kinds),
        "Auditor failed negative text/label/target controls",
    )
    require(bool(audit["reviews"]), "Unsupported gradient must block a clean result")
    black = next(item for item in audit["text"] if item["text"] == "Black on white")
    require(abs(black["ratio"] - 21) < 1e-8, "sRGB black/white oracle")
    gray = next(item for item in audit["text"] if item["text"] == "Bad contrast")
    require(
        4.47 < gray["ratio"] < 4.49 and gray["threshold"] == 4.5,
        "Do not round 4.478 up to a passing 4.5",
    )
    page.keyboard.press("Tab")
    focus: FocusRecord = page.evaluate(FOCUS)
    require(not focus["ok"] and focus["ratio"] == 1, "Auditor missed invisible focus")
    alpha: list[float] = page.evaluate("""() => window.__ux.over([0,0,0,0.5],[255,255,255,1])""")
    require(alpha == [127.5, 127.5, 127.5, 1], "sRGB alpha composition oracle")
    require(audit["controlCount"] == 2, "Hidden controls must not enter keyboard count")

    def rejected_keyboard(expected: int, message: str) -> list[FocusRecord]:
        records: list[FocusRecord] = []
        try:
            keyboard_audit(page, expected, records)
        except AssertionError as error:
            require(message in str(error), f"Unexpected keyboard rejection: {error}")
        else:
            raise AssertionError(f"Keyboard auditor missed: {message}")
        require(bool(records), "Failed keyboard stops must remain in evidence")
        return records

    negative_focus = rejected_keyboard(2, "Keyboard focus missing/low contrast")
    page.set_content("""<!doctype html><html><head><style>
      body { background:#fff; color:#000; }
      input { width:100px; height:48px; background:#fff; color:#000;
        border:1px solid #cbd5e1; }
      </style></head><body><label for="faint-border">Faint border</label>
      <input id="faint-border" /></body></html>""")
    faint_border: AuditResult = page.evaluate(AUDITOR)
    require(
        faint_border["controlCount"] == 1
        and len(faint_border["controlBorders"]) == 4
        and len(faint_border["problems"]) == 4
        and not faint_border["reviews"],
        "Faint border fixture must be screened on all four sides without unrelated failures",
    )
    require(
        all(
            item["kind"] == "control-border"
            and item["element"] == "#faint-border"
            and item["backgroundRatio"] < 3
            and item["adjacentRatio"] < 3
            for item in faint_border["problems"]
        ),
        "Auditor missed faint control border against control/adjacent backgrounds",
    )
    page.set_content("""<!doctype html><html><head><style>
      body { background:#fff; color:#000; }
      button, input { min-width:100px; height:48px; background:#fff; color:#000;
        border:1px solid #000; }
      button:focus-visible, input:focus-visible, input[type="date"]:focus-within {
        outline:3px solid #000; outline-offset:3px;
      }
      </style></head><body><button id="before-date">Before date</button>
      <label for="fixture-date">Date</label><input id="fixture-date" type="date" value="2026-10-23" />
      <button id="after-date">After date</button></body></html>""")
    date_audit: AuditResult = page.evaluate(AUDITOR)
    require(
        not date_audit["problems"] and not date_audit["reviews"],
        "Native date fixture must satisfy unchanged DOM thresholds",
    )
    date_records = keyboard_audit(page, date_audit["controlCount"])
    date_stops = [item for item in date_records if item.get("element") == "#fixture-date"]
    require(len(date_stops) > 1, "Native date regression did not exercise repeated DOM focus")
    require(
        [item["element"] for item in date_records if not item.get("body")][-1] == "#after-date",
        "Native date traversal did not reach its successor",
    )
    page.locator("#fixture-date").evaluate("""el => {
      el.onkeydown = event => { if (event.key === 'Tab') event.preventDefault(); };
    }""")
    date_trap = rejected_keyboard(3, "Native date keyboard stop limit exceeded")
    page.locator("#fixture-date").evaluate("el => { el.onkeydown = null; }")
    page.locator("#after-date").evaluate("""el => {
      el.onkeydown = event => {
        if (event.key === 'Tab') {
          event.preventDefault(); document.querySelector('#fixture-date').focus();
        }
      };
    }""")
    date_loop = rejected_keyboard(3, "Nonconsecutive repeated keyboard control")
    page.set_content("""<!doctype html><html><head><style>
      body { color:#000; background:#fff; }
      h1 { color:#777; font-size:32px; }
      label { font-size:13px; }
      summary { min-height:44px; }
      input { width:100px; height:48px; border:1px solid #000; background:#fff; }
      </style></head><body><h1>Large low contrast</h1><label for="tiny">Tiny label</label>
      <details><summary>Open native disclosure</summary><input id="tiny" /></details>
      </body></html>""")
    closed: AuditResult = page.evaluate(AUDITOR)
    require(closed["controlCount"] == 1, "Closed details must expose summary only")
    require(
        any(
            item["kind"] == "text-contrast" and item["threshold"] == 4.5
            for item in closed["problems"]
        ),
        "Large text must still meet R2 4.5:1",
    )
    require(any(item["kind"] == "small-label" for item in closed["problems"]), "Missed <14px label")
    page.locator("summary").focus()
    page.keyboard.press("Space")
    opened: AuditResult = page.evaluate(AUDITOR)
    require(opened["controlCount"] == 2, "Expanded disclosure must include its input")
    page.set_content("""<!doctype html><html><head><style>
      body { background:#fff; color:#000; }
      button { position:fixed; bottom:8px; left:8px; height:48px; width:100px;
        background:#fff; color:#000; scroll-margin:16px; }
      button:focus-visible { outline:3px solid #000; outline-offset:3px; }
      .sidebar { position:fixed; bottom:0; left:0; width:100%; height:80px; background:#fff; }
      </style></head><body><button>Covered control</button>
      <aside class="sidebar"><nav aria-label="Fixture"></nav></aside></body></html>""")
    page.evaluate(AUDITOR)
    occluded = rejected_keyboard(1, "Keyboard focus missing/low contrast/occluded")
    require(not occluded[-1]["geometryOK"], "Fixed-nav occlusion must fail geometry")
    return {
        "status": "PASS",
        "negative_kinds": sorted(kinds),
        "gradient_review": True,
        "black_white_ratio": black["ratio"],
        "gray_white_ratio": gray["ratio"],
        "invisible_focus_rejected": True,
        "alpha_oracle": alpha,
        "keyboard_negative_focus": negative_focus,
        "faint_control_border_rejected": faint_border,
        "native_date_traversal": date_records,
        "native_date_trap_rejected": date_trap,
        "native_date_nonconsecutive_repeat_rejected": date_loop,
        "large_text_rejected": True,
        "small_label_rejected": True,
        "disclosure_controls_checked": True,
        "occluded_focus_rejected": occluded,
    }


def toggle_tools(page: Page, opened: bool) -> None:
    if page.locator("#demo-tools").evaluate("el => el.open") != opened:
        page.locator("#demo-tools > summary").focus()
        page.keyboard.press("Space")
    require(
        page.locator("#demo-tools").evaluate("el => el.open") == opened,
        "Native tools toggle failed",
    )


def set_state(page: Page, state: str) -> None:
    toggle_tools(page, True)
    page.locator("#state").select_option(state)
    toggle_tools(page, False)
    settle(page)
    require(page.locator("#state").is_hidden(), "Collapsed tools leaked state selector")


def navigate(page: Page, target: str) -> None:
    current: str = page.evaluate("() => location.hash")
    if current == f"#{target}":
        return
    if target == "entrenamiento":
        navigate(page, "hoy")
        page.get_by_role("link", name="Comenzar", exact=True).click()
    elif target == "bienvenida":
        toggle_tools(page, True)
        page.locator("#onboarding-link").click()
    elif target == "registro":
        navigate(page, "bienvenida")
        page.locator("#open-registration").click()
    else:
        page.locator(f'nav a[href="#{target}"]').click()
    page.wait_for_function("target => location.hash === '#' + target", arg=target)
    settle(page)
    if target == "bienvenida":
        toggle_tools(page, False)


def expand_disclosures(page: Page) -> None:
    # Native activation rather than setting .open or ignoring newly exposed fields.
    for disclosure in page.locator("details").all():
        if not disclosure.evaluate("el => el.open"):
            summary = disclosure.locator(":scope > summary")
            summary.focus()
            page.keyboard.press("Space")
        require(disclosure.evaluate("el => el.open"), "Disclosure did not expand from keyboard")
    settle(page)


def session_geometry(page: Page) -> SessionGeometry:
    require(page.viewport_size == {"width": 390, "height": 844}, "R2 geometry requires 390x844")
    require(
        not page.locator("#demo-tools").evaluate("el => el.open"), "Hoy tools must start closed"
    )
    # Navigation already scrolled to the native top; do not scroll to fit the CTA.
    result: SessionGeometry = page.evaluate("""() => {
      const session=document.querySelector('#today-session'), cta=document.querySelector('#start-training');
      const r=session.getBoundingClientRect(), b=cta.getBoundingClientRect(), s=getComputedStyle(session);
      const nav=document.querySelector('nav'), shell=nav.closest('.sidebar');
      const n=shell.getBoundingClientRect();
      const visible=el => {
        const r=el.getBoundingClientRect();
        return el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) &&
          r.width > 0 && r.height > 0 && r.left >= 0 && r.right <= innerWidth &&
          r.top >= 0 && r.bottom <= innerHeight;
      };
      return {scrollY,navTop:n.top,sessionTop:r.top,sessionBottom:r.bottom,
        ctaTop:b.top,ctaBottom:b.bottom,ctaWidth:b.width,
        contentWidth:r.width-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-
          parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth),
        primaryCount:document.querySelectorAll('#view .primary').length,
        toolsClosed:!document.querySelector('#demo-tools').open,
        navVisible:getComputedStyle(shell).position === 'fixed' && nav.querySelectorAll('a').length === 4 &&
          [...nav.querySelectorAll('a')].every(link => visible(link) &&
            link.textContent.trim().length > 1 && link.querySelector('[aria-hidden="true"]') &&
            visible(link.querySelector('[aria-hidden="true"]')))};
    }""")
    require(
        result["scrollY"] == 0
        and result["sessionTop"] >= 0
        and result["sessionBottom"] <= result["navTop"] - 6
        and result["ctaTop"] >= result["sessionTop"]
        and result["ctaBottom"] <= result["navTop"] - 6,
        "Hoy session/Comenzar must fit above fixed nav without scrolling at 390x844",
    )
    require(abs(result["ctaWidth"] - result["contentWidth"]) <= 1, "Comenzar must be full width")
    require(
        result["primaryCount"] == 1 and result["toolsClosed"],
        "Hoy must have one primary and compact tools",
    )
    require(result["navVisible"], "All four nav links need visible icon and text at 390px")
    return result


def timer_metrics(page: Page, report: Report) -> TimerMetrics:
    result: TimerMetrics = page.evaluate("() => ({...window.__restAudit})")
    report.setdefault("rest_timer", []).append(result)
    require(result["active"] <= 1, "Duplicate live rest intervals")
    return result


def remaining_rest(page: Page) -> int:
    match = re.search(r"(\d+) s restantes", page.locator("#rest-timer").inner_text())
    require(match is not None, "Expected an active illustrative rest countdown")
    if match is None:
        raise AssertionError("Missing rest countdown")
    return int(match.group(1))


def functional_flows(page: Page, report: Report) -> list[str]:
    checks: list[str] = []
    set_state(page, "normal")
    navigate(page, "hoy")
    require(
        bool(page.locator("nav a").all_text_contents())
        and page.locator('[aria-current="page"]').count() == 1,
        "Stable navigation/current page",
    )
    navigate(page, "entrenamiento")
    table = page.get_by_role("table", name="Registro rápido · Datos ficticios")
    require(
        table.get_attribute("id") == "sets-table", "Rapid editor must be a semantic named table"
    )
    require(table.locator("tr[data-set]").count() == 3, "Three independent prescribed/actual rows")
    require(table.locator('th[scope="col"]').count() == 5, "Rapid table column headers missing")
    for n in range(1, 4):
        row = table.locator(f'tr[data-set="{n}"]')
        require(row.locator('th[scope="row"]').inner_text() == str(n), "Series row header missing")
        for key in ("load", "reps", "rpe", "rir"):
            require(
                page.locator(f"#{key}-{n}").input_value() == "", "Targets must not prefill actuals"
            )
        details = page.locator("details.set-details").nth(n - 1)
        require(details.locator("input").is_hidden(), "Optional RIR must start collapsed")
        details.locator("summary").click()
        require(
            "Prescrito A: 8 rep · 40 kg · RPE 7 / 10 · RIR 3." in details.inner_text(),
            "Each series needs explicit prescription distinct from actuals",
        )
        require(
            "Anterior ficticio" in row.locator("xpath=following-sibling::tr[1]").inner_text()
            and "No son valores realizados hoy"
            in row.locator("xpath=following-sibling::tr[1]").inner_text(),
            "Previous values must be fictitious, not actual input defaults",
        )
        button = page.locator(f"#check-{n}")
        box = button.bounding_box()
        require(
            box is not None and box["width"] >= 48 and box["height"] >= 48,
            "Set check must be >=48px square",
        )
        require(
            button.get_attribute("aria-pressed") == "false" and button.inner_text() == "Pendiente",
            "Pending state needs text and aria-pressed",
        )
    # Missing and out-of-range data in each required column must block marking.
    for key in ("load", "reps", "rpe"):
        for field, value in (("load", "0"), ("reps", "7"), ("rpe", "7.5")):
            page.locator(f"#{field}-1").fill(value)
        for invalid in ("", "-1", {"load": "500.5", "reps": "101", "rpe": "10.5"}[key]):
            page.locator(f"#{key}-1").fill(invalid)
            page.locator("#check-1").click()
            require(
                page.locator("#check-1").get_attribute("aria-pressed") == "false",
                "Missing/invalid real data marked completed",
            )
            require(timer_metrics(page, report)["active"] == 0, "Invalid series started rest")
        page.locator(f"#{key}-1").fill({"load": "0", "reps": "7", "rpe": "7.5"}[key])
    for n in range(1, 4):
        page.locator(f"#reps-{n}").fill(str(8 - n))
        page.locator(f"#load-{n}").fill("0" if n == 1 else "37.5")
        page.locator(f"#rpe-{n}").fill(str(7 + n / 2))
        page.locator(f"#rir-{n}").fill(str(n))
    page.locator("#minutes").fill("0")
    page.locator("#save-training").click()
    summary = page.locator("#record-summary").inner_text()
    require(
        "0 kg" in summary and "0 min" in summary and "Sin datos" in summary,
        "Measured zero and absence must remain distinct",
    )
    require("no enviado" in summary.lower(), "Memory-only save must not claim server success")
    for n in range(1, 4):
        load = "0" if n == 1 else "37.5"
        rpe = f"{7 + n / 2:g}"
        require(
            f"Serie {n} · Pendiente: {8 - n} rep · {load} kg · RPE {rpe} · RIR {n}" in summary,
            "Per-set reps/load/RPE/RIR observations lost or coupled",
        )
    checks.append(
        "inicio -> entrenamiento: semantic three-row table, explicit targets/previous != empty actuals, independent reps/load/RPE/RIR, zero != null, memory-only save"
    )
    before = timer_metrics(page, report)
    page.locator("#check-1").click()
    require(
        page.locator("#check-1").get_attribute("aria-pressed") == "true"
        and "Realizada" in page.locator("#check-1").inner_text(),
        "Completed needs distinct text and aria-pressed",
    )
    for key in ("load", "reps", "rpe", "rir"):
        require(page.locator(f"#{key}-1").is_disabled(), "Completed row must lock all actuals")
    require(89 <= remaining_rest(page) <= 90, "Mark must start automatic 90s illustrative rest")
    first = timer_metrics(page, report)
    require(
        first["active"] == 1 and first["created"] == before["created"] + 1,
        "Rest interval not created exactly once",
    )
    page.clock.fast_forward(10000)
    require(79 <= remaining_rest(page) <= 80, "Countdown did not use elapsed clock time")
    navigate(page, "plan")
    navigate(page, "entrenamiento")
    require(77 <= remaining_rest(page) <= 80, "Navigation restarted/lost rest deadline")
    require(
        page.locator("#check-1").get_attribute("aria-pressed") == "true",
        "Navigation lost checked row",
    )
    page.locator("#check-2").click()
    second = timer_metrics(page, report)
    require(
        second["active"] == 1 and second["created"] == first["created"],
        "Second mark duplicated the running interval",
    )
    require(
        89 <= remaining_rest(page) <= 90, "Second mark should restart the illustrative deadline"
    )
    page.clock.fast_forward(90000)
    require(
        "Sin descanso activo" in page.locator("#rest-timer").inner_text(),
        "Rest did not finish after virtual 90s",
    )
    ended = timer_metrics(page, report)
    require(
        ended["active"] == 0 and ended["trainingSubmits"] == before["trainingSubmits"],
        "Rest completion auto-submitted or leaked interval",
    )
    require(
        page.locator("#check-1").get_attribute("aria-pressed") == "true"
        and page.locator("#check-2").get_attribute("aria-pressed") == "true"
        and page.locator("#check-3").get_attribute("aria-pressed") == "false",
        "Rest completion must not auto-mark/unmark series",
    )
    page.locator("#check-2").click()
    for key in ("load", "reps", "rpe", "rir"):
        require(page.locator(f"#{key}-2").is_enabled(), "Explicit unmark must enable editing")
    page.locator("#check-3").click()
    require(89 <= remaining_rest(page) <= 90, "New mark must restart rest after expiry")
    page.locator("#skip-rest").click()
    skipped = timer_metrics(page, report)
    require(
        skipped["active"] == 0 and skipped["trainingSubmits"] == before["trainingSubmits"],
        "Skip rest leaked interval or submitted",
    )
    require(
        "Sin descanso activo" in page.locator("#rest-timer").inner_text()
        and page.locator("#skip-rest").is_disabled(),
        "Skip must visibly end rest",
    )
    require(
        page.locator("#check-2").get_attribute("aria-pressed") == "false",
        "Skip marked another series",
    )
    checks.append(
        "rapid checks: >=48px, missing/invalid kg/reps/RPE rejected; valid rows lock, explicit unmark unlocks; automatic 90s via Playwright clock, one interval, navigation retention, expiry/skip never submit or mark another set"
    )
    navigate(page, "plan")
    require(page.locator("#week-strip li").count() == 7, "Plan needs seven-day strip")
    require(page.locator("#new-date").is_hidden(), "Reschedule form must start hidden")
    page.locator("#show-reschedule").click()
    page.locator("#new-date").fill("2026-10-25")
    page.locator("#cancel-reschedule").click()
    require(
        page.locator("[data-plan-date]").inner_text() == "2026-10-23"
        and page.locator("#new-date").is_hidden(),
        "Cancel changed date or left form open",
    )
    page.locator("#show-reschedule").click()
    require(
        page.locator("#new-date").input_value() == "2026-10-23",
        "Cancel did not discard pending date",
    )
    page.locator("#new-date").fill("2026-10-24")
    page.locator("#reschedule").click()
    require(page.locator("[data-plan-date]").inner_text() == "2026-10-24", "Reschedule in memory")
    navigate(page, "hoy")
    require(page.locator("[data-plan-date]").inner_text() == "2026-10-24", "Date visible from Hoy")
    checks.append(
        "reprogramacion: hidden until native disclosure, cancel discards, explicit submit propagates future date to Hoy"
    )
    navigate(page, "progreso")
    require(
        "Sin datos" in page.locator("#view").inner_text()
        and "0 m" in page.locator("#view").inner_text(),
        "Progress labels missing zero/null",
    )
    checks.append("progreso: estimated/measured/zero/missing labeled")
    navigate(page, "entrenador")
    original = page.locator("[data-plan-name]").inner_text()
    navigate(page, "plan")
    require(
        page.locator("[data-plan-name]").inner_text() == original,
        "Preview changed plan without acceptance",
    )
    navigate(page, "entrenador")
    page.locator("#reject-proposal").click()
    require(page.locator("[data-plan-name]").inner_text() == original, "Reject changed plan")
    page.locator("#reset-proposal").click()
    page.locator("#accept-proposal").click()
    require(
        "Fuerza B" in page.locator("[data-plan-name]").inner_text(),
        "Explicit acceptance did not change demo",
    )
    navigate(page, "plan")
    require(
        "Fuerza B" in page.locator("[data-plan-name]").inner_text(), "Accepted plan not reflected"
    )
    navigate(page, "entrenamiento")
    require(page.locator("#load-1").input_value() == "0", "Acceptance destroyed prior actuals")
    require("3 × 8" not in page.locator("#view").inner_text(), "Unexpected aggregate prescription")
    checks.append(
        "propuesta IA: preview/reject leave plan untouched; explicit acceptance updates only future demo"
    )
    for state in ("offline", "pending", "conflict", "error", "loading", "empty"):
        set_state(page, state)
        require(bool(page.locator("#announcement").inner_text()), "State must be announced")
        require(
            page.locator("#state-panel h2").count() == 1
            and page.locator("#state-panel").is_visible(),
            "State must remain visibly explained outside collapsed tools",
        )
        if state in ("conflict", "error"):
            require(
                page.locator("#save-training").is_disabled()
                and page.locator("#check-2").is_disabled(),
                "Conflict/error must block editing action",
            )
        if state in ("empty", "loading"):
            require(page.locator("#view").is_hidden(), "Empty/loading must not expose results")
    set_state(page, "normal")
    navigate(page, "entrenador")
    page.locator("#reset-proposal").click()
    require(
        "Fuerza A" in page.locator("[data-plan-name]").inner_text(),
        "Reset did not restore original plan",
    )
    checks.append(
        "states: live announcements and visible notices with tools closed; no auto-success; conflict/error block writes; loading/empty hide results; proposal reset restores A"
    )
    page.reload()
    settle(page)
    navigate(page, "entrenamiento")
    require(page.locator("#load-1").input_value() == "", "Reload unexpectedly persisted actuals")
    require(
        page.locator("#check-1").get_attribute("aria-pressed") == "false"
        and "Sin descanso activo" in page.locator("#rest-timer").inner_text(),
        "Reload persisted check/rest",
    )
    navigate(page, "plan")
    require(
        page.locator("[data-plan-date]").inner_text() == "2026-10-23",
        "Reload unexpectedly persisted date",
    )
    require(
        "Fuerza A" in page.locator("[data-plan-name]").inner_text(),
        "Reload unexpectedly persisted proposal",
    )
    checks.append("reload: actuals/date/proposal/check/rest reset; no persistent demo state")
    return checks


def onboarding_flows(page: Page, report: Report) -> list[str]:
    navigate(page, "bienvenida")
    require(
        "ficticia" in page.locator("#view").inner_text().lower(),
        "Welcome must identify fictitious demo",
    )
    navigate(page, "registro")
    form = page.locator("#signup-form")
    for selector in ("#signup-name", "#signup-email", "#signup-password", "#signup-adult"):
        require(
            page.locator(selector).evaluate("el => el.required && el.labels.length > 0"),
            "Onboarding fields must have native labels and required validation",
        )
    page.locator("#signup-submit").click()
    require(
        not form.evaluate("el => el.checkValidity()")
        and page.locator("#signup-result").is_hidden(),
        "Empty signup must not succeed",
    )
    page.locator("#signup-name").fill("Atleta Ficticia")
    page.locator("#signup-email").fill("not-an-email")
    page.locator("#signup-password").fill("short")
    page.locator("#signup-adult").select_option("adult")
    page.locator("#signup-submit").click()
    require(
        page.locator("#signup-email").evaluate("el => el.validity.typeMismatch")
        and page.locator("#signup-result").is_hidden(),
        "Bad email must fail client validation",
    )
    page.locator("#signup-email").fill("atleta@example.test")
    page.locator("#signup-submit").click()
    require(
        page.locator("#signup-password").evaluate("el => el.validity.tooShort")
        and page.locator("#signup-result").is_hidden(),
        "Password shorter than eight must fail",
    )
    # Deliberately fictional; never interpolated into any assertion, log or screenshot.
    password = "Fictional-demo-42"
    page.locator("#signup-password").fill(password)
    page.locator("#signup-adult").select_option("")
    page.locator("#signup-submit").click()
    require(
        page.locator("#signup-adult").evaluate("el => el.validity.valueMissing")
        and page.locator("#signup-result").is_hidden(),
        "Adult selection required",
    )
    page.locator("#signup-adult").select_option("adult")
    require(
        form.evaluate("el => el.checkValidity()"), "Fictional valid signup did not validate locally"
    )
    input_audit: AuditResult = page.evaluate(AUDITOR)
    report["onboarding_input_audit"] = input_audit
    require(password not in json.dumps(input_audit), "Password leaked into auditor evidence")
    require(
        any(
            item["element"] == "#signup-password" and item["text"] == "[REDACTED PASSWORD]"
            for item in input_audit["text"]
        ),
        "Password foreground/background must still be screened with redacted sample",
    )
    require(
        not input_audit["problems"] and not input_audit["reviews"],
        "Populated registration DOM audit failed",
    )
    page.locator("#signup-submit").click()
    result = page.locator("#signup-result").inner_text()
    require(
        "NO se ha creado una cuenta" in result
        and "NO se ha enviado correo" in result
        and "NO hay sincronización con servidor" in result,
        "Registration result must deny account/email/server success",
    )
    require(
        page.locator("#signup-password").input_value() == "",
        "Password must be cleared after local validation",
    )
    require(password not in page.locator("body").inner_text(), "Password echoed in visible result")
    require(
        page.evaluate(
            "() => Object.keys(demo).every(k => !/password|email|credential|signup.name/i.test(k)) && !JSON.stringify(demo).includes('atleta@example.test')"
        ),
        "Registration credentials persisted in demo model",
    )
    require(
        page.evaluate(
            "() => !JSON.stringify(demo).includes(document.querySelector('#signup-password').defaultValue) || document.querySelector('#signup-password').defaultValue === ''"
        ),
        "Unexpected password default",
    )
    require(
        not page.evaluate(
            "secret => JSON.stringify(demo).includes(secret) || document.documentElement.outerHTML.includes(secret)",
            password,
        ),
        "Password persisted in model/markup",
    )
    navigate(page, "hoy")
    navigate(page, "registro")
    require(page.locator("#signup-result").is_visible(), "Local demo outcome lost before reload")
    page.reload()
    settle(page)
    require(
        page.locator("#signup-result").is_hidden() and page.locator("#signup-form").is_visible(),
        "Reload must reset registration outcome",
    )
    for selector in ("#signup-name", "#signup-email", "#signup-password", "#signup-adult"):
        require(
            page.locator(selector).input_value() == "", "Reload must not retain registration input"
        )
    return [
        "bienvenida -> registro: labelled required client validation rejects empty/bad email/short password/missing adult; fictional valid data yields NO account/email/server outcome, password redacted in computed audit then cleared/not echoed/persisted; reload resets"
    ]


def record_audit(
    page: Page,
    report: Report,
    width: int,
    theme: str,
    target: str,
    state: str,
    disclosure: str,
    tokens: dict[str, str],
) -> None:
    audit: AuditResult = page.evaluate(AUDITOR)
    entry: AuditEntry = {
        "width": width,
        "theme": theme,
        "route": target,
        "state": state,
        "disclosure": disclosure,
        "tokens": tokens,
        "problems": audit["problems"],
        "reviews": audit["reviews"],
        "text": audit["text"],
        "targets": audit["targets"],
        "controlBorders": audit["controlBorders"],
        "controlCount": audit["controlCount"],
        "keyboard": [],
    }
    report["audits"].append(entry)
    try:
        keyboard_audit(page, audit["controlCount"], entry["keyboard"])
    except AssertionError as error:
        entry["problems"].append({"kind": "keyboard", "error": str(error)})
    entry["status"] = "PASS" if not entry["problems"] and not entry["reviews"] else "FAIL"


def capture(page: Page, args: Arguments, report: Report, name: str) -> None:
    require(name in SCREENSHOTS, "Unexpected capture name")
    require(
        not page.locator("#demo-tools").evaluate("el => el.open"),
        "Capture must have tools collapsed",
    )
    require(
        page.locator('input[type="password"]').evaluate_all(
            "els => els.every(el => el.value === '')"
        ),
        "Never capture sample passwords",
    )
    page.evaluate("() => { document.activeElement.blur(); window.scrollTo(0,0); }")
    settle(page)
    page.screenshot(path=str(args.output / name), full_page=True)
    report.setdefault("screenshots", []).append(name)


def run_browser(args: Arguments, report: Report) -> None:
    from playwright.sync_api import sync_playwright

    network: list[str] = []
    report["network_attempts"] = network
    errors: list[str] = []
    report["javascript_errors"] = errors
    allowed = {path.resolve() for path in SOURCE_PATHS if path.is_relative_to(PROTOTYPE)}
    with sync_playwright() as playwright:
        executable_path: str | None = None
        if args.browser_executable:
            executable = Path(args.browser_executable).resolve(strict=True)
            executable_path = str(executable)
            report["tools"]["browser_executable_sha256"] = hashlib.sha256(
                executable.read_bytes()
            ).hexdigest()
        browser = playwright.chromium.launch(headless=True, executable_path=executable_path)
        report["tools"]["chromium"] = browser.version
        try:
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                reduced_motion="reduce",
                service_workers="block",
            )

            def guard(request_route: Route) -> None:
                url = request_route.request.url
                parsed = urlparse(url)
                if parsed.scheme == "file":
                    local = unquote(parsed.path)
                    if sys.platform == "win32" and re.match(r"^/[A-Za-z]:", local):
                        local = local[1:]
                    if Path(local).resolve() in allowed:
                        request_route.continue_()
                        return
                network.append(url)
                request_route.abort()

            context.route("**/*", guard)
            context.on(
                "request",
                lambda request: (
                    network.append(request.url)
                    if urlparse(request.url).scheme not in ("file", "about", "data")
                    else None
                ),
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_default_timeout(10000)
            report["auditor_self_tests"] = self_test(page)
            # Install the real Playwright clock before observing app intervals.
            # It runs normally; only fast_forward advances the 90-second examples.
            page.clock.install()
            page.add_init_script(TIMER_OBSERVER)
            page.goto((PROTOTYPE / "index.html").as_uri(), wait_until="load")
            settle(page)
            require(page.evaluate("() => location.protocol") == "file:", "Not a file:// session")
            require(
                page.locator("#state option").evaluate_all("els => els.map(e=>e.value)")
                == list(STATES),
                "State selector differs from frozen acceptance",
            )
            report["flows"] = functional_flows(page, report)
            report["flows"].extend(onboarding_flows(page, report))
            page.reload()
            page.keyboard.press("Tab")
            require(
                page.locator(".skip").evaluate("el => el === document.activeElement"),
                "Skip is not first Tab",
            )
            page.keyboard.press("Enter")
            require(
                page.locator("#main").evaluate("el => el === document.activeElement"),
                "Skip target not focused",
            )
            page.locator("#theme").focus()
            page.keyboard.press("Enter")
            require(
                page.locator("html").get_attribute("data-theme") == "dark",
                "Keyboard theme toggle failed",
            )
            page.keyboard.press("Space")
            require(
                page.locator("html").get_attribute("data-theme") == "light",
                "Keyboard reverse theme failed",
            )
            report["keyboard_activation"] = [
                "skip: Tab+Enter",
                "theme: Enter+Space",
                "native disclosures: summary+Space/click",
            ]
            page.reload()
            report["audits"] = []
            report["session_geometry"] = {}
            for width in (390, 1440):
                page.set_viewport_size({"width": width, "height": 844 if width == 390 else 900})
                for theme in ("light", "dark"):
                    if page.locator("html").get_attribute("data-theme") != theme:
                        page.locator("#theme").click()
                    settle(page)
                    tokens: dict[str, str] = page.evaluate("""() => {
                      const s=getComputedStyle(document.documentElement);
                      return Object.fromEntries(['--app-bg','--surface','--text','--muted','--accent',
                        '--border','--control-border','--primitive-slate-500','--primitive-slate-400',
                        '--focus','--hero-background','--hero-foreground','--control-height',
                        '--primitive-blue-600','--primitive-blue-800'].map(k=>[k,s.getPropertyValue(k).trim()]));
                    }""")
                    require(
                        tokens["--primitive-blue-600"].lower() == "#0400ff",
                        "Brand identity changed",
                    )
                    require(
                        tokens["--primitive-blue-800"].lower() == "#0300cc", "Brand hover changed"
                    )
                    for target in ROUTES:
                        set_state(page, "normal")
                        navigate(page, target)
                        for state in STATES:
                            set_state(page, state)
                            # Fresh route renders restore every route-local disclosure closed.
                            require(
                                page.locator("details[open]").count() == 0,
                                "Baseline disclosures must be collapsed",
                            )
                            if target == "hoy" and state == "normal" and width == 390:
                                # Native navigation sets scroll to zero; state-tool toggles may scroll.
                                # Re-enter Hoy via another nav destination, not a forced fit scroll.
                                navigate(page, "plan")
                                navigate(page, "hoy")
                                report["session_geometry"][theme] = session_geometry(page)
                            if state == "normal":
                                name: str | None = None
                                if target == "hoy":
                                    name = f"hoy-{width}-{theme}.png"
                                elif width == 390 and target in ("plan", "bienvenida", "registro"):
                                    label = "onboarding" if target == "bienvenida" else target
                                    name = f"{label}-390-{theme}.png"
                                if name is not None:
                                    capture(page, args, report, name)
                            record_audit(
                                page, report, width, theme, target, state, "collapsed", tokens
                            )
                        set_state(page, "normal")
                        expand_disclosures(page)
                        record_audit(
                            page, report, width, theme, target, "normal", "expanded", tokens
                        )
                        toggle_tools(page, False)
                        # Navigate away to discard local expanded disclosures before next route.
                        navigate(page, "plan" if target == "hoy" else "hoy")
            baseline = sum(item["disclosure"] == "collapsed" for item in report["audits"])
            expanded = sum(item["disclosure"] == "expanded" for item in report["audits"])
            report["audit_counts"] = {
                "baseline": baseline,
                "expanded": expanded,
                "total": len(report["audits"]),
            }
            require(
                baseline == 196 and expanded == 28 and len(report["audits"]) >= 224,
                "Incomplete seven-route baseline/expanded matrix",
            )
            require(
                set(report.get("screenshots", [])) == SCREENSHOTS
                and len(report["screenshots"]) == 10,
                "Missing ten required named screenshots",
            )
            require(
                all(item["status"] == "PASS" for item in report["audits"]),
                "DOM/keyboard audit has failures or unsupported paint requiring review",
            )
            require(not errors, "JavaScript errors occurred")
            require(not network, "Unexpected resource/network attempt")
            require(
                page.locator("img").evaluate_all(
                    "els => els.every(e=>e.complete && e.naturalWidth>0)"
                ),
                "Local logo failed to load",
            )
            context.close()
        finally:
            browser.close()
            report["browser_closed"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, type=Path, help="New isolated evidence directory"
    )
    parser.add_argument(
        "--browser-executable", help="Existing Chromium executable; never downloaded"
    )
    args = parser.parse_args(namespace=Arguments())
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error("--output must not exist; do not overwrite evidence")
    args.output.mkdir(parents=True)
    report: Report = {
        "schema": 2,
        "status": "FAIL",
        "scope": "STATIC_PROTOTYPE_BOUNDED_UX_SCREENING_R2",
        "started_at": datetime.now(UTC).isoformat(),
        "tools": {"python": platform.python_version()},
        "human_approval": "PENDING",
        "independent_review": "BT2 PENDING",
        "screen_reader": "NOT RUN",
        "physical_device": "NOT RUN",
        "external_validation": "NOT RUN",
        "limitations": [
            "Solid-color DOM text >=4.5:1 for every size; no SVG/pseudo/placeholder pixel audit.",
            "Input/select borders: solid, >=3:1 against control and parent backgrounds; not a pixel audit.",
            "Focus: opaque solid 3px outline, 3px gap, >=3:1; native Tab geometry requires 6px room and non-nav controls above fixed mobile nav, not pixel-area certification.",
            "Tab/Shift+Tab DOM traversal, native date bounded stops, native disclosures and mobile scroll-margin screened; other occluders and assistive technology require independent human review.",
            "196 collapsed route/state/theme/width audits plus 28 expanded route/theme/width audits (224 minimum); ten named baseline PNGs are not exhaustive visual approval.",
            "Mobile viewport 390x844, desktop 1440x900; simulated Chromium is not a physical device or screen reader.",
            "Automatic illustrative 90s rest uses Playwright virtual time, no real-time/device timer certification.",
            "Only fictional registration credentials: local client validation, redacted password input audit, no sample password captures, no account/email/server acceptance.",
            "In-memory fictitious UI only; no backend, persistence, sport validity or actual offline-sync acceptance.",
            "BT2 independent review pending; external/human/screen-reader/device validation not run by this auditor.",
        ],
    }
    try:
        report["source_before"] = fingerprint()
        report["static"] = static_checks()
        report["tools"]["playwright"] = importlib.metadata.version("playwright")
        run_browser(args, report)
        report["source_after"] = fingerprint()
        require(
            report["source_before"] == report["source_after"], "Sources changed during evidence run"
        )
        report["artifacts"] = {
            name: hashlib.sha256((args.output / name).read_bytes()).hexdigest()
            for name in report["screenshots"]
        }
        report["status"] = "PASS"
    except Exception as error:
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
        if all(path.is_file() for path in SOURCE_PATHS):
            report["source_after"] = fingerprint()
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        (args.output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(args.output / "report.json"),
                "error": report.get("error"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
