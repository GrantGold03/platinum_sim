---
description: "Task list for 002 Web UI Redesign"
---

# Tasks: Web UI Redesign

**Input**: Design documents from `specs/002-webui-redesign/`. These are plan.md, spec.md,
research.md (R1–R8), data-model.md, contracts/http-api.md, contracts/ui.md, and quickstart.md
(V1–V7).

**Tests**: included. The constitution requires a local suite that runs green and positive
controls (Principle V). Spec SC-006 requires every FR to be covered by an automated check or a
browser walkthrough.

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task can run in parallel, because it
touches different files and has no unfinished dependency.

## Ground rules for every task

- **Scope**:
  - Do not edit `sim/`, `src/platsim/optimizer/`, `src/platsim/sim/` or `src/platsim/report/`.
    The plan keeps battle code and report output unchanged (FR-030).
  - Read-only reuse is fine:
    - `platsim.decomp.species.load_species()`: `Species.abilities`, where `[1]` is `None` for
      ABILITY_NONE.
    - `platsim.legality.validator.showdown_name`, the display-name function the optimizer passes
      to the report writers (`optimizer/run.py:672`; the type is `NameFn`, `report/csv_report.py:20`).
      Use it for ability names so they match the CSV.
- **Existing tests**: these live in `tests/integration/test_web.py`. Reuse its `catalog` fixture,
  `StubRunner` and `_wait`.
- **Baseline**: the existing tests passed at `8 passed in 35.98s` on 2026-10-09.
- **Recording results**: record the real test output for each checkpoint in
  `specs/002-webui-redesign/validation-log.md`.
- **Temp files** go in the session scratchpad, never in `/tmp` or the repo.

## Path conventions

- Server: `src/platsim/web/`. Page: `src/platsim/web/static/`.
- Tests: `tests/integration/` and `tests/browser/`.

---

## Phase 1: Setup

- [X] T001 Add `"playwright"` to `[dependency-groups].dev` in `pyproject.toml`. Register the pytest marker `browser: real-browser tests (system Chrome)` under `[tool.pytest.ini_options]` `markers`. Run `uv sync --group dev` and record the output. Do **not** run `playwright install`, because the tests use the system Chrome through `channel="chrome"` (research R6).
- [X] T002 [P] Update `RUN-STATE.md` before any code changes (analysis I3; your CLAUDE.md says to update it as work lands). Add a 002 section with:
  - **Goal**: the spec summary;
  - **Method**: plan.md Summary;
  - **Next**: Phase 2, then US1;
  - **Traps**: R8 (`platsim_code_hash`) and R1 (an orphaned job after server stop).

  Then record the baseline in a new `specs/002-webui-redesign/validation-log.md`:
  - the output of `uv run pytest -q tests/integration/test_web.py`;
  - the output of `sha256sum runs/final-defaults/result.json runs/final-defaults/result.csv runs/final-defaults/result.xlsx runs/final-defaults/team.txt` (quickstart V6, "before").
- [X] T003 [P] Create the fixture `tests/fixtures/web_final_defaults/`:
  - Copy `result.json`, `result.csv`, `result.xlsx` and `team.txt` from `runs/final-defaults/`, byte for byte.
  - Add a `README.md` saying these are a frozen copy of a real run, used to test the result view and the browser tests.
  - Add a `job.json` for a `done` job with id `job-20261008T000000Z-f1f1f1`. The id must match `ID_RE` (`app.py:59`, `^job-\d{8}T\d{6}Z-[0-9a-f]{6}$`), or the server skips the job and returns 404. Copy the field shapes from any existing `runs/job-*/job.json`, set `options.budget` to `"standard"`, and leave out `platsim_version`.

---

## Phase 2: Foundational (blocks all stories)

- [X] T004 Split the shared web test helpers into two files (analysis U2). Everything else in the 002 test tasks refers to these two names.
  - **`tests/integration/_web_helpers.py`**, an importable plain module: move `StubRunner`, `_synthetic_report`, `_available_team` and `_wait` here from `tests/integration/test_web.py`, and import them back into `test_web.py`. Add:
    - `copy_fixture_run(dest_dir) -> str`: copies `tests/fixtures/web_final_defaults/` to `dest_dir/<fixture id>/`, rewrites the `result_paths` in its `job.json` to point there, and returns the job id;
    - `make_app(runs_dir, catalog, runner=None, **kw)` around `webapp.create_app(...)`.
  - **`tests/conftest.py`**, the existing root conftest: add the fixtures here, so both `tests/integration/` and `tests/browser/` can use them (analysis N4). Move `ledger` and `catalog` here from `test_web.py`, with scope `session`, so the roughly 35 s catalog build happens once per test session rather than once per module. Add `fixture_runs_dir(tmp_path)`, which calls `copy_fixture_run(tmp_path)`. Also add `tests/integration` to `sys.path` at the top of this conftest, so `_web_helpers` and `_fake_runners` import the same way from any test folder, and from a `spawn` child, which inherits the parent's `sys.path`.
  - **Do not** name a file `conftest_web.py`, because pytest only loads files named `conftest.py`. Do not import from `conftest` by module name.
- [X] T005 In `src/platsim/web/app.py`, extend the `JobStore` and `JobRunner` state model (data-model "Job"):
  - Allow the status `cancelled`.
  - In `run_one`, when the status becomes `running`, store `platsim_version = importlib.metadata.version("platsim")`. Fall back to `None` on `PackageNotFoundError`. Do not store it at creation: a job queued before a restart would otherwise show the version from before an upgrade (Constitution IV 1.1.0, analysis N5).
  - In `run_one`'s `on_progress`, set `progress.stage_started` to `_now()` whenever the stage differs from the stored one. Also set it when the status becomes `running`. `on_progress` replaces the whole `progress` dict (`app.py:216-220`), so when the stage is **unchanged**, copy the stored `stage_started` into the new dict. Otherwise every same-stage update erases it and breaks the ETA (analysis P3-01).
  - When a job finishes `done`, store `verdict` in `job.json`: read `qualified` and `borderline` from its `result.json`, and write `qualified`, `borderline` or `not_qualified`. `job.json` alone cannot tell borderline from not qualified (analysis P3-02).
  - In `JobStore.load_existing`, treat `cancelled` as terminal: it is not resubmitted and not marked failed.

  Do not change any existing behaviour beyond these.

