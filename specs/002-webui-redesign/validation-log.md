# Validation log: 002 Web UI redesign

This log records real command output, newest at the bottom.

## T002: baseline, 2026-10-09 (branch 002-webui-redesign, before any code change)

`uv run pytest -q tests/integration/test_web.py` exited with code 0:

```
8 passed, 1 warning in 36.96s
```

The four `runs/final-defaults` report files, hashed before the change (quickstart V6, "before"):

```
ade487fb6ff4345910e40935449e49e7b288c51750259040249af30ccc64277d  runs/final-defaults/result.json
8aef11f4ccb7639b55dcedd9c37d2aff47e0d966c52633768510e9bda6b1efd0  runs/final-defaults/result.csv
78be928d6cc26625817cd102be4ccf8e4fd59d909f99ede94965977ff0250aed  runs/final-defaults/result.xlsx
e2b11bf5818435cc6606c3aa900056b6d2776ec9d5bfa260c0c5203dc45ddb34  runs/final-defaults/team.txt
```

## Phase 2 checkpoint (T004, T005), 2026-10-09

The shared helpers moved to `tests/integration/_web_helpers.py`, the session `ledger`/`catalog`
fixtures to `tests/conftest.py`, and `app.py` now records `platsim_version`, `stage_started`,
`seen_stages` and `verdict`. `uv run pytest -q tests/integration/test_web.py` exited with code 0:

```
8 passed, 1 warning in 36.19s
```

## US1 checkpoint (T006–T014), 2026-10-09

- I confirmed the tests fail before the implementation:
  `uv run pytest -q tests/integration/test_web_sprites.py tests/integration/test_web_result_view.py`
  exited with code 1 (3 failed, including `KeyError: 'per_trainer'`).
- After the implementation,
  `uv run pytest -q tests/integration/test_web.py tests/integration/test_web_sprites.py tests/integration/test_web_result_view.py`
  exited with code 0:
  ```
  11 passed, 1 warning in 35.93s
  ```
- Headless Chrome at 1920×1080 against a copy of the fixture run (`platsim serve --port 8765`).
  Observed:
  - two columns;
  - verdict "qualified", clear rate "86.5%" (dotted, with a tooltip), and "58.23 (level gap of 4)";
  - "platsim version not recorded" and the warning text;
  - a chart with 5 bars (Cynthia 86.9% with a visible whisker) and a dashed threshold at 75%;
  - six cards with transparent decomp sprites, and Luxray showing "Rivalry/Intimidate (no significant difference)".

  On the first screenshot the Optimize button was cut off at the bottom. I tightened the left
  column's spacing, and on the second screenshot the Optimize button, summary and chart all fit
  in 1080 px.
- The run label read "… · done" until T027 added the server-side `label`/`verdict`.

## US2 checkpoint (T015–T019), 2026-10-09

- `uv run pytest -q tests/integration/test_web.py` exited with code 0:
  ```
  9 passed, 1 warning in 35.84s
  ```
  The new test covers `sprite_icon` and the budget reaching `job.json`. Note: I wrote this test
  after T016, not before it.
- Headless Chrome at 360×800: the columns stack with setup first, there is no horizontal
  overflow, the species list is hidden with an empty search, and the budget select reads
  "standard (2,000+ runs)".

## US3 checkpoint (T020–T029), 2026-10-09

- `uv run pytest -q tests/integration/test_web_eta.py tests/integration/test_web.py tests/integration/test_web_cancel.py`
  exited with code 0:
  ```
  14 passed, 1 warning in 37.96s
  ```
  Cancel's positive control held: the job process and its `sleep` were alive before the cancel.
  The cancel took at most 10 s, and both processes were gone afterwards.
- **First run of `tests/integration/test_web_shutdown.py`: it failed, and the test was at fault.**
  - Its child lookup used `/proc/<pid>/task/<pid>/children`, which doesn't exist on this kernel
    (no CONFIG_PROC_CHILDREN). So the positive control saw no job process.
  - The assertion sat outside the cleanup `try`, so the test leaked 2 servers, 2 job processes
    and 2 `sleep 300`.
  - I used the leaked processes as a manual check: SIGINT to server 1 and SIGKILL to server 2.
    Twelve seconds later the servers, job processes, resource trackers and sleeps were all gone.
  - The test now uses `pgrep -P` and records every pid before asserting anything.
