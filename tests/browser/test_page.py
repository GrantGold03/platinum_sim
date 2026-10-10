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
        for sel in ("#optimize", "#summary", "#chart"):  # SC-001, SC-003: all on screen at 1080p
            b = page.locator(sel).bounding_box()
            assert b["y"] >= 0 and b["y"] + b["height"] <= 1080, (sel, b)

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

        # The "obtained from" text is shown in full, not cut off (FR-023, T039).
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

        assert page.locator("g.bar-group").count() == 5  # FR-027
        label = page.locator("g.bar-group").last.get_attribute("aria-label")
        assert "%" in label and "battles" in label and "1,990" in label

        # Keyboard: Tab reaches the clear rate, a chart bar (visible tip) and a move chip (FR-028).
        page.focus("#seed")
        assert _tab_until(page, "document.activeElement.classList.contains('clear-rate')")
        assert tip.is_visible()
        assert _tab_until(page, "document.activeElement.matches('g.bar-group')")
        assert _visible(page, "#chart-tip") and "battles" in page.inner_text("#chart-tip")
        assert _tab_until(page, "document.activeElement.classList.contains('move')")
        assert page.evaluate("getComputedStyle(document.activeElement.nextElementSibling).display") == "block"

        # Run picker option text (FR-015).
        opt = page.locator("#run-picker option").first.inner_text()
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} · ", opt) and "Infernape" in opt and "qualified" in opt, opt

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

        page.check("#show-excluded")
        page.fill("#search", "munchlax")
        excl = page.locator("#results li.excluded")
        excl.first.wait_for()
        assert excl.first.locator("button").is_disabled() and excl.first.locator(".reason").inner_text()
        page.uncheck("#show-excluded")
        page.fill("#search", "alakazam")
        with page.expect_request(lambda r: "trade_evolutions=1" in r.url):
            page.check("#allow-trade-evolutions")
        page.uncheck("#allow-trade-evolutions")

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

        # ---- US4: picker shows failed/cancelled runs as a status (FR-016) ----
        page.wait_for_function("document.querySelectorAll('#run-picker option').length >= 3", timeout=15000)
        page.select_option("#run-picker", running["id"])
        _wait_text(page, "#run-message", "cancelled by user")
        assert not _visible(page, "#result")
        page.select_option("#run-picker", FIXTURE_ID)  # SC-005: open the dropdown, pick the run
        _wait_text(page, "#summary", "58.23")
        assert page.locator(".mon").count() == 6

        if shots:
            for scheme in ("light", "dark"):
                page.emulate_media(color_scheme=scheme)
                page.screenshot(path=os.path.join(shots, f"browser-{scheme}.png"), full_page=True)

        # ---- narrow screen (FR-002) ----
        small = chrome.new_context(viewport={"width": 360, "height": 800})
        sp = small.new_page()
        sp.on("request", lambda r: urls.append(r.url))
        sp.goto(base + "/")
        _wait_text(sp, "#summary", "58.23")
        assert sp.evaluate("document.scrollingElement.scrollWidth") <= 360
        assert sp.locator("#setup").bounding_box()["y"] < sp.locator("#results-col").bounding_box()["y"]
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