**Checkpoint**: `uv run pytest -q tests/integration/test_web.py` is still 8 passed. Record the output, and update RUN-STATE.md (Done/Next).

---

## Phase 3: User Story 1 – Read a result at a glance (P1) 🎯 MVP

**Goal**: the right panel shows the newest finished run as a short summary, a per-trainer chart,
and six sprite cards with move-source tooltips.

**Independent test**: serve the fixture runs dir with no new job. The panel matches
`runs/final-defaults/result.json` (spec US1, quickstart V2, V3).

### Tests for User Story 1

- [X] T006 [P] [US1] Write `tests/integration/test_web_sprites.py` against `GET /api/sprites/{species}/{kind}.png` (contracts/http-api.md):
  - `infernape/front.png` → 200 `image/png`. This is the positive control: parse the PNG chunks and assert that a `tRNS` chunk comes right after `PLTE` and its first byte is `0x00`.
  - `blissey/front.png` → 200. It has no `male_front.png`, so this proves the `female_front.png` fallback.
  - `infernape/icon.png` → 200.
  - `notamon/front.png`, `infernape/back.png` and `..%2Fetc/front.png` → 404.
  - A second request for the same sprite returns identical bytes.
- [X] T007 [P] [US1] Write `tests/integration/test_web_result_view.py` using the T003 fixture via T004. Check `GET /api/jobs/<fixture id>`:
  - `summary` keys are exactly `verdict, clear_rate, clear_ci95, n_runs, avg_final_level, level_gap, threshold, budget, legality_options, warnings, no_qualifying, platsim_version`.
  - `verdict == "qualified"`.
  - `platsim_version is None`, because the fixture has none.
  - `per_trainer` is 5 items in order aaron, bertha, flint, lucian, cynthia, and Cynthia's `rate` is ≈ 0.8688 with `battles == 1990`.
  - The `team` has 6 items.
  - Slot 3 (Luxray) has `ability == "Rivalry/Intimidate (no significant difference)"`.
  - Slot 6 (Gardevoir) has `ability` ending in `"(no significant difference)"`.
  - Slot 1 has `ability == "Blaze"`.
  - Every move has a non-empty `name` and `source`.
  - No team item has any of the keys `nature`, `ivs`, `evs`, `ability_choice`, `held_item_source`.
  - The response has no `table` key.
  - `downloads` still has all 4 links, and each download is byte-identical to the fixture file (V6).

### Implementation for User Story 1

- [X] T008 [P] [US1] Create `src/platsim/web/sprites.py` (research R3):
  - **Allowlist**: build the allowed species keys from the folder names under `pokeplatinum/res/pokemon/`, using the repo-root constant in `platsim.pins`. Exclude `egg` and `bad_egg`.
  - **`sprite_png(species, kind) -> bytes | None`**:
    - `front` reads `male_front.png`, falling back to `female_front.png`. `icon` reads `icon.png`.
    - Insert a `tRNS` chunk containing the single byte `0x00` right after `PLTE`, with its length and CRC computed by `zlib.crc32`. Use the standard library only.
    - Cache results in a dict keyed by `(species, kind)`.
  - Return `None` for anything not in the allowlist or any missing file.
- [X] T009 [P] [US1] Create `src/platsim/web/result_view.py` with `build_result_view(job: dict) -> dict`, which returns `{summary, per_trainer, team}` per data-model "ResultView":
  - **Sources**: read `result_paths["json"]` and `result_paths["csv"]`. Join CSV rows to `result.json` `team.builds` by slot order.
  - **verdict**: `qualified` if `qualified`; else `borderline` if `borderline`; else `not_qualified`.
  - **summary**:
    - `clear_rate`, `clear_ci95` and `n_runs`, copied from `result.json`;
    - `avg_final_level = expected_avg_final_level`;
    - `level_gap = final_level_gap_max`;
    - `budget = budget_preset`;
    - `legality_options = provenance.legality_options`;
    - `platsim_version = job.get("platsim_version")`;
    - `threshold`, `warnings` and `no_qualifying`, copied from `result.json` (analysis P4-12).
  - **per_trainer**: built from `per_battle`, ordered aaron, bertha, flint, lucian, cynthia, with any other keys after, in file order. `label` is the trainer name capitalised. A missing `per_battle` gives `[]`.
  - **team[i]**:
    - `species_key = builds[i].species`;
    - `sprite = f"/api/sprites/{species_key}/front.png"`;
    - the CSV's display values for species, start and final level, held item and obtained-from;
    - `moves = [{name: CSV "Move n", source: CSV "Move n source"}]`.
  - **ability**:
    - if `ability_reason == "tie_default"`, look up the build species' decomp `abilities` (`load_species()`, matching on the species key or constant). Order them chosen-first, render each through the report's display-name function, and join them as `"A/B (no significant difference)"`;
    - if the other ability is missing, return `"A (no significant difference)"`;
    - otherwise return the CSV `Ability` value.
  - **Errors**: unreadable files make the function return `None`. It must not raise.
- [X] T010 [US1] In `src/platsim/web/app.py`:
  - Add the route `GET /api/sprites/{species}/{kind}.png`, which calls `sprites.sprite_png` and responds `image/png` with `Cache-Control: max-age=86400`. A miss gives 404 `{"detail": ...}`.
  - In `get_job`, replace the `summary`/`table` assembly with `view.update(build_result_view(job) or {})`.
  - Delete `SUMMARY_KEYS`, `_read_summary` and `_read_table`, once nothing references them.
  - Update the existing assertions in `tests/integration/test_web.py` that read the old `summary`/`table` shape to the new shape. Do not delete tests.

  Depends on T008 and T009.
