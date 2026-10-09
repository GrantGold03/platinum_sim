# Research: Web UI Redesign

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-09

Each item records what was checked in this repository on 2026-10-09, the decision, and what was
rejected. "Observed" means the check was run in this session. Anything else is labelled
unverified.

## R1. Cancelling a running job (FR-011, FR-012, SC-004)

**Observed**:
- The web runner calls `run_optimization` in a thread (`src/platsim/web/app.py:201-238`).
- The optimizer's progress wrapper catches every `Exception` raised by the callback and logs it
  (`src/platsim/optimizer/run.py:163-174`), so raising from `on_progress` does not stop a job.
- `WorkerPool.close()` queues one stop sentinel per worker *behind* the battles already queued,
  then joins them (`src/platsim/sim/pool.py`, `close`). A cooperative stop therefore waits for
  every queued battle. A single `pool.map` in level search or confirm submits hundreds to
  thousands of battles at once, which takes minutes.
- The battles run in long-lived `node sim/worker.mjs` child processes (`sim/pool.py:83`).

**Decision**: run each web job in its own child process, started with the `spawn` start method.
The child calls `os.setsid()` first, so it and its Node workers share one process group, then
calls `run_optimization` unchanged. Progress returns to the server through a
`multiprocessing` queue. Cancel sends `SIGTERM` to the process group, then `SIGKILL` after 5 s if
anything is still alive. A queued job is cancelled by marking it before it starts. `run_one`
already skips jobs that are not `queued`.

**Rationale**: this meets SC-004 (10 s) without changing the optimizer or the worker pool, so
battle behaviour and `sim_code_hash` stay the same. Killing the process group also removes the
Node workers, which a thread-based cancel cannot reach.

