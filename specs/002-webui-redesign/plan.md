# Implementation Plan: Web UI Redesign

**Branch**: `002-webui-redesign` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-webui-redesign/spec.md`

## Summary

Redesign the page served by `platsim serve` so that setup is on the left and results on the
right.
- **Results**: show the newest run by default, with a run picker, and present it as a short
  summary, a per-trainer clear-rate chart, and six team cards with decomp sprites.
- **Progress**: appears only while a job is queued or running. It shows elapsed time, an ETA
  based on history, and a Cancel button.
- **Server**:
  - A shaped result view replaces the raw CSV table.
  - A sprite endpoint serves the vendored decomp PNGs, with transparency added.
  - A cancel endpoint is added.
  - Each web job runs in its own process group, so it can be stopped within 10 s.
- **Unchanged**: the optimizer, the simulator and the four downloadable reports.

## Technical Context

**Language/Version**: Python 3.14.7 (server); browser JavaScript (ES2020, no build step)

**Primary Dependencies**:
- FastAPI and uvicorn (existing).
- Standard library `multiprocessing`, `struct` and `zlib`.
- Dev only: `playwright` (Python), driving the system Chrome.

**Storage**:
- Files under `runs/<job id>/`. `job.json` gains `platsim_version`, `cancel_requested`, `verdict`,
  `progress.stage_started` and `progress.seen_stages`.
- Read only: `runs/*/state.json` timings, and the decomp `res/pokemon/*` (PNG and data.json).

**Testing**:
- pytest, covering the existing `tests/integration/test_web.py` (8 tests, passing) plus new
  sprite, cancel and result-view tests.
- Playwright browser tests marked `browser`.

**Target Platform**: Linux, on a local machine. The server binds to 127.0.0.1. Desktop and
phone-width browsers are supported.

**Project Type**: a local web UI on top of the existing Python CLI package

**Performance Goals**: cancel completes within 10 s (SC-004). The elapsed time ticks every 1 s.
Each sprite is served from an in-memory cache after its first read.

**Constraints**:
- Offline at runtime, with no CDN and no external sprite source (Constitution, Technical
  Constraints).
- No build step.
- Downloadable reports stay byte-identical (FR-030).
- No change to `sim/` (that would change `sim_code_hash`).

**Scale/Scope**:
- One user and one job at a time (FIFO), with up to 50 runs listed.
- 3 static files rewritten, `app.py` extended.
- 7 new test files (sprites, result view, eta, cancel, shutdown, process determinism, browser), plus 3 helper modules (`_web_helpers.py`, `_fake_runners.py`, `_serve_fake.py`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | PASS | The sprites and the second ability name for a tie are read from `pokeplatinum/res/pokemon/` (R3, R4). Nothing is hand-copied or committed. |
| II. Showdown is the battle engine | PASS | `sim/` is not touched, and the battle path is unchanged. The child process runs the same `run_optimization`. Principle II requires the opponent policy to be named in every result. That is satisfied by the report files, which IV (1.1.0) defines as the reported result. `result.json` carries `opponent_policy`, and the page links to it (FR-022). |
| III. In-game legality | PASS | The validator and legality flags are unchanged. The page sends the same flags. |
| IV. Reproducible, statistically honest (v1.1.0) | PASS | Checked against amendment 1.1.0, "report files vs. views": (a) Every downloadable report keeps all of the provenance unchanged (FR-030, checked by V6). (b) Every win rate on the page has its interval and battle count one hover or focus away: the clear-rate tooltip (FR-017) and the per-trainer chart (FR-027). The Cynthia win rate is not shown. (c) The page links to the run's report files (FR-022). (d) The version shown is the one the job recorded, and "not recorded" otherwise (R5). (e) Running in a child process is meant not to change seeds or ordering. Two checks will show it: T024 (a 40-run evaluate, child process vs in-process, byte-identical) and T035 (a real `quick` optimize, web vs command line, byte-identical). It stays unverified until they run. |
| V. Verified claims, positive controls | PASS | Positive controls: a sprite with `tRNS` (V2), a running child pid before cancel (V4), a fixture run with a known Cynthia rate (V3). Browser tests skip with a reason rather than passing silently. The real-browser check closes the RUN-STATE gap. |
| Technical constraints | PASS | Offline. The ROM is unused. Generated data is not hand-edited. Sprites are converted on request, not committed. |
| Workflow gates | PASS | Spec Kit flow. The local suite must be green before done. `RUN-STATE.md` is updated when implementation starts. |

**Post-design re-check (after Phase 1)**: still PASS. The design adds one process boundary,
which is justified below. It adds no new runtime dependency and no network access.

## Project Structure

### Documentation (this feature)

```text
specs/002-webui-redesign/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R8
├── data-model.md
├── quickstart.md        # V1–V7
├── contracts/
│   ├── http-api.md
│   └── ui.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/platsim/web/
├── app.py               # JobStore/JobRunner: cancelled status, process-mode runner, stage_started,
│                        #   platsim_version; result view; cancel + sprite routes
├── job_process.py       # NEW: spawn child, setsid, parent-death guard, progress queue, killpg cancel (R1)
├── result_view.py       # NEW: result.json + result.csv → summary / per_trainer / team (incl. ability tie)
├── sprites.py           # NEW: allowlist, male→female fallback, tRNS injection, cache (R3)
├── eta.py               # NEW: stage-timing history + ETA (R2)
├── species_catalog.py   # + sprite_icon per item
└── static/
    ├── index.html       # two-column layout, budget select, seed term, run picker
    ├── app.js           # rewritten views: search gating, team icons, progress/ETA/cancel, chart, cards
    └── style.css        # grid layout, cards, tooltip, chart, sprite sizing

tests/
├── conftest.py                      # CHANGED: session `ledger`/`catalog` fixtures, fixture_runs_dir, sys.path for helpers
├── fixtures/web_final_defaults/     # NEW: frozen copy of runs/final-defaults + job.json (id job-20261008T000000Z-f1f1f1)
├── integration/_web_helpers.py      # NEW: StubRunner, copy_fixture_run, make_app
├── integration/test_web.py          # updated for new summary shape
├── integration/test_web_result_view.py  # NEW
├── integration/_fake_runners.py      # NEW: picklable fake runners (spawn)
├── integration/_serve_fake.py        # NEW: server launcher for the shutdown test
├── integration/test_web_shutdown.py  # NEW: no orphaned jobs after SIGINT/SIGKILL of the server
├── integration/test_web_process_determinism.py  # NEW: child process vs in-process, byte-identical
├── integration/test_web_sprites.py  # NEW
├── integration/test_web_cancel.py   # NEW (process mode, module-level fake runner)
├── integration/test_web_eta.py      # NEW
└── browser/test_page.py             # NEW, @pytest.mark.browser (Playwright + system Chrome)
```

**Structure Decision**: keep the single-package layout. The new server logic goes in small
modules next to `app.py`, so `app.py` stays the routing layer. The page stays three static files.

## Delivery order (each slice ships on its own)

1. **Result view and team cards** (US1, P1): `result_view.py`, the sprite endpoint, the summary,
   the chart and the cards. This is the biggest visible change, and it needs no job-runner
   changes.
2. **Two-column setup** (US2, P1): layout, search gating, team icons, the budget select and the
   seed tooltip.
3. **Progress, ETA and cancel** (US3, P2): `job_process.py`, `eta.py`, the cancel route and the
   progress view.
4. **Run picker** (US4, P2): the dropdown on `GET /api/jobs`, with failed and cancelled views.
5. **Browser walkthrough** (SC-006) and the V6 report-hash check.

## Risks (raised once, not blocking)

- **The version label is static.** `pyproject` has stayed at 0.1.0 throughout 001, so every run
  will show "platsim 0.1.0" until the version is bumped (R5).
- **Process mode adds ledger time.** Each web job adds about 35–75 s of ledger build at start
  (R1). That is small next to 25 min to 4.6 h jobs.
- **Any web edit changes `platsim_code_hash`.** This blocks resuming an unfinished
  `state.json` made before the change. None exists today (R8, observed).
- **The ETA is rough.** Confirm-stage time on the standard budget varied from 1.3 k to 11.4 k s
  across 3 runs (R2). The page labels the value "about".

- **A job could outlive the server.** Each job has its own session, so Ctrl-C no longer reaches it. This is mitigated by a shutdown hook plus a parent-death guard in the child (T026, T027), and tested by T023.

## Complexity Tracking

| Added complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Each web job runs in a spawned child process with its own process group | SC-004 (stop within 10 s) and FR-012 (stop the Node workers) | A cooperative cancel flag waits for `WorkerPool.close()` to drain every queued battle (minutes), and the optimizer swallows callback exceptions (`optimizer/run.py:172`). Fixing either means changing the optimizer or pool behaviour for a UI feature (R1). |
| A server-side PNG `tRNS` rewrite | The decomp sprites have an opaque background, index 0 (R3) | Committing converted images duplicates generated data (constitution). Pillow would add a runtime dependency for a 20-line chunk insert. |