- [X] T011 [P] [US1] In `src/platsim/web/static/index.html`, rebuild the markup as two columns (contracts/ui.md layout):
  - `<main class="layout">` with `<section id="setup">` (left) and `<section id="results-col">` (right). Do not use `id="results"`: the existing species list already uses it (`index.html:42`, `app.js:11`; analysis N3).
  - Move all existing setup controls into `#setup`, keeping their ids so the US2 tasks can extend them.
  - `#results-col` contains:
    - `#progress` (hidden);
    - `#run-picker` (a labelled `<select>`, filled by US4; until then it holds the single newest run);
    - `#summary`;
    - `#chart` (`<figure>` with a `<figcaption>` "Clear rate by trainer");
    - `#team-cards`;
    - `#downloads`.
  - Keep every `aria-live` region and label.
- [X] T012 [P] [US1] In `src/platsim/web/static/style.css`, add the layout, cards and chart styles.
  - **Layout**: a grid of `minmax(320px, 2fr) 3fr`. The left column is sticky (`position: sticky; top: 0; max-height: 100vh; overflow: auto`). Below 900px it becomes a single column, with no horizontal scroll at 360px.
  - **Sprites**:
    - `.sprite-front`: an 80×80 box, `overflow: hidden`; the `img` has `width: 160px; height: 80px; object-fit: none; object-position: 0 0; image-rendering: pixelated`.
    - `.sprite-icon`: the same idea for a 32×32 box from the 32×64 icon.
    - `.sprite-placeholder`: the same size, a neutral border.
  - **Team cards**: a grid that is 3-up on wide screens, 2-up on medium and 1-up on narrow. Each card shows the sprite, name, "Lv 58 → 58.8", ability, item, an obtained-from line (truncated with the full text in `title`), and 4 move chips.
  - **Tooltips**: one `.tip` style, shown on `:hover` and `:focus-visible`, used for move sources and later the seed. Use only the existing CSS variables, so light and dark both work.
- [X] T013 [US1] In `src/platsim/web/static/app.js`, rewrite the result rendering (contracts/ui.md).
  - **Summary**:
    - a verdict badge;
    - the clear rate as `NN.N%`, with no interval or run count inline. The clear rate is a `<span tabindex="0" aria-describedby="clear-tip">`. Its `.tip` reads `95% interval ${lo}–${hi}% · ${n_runs.toLocaleString()} runs` and shows on hover or focus only (FR-017, analysis C1);
    - one line: `${avg.toFixed(2)} (level gap of ${gap})`, where the gap has no decimals if it is a whole number, otherwise one;
    - threshold, budget, legality options and warnings;
    - `platsim ${v}`, or "platsim version not recorded".
  - **Team cards**: built from `team`. Give each visible field element the class `field` (sprite, species, levels, ability, held item, obtained from, moves, slot), so SC-002 can be counted. Each `img` gets an `onerror` that swaps in `.sprite-placeholder`. Each move is a `<span class="move" tabindex="0" aria-describedby=…>` with its source in a `.tip` element.
  - **Chart**: drawn by `renderChart(per_trainer, threshold)`, as inline SVG with no library.
    - One horizontal bar per trainer, with x from 0 to 100% and the rate drawn as text.
    - A CI whisker from `ci95`, and a dashed threshold line.
    - Each bar is a `<g tabindex="0" role="img" aria-label="Cynthia 86.9%, 95% interval 85.3–88.3%, 1,990 battles">` with a `<title>` of the same text. Format every count with `toLocaleString()`, so it matches the clear-rate tooltip ("2,000 runs") (analysis P3-12).
    - **Visible tooltip** (analysis N9): on hover and on `:focus-visible`, show the same text as a visible `.tip` next to the bar, so sighted keyboard users see it too (FR-027).
    - A visually hidden `<table>` repeats the numbers.
    - An empty `per_trainer` shows "Per-trainer data is not available for this run".
  - **Downloads**: unchanged links.
  - **Removed**: delete the old summary `<dl>` builder, the 20-column table renderer and the `best_so_far` dump.
- [X] T014 [US1] On page load in `src/platsim/web/static/app.js`, call `GET /api/jobs`, pick the newest job with `status == "done"`, fetch it, and render it. With none, show "No runs have finished yet." This is a minimal version of FR-014; US4 adds the dropdown. Depends on T013.

**Checkpoint (US1)**: T006 and T007 pass, and RUN-STATE.md is updated (Done/Next). Then:
1. Run `uv run platsim serve --runs-dir <scratchpad copy of the fixture dir>`.
2. Take a headless screenshot: `google-chrome --headless --screenshot=<scratchpad>/us1.png --window-size=1920,1080 http://127.0.0.1:<port>/`.
3. View the screenshot and record what you see in validation-log.

---

## Phase 4: User Story 2 – Set up a run on the left (P1)

**Goal**: the left column has search gating, team icons, a budget choice and the seed tooltip.

**Independent test**: with no runs, build six species, choose "thorough" and start. The POST body
carries `budget: "thorough"` (spec US2).

### Tests for User Story 2

- [X] T015 [US2] Add these tests to `tests/integration/test_web.py`:
  - `GET /api/species?q=garch` items include `sprite_icon == "/api/sprites/garchomp/icon.png"`.
  - A `POST /api/jobs` with `budget: "thorough"` stores `options.budget == "thorough"` in `job.json`.
  - A `POST` without `budget` stores `"standard"`.

### Implementation for User Story 2

- [X] T016 [P] [US2] In `src/platsim/web/species_catalog.py`, have `SpeciesInfo.to_json` add `"sprite_icon": f"/api/sprites/{self.key}/icon.png"`.
- [X] T017 [US2] In `src/platsim/web/static/index.html`, add these to `#setup`:
  - **Budget**: `<label for="budget">Budget</label><select id="budget">` with options quick, standard (selected) and thorough. Each option's text gives its run count from `src/platsim/budget.py` `PRESETS`, e.g. "standard: confirm at least 2,000 runs". Read the real field names from `BudgetPreset`.
  - **Seed**: the label becomes `<span class="term" tabindex="0" aria-describedby="seed-tip">Seed</span>` plus a `<span id="seed-tip" role="tooltip" class="tip">`. Its text: "The seed fixes the random battles. The same team, options and seed always give the same result. A different seed gives an independent sample."

  The species results container must start with `hidden`.