- After that fix, `uv run pytest -q -s tests/integration/test_web_shutdown.py` exited with code 0:
  ```
  SIGINT: everything gone after 0.2s
  SIGKILL: everything gone after 0.1s
  2 passed in 1.50s
  ```
  `pgrep -af "sleep 300|_serve_fake|spawn_main"` found no stray processes.
- `uv run pytest -q -s tests/integration/test_web_process_determinism.py` exited with code 0:
  ```
  child 82.8s, in-process 78.3s
  1 passed in 161.17s (0:02:41)
  ```
  A real 40-run evaluate of the reference team gave a byte-identical `result.json` in a spawned
  child and in-process (analysis V1-B).

## US4 checkpoint (T030–T031), 2026-10-09

`uv run pytest -q tests/integration/test_web.py -k labels_and_cap` exited with code 0:

```
1 passed, 10 deselected, 1 warning in 40.98s
```

It checks:
- jobs listed newest first, with labels ending "· qualified", "· failed" and "· cancelled";
- the failed job's error, and no team for it;
- the cancelled job's error, "cancelled by user";
- 51 fixture copies give 50 listed, newest first.

## T032: browser walkthrough, 2026-10-09

`PLATSIM_SCREENSHOT_DIR=<scratchpad>/shots uv run pytest -q -m browser tests/browser/` exited with code 0:

```
2 passed in 45.05s
```

`pgrep` found no stray `sleep 300` or `spawn_main` processes afterwards.

I viewed `browser-light.png` and `browser-dark.png`. Both themes render with readable
contrast. The run label reads "… · qualified", "Run cancelled" sits in the status line above the
result, six Garchomp slot icons are visible, and the chart, cards and downloads are intact.

## T034: quickstart V6, report bytes unchanged (FR-030, SC-007), 2026-10-09

The four files downloaded from `GET /api/jobs/job-20261008T000000Z-f1f1f1/<name>` on the new
server:

```
ade487fb6ff4345910e40935449e49e7b288c51750259040249af30ccc64277d  result.json
8aef11f4ccb7639b55dcedd9c37d2aff47e0d966c52633768510e9bda6b1efd0  result.csv
78be928d6cc26625817cd102be4ccf8e4fd59d909f99ede94965977ff0250aed  result.xlsx
e2b11bf5818435cc6606c3aa900056b6d2776ec9d5bfa260c0c5203dc45ddb34  team.txt
```

`diff` against the T002 hashes of `runs/final-defaults` showed no difference: all four are
byte-identical.

## T033: full suite, 2026-10-09

The commands ran in sequence, from 17:06:47Z to 19:35:25Z.

`uv run pytest -q -m "not browser"` exited with code 0:

```
381 passed, 2 deselected, 1 warning in 8871.82s (2:27:51)
```

The one warning is the existing `StarletteDeprecationWarning` from `fastapi/testclient.py`
(httpx). Most of the 2 h 28 min is feature 001's `test_optimize_small.py`, which runs two
quick optimizations. The task's "about 1 h" estimate was low.

`PLATSIM_SCREENSHOT_DIR=<scratchpad>/shots uv run pytest -q -m browser tests/browser/` exited
with code 0:

```
2 passed in 43.86s
```

I viewed `browser-light.png` and `browser-dark.png` from this run. Observed:
- two columns at 1920 px;
- "Run cancelled" in the status line;
- the picker reads "2026-10-07 20:00 · Infernape, Staraptor, Luxray, Garchomp, Gyarados, Gardevoir · qualified";
- the summary shows verdict "qualified", clear rate "86.5%", "58.23 (level gap of 4)",
  threshold, budget, legality, "platsim version not recorded" and the warning;
- 5 bars, with whiskers and the dashed 75% line;
- six cards with transparent sprites, Luxray and Gardevoir with "(no significant difference)",
  and moves as chips;
- 4 download links.

Both themes are readable. In both, the Optimize button and the whole chart fit in 1080 px.

