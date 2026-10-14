"""002 T032: the redesigned page in a real browser (quickstart V5, spec US1-US4, SC-001 to SC-006).

The page is served by uvicorn with the frozen final-defaults run (tests/fixtures/web_final_defaults)
and `_fake_runners.sleepy_runner` in process mode. Process mode is required, because cancel can't
stop a thread-mode runner (analysis I2). The system Chrome is driven through Playwright
(channel="chrome"), so no browser is downloaded. The test is skipped, with the reason given, if
Chrome or Playwright is missing. A skip is not a pass.

Set PLATSIM_SCREENSHOT_DIR to save light and dark screenshots.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import socket
import threading
import time
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.browser

if shutil.which("google-chrome") is None:
    pytest.skip("google-chrome not found (the browser tests use the system Chrome)", allow_module_level=True)
sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed (uv sync --group dev)")

import _fake_runners  # noqa: E402
from _web_helpers import FIXTURE_DIR, FIXTURE_ID, copy_fixture_run  # noqa: E402
from platsim.web import app as webapp  # noqa: E402

REMOVED = ("cynthia win", "policies", "objective", "nature", "ivs", "evs", "ability choice", "held item source",
           "move 1 source", "best so far")
HASH_RE = re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b")


# 003 FR-001, FR-002, SC-001: every text the page shows, including hidden tooltips and attributes.
SHOWN_TEXT_JS = """() => {
  const out = [document.body.innerText];
  for (const n of document.querySelectorAll('.tip, [role=tooltip], option')) out.push(n.textContent);
  for (const n of document.querySelectorAll('[title], [aria-label], [placeholder]'))
    for (const a of ['title', 'aria-label', 'placeholder']) if (n.getAttribute(a)) out.push(n.getAttribute(a));
  return out.join('\\n');
}"""
# The word is always written "Pokémon"; identifiers such as pokemon-showdown/ are not page text.
WORDING_RE = re.compile(r"\b(?:FR|SC)-\d+|species|(?<![\w/-])pokemon(?![\w/-])", re.IGNORECASE)


def _assert_wording(page, where: str) -> None:
    hits = WORDING_RE.findall(page.evaluate(SHOWN_TEXT_JS))
    assert not hits, (where, hits)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def served(runs_dir, catalog, runner=_fake_runners.sleepy_runner):
    import uvicorn

    app = webapp.create_app(runner=runner, isolate=True, runs_dir=runs_dir, catalog=catalog)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    end = time.monotonic() + 20
    while not server.started and time.monotonic() < end:
        time.sleep(0.05)
    assert server.started, "uvicorn never started"
    try:
        yield f"http://127.0.0.1:{port}", app
    finally:
        app.state.jobs.shutdown(timeout=15)
        server.should_exit = True
        t.join(10)


@pytest.fixture(scope="module")
def chrome():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        yield browser
        browser.close()


def _visible(page, selector) -> bool:
    return page.locator(selector).first.is_visible()


def _tab_until(page, predicate_js: str, limit: int = 120) -> bool:
    for _ in range(limit):
        page.keyboard.press("Tab")
        if page.evaluate(predicate_js):
            return True
    return False


CONTROLS = "#setup input, #setup select, #setup button, #results-col input, #results-col select, #results-col button"
UNNAMED_JS = """() => [...document.querySelectorAll('""" + CONTROLS + """')]
  .filter(c => {
    const byIds = (c.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean)
      .map(id => (document.getElementById(id) || {}).textContent || '').join(' ');
    const byLabels = [...(c.labels || [])].map(l => l.textContent).join(' ');
    const own = c.tagName === 'BUTTON' ? c.textContent : '';
    return !((c.getAttribute('aria-label') || '') + byIds + byLabels + own).trim();
  })
  .map(c => c.outerHTML.slice(0, 120))"""


def _wait_text(page, selector, needle, timeout=15):
    page.locator(selector).filter(has_text=needle).first.wait_for(timeout=timeout * 1000)


def test_page_walkthrough(tmp_path, catalog, chrome):
    copy_fixture_run(tmp_path)
    shots = os.environ.get("PLATSIM_SCREENSHOT_DIR")
    with served(tmp_path, catalog) as (base, app):
        ctx = chrome.new_context(viewport={"width": 1920, "height": 1080})
        page = ctx.new_page()
        urls: list[str] = []
        posts: list[str] = []
        dialogs: list[str] = []
        page.on("request", lambda r: (urls.append(r.url), posts.append(r.post_data or "") if r.method == "POST" else None))
        page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(base + "/")

        # ---- US1: the result panel shows the newest run (FR-014, FR-017 to FR-027) ----
        _wait_text(page, "#summary", "58.23 (level gap of 4)")
        summary = page.inner_text("#summary")
        assert "%" in summary and "standard" in summary and "75.0%" in summary
        assert "egg moves off" in summary and "statistically indistinguishable" in summary  # FR-020
        assert "platsim version not recorded" in summary  # FR-021
        assert not _visible(page, "#progress-card")  # FR-008: nothing running
        setup, results = page.locator("#setup").bounding_box(), page.locator("#results-col").bounding_box()
        assert setup["x"] + setup["width"] <= results["x"]  # FR-001
        for sel in ("#optimize", "#summary", ".mon >> nth=0"):  # SC-003 + 003 FR-019: summary and first card row
            b = page.locator(sel).bounding_box()
            assert b["y"] >= 0 and b["y"] + b["height"] <= 1080, (sel, b)
        # 003 FR-019: summary, then the roster, then the chart, then the downloads (DOM order and position).
        order = page.eval_on_selector_all("#result > *", "els => els.map(e => e.id)")
        assert order == ["summary", "team-cards", "chart", "downloads"], order
        ys = [page.locator(f"#{i}").bounding_box()["y"] for i in order]
        assert ys == sorted(ys), ys

        # Clear-rate tooltip: hidden, then shown on hover and on keyboard focus (FR-017).
        tip = page.locator("#summary .clear-rate + .tip")
        assert not tip.is_visible()
        page.hover("#summary .clear-rate")
        assert tip.is_visible() and "95% interval 84.9–87.9%" in tip.inner_text() and "2,000 runs" in tip.inner_text()
        page.mouse.move(5, 5)
        assert not tip.is_visible()

        body = page.inner_text("body").lower()
        for word in REMOVED:  # FR-013, FR-018, FR-024, FR-026
            assert word not in body, word
        fixture = json.loads((FIXTURE_DIR / "result.json").read_text())
        for h in (fixture["decomp_commit"], fixture["platsim_code_hash"]):  # positive control for the hash check
            assert HASH_RE.search(h), h
        assert not HASH_RE.search(page.inner_text("body")), HASH_RE.search(page.inner_text("body"))  # FR-021

        cards = page.locator(".mon")
        assert cards.count() == 6
        assert "(no significant difference)" in page.locator(".mon", has_text="Luxray").inner_text()
        for i in range(6):  # SC-002: at most 8 fields per card
            assert cards.nth(i).locator(":scope > .field").count() <= 8
        page.wait_for_function("[...document.querySelectorAll('.sprite-front img')].every(i => i.complete)")
        widths = page.eval_on_selector_all(".sprite-front img", "els => els.map(e => e.naturalWidth)")
        assert widths == [160] * 6, widths

        # The "obtained from" text is shown in full, not cut off (FR-023, T039). The fixture run keeps the
        # text it was recorded with (003 FR-018: old runs are never rewritten), and it is long enough to wrap.
        team = page.request.get(base + f"/api/jobs/{FIXTURE_ID}").json()["team"]
        shown = page.eval_on_selector_all(".mon .obtained", "els => els.map(e => [e.textContent, e.scrollWidth <= e.clientWidth + 1, e.getBoundingClientRect().height])")
        assert [t for t, _, _ in shown] == [m["obtained_from"] for m in team]
        assert all(fits for _, fits, _ in shown), shown
        line = page.evaluate("parseFloat(getComputedStyle(document.querySelector('.mon .obtained')).lineHeight)")
        assert any(h > 1.5 * line for _, _, h in shown), "positive control: at least one source wraps onto a second line"
        assert not _visible(page, "#no-runs")  # positive control for T041

        move = page.locator(".move").first
        move_tip = page.locator(".mon .tip").first
        move.hover()
        assert move_tip.is_visible() and move_tip.inner_text().strip()  # FR-026
        page.mouse.move(5, 5)
        # 003 FR-022: each move is coloured by its type, and the tooltip names the type first.
        chips = page.eval_on_selector_all(".mon .move", """els => els.map(e => [e.dataset.type, getComputedStyle(e).color,
            getComputedStyle(document.documentElement).getPropertyValue('--type-' + (e.dataset.type || '').toLowerCase()).trim(),
            e.nextElementSibling.textContent])""")
        assert len(chips) == 24 and all(t for t, _, _, _ in chips), chips[:3]
        def _rgb(h):
            return f"rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})"
        assert all(c == _rgb(v) for _, c, v, _ in chips), chips[:3]
        assert all(tip.startswith(f"{t} · ") for t, _, _, tip in chips), chips[:3]

        assert page.locator("g.bar-group").count() == 5  # FR-027
        label = page.locator("g.bar-group").last.get_attribute("aria-label")
        assert "%" in label and "battles" in label and "1,990" in label

        # Keyboard: Tab reaches the clear rate, a chart bar (visible tip) and a move chip (FR-028).
        page.focus("#seed")
        assert _tab_until(page, "document.activeElement.classList.contains('clear-rate')")
        assert tip.is_visible()
        assert _tab_until(page, "document.activeElement.matches('g.bar-group')")
        assert _visible(page, "#trainer-pop") and "battles" in page.inner_text("#trainer-pop .pop-head")
        page.keyboard.press("Escape")
        assert not _visible(page, "#trainer-pop")
        assert _tab_until(page, "document.activeElement.classList.contains('move')")
        assert page.evaluate("getComputedStyle(document.activeElement.nextElementSibling).display") == "block"

        # ---- 003 US4: trainer pop-up on hover, focus and tap (FR-020, SC-006) ----
        league = page.request.get(base + "/api/league").json()
        assert [t["trainer"] for t in league] == ["aaron", "bertha", "flint", "lucian", "cynthia"]
        bars = page.locator("g.bar-group")
        for i, t in enumerate(league):
            page.mouse.move(5, 5)
            bars.nth(i).hover()
            pop = page.locator("#trainer-pop")
            pop.wait_for(state="visible")
            assert f"{t['name']}'s team" == pop.get_attribute("aria-label")
            head = page.inner_text("#trainer-pop .pop-head")
            assert t["name"] in head and "%" in head and "interval" in head and "battles" in head, head
            # Only the pop-up: no second box from the chart tooltip, and no SVG <title> (the browser
            # draws that as its own native tooltip, which screenshots don't capture).
            assert not _visible(page, "#chart-tip")
            assert page.locator("#chart-body svg title").count() == 0
            page.wait_for_function("[...document.querySelectorAll('#trainer-pop img')].every(i => i.complete && i.naturalWidth > 0)")
            assert page.locator("#trainer-pop img").count() == 1 + len(t["party"])
            assert page.locator("#trainer-pop .pop-empty").count() == 6 - len(t["party"])
            box = pop.bounding_box()
            assert box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["width"] <= 1920 and box["y"] + box["height"] <= 1080
            if shots:
                pop.screenshot(path=os.path.join(shots, f"pop-{t['trainer']}.png"))
            page.keyboard.press("Escape")
            assert not pop.is_visible()
        page.mouse.move(5, 5)

        # Run picker option text (FR-015).
        opt = page.locator("#run-picker option").first.inner_text()
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} · ", opt) and "Infernape" in opt and "qualified" in opt, opt

        _assert_wording(page, "fixture result shown")

        # ---- US2: setup (FR-003 to FR-007) ----
        assert not _visible(page, "#results")
        page.fill("#search", "gar")
        page.locator("#results li").first.wait_for()
        assert _visible(page, "#results")
        page.fill("#search", "")
        page.wait_for_function("document.getElementById('results').hidden")

        page.fill("#search", "garchomp")
        add = page.locator("button[aria-label='Add Garchomp to the team']")
        add.wait_for()
        for n in range(1, 6):
            add.click()
            assert page.inner_text("#team-count") == f"({n}/6)"
            assert page.is_disabled("#optimize")  # FR-007: fewer than 6
        page.wait_for_function("[...document.querySelectorAll('#slots img')].every(i => i.complete && i.naturalWidth > 0)")
        add.click()
        assert page.inner_text("#team-count") == "(6/6)" and add.is_disabled()  # duplicates; 7th refused
        assert page.is_enabled("#optimize")

        # Every control on the page has an accessible name (FR-028, T038), with a positive control.
        page.evaluate("document.getElementById('setup').append(Object.assign(document.createElement('input'), {id: 'planted'}))")
        assert page.evaluate(UNNAMED_JS) == ['<input id="planted">'], "positive control: an unlabelled input is caught"
        page.evaluate("document.getElementById('planted').remove()")
        assert page.locator("#results li button").count() and page.locator("#slots button").count()
        assert page.evaluate(UNNAMED_JS) == []

        # 003 US1: pokemon that can't be used are always listed, crossed out with the reason.
        assert page.locator("#show-excluded").count() == 0
        page.fill("#search", "golem")
        excl = page.locator("#results li.excluded")
        excl.first.wait_for()
        assert excl.first.locator("button").is_disabled() and "Graveler" in excl.first.locator(".reason").inner_text()
        assert "No Pokémon match" not in page.inner_text("#search-status")
        page.fill("#search", "zzzz")
        _wait_text(page, "#search-status", "No Pokémon match")
        page.fill("#search", "alakazam")
        with page.expect_request(lambda r: "trade_evolutions=1" in r.url):
            page.check("#allow-trade-evolutions")
        page.uncheck("#allow-trade-evolutions")

        # The trade-evolution note is a tooltip: hidden, shown on hover and on keyboard focus (FR-007).
        trade_tip = page.locator("#trade-help")
        page.evaluate("document.activeElement.blur()")
        page.mouse.move(5, 5)
        assert not trade_tip.is_visible()
        page.hover("label[for='allow-trade-evolutions']")
        assert trade_tip.is_visible()
        page.mouse.move(5, 5)
        page.focus("#allow-trade-evolutions")
        assert trade_tip.is_visible()
        page.evaluate("document.activeElement.blur()")

        # Wording scan (SC-001) over setup with every rule combination, with a positive control.
        page.evaluate("document.body.append(Object.assign(document.createElement('p'), {id: 'planted', textContent: 'species FR-001'}))")
        with pytest.raises(AssertionError):
            _assert_wording(page, "positive control")
        page.evaluate("document.getElementById('planted').textContent = 'Choose pokemon'")
        with pytest.raises(AssertionError):
            _assert_wording(page, "positive control: unaccented")
        page.evaluate("document.getElementById('planted').remove()")
        assert "Pokémon" in page.evaluate(SHOWN_TEXT_JS), "positive control: the accented word is read"
        rules = page.eval_on_selector_all("#setup .rules input[type=checkbox]", "els => els.map(e => e.id)")
        assert rules, "positive control: the rule checkboxes exist"
        page.fill("#search", "a")
        for mask in range(2 ** len(rules)):
            for i, rid in enumerate(rules):
                page.set_checked(f"#{rid}", bool(mask >> i & 1))
            with page.expect_response(lambda r: "/api/species" in r.url):
                page.fill("#search", "a ")
                page.fill("#search", "a")
            _assert_wording(page, f"search 'a', rules {mask:b}")
        for rid in rules:
            page.set_checked(f"#{rid}", False)

        seed_tip = page.locator("#seed-tip")
        assert not seed_tip.is_visible()
        page.hover("#seed-term")
        assert seed_tip.is_visible()
        page.mouse.move(5, 5)
        assert not seed_tip.is_visible()
        page.focus("#budget")
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "seed-term" and seed_tip.is_visible()  # FR-006

        assert page.input_value("#budget") == "standard"
        n_posts = len(posts)
        for bad in ("0", "150"):
            page.fill("#min-clear", bad)
            page.click("#optimize")
            assert _visible(page, "#form-error")
        assert len(posts) == n_posts, "an invalid min clear rate must not POST"
        page.fill("#min-clear", "75")
        page.select_option("#budget", "thorough")
        with page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/api/jobs")) as req:
            page.click("#optimize")
        assert '"budget":"thorough"' in req.value.post_data  # FR-005

        # ---- US3: progress, queue and cancel (FR-008 to FR-013) ----
        page.locator("#progress-card").wait_for(state="visible", timeout=15000)
        _wait_text(page, "#progress", "Stage: screen", timeout=30)
        e1 = page.inner_text("#progress .elapsed")
        time.sleep(1.3)
        assert page.inner_text("#progress .elapsed") != e1  # ticking
        eta = page.inner_text("#progress .eta")
        assert eta == "estimating…" or eta.startswith("about "), eta
        jobs = page.request.get(base + "/api/jobs").json()
        running = next(j for j in jobs if j["status"] == "running")
        assert running["progress"]["best_so_far"], "FR-013 positive control: best_so_far is present in the API"
        assert "best so far" not in page.inner_text("body").lower()

        with page.expect_request(lambda r: r.method == "POST" and r.url.endswith("/api/jobs")):
            page.click("#optimize")
        _wait_text(page, "#queue li", "position 1 ·")  # FR-009
        page.locator("#queue li button").click()
        assert dialogs and "Cancel this run?" in dialogs[-1]  # FR-011
        page.wait_for_function("document.querySelectorAll('#queue li').length === 0", timeout=15000)
        assert page.request.get(base + f"/api/jobs/{running['id']}").json()["status"] == "running"

        page.locator("#progress button.danger").click()
        page.locator("#progress-card").wait_for(state="hidden", timeout=15000)
        _wait_text(page, "#run-status", "Run cancelled")
        assert _visible(page, "#run-status")  # outside #progress (P4-07)

        _assert_wording(page, "after cancel")

        # A server-side 422 (an unusable pokemon in the team) is shown without "species" or ids.
        page.fill("#search", "alakazam")
        page.check("#allow-trade-evolutions")
        ala = page.locator("button[aria-label='Add Alakazam to the team']")
        ala.wait_for()
        page.locator("#slots button").first.click()  # free a slot (remove one Garchomp)
        ala.click()
        page.uncheck("#allow-trade-evolutions")
        page.click("#optimize")
        page.locator("#form-error").wait_for(state="visible")
        assert "Alakazam" in page.inner_text("#form-error")
        _assert_wording(page, "422 error")

        # ---- US4: picker shows failed/cancelled runs as a status (FR-016) ----
        page.wait_for_function("document.querySelectorAll('#run-picker option').length >= 3", timeout=15000)
        page.select_option("#run-picker", running["id"])
        _wait_text(page, "#run-message", "cancelled by user")
        assert not _visible(page, "#result")
        page.select_option("#run-picker", FIXTURE_ID)  # SC-005: open the dropdown, pick the run
        _wait_text(page, "#summary", "58.23")
        assert page.locator(".mon").count() == 6

        # 003 FR-023: the theme toggle, top right; the choice survives a reload; no choice = system setting.
        btn = page.locator("#theme-toggle")
        head, b = page.locator("header.site").bounding_box(), btn.bounding_box()
        assert b["x"] > head["x"] + head["width"] / 2 and b["y"] < head["y"] + head["height"] / 2, (b, head)
        page.emulate_media(color_scheme="light")
        page.evaluate("localStorage.removeItem('platsim-theme')")
        page.reload()
        _wait_text(page, "#summary", "58.23")
        assert page.evaluate("document.documentElement.dataset.theme || ''") == ""
        assert btn.get_attribute("aria-pressed") == "false"
        light_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        btn.click()
        assert page.evaluate("document.documentElement.dataset.theme") == "dark" and btn.get_attribute("aria-pressed") == "true"
        assert page.evaluate("getComputedStyle(document.body).backgroundColor") != light_bg
        page.reload()
        _wait_text(page, "#summary", "58.23")
        assert page.evaluate("document.documentElement.dataset.theme") == "dark"  # remembered
        page.evaluate("localStorage.removeItem('platsim-theme')")
        page.emulate_media(color_scheme="dark")
        page.reload()
        _wait_text(page, "#summary", "58.23")
        assert page.evaluate("document.documentElement.dataset.theme || ''") == ""
        assert btn.get_attribute("aria-pressed") == "true" and btn.inner_text() == "Light mode"  # follows the system
        page.emulate_media(color_scheme="light")
        if shots:
            for scheme in ("light", "dark"):
                if page.evaluate("document.documentElement.dataset.theme || 'light'") != scheme:
                    btn.click()
                page.screenshot(path=os.path.join(shots, f"browser-{scheme}.png"), full_page=True)
        page.evaluate("localStorage.removeItem('platsim-theme'); delete document.documentElement.dataset.theme")

        # ---- narrow screen (FR-002) ----
        small = chrome.new_context(viewport={"width": 360, "height": 800})
        sp = small.new_page()
        sp.on("request", lambda r: urls.append(r.url))
        sp.goto(base + "/")
        _wait_text(sp, "#summary", "58.23")
        assert sp.evaluate("document.scrollingElement.scrollWidth") <= 360
        assert sp.locator("#setup").bounding_box()["y"] < sp.locator("#results-col").bounding_box()["y"]
        small.close()

        # Tap opens the pop-up on a touch screen, and it stays inside a 360 px viewport (003 FR-020).
        touch = chrome.new_context(viewport={"width": 360, "height": 800}, has_touch=True, is_mobile=True)
        tp = touch.new_page()
        tp.goto(base + "/")
        _wait_text(tp, "#summary", "58.23")
        tp.wait_for_function("document.querySelectorAll('g.bar-group').length === 5")
        tp.wait_for_timeout(300)  # /api/league
        tp.locator("g.bar-group").last.scroll_into_view_if_needed()
        tp.locator("g.bar-group").last.tap()
        tp.locator("#trainer-pop").wait_for(state="visible")
        box = tp.locator("#trainer-pop").bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 360, box
        assert tp.locator("#trainer-pop img").count() == 7  # Cynthia + six
        if shots:
            tp.screenshot(path=os.path.join(shots, "browser-360-pop.png"))
        touch.close()
        small = chrome.new_context(viewport={"width": 360, "height": 800})
        sp = small.new_page()
        sp.goto(base + "/")
        _wait_text(sp, "#summary", "58.23")
        if shots:
            sp.screenshot(path=os.path.join(shots, "browser-360.png"), full_page=True)
        small.close()
        ctx.close()

    # ---- offline (FR-029), with a positive control (analysis N1) ----
    assert urls and any("/api/sprites/" in u for u in urls) and any("/api/jobs" in u for u in urls)
    assert {urlparse(u).hostname for u in urls} == {"127.0.0.1"}, {urlparse(u).hostname for u in urls}


def test_older_run_without_per_trainer(tmp_path, catalog, chrome):
    """Separate app and runs dir (analysis P4-11): an older run with no per_battle."""
    copy_fixture_run(tmp_path, drop_keys=("per_battle",))
    with served(tmp_path, catalog) as (base, _app):
        page = chrome.new_page()
        page.goto(base + "/")
        _wait_text(page, "#chart", "Per-trainer data is not available for this run")
        page.close()


def test_finish_is_announced_and_shown(tmp_path, catalog, chrome):
    """A run that finishes updates the status line and the result panel without a reload (FR-014,
    FR-028). Found in the T035 walkthrough: the status line used to keep saying "Run cancelled"."""
    copy_fixture_run(tmp_path)
    with served(tmp_path, catalog, runner=_fake_runners.instant_runner) as (base, _app):
        page = chrome.new_page()
        page.goto(base + "/")
        _wait_text(page, "#summary", "58.23")  # positive control: the fixture run is shown first
        assert page.input_value("#run-picker") == FIXTURE_ID
        page.fill("#search", "garchomp")
        add = page.locator("button[aria-label='Add Garchomp to the team']")
        add.wait_for()
        for _ in range(6):
            add.click()
        page.click("#optimize")
        _wait_text(page, "#run-status", "Run finished:", timeout=30)
        newest = page.request.get(base + "/api/jobs").json()[0]
        assert newest["status"] == "done" and newest["id"] != FIXTURE_ID
        page.wait_for_function(f"document.getElementById('run-picker').value === {json.dumps(newest['id'])}")
        assert newest["label"] in page.inner_text("#run-status")
        page.close()


def test_no_runs_yet(tmp_path, catalog, chrome):
    """An empty runs directory says no runs have finished yet, with no result shown (US4/AC4, T041)."""
    with served(tmp_path, catalog) as (base, _app):
        page = chrome.new_page()
        page.goto(base + "/")
        page.locator("#no-runs").wait_for(state="visible", timeout=15000)
        assert page.inner_text("#no-runs").strip() == "No runs have finished yet."
        assert not _visible(page, "#result") and page.locator(".mon").count() == 0
        assert page.request.get(base + "/api/jobs").json() == []
        page.close()


def test_required_hms_step(tmp_path, catalog, chrome):
    """006 US3: four steps in order; step 3 lists the eight HMs unchecked; a checked HM is sent with
    the run; the results summary has a "Required HMs" row ("none" for the frozen default run)."""
    copy_fixture_run(tmp_path)
    with served(tmp_path, catalog) as (base, _app):
        page = chrome.new_page()
        posts: list[str] = []
        page.on("request", lambda r: posts.append(r.post_data or "") if r.method == "POST" and r.url.endswith("/api/jobs") else None)
        page.goto(base + "/")
        heads = [h.strip() for h in page.locator("#setup h2").all_inner_texts()]
        assert [h.split()[0] + " " + h.split()[1].split("(")[0] for h in heads][:4] == [
            "1. Choose", "2. Team", "3. Required", "4. Optimize"], heads
        page.locator("input.hm").first.wait_for(timeout=15000)
        boxes = page.locator("input.hm")
        assert boxes.count() == 8
        assert [boxes.nth(i).get_attribute("id") for i in range(8)] == [
            "require-hm-cut", "require-hm-fly", "require-hm-surf", "require-hm-strength", "require-hm-defog",
            "require-hm-rock_smash", "require-hm-waterfall", "require-hm-rock_climb"]
        assert not any(boxes.nth(i).is_checked() for i in range(8))
        assert "HM03 Surf" in page.inner_text("#hm-step")
        _wait_text(page, "#summary", "Required HMs")
        assert "Required HMs" in page.inner_text("#summary") and "none" in page.inner_text("#summary")
        # a checked HM is sent: fill the team through the page's own search, then optimize
        page.check("#require-hm-surf")
        for _ in range(6):
            page.fill("#search", "garchomp")
            page.locator("#results li button, #results li").first.click()
        page.click("#optimize")
        page.wait_for_timeout(1500)
        assert any('"required_hms": ["surf"]' in p or '"required_hms":["surf"]' in p for p in posts), posts
        page.close()