- [X] T018 [US2] In `src/platsim/web/static/app.js`:
  - **Search gating**: when the trimmed search value is empty, hide the result list and send no request. On the first character, show it and search; clearing hides it again. Keep the 150 ms debounce, the 503 retry text, the excluded toggle, and the trade-evolution re-search.
  - **Team slots**: render `<span class="sprite-icon"><img src=sprite_icon alt=""></span>` before the name, with the same placeholder `onerror` as T013.
  - **Submit**: include `budget: $('#budget').value` in the POST body.
- [X] T019 [US2] In `src/platsim/web/static/style.css`, add `.term`, an underlined term with a help cursor. The seed `.tip` shows only on `.term:hover + .tip`, `.term:focus-visible + .tip`, or with an equivalent wrapper. It is hidden otherwise (FR-006).

**Checkpoint (US2)**: T015 passes, and RUN-STATE.md is updated. Take a headless screenshot at 1920×1080 and at 360×800, view both, and record them.

---

## Phase 5: User Story 3 – Follow and cancel a running job (P2)

**Goal**: progress appears only while a job is queued or running, with elapsed time, an ETA and
Cancel. Cancel stops the job and its Node workers within 10 s.

**Independent test**: quickstart V4 (fake runner in a child process), then V7 (one real quick
job).

### Tests for User Story 3

- [X] T020 [P] [US3] Write `tests/integration/test_web_eta.py` against `src/platsim/web/eta.py`, using synthetic `state.json` files in `tmp_path`:
  - The medians per budget and stage are correct.
  - The current stage with `runs_planned=100, runs_done=25` and 60 s in the stage gives about 180 s for that stage, plus the medians of the later stages.
  - With no history for the budget, `eta_s is None`.
  - A `state.json` without `timing` is ignored.
  - **Positive control**: loading `runs/` from the real repo returns at least one `standard` median for `confirm`.
- [X] T021 [P] [US3] Write `tests/integration/test_web_cancel.py`. Put every fake runner in a new importable module, `tests/integration/_fake_runners.py`, never inside a test module, so a `spawn` child can unpickle it by name. T023, T024 and T032 reuse it.
  - **`sleepy_runner(req, progress)`**: starts `subprocess.Popen(["sleep", "300"])` (a stand-in for Node workers), writes its pid to `req.out_dir/"child.pid"`, then calls `progress(Progress("screen", i, 1000, best_so_far={"clear_rate": 0.5, "levels": [50] * 6}))` every 0.2 s for up to 120 s. The `best_so_far` gives FR-013's absence check a positive control (analysis P4-01).
  - **Positive control**: the job reaches `running`, `child.pid` exists, and that pid is alive (`os.kill(pid, 0)`).
  - **Cancel a running job**: `POST /api/jobs/{id}/cancel` → 202. Within 10 s the status is `cancelled`, and the `sleep` pid is gone (`ProcessLookupError`, or a zombie reaped). Use `time.monotonic` to assert at most 10 s.
  - **Next job starts**: a second job queued behind it then reaches `running`.
  - **Cancel a queued job**: → 200 and `cancelled`, and it never reaches `running`.
  - **Cancel a finished job**: a done job → 409. An unknown id → 404.
  - **Race**: add `instant_runner` to `_fake_runners.py`. It writes the report files with `write_all(_synthetic_report(req.species), req.out_dir)` and returns at once. Post cancel immediately after it starts → the final status is exactly one of `done` or `cancelled`, and `done` has result files.
  - Build the app with `create_app(runner=..., isolate=True, catalog=<the session catalog fixture>, runs_dir=tmp_path)`. POST `/api/jobs` needs a catalog to resolve the species (analysis P4-15). Never leave out `runs_dir`: the default is the repo's real `runs/` (`app.py:48`; analysis P5-04). **Teardown**: a fixture cancels every job still queued or running and stops the JobRunner, so no `sleep 300` or job child outlives the test.
- [X] T022 [US3] Add `HOLD = threading.Event()` and `two_beat_runner` (described below) to `tests/integration/_fake_runners.py`. This task creates them, and T030 reuses them (analysis P5-01). Then add a test to `tests/integration/test_web.py` (thread mode, `StubRunner(block=True)`): while the job is running, `GET /api/jobs/{id}` includes an `eta_s` key and `progress.stage_started`. Wait at least 1.1 s after `running` before asserting `elapsed_s > 0`, because stored times have 1 s resolution (analysis P3-15). The view also has `platsim_version == importlib.metadata.version("platsim")`, recorded at run start (FR-021, analysis N5 and P3-03). Check `stage_started` with `_fake_runners.two_beat_runner` (analysis P4-03). It sends `Progress("screen", 1, 10)`, sleeps 1.1 s, sends `Progress("screen", 2, 10)`, then blocks on `HOLD` (call `HOLD.clear()` first). Between the two updates `stage_started` must stay the same, while `progress.runs_done` changes from 1 to 2. A bug that resets the time on every update would show a later second, because 1.1 s is more than the 1 s time resolution (P3-01). After release and done, `elapsed_s` is fixed, finished minus started, and `job.json` has `verdict == "qualified"` (P3-02).
- [X] T023 [US3] Write `tests/integration/test_web_shutdown.py`, which checks that no job outlives the server (analysis U1). It depends on T021, because it reuses `_fake_runners.py`.
  - **Launcher**: add a script, `tests/integration/_serve_fake.py`. It puts its own folder on `sys.path` and builds `create_app(runner=_fake_runners.sleepy_runner, isolate=True, runs_dir=argv, catalog=<a SpeciesCatalog of 6 hand-built SpeciesInfo entries, so there is no 35 s ledger build>)`. Then it runs uvicorn on the port given in argv. The uvicorn start MUST be inside `if __name__ == "__main__":`, because a `spawn` child re-imports the launcher as `__mp_main__`, and without the guard every job child would start a second server (analysis N7).
  - **Start**: the test starts it with `subprocess.Popen([sys.executable, <path to _serve_fake.py>, port, runs_dir])` and posts one job.
  - **Positive control**: the job reaches `running`, and both the job child pid and the `sleep` pid from `child.pid` are alive.
  - **Case A**: send `SIGINT` to the server. Within 10 s, both pids are gone. Then `runs_dir/<id>/job.json` has `status == "failed"` and `error == "server stopped while running"`, not `cancelled` (analysis P4-04).
  - **Case B**: in a fresh server, send `SIGKILL` to the server. Within 10 s, both pids are gone. This case proves the parent-death guard from T026, because no shutdown hook can run.
  - **Cleanup**: on failure, killpg any pids that are left over, so the test never leaks processes.