Notes for user testing (not defects against the spec):
- The "obtained from" line is cut off with "…" on cards.
- "Run cancelled" stays in the status line while an older run is shown below it.

### Requirement → check map (SC-006)

"walkthrough" means `tests/browser/test_page.py::test_page_walkthrough`. All the checks listed
passed in the runs above, apart from rows marked pending or partial.

| Req | Check | Result |
|-----|-------|--------|
| FR-001 | walkthrough: `#setup` ends left of `#results-col` at 1920 px | pass |
| FR-002 | walkthrough: 360 px, scrollWidth ≤ 360, setup above results | pass |
| FR-003 | walkthrough: `#results` hidden while empty, shown after typing, hidden again | pass |
| FR-004 | walkthrough: every `#slots img` loads (naturalWidth > 0); `test_web.py::test_budget_and_species_icons` (`sprite_icon` URL returns 200) | pass |
| FR-005 | walkthrough: POST body has `"budget":"thorough"`; `test_budget_and_species_icons`: the budget reaches `job.json` | pass |
| FR-006 | walkthrough: seed tip hidden, shown on hover, hidden after, shown on keyboard focus | pass |
| FR-007 | walkthrough: Optimize disabled below 6, duplicates allowed, 7th refused, excluded species with reason, trade-evolution refresh request, min clear rate 0/150 rejected without a POST; `test_web.py::test_legality_options_page_search_and_jobs` | pass |
| FR-008 | walkthrough: `#progress-card` hidden with nothing running, visible while running, hidden after cancel | pass |
| FR-009 | walkthrough: elapsed text changes within 1.3 s, "Stage: screen", queued "position 1 ·"; `test_web.py::test_running_view_fields` | pass (species in the queued row are not asserted) |
| FR-010 | `test_web_eta.py` (2 tests); walkthrough: ETA reads "estimating…" or "about …" | pass |
| FR-011 | walkthrough: Cancel on the queued and running job, confirmation dialog "Cancel this run?"; `test_web_cancel.py::test_cancel_running_then_queued` | pass |
| FR-012 | `test_web_cancel.py` (2 tests): status cancelled, processes gone ≤ 10 s, next job starts; walkthrough: cancelled run shows no `#result` | pass |
| FR-013 | walkthrough: "best so far" absent from page while the API has `best_so_far` (positive control) | pass |
| FR-014 | walkthrough: page loads on the newest done run | pass on load; "switches when a new run finishes" is T035 (pending) |
| FR-015 | walkthrough: option text "YYYY-MM-DD HH:MM · species · verdict"; `test_web.py::test_job_list_labels_and_cap` | pass |
| FR-016 | walkthrough: cancelled run shows "cancelled by user" and no result; `test_job_list_labels_and_cap` (failed and cancelled) | pass |
| FR-017 | walkthrough: tip hidden, then "95% interval 84.9–87.9%" and "2,000 runs" on hover and on keyboard focus | pass |
| FR-018 | walkthrough: "cynthia win", "policies", "objective" absent | pass |
| FR-019 | walkthrough: "58.23 (level gap of 4)"; `test_web_result_view.py::test_result_view` | pass |
| FR-020 | walkthrough: threshold 75.0%, budget, "egg moves off", warning text | pass |
| FR-021 | walkthrough: "platsim version not recorded", no hex hash on the page (positive control: fixture hashes match the regex); `test_running_view_fields`: `platsim_version` recorded | pass |
| FR-022 | `test_result_view`: the four downloads return the fixture bytes; screenshots show 4 links | pass |
| FR-023 | `test_result_view` (team fields, sprite URL, 4 moves with sources); walkthrough: 6 cards, sprites 160 px wide; screenshots | pass |
| FR-024 | walkthrough: nature, IVs, EVs, ability choice, held item source absent; `test_result_view`: hidden keys absent | pass |
| FR-025 | `test_result_view`: "Rivalry/Intimidate (no significant difference)", single "Blaze"; walkthrough: Luxray card | pass |
| FR-026 | walkthrough: no "move 1 source"; move tip on hover and on keyboard focus | pass |
| FR-027 | walkthrough: 5 bar groups, aria-label has % and "1,990 battles", tip on focus; `test_older_run_without_per_trainer` | pass |
| FR-028 | walkthrough: keyboard reaches clear rate, chart bar, move chip; light and dark screenshots viewed; every control in `#setup`/`#results-col` has an accessible name (T038, with a planted unlabelled input as the positive control); status announcements by `test_finish_is_announced_and_shown` and the cancel walkthrough | pass (after T038) |
| FR-029 | walkthrough: every request went to 127.0.0.1, with sprites and `/api/jobs` seen (positive control); `test_web_sprites.py` | pass |
| FR-030 | T034: four report hashes identical to the T002 baseline; `test_result_view` byte-compares the downloads | pass |
| SC-001 | walkthrough: `#optimize`, `#summary`, `#chart` all within 1080 px | pass (proxy; the "10 seconds" is a human measure) |
| SC-002 | walkthrough: ≤ 8 `.field` per card | pass |
| SC-003 | walkthrough: same 1080 px check, during setup | pass |
| SC-004 | `test_web_cancel.py`: elapsed ≤ 10 s, then the next job runs | pass; a real-job cancel is T035 (pending) |
| SC-005 | walkthrough: `select_option` on the picker shows the run; `test_job_list_labels_and_cap`: 51 runs → 50 listed | pass |
| SC-006 | this table | pass, except FR-028 partial and the T035 items pending |
| SC-007 | T034 hashes; T035 web-vs-CLI `cmp` (pending) | pass for the fixture |