**Costs and risks**:
- `build_ledger()` is cached per process (`@cache`, `availability/ledger.py:192`). A spawned
  child builds it again, which adds about 35 s, or 56–76 s under load (measured in feature 001's T076), to the
  start of every job. Jobs take 25 min (quick) to 4.6 h (standard), going by the timings in
  `runs/*/state.json`.
- Python 3.14 on Linux defaults to `forkserver`. `fork` is unsafe with uvicorn's threads. The
  code asks for `spawn` explicitly.
- The runner must be a picklable module-level function. The `runner=` injection that tests use
  stays: tests can still run jobs in a thread (`isolate=False`). The process mode is covered by the cancel,
  shutdown and process-determinism tests (T021, T023, T024), with fake runners in
  `tests/integration/_fake_runners.py`.

**Rejected**:
- *Cooperative cancel flag checked at progress calls*: blocked by the pool draining queued
  battles (minutes, not 10 s) and by the swallowed exception. Fixing that needs changes to the
  optimizer and the pool.
- *A `WorkerPool.abort()` reached from the web thread*: the web layer has no reference to the
  pool, so this needs an API change in `optimizer/api.py`, and killed workers trigger the pool's
  restart logic.
- *Shell out to `platsim optimize`*: the command line reports no structured progress.

## R2. ETA (FR-010)

**Observed**:
- `Progress` has `stage`, `runs_done` and `runs_planned`. `runs_planned` is set only for
  `ability_screen` (6) and `confirm` (the preset's `confirm_min`). The screen stage reports it
  per round. Level search is open-ended, with no total.
- Each `state.json` records how long each finished stage took (`timing`). From five runs on
  disk:

  | run | budget | screen | level_search | confirm | total |
  |---|---|---|---|---|---|
  | final-defaults | standard | 390 s | 4821 s | 11435 s | 16728 s |
  | optimize-36cef906f4d5 | standard | 378 s | 5452 s | 3829 s | 9742 s |
  | job-…2d8f18 | standard | 259 s | 3256 s | 1344 s | 4880 s |
  | job-…feb186 | quick | 135 s | 759 s | 617 s | 1534 s |
  | optimize-smoke-quick | quick | 141 s | 889 s | — | 1739 s |

**Decision**: the server computes `eta_s` as follows.
- **Current stage**: when `runs_planned` and `runs_done > 0` are known, the remaining time is
  `(planned − done) × in-stage elapsed / done`. Otherwise it is
  `max(median stage time − in-stage elapsed, 0)`.
- **Later stages**: add the median time of each stage still to come, in the order calibrate →
  ability_screen → screen → level_search → confirm. The medians come from every
  `runs/*/state.json` that used the same budget, read once at startup and refreshed when a job
  finishes.
- **No history** for that budget gives `eta_s: null`, and the page shows "estimating…".
- The page shows the value as "about N min left", or "estimating…".

Recording when each stage started requires the server to save a `stage_started` time whenever
the stage changes.

**Rationale**: no change to the optimizer, and it uses data that is already on disk. Confirm
times vary from about 1.3 k to 11.4 k s on the standard budget, so the ETA is rough. The spec
already requires it to be labelled as an estimate, and the edge cases cover it.

**Rejected**: a percentage bar with no history, which would be misleading during level search.
Adding a `total_planned` to the optimizer, which is not possible because level search length
depends on results.

## R3. Sprites (FR-004, FR-023, FR-029)

**Observed**:
- `pokeplatinum/res/pokemon/<species>/` has 501 folders.
- `male_front.png` is 160×80, palette-indexed, with two 80×80 frames.
- `icon.png` is 32×64, palette-indexed, with two 32×32 frames.
- The embedded palettes match `normal.pal`.
- Index 0 is a solid background colour (for example 189,230,180), not transparent. There is no
  `tRNS` chunk.
- Some species have only `female_front.png`: Blissey, Chansey, Cresselia, Froslass, Happiny,
  Illumise, Jynx, Kangaskhan, …
- **Positive control (observed)**: adding a one-entry `tRNS` chunk (index 0 → alpha 0) using the
  standard library (`struct` + `zlib.crc32`) gave correct transparent sprites for Infernape,
  Luxray, Gardevoir and Blissey (female fallback), both front and icon. The preview was rendered
  in the session scratchpad and viewed.

**Decision**:
- **Endpoint**: `GET /api/sprites/{species}/{front|icon}.png`. It serves the decomp file with
  the `tRNS` chunk added. It falls back from `male_front` to `female_front`, and returns 404 for
  unknown species. The page shows a placeholder on 404 (spec edge case).
- **Frames**: the page shows only the first frame using CSS (a fixed box with
  `object-position: 0 0`, `overflow: hidden`).
- **Scaling**: `image-rendering: pixelated`. Icons are used in team slots and front sprites on
  the result cards.
- **Validation**: the species key is validated against the decomp folder names, so paths cannot
  escape that folder.
- **Caching**: responses are cached in memory per species.

**Rationale**: works offline, uses data already in the repo, adds no new dependency, and Pillow
is not needed at runtime. The `.nds` ROM is not used (Constitution, Technical Constraints).

**Rejected**: downloading from Showdown or PokeAPI, which breaks offline use. Committing
converted copies, which duplicates generated data that the constitution says must be
reproducible and not hand-edited. Converting with Pillow, which would add a runtime dependency
for one chunk insert.

## R4. Ability tie display (FR-025)

**Observed**:
- `team.builds[].ability_reason` in `result.json` is one of `single_ability`,
  `no_battle_effect`, `tested_better` or `tie_default` (`optimizer/abilities.py:224,359-363`).
- In `runs/final-defaults`, Luxray and Gardevoir are `tie_default`.
- `result.json` does not record the other ability. `state.json` does
  (`stages.ability_screen.*.stats.abilities`), but `state.json` is checkpoint state, not report
  data.
- The decomp lists both of a species' abilities in `res/pokemon/<species>/data.json`
  (`"abilities": [A, B]`, with `ABILITY_NONE` meaning there is no second ability).

**Decision**: for a `tie_default` build, the server reads the species' two abilities from the
decomp (through the existing decomp reader), orders them chosen-first, and returns
`ability_display = "Rivalry/Intimidate (no significant difference)"`. Any other reason shows the
chosen ability alone. If the second ability cannot be found, the chosen ability is shown followed
by "(no significant difference)" (spec edge case).

**Rationale**: the decomp is ground truth (Principle I) and is always present. The reports stay
unchanged (FR-030).

## R5. "platsim version" (FR-021)

**Observed**:
- `pyproject.toml` has `version = "0.1.0"`, and it has not been bumped across all of 001.
- No report and no `job.json` records a platsim version. Reports identify code by
  `platsim_code_hash`, `sim_code_hash` and `repo_commit`.

**Decision**:
- **New jobs**: when a web job starts running (not when it is created, so a job queued across
  an upgrade gets the version it actually ran with), the server stores
  `importlib.metadata.version("platsim")` in `job.json` as `platsim_version`. `job.json` is web
  bookkeeping, not one of the four downloadable reports, so FR-030 still holds.
- **Older jobs**: jobs without the field show "platsim version not recorded". The server never
  shows its own current version against an old run, because that would be false provenance
  (Principle IV).

**Risk (raised in plan)**: while the version stays at 0.1.0, every run shows the same label,
even across code that changes results. The hashes stay in the JSON report. Bumping the version
when behaviour changes is outside this feature.

## R6. Browser verification (SC-006)

**Observed**: there is no browser automation in the repository, and Playwright is not installed.
`/usr/bin/google-chrome` and `/usr/bin/firefox` exist. The 8 existing web tests
(`tests/integration/test_web.py`) pass: `8 passed in 35.98s`. The page's JavaScript has never
run under test (README, feature 001's T076 note).

**Decision**: add `playwright` (Python) to the **dev** dependency group, and drive the system
Chrome with `channel="chrome"`, so no browser download is needed. The tests are marked
`@pytest.mark.browser` and skipped with a reason if Chrome is missing. They run against
`create_app` with a fake runner and a pre-built fixture run, and cover the user-story scenarios.
Installing the package is a one-time PyPI download, done once at dev time. Runtime stays
offline.

**Rejected**: headless-Chrome screenshots only, which cannot check hover or keyboard focus or
interaction. Leaving browser checks manual, which is the gap SC-006 is meant to close.

## R7. Per-trainer chart (FR-027)

**Decision**: a horizontal bar chart drawn as inline SVG by `app.js`, with no library.
- **Data**: one bar per trainer, in battle order from `per_battle`.
- **Interval**: a whisker for the 95% interval.
- **Axis**: x from 0 to 100%, with a dashed line marking the run's threshold.
- **Values**: each bar's value is drawn as text next to it.
- **Details on hover or focus**: the interval and battle count, through `<title>`, plus a
  focusable `<g tabindex=0>` with an `aria-label`.
- **Colours**: CSS variables, so light and dark themes both work.
- **Accessible table**: a visually hidden `<table>` repeats the numbers for screen readers.
- **Older runs**: a run with no `per_battle` shows "per-trainer data not available for this
  run".

**Rationale**: five bars do not justify a dependency. The page has no build step and no CDN
(offline).

## R8. Code-hash side effect (trap)

**Observed**: `platsim_code_hash` covers every `src/platsim/**/*.py` and is a behaviour key for
resume (`version.BEHAVIOUR_KEYS`). **Any edit to `src/platsim/web/*.py` changes it.**

**Consequence**: once this feature lands, a half-finished optimize directory with a `state.json`
from before the change refuses to resume until it is rerun with `--force-new`. No such directory
is in progress today. All five `runs/*/state.json` files have a `report` stage (observed
2026-10-09). The other 11 entries under `runs/` have no `state.json`, so there is nothing for
them to resume. This is expected behaviour, not a bug. It is noted so
nobody chases it later. Finished results are not affected.