- [X] T024 [US3] Write `tests/integration/test_web_process_determinism.py`, which checks that the process boundary does not change results (analysis V1, Constitution IV). It depends on T021, because it edits `_fake_runners.py`.
  - **Runner**: add `evaluate_runner(req, progress)` to `tests/integration/_fake_runners.py`. It calls `platsim.cli.main(["evaluate", <repo>/tests/fixtures/reference_team.json, "--runs", "40", "--seed", "web-proc", "--budget", "quick", "--workers", "4", "--out", str(req.out_dir)])`, asserts the return value is 0, and returns `OptimizeResult(req.out_dir, False)`.
  - **Comparison**: run it once through `job_process.run_in_process` (a child process) and once by calling it directly in the test process. Use separate `out_dir`s.
  - **Assertion**: the two `result.json` files are byte-identical.
  - **Positive control**: `n_runs == 40`, and `per_battle` is not empty.
  - **Time**: about 1–2 min. Record the time.

### Implementation for User Story 3

- [X] T025 [P] [US3] Create `src/platsim/web/eta.py` (research R2):
  - **`StageHistory.load(runs_dir)`**: reads every `*/state.json` and collects `timing[stage]` lists per `fingerprint.budget`, skipping `total_s_this_session`. It keeps medians, and `refresh()` reloads them.
  - **`STAGE_ORDER`**: `("calibrate", "ability_screen", "screen", "level_search", "confirm")`.
  - **`eta_seconds(history, budget, stage, runs_done, runs_planned, in_stage_s) -> float | None`**:
    - **Current stage**: `(planned - done) * in_stage_s / done` when both are known and `done > 0`. Otherwise `max(median(stage) - in_stage_s, 0)`.
    - **Later stages**: add the median of every stage after the current one in `STAGE_ORDER`.
    - **Missing data**: return `None` if a needed median is missing.
    - **Stages not in the order** (analysis P4-09, checked against `optimizer/run.py`): the optimizer sends `resolve`, then `prune` (pass A), then `calibrate`, then `prune` again (pass B, `run.py:344`), then `ability_screen`, `screen`, `level_search` (with `setup_check` interleaved), `confirm` and `done`.
      - `resolve`, and a `prune` before any `calibrate`: every stage from `calibrate` on is still to come.
      - A `prune` after `calibrate`: every stage from `ability_screen` on is still to come. To tell the two apart, keep `progress.seen_stages`, a list carried forward like `stage_started`.
      - `setup_check`: count it as `level_search`.
      - `champion_topup` and `report` are never sent as progress stages, so they need no rule.
      - The server's own stages: `starting` counts as `resolve`. `queued`, `done`, `failed` and `cancelled` return `None`. Any unknown stage also returns `None`, never an exception (analysis P5-05).
- [X] T026 [P] [US3] Create `src/platsim/web/job_process.py` (research R1):
  - **Process start**: `run_in_process(runner, req, on_progress, cancel_event) -> OptimizeResult` uses `multiprocessing.get_context("spawn")`. The child target calls `os.setsid()`, then runs `runner(req, progress=lambda p: q.put(("progress", p)))`, then puts `("result", result)`, or `("error", repr, traceback text, is_invalid_request, reasons)`.
  - **Parent loop**: the parent thread drains the queue with a 0.2 s timeout and forwards progress.
  - **Cancel**: when `cancel_event` is set, `os.killpg(child.pid, SIGTERM)`, wait up to 5 s, then `SIGKILL` the group, `join`, and raise `JobCancelled`.
  - **Abnormal exit**: a child that exits without a result raises `RuntimeError("worker process exited with code N")`.
  - **Parent-death guard** (analysis U1): this is the first thing the child does after `os.setsid()`.
    - Call `prctl(PR_SET_PDEATHSIG, SIGTERM)` through `ctypes`, on Linux only, skipping if it is unavailable.
    - Install a `SIGTERM` handler that runs `os.killpg(os.getpgrp(), SIGKILL)`. This takes down the Node workers too, and cancel's SIGTERM goes through the same path.
    - Start a daemon thread that polls `os.getppid()` every 1 s and does the same killpg if the parent pid changes.
    - **Thread caveat**: PDEATHSIG fires when the *thread* that started the child exits. The child must be started from the long-lived JobRunner thread, never from a short-lived one.
  - **Types**: `JobCancelled` must subclass `BaseException`, not `Exception`. Re-raise `InvalidRequest` in the parent with its reasons, so the existing failed-job handling still works.