## T035: quickstart V7, real quick jobs through `platsim serve`, 2026-10-09

`uv run platsim serve` (port 8000, `runs/`) was driven by a Playwright script in the scratchpad
(system Chrome, 1920×1080). Before starting, no `sim/worker.mjs` was running and port 8000 was
free. Driver output:

```
15:37:50 job A: job-20261009T193750Z-a1822a
15:37:51 job B: job-20261009T193751Z-1fdb5e queue row: position 1 · infernape, staraptor, luxray, garchomp, gyarados, gardevoir
15:38:28 A stage: prune worker pids: [48096, 48097, 48098, 48099, 48100, 48101, 48102, 48103, 48104, 48105, 48106, 48107, 48108, 48109, 48110, 48111]
15:38:29 elapsed ticks: elapsed 0:00:37 -> elapsed 0:00:38 | ETA: about 27 min left
15:38:30 A cancelled after 0.2s; A's pids gone after 0.2s; still alive: []
15:38:30 B status: running at 0.2s after cancel
16:10:15 B finished: done after 1906s (elapsed_s=1900.0)
16:10:15 picker value is B; page reloads during the run: 0
16:10:15 summary: Verdict | not qualified | Clear rate | 91.6% | Final level | 58.04 (level gap of 5) | Threshold | 75.0% | Budget | quick | Legality options | egg moves off, trade evolutions off | Version | platsim 0.1.0 | QUICK BUDGET: ...
16:10:15 picker options: ['2026-10-09 15:37 · Infernape, Staraptor, Luxray, Garchomp, Gyarados, Gardevoir · not qualified', '2026-10-09 15:37 · Garchomp, Garchomp, Garchomp, Garchomp, Garchomp, Garchomp · cancelled', '2026-10-08 19:52 · Garchomp, Infernape, Staraptor, Rotom, Floatzel, Weavile · qualified', '2026-10-08 07:51 · Infernape, Staraptor, Luxray, Garchomp, Gyarados, Gardevoir · not qualified']
drive exit=0
serve exit=0
```

- Positive control: A was running (stage `prune`, past `resolve`) with 16 worker pids alive
  before the cancel.
- SC-004: A was `cancelled` 0.2 s after the click, and none of its 16 recorded pids was alive
  0.2 s after the click. B started at once.
- FR-014: the result panel switched to B without a reload.
- FR-021: the summary shows "platsim 0.1.0" for a newly recorded run.
- After Ctrl-C (SIGINT) the server exited with code 0, and `pgrep -af "sim/worker.mjs|platsim serve"` matched nothing but itself.