- [X] T027 [US3] In `src/platsim/web/app.py`, wire cancel and the process mode. Depends on T005, T025 and T026.
  - **`create_app(..., isolate: bool | None = None)`**: `None` means `isolate = (runner is run_optimization)`, so the real optimizer always runs in a child and test stubs stay in a thread unless asked.
  - **`JobRunner`**: keeps a `cancel_events[jid]`.
  - **`run_one` start** (analysis P4-05):
    - Create `cancel_events[jid]` before anything else.
    - Then, under `store.lock`, re-read the job. If it is no longer `queued`, for example because a cancel landed, return without running. Otherwise set `running` while still holding the lock.
    - Today's code reads, then writes `running` without the lock (`app.py:203-212`), so a cancel between the two is lost.
  - **`run_one` end**: uses `job_process.run_in_process` when isolated. It catches `JobCancelled`:
    - If `self.shutting_down` is set (analysis P4-04), save `status="failed"` with `error="server stopped while running"`.
    - Otherwise save `status="cancelled"` with `error="cancelled by user"` (analysis P4-06).
    - Both also set `finished` and `progress.stage` to the status.
  - **killpg before the child exists**: `os.killpg` can raise `ProcessLookupError` if the child has not yet called `setsid()`. Treat it as "not started yet": poll every 0.1 s for up to 2 s until the child's group exists, then signal it (analysis P4-05).
  - **Race**: before writing `done`/`cancelled`, if `result.json` exists and the runner returned normally, the status is `done`.
  - **Route `POST /api/jobs/{id}/cancel`**, per contracts/http-api.md:
    - queued → under `store.lock`, mark `cancelled` with `error="cancelled by user"` and respond 200;
    - running → set `cancel_requested`, set the event, respond 202;
    - terminal → 409;
    - unknown → 404.
  - **`_view`**:
    - `elapsed_s`: now (or `finished`) minus `started`;
    - `eta_s` (running only): from `eta.eta_seconds`, using `progress.stage_started`;
    - `label`: `"<6 display names> · <verdict or status>"`, with no time (analysis A1). For done jobs, the verdict comes from `job.json` `verdict` (T005). Older done jobs without that field get it from their `result.json`, read once and cached by job id. If that file can't be read, fall back to the status `done`, and never raise. One broken run must not make `GET /api/jobs` fail (analysis P5-03). For other jobs, the status (`queued`, `running`, `failed` or `cancelled`) is shown. Use catalog names when the catalog is ready, else the keys;
    - `platsim_version`.
  - **History**: load `StageHistory` at startup and `refresh()` it after each job ends.
  - **Shutdown** (analysis U1): add a FastAPI `lifespan` shutdown step and an `atexit` handler. Both set `JobRunner.shutting_down = True` **first**, then set every cancel event and `killpg` each active job group with SIGTERM, then SIGKILL after 5 s. Then they **join the JobRunner thread for up to 10 s**. The thread is a daemon (`app.py:182`), so without the join the process could exit before `run_one` writes the final status. If the join times out, the hook writes `failed` / "server stopped while running" itself under `store.lock` (analysis P5-02). A job stopped this way is saved as `failed` with the error "server stopped while running". That matches today's restart behaviour.
- [X] T028 [US3] In `src/platsim/web/static/app.js`, rebuild the progress view:
  - **Visibility**: render `#progress` only while a job is queued or running, and hide it otherwise. This includes after a reload, when `GET /api/jobs` has no queued or running job.
  - **Queued jobs** (analysis U4): below the running job, list every queued job as `position N · <6 species names>` (that exact wording, analysis P5-06), each with its own Cancel button that uses the same confirm/POST flow. If nothing is running, the first queued job is shown at the top as "waiting to start".
  - **Content**: stage, queue position (queued), elapsed `H:MM:SS` ticking every 1 s on the client from `started`, and the ETA as "about N min left" or "estimating…". Use exactly that wording everywhere (analysis P4-13).
  - **Cancel button**: `confirm("Cancel this run? Progress so far will be discarded.")`, then POST. Disable the button while waiting, and announce "Run cancelled" through a new `<p id="run-status" role="status" aria-live="polite">` that sits **outside** `#progress`, at the top of `#results-col`. `#progress` is hidden on cancel (FR-008), so an announcement placed inside it would never be heard (analysis P4-07).
  - **On done**: when the job reaches `done`, hide progress and render that job's result (T013). On `cancelled` or `failed`, hide progress and show the status message.
  - **Removed**: the `best_so_far` dump.
- [X] T029 [P] [US3] In `src/platsim/web/static/style.css`, add the styles for the progress block, the elapsed and ETA line, and the cancel button. The cancel button is a secondary/danger style built from the existing variables.

**Checkpoint (US3)**: T020–T024 pass, and RUN-STATE.md is updated, with the output recorded, including the cancel timing that
was measured.

---

## Phase 6: User Story 4 – Look at earlier runs (P2)

**Goal**: a dropdown of earlier runs, with the newest finished run shown by default.

**Independent test**: with two finished runs, the newest is shown. Picking the other switches the
panel (spec US4).

### Tests for User Story 4

- [X] T030 [US4] Add a test to `tests/integration/test_web.py`. Add `seed_switch_runner` to `tests/integration/_fake_runners.py`, and use it in one app in thread mode (`isolate=False`). The runner behaves by seed:
  - `"fail"`: raises `RuntimeError("synthetic failure")`;
  - `"hold"`: blocks on `_fake_runners.HOLD`, the module-level `threading.Event` that T022 creates (30 s timeout), then succeeds;
  - anything else: behaves like `StubRunner`.

  Call `_fake_runners.HOLD.clear()` at the start of the test, so state never leaks between tests (analysis P4-10). To get a cancelled-while-queued job, post a `"hold"` job, wait for it to run, post a second job, cancel the second (200), then `HOLD.set()`. Through it, make 2 done jobs, 1 failed job (seed `"fail"`), and 1 cancelled job (cancelled while queued) (analysis N17). `GET /api/jobs` must return them newest first, each with a `label` containing its status or verdict. `GET` on the failed job has `error` and no `team`. The cancelled job has `error == "cancelled by user"` (P4-06). **List cap** (SC-005, analysis P4-14): write 51 copies of the fixture run into a fresh runs dir, each at `runs_dir/<id>/job.json`, where the folder name equals the id, because `load_existing` skips any other (`app.py:148`). Each copy has a new id matching `ID_RE`, a `created` one second apart, and `result_paths` rewritten to that copy's own files (use `copy_fixture_run` with the id as a parameter) (analysis P5-03). `GET /api/jobs` returns 50, and the newest copy is first.

### Implementation for User Story 4