**Defect found and fixed.** The screenshot after B finished (`v7-done-b.png`) showed two problems:
- The status line still read "Run cancelled", because `app.js` announced only cancellations.
  It now also announces "Run started.", "Run finished: <label>" and "Run failed: <reason>".
- The selected "quick (500 runs, never qualifies)" text was cut off in the budget select.
  It now reads "quick (500 runs, test only)". The QUICK BUDGET warning still says the run can
  never qualify.

I added `tests/browser/test_page.py::test_finish_is_announced_and_shown` (instant runner).
- Without the `done` announcement it fails: `TimeoutError: Locator.wait_for: Timeout 30000ms exceeded`, `1 failed, 2 deselected in 67.05s`.
- With it, `uv run pytest -q -m browser tests/browser/` exited with code 0: `3 passed in 56.16s`.

These edits touch only `static/` and `tests/`. `platsim_code_hash` covers only
`src/platsim/**/*.py` and `pyproject.toml` (`version.py:71`), so they can't change the CLI
comparison below.

### T035 comparison with the command line (analysis V1-A, Constitution IV)

`uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed t058 --out <scratchpad>/cli-t058`
ran from 20:10:26Z to 20:42:03Z (31.6 min) and exited with code 0. Then:

```
cmp runs/job-20261009T193751Z-1fdb5e/result.json <scratchpad>/cli-t058/result.json   -> exit 0
d71fbb3243541091469853b6484265ca0c94f39286b06c2d61b8e249a2c14bc4  runs/job-20261009T193751Z-1fdb5e/result.json
d71fbb3243541091469853b6484265ca0c94f39286b06c2d61b8e249a2c14bc4  <scratchpad>/cli-t058/result.json
```

The web job's report is byte-identical to the CLI's for the same request. The hash is not the
empty-file hash (`e3b0c442…`).

With this run, the FR-014 "switches when a new run finishes", SC-004 (real job) and SC-007 (new
run) rows of the T033 table pass. FR-028 stays partial: `aria-live` announcements are now
exercised by `test_finish_is_announced_and_shown` and the cancel walkthrough, but control labels
are not asserted.

## Phase 8: Convergence (T038–T041), 2026-10-10

`/speckit-converge` found 4 gaps (1 medium, 3 low). All are fixed:

- **T040** (Edge Cases, ability tie with more than two abilities). Test first:
  `test_ability_tie_label` failed on the three-ability case
  (`AssertionError: assert 'Keen Eye/Tan...t difference)' == 'Keen Eye (no...t difference)'`).
  `result_view._ability` now joins only when exactly one other ability exists. Then
  `uv run pytest -q tests/integration/test_web_result_view.py` exited with code 0: `3 passed`.
  The real Luxray and Gardevoir ties still read "A/B (no significant difference)".
- **T039** (FR-023): the "obtained from" line wraps in full instead of being cut off with
  "…" (`style.css` `.mon > .obtained`; the `title` attribute is gone). The walkthrough now
  checks that each card's text equals the API's `obtained_from` and is not clipped. Positive
  control: at least one source wraps onto a second line. Negative control: with the old CSS put
  back, the walkthrough failed (`AssertionError` listing all six as not fitting,
  `1 failed, 3 deselected in 35.96s`). The fix was then restored and checked with `cmp`.
  In the screenshot the full sources are visible, and the summary and chart still fit in 1080 px.
- **T038** (FR-028, SC-006): the walkthrough checks that every `input`/`select`/`button` in both
  columns has an accessible name. Positive control: a planted `<input id="planted">` is the only
  item reported.
- **T041** (US4/AC4): `test_no_runs_yet`. An empty runs directory shows "No runs have finished
  yet." and no result. Positive control: `#no-runs` is hidden in the walkthrough, where a run
  exists.

`PLATSIM_SCREENSHOT_DIR=<scratchpad>/shots uv run pytest -q -m browser tests/browser/` exited with code 0:
`4 passed in 47.65s`. The web integration tests
(`test_web.py`, `_result_view`, `_sprites`, `_eta`, `_cancel`, `_shutdown`) exited with code 0:
`21 passed, 1 warning in 42.73s`.