- [X] T031 [US4] In `src/platsim/web/static/app.js`, populate `#run-picker` from `GET /api/jobs` (newest first). The option text is `created`, formatted in the browser's local time as `YYYY-MM-DD HH:MM`, then ` · ` and the job's `label` (analysis A1).
  - **Default**: the newest `done` job.
  - **No remembered choice** (analysis N6, decision 2026-10-09): every page load, and every time a new job finishes, shows the newest `done` job (FR-014). The dropdown pick lasts only until then, and nothing is stored in `localStorage`.
  - **On change**: fetch and render. A failed or cancelled job shows `Status: failed` or `cancelled` and its `error`, instead of the summary, chart and cards.
  - **Refresh**: refresh the list whenever a job changes status.
  - **Cleanup**: replace the old `platsim:lastJob` resume logic with this (progress tracking now comes from `GET /api/jobs`).

**Checkpoint (US4)**: T030 passes, and RUN-STATE.md is updated.

---

## Phase 7: Polish & cross-cutting

- [X] T032 Write `tests/browser/test_page.py` (`@pytest.mark.browser`). Skip with a stated reason if `shutil.which("google-chrome")` is None or `playwright` won't import.
  - **Server**: start `uvicorn` in a thread on a free port with `create_app(runner=_fake_runners.sleepy_runner, isolate=True, runs_dir=<fixture copy>, catalog=<the session `catalog` fixture from tests/conftest.py>)`. Process mode is required, because cancel cannot stop a thread-mode runner (analysis I2). Register `page.on("dialog", lambda d: d.accept())` before pressing Cancel.
  - **Browser**: open it with `p.chromium.launch(channel="chrome")`.
  - **Assertions**, covering US1–US4 (quickstart V5):
    - two columns at 1920×1080, with `#setup` to the left of `#results-col`. At that size, the Optimize button and `#summary` are both inside the viewport without scrolling (SC-003, analysis G3);
    - **offline** (FR-029, analysis G3): record every request with `page.on("request")` for the whole test. **Positive control** (analysis N1): assert the list is not empty and contains at least one `/api/sprites/` URL and one `/api/jobs` URL. Then assert that every URL's host is `127.0.0.1`;
    - at 360×800, `document.scrollingElement.scrollWidth <= 360` (analysis I4);
    - no species list before typing, a list after typing "gar", and hidden again after clearing;
    - adding Garchomp shows an icon `img` that has loaded (`naturalWidth > 0`);
    - the budget select defaults to standard, and choosing thorough sends `"budget":"thorough"` (`page.expect_request`);
    - the seed tooltip is hidden, visible on hover, and visible on keyboard focus;
    - no `#progress` before a job, and `#progress` with ticking elapsed time, "estimating…" or "about", and a Cancel button while the fake job runs;
    - cancel → `#progress` hidden, and `#run-status` is visible and its text contains "Run cancelled" (FR-028, analysis P3-07 and P4-07);
    - **FR-013 positive control** (analysis P4-01): while the fake job runs, `GET /api/jobs/{id}` has a non-null `progress.best_so_far`, and the page text (case-insensitive) does not contain "best so far";
    - while the fake job runs, `#progress` shows the stage text "screen" (FR-009, P3-07);
    - Tab focus on a chart bar shows its visible `.tip`, with the interval and battle count (FR-027, analysis N9, P3-07);
    - the summary shows the legality options and the fixture's warning text (FR-020, P3-07);
    - in a **separate app and runs dir** (so it doesn't change which run is newest in the main test; analysis P4-11), a fixture copy whose `result.json` has no `per_battle` shows a chart area that reads "Per-trainer data is not available for this run" (edge case, P3-07);
    - at 1920×1080, `#chart` is inside the viewport together with `#summary`, without scrolling (SC-001, P3-13);
    - each team card shows at most 8 field elements, counted as direct children with the class `.field` (SC-002, P3-13). T013 gives each card field that class;
    - the run picker defaults to the fixture run, and switching works: opening the `<select>` and picking an option renders that run, two actions (SC-005);
    - at 360×800, `#setup`'s top is above `#results-col`'s top, so setup comes first when stacked (FR-002, analysis P4-14);
    - with one job running and one queued, the queued row shows "position 1" (FR-009, P4-14);
    - pressing Cancel raises a dialog whose message contains "Cancel this run?". Record `dialog.message` in the dialog handler before accepting (FR-011, P4-14);
    - the summary contains "58.23 (level gap of 4)" and "%" (analysis A2);
    - the clear-rate tooltip is hidden, then shows "95% interval" and "runs" on hover and on keyboard focus;
    - the page text contains none of: "Cynthia win", "Policies", "Objective", "Nature", "IVs", "EVs", "Ability choice", "Held item source", "Move 1 source", "best so far" (case-insensitive);
    - Luxray's card contains "(no significant difference)";
    - **assertion gaps** (analysis N10):
      - each run-picker option text matches `^\d{4}-\d{2}-\d{2} \d{2}:\d{2} · ` and includes the species names and the verdict or status (FR-015);
      - picking a failed or cancelled run shows its status and error, and no team cards (FR-016);
      - the summary shows the budget ("standard" for the fixture) and the threshold (FR-020);
      - the fixture run shows "platsim version not recorded", and no commit hash appears: the regex `\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b` must have no match in `document.body.innerText`. The lookahead excludes digit-only runs such as dates, and there is no upper length limit, so the 64-hex `sha256:` code hashes are caught too (analysis P4-02). **Positive control**: the same regex matches both the fixture's `decomp_commit` and its `platsim_code_hash` strings (FR-021, P3-11);
    - hovering a move shows its source text, and so does pressing Tab until a move chip has focus (FR-028, analysis G2);
    - each chart bar group can be reached with Tab and has an `aria-label` containing a percentage and "battles" (FR-028, analysis G2);
    - **existing setup behaviour** (FR-007, analysis G1):
      - the same species can be added twice;
      - the 7th add is refused and the count stays at "(6/6)";
      - Optimize is disabled with fewer than 6 species;
      - a min clear rate of 0 or 150 shows the inline error and sends no POST;
      - ticking "show excluded species" lists Munchlax as disabled with its reason;
      - ticking "Allow trade evolutions" re-runs the search and the `trade_evolutions=1` request is seen;
    - **queued jobs** (analysis U4): with one job running and a second job queued, the progress section lists the queued job with its own Cancel, and cancelling it removes it from the list while the running job keeps going;
    - the chart has 5 bar groups;
    - each front sprite `img` has `naturalWidth == 160`.
  - **Screenshots**: save light and dark (`page.emulate_media(color_scheme=...)`) screenshots to the session scratchpad path, which the test reads from env `PLATSIM_SCREENSHOT_DIR` and skips saving if unset.
- [X] T033 Run the full suite. This is **about 1 h of local CPU, with no paid resources** (analysis P4-08): `uv run pytest -q` includes feature 001's `tests/integration/test_optimize_small.py`, which runs two quick optimizations at 20–40 min each, plus the browser tests. Run `uv run pytest -q -m "not browser"`, then `uv run pytest -q -m browser tests/browser/`, so the browser tests run only once. View the light and dark screenshots. Paste the real output and what you observed into `validation-log.md`. Add a table to it mapping each FR-001 to FR-030 and each SC-001 to SC-007 to the test or walkthrough step that checks it, with pass or fail (SC-006, analysis P3-13).
- [X] T034 Repeat quickstart V6: the downloaded report bytes match the T002 hashes. Record the result in `specs/002-webui-redesign/validation-log.md`.
- [X] T035 Quickstart V7: real `quick` jobs through `uv run platsim serve`, plus the same request through the command line for comparison. This takes about 2 × 25 min of local CPU, plus a few minutes for the cancelled job, with no paid resources. Follow quickstart V7 steps 1–5:
  - **Job A (cancel test)**: start a throwaway quick job (any six available species). Queue reference job B behind it. Wait until A's stage is past `resolve` and `pgrep -f sim/worker.mjs` returns pids (positive control: A's workers exist; they start only after the roughly 35 s ledger build). Record that pid set, then cancel A **while it is running**. Check:
    - A is `cancelled` within 10 s (SC-004);
    - none of A's recorded pids is still alive. Compare pid sets, not counts, because B starts its own workers (analysis P3-14);
    - B starts.
  - **Job B (reference)**: exactly the request in `tests/integration/test_optimize_small.py`. That is species `infernape staraptor luxray garchomp gyarados gardevoir`, budget quick, seed `t058`, min clear 75%, and both legality boxes unchecked. When it finishes, the result panel switches to it without a reload (FR-014, analysis P3-07).
  - **Comparison** (analysis V1-A, Constitution IV): run `uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed t058 --out <scratchpad>/cli-t058`. Then run `cmp runs/<job B id>/result.json <scratchpad>/cli-t058/result.json`, and paste its exit code. 0 means byte-identical, the same standard as feature 001's T058 (`tests/integration/test_optimize_small.py`). On a difference, `diff` the two files and stop before release.

  Record the timings, the pid sets and the `cmp` exit code in `specs/002-webui-redesign/validation-log.md`.
- [X] T036 [P] Update `README.md`, in the "Web UI" paragraph and the HTTP API list:
  - the new endpoints (cancel, sprites);
  - the budget selector;
  - that the run picker lists web jobs only;
  - that each job now runs in its own process and the ledger build adds about 35 s per job.

  Remove the "No browser was available, so the page's JavaScript was not run" note only once T033 has passed.
- [X] T037 [P] Update `RUN-STATE.md`:
  - **Done**: 002 web UI redesign.
  - **Next**: remove "real-browser UI check" if T033 passed.
  - **Traps**:
    - editing `src/platsim/web/*.py` changes `platsim_code_hash`, which blocks resuming an older unfinished `state.json` (R8);
    - pyproject is still 0.1.0, so the version label doesn't change between runs (R5).

---

## Dependencies & execution order

```text
Setup (T001–T003) ─▶ Foundational (T004–T005) ─┬─▶ US1 (T006–T014) 🎯 MVP
                                                ├─▶ US2 (T015–T019)   [index.html/app.js/style.css shared with US1 → do after US1]
                                                ├─▶ US3 (T020–T029)   [server side independent of US1/US2; page part after US1]
                                                └─▶ US4 (T030–T031)   [needs T027 labels + T013 rendering]
All stories ─▶ Polish (T032–T037)
```

- **US1** is the MVP. Inside it, T008 and T009 can run in parallel, and T010 needs both. T011
  and T012 can run in parallel, then T013, then T014.
- **US2** edits the same three static files as US1, so run it after T013 to avoid conflicts.
  T016 (server) can run any time after Phase 2.
- **Shared test files** (analysis N8): T004, T010, T015, T022 and T030 all edit `tests/integration/test_web.py`, so run them in that order and never in parallel. T021 creates `tests/integration/_fake_runners.py`; T022 (adds `HOLD` and `two_beat_runner`), T023, T024 and T030 come after it, in that order.
- **US3**: T025 and T026 are new modules and can run in parallel with US1. T027 needs T005, T025
  and T026. T028 needs T013.
- **US4** needs T027 (the `label` and `cancelled` status) and T013.

## Parallel examples

```text
After Phase 2, in parallel:
  T006 test_web_sprites.py      T007 test_web_result_view.py
  T008 sprites.py               T009 result_view.py
  T011 index.html               T012 style.css
  T020 test_web_eta.py          T021 test_web_cancel.py
  T025 eta.py                   T026 job_process.py
  T016 species_catalog.py
```

## Implementation strategy

1. **MVP**: Phases 1–3 (US1). The new results panel works for existing runs. Stop and validate
   with the US1 checkpoint screenshot.
2. **US2**: the setup column. Every P1 requirement is then met.
3. **US3**: cancel, ETA and the process mode. This is the riskiest slice, because it adds a
   process boundary. Validate it with T021's timing assertions, T023's shutdown checks and T024's determinism check before any real job.
4. **US4**: the run picker.
5. **Polish**: the browser walkthrough (T032–T033) closes SC-006 and the RUN-STATE gap. Then the
   report-hash check, one real quick job, and the docs.

Each checkpoint records real test output in `validation-log.md`. Nothing is marked done without
running its check.
