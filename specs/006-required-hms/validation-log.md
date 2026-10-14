# Validation log: 006

## T001 Baseline (2026-10-13, worktree ../platinum_sim-006)

- HEAD: `dccb3a44e7dbaf4533241a4fcd9270d5563886d1`, branch `006-required-hms`.
- `uv sync` succeeded. `uv run platsim extract` → exit 0. `extract --check` → "up to date (11 files)".
  `platsim` imports from `/home/grant/Desktop/platinum_sim-006/src/platsim/__init__.py`.
- `pytest -q tests/unit/test_validator.py tests/unit/test_source_preference.py tests/unit/test_optimizer_candidates.py tests/integration/test_web.py`
  → `80 passed, 1 skipped, 1 warning in 112.23s`. The 005 full suite was running in the main
  checkout at the same time.
- Default `job_fingerprint` for infernape, garchomp, gyarados, lucario, chatot and staraptor (the
  FR-009 reference), followed by `default_out_dir`:
```
{"species": ["SPECIES_INFERNAPE", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_LUCARIO", "SPECIES_CHATOT", "SPECIES_STARAPTOR"], "min_clear": 0.75, "seed": "default", "budget": "standard", "legality_options": {"allow_egg_moves": false, "allow_trade_evolutions": false}, "state_version": 3}
/home/grant/Desktop/platinum_sim-006/runs/optimize-beec2c608d05
```
- `sha256sum tests/fixtures/web_final_defaults/*`:
```
4bcd3bb1fdc1dadb7c1f8cb2303e0beb7df02ba38338173fc9f81fe74362376d  tests/fixtures/web_final_defaults/job.json
308efe3f5054b45177dc2529c7de2ab6cdd6d5c4e8e728e743144d4b328c542a  tests/fixtures/web_final_defaults/README.md
8aef11f4ccb7639b55dcedd9c37d2aff47e0d966c52633768510e9bda6b1efd0  tests/fixtures/web_final_defaults/result.csv
ade487fb6ff4345910e40935449e49e7b288c51750259040249af30ccc64277d  tests/fixtures/web_final_defaults/result.json
78be928d6cc26625817cd102be4ccf8e4fd59d909f99ede94965977ff0250aed  tests/fixtures/web_final_defaults/result.xlsx
e2b11bf5818435cc6606c3aa900056b6d2776ec9d5bfa260c0c5203dc45ddb34  tests/fixtures/web_final_defaults/team.txt
```

## T002 Runs

The worktree has no `runs/` directory (it is git-ignored), so nothing needs resuming.

## T003–T010 Foundational + US2 refusal (2026-10-13)

- **T003**: `MS.hm_moves()` (cached) replaces the planned `HM_MOVES` constant, so nothing loads
  at import time. It is built from `decomp.items.tm_moves()` and `load_moves()`. `hm_key` and
  `normalize_hms` come with it. **T004**: `OptimizeRequest.required_hms`, normalised in
  `__post_init__` with a lazy import, so `api.py` stays light. Then
  `pytest tests/unit/test_required_hms.py` → `2 passed`.
- **Probe for T005**: no legality option changes any HM's learnability for the 188 default species
  (`differs: 0`). Control: Staraptor learns Fly. The option path is therefore tested with a
  stand-in source that exists only in the option-on view.
- **Tests first**: 4 failed (missing `unlearnable_moves`, no refusal, web 201).
  - One test fix: `WorkerPool` is imported inside `run_optimization`, so the monkeypatch targets
    `platsim.sim.pool`.
- **After T007–T009**: `pytest -q tests/unit/test_required_hms.py tests/integration/test_web.py` →
  `1 failed, 21 passed`. The failure was my test's expected order: HM order is Fly (02), Defog
  (05), Waterfall (07). After fixing it, `test_required_hms.py` → `5 passed`.

## T011–T018 US1 carried in a moveset (2026-10-13)

- **Tests first**: `4 failed, 5 passed, 1 skipped` (validator keyword, placement, fingerprint).
  Two test-fixture fixes:
  - the baseline movesets clashed on a single-copy TM (Garchomp and Gyarados both used
    Earthquake), so the fixture now runs `R.repair` as the optimizer does;
  - the Fly-refusal team also had Chatot, a Fly learner, so Chatot was dropped.
- **Implementation**:
  - T014: validator `REQUIRED_HM_MISSING`.
  - T015: `place_required_hms` + `realize(..., required_hms=)` + `repair(..., required_hms=)`.
    `repair`'s partial-team probe stays HM-free, because the carrier may be a later member.
  - T016: all 10 `realize`/`repair` calls in `run.py`, both `validate` calls, the fingerprint and
    provenance (only when set), and `final_team_labels` built from the placed specs.
  - T017: `evaluate(..., required_hms=)` and its provenance; `rerender` validates with the
    recorded HMs; CLI `--require-hm` on validate, evaluate and optimize.
  - A self-inflicted syntax error, from a `sed` comment placed mid-call, was caught and fixed.
- **CLI checks**:
  - `platsim validate tests/fixtures/legal_team.json --require-hm fly` →
    `REQUIRED_HM_MISSING: required HM Fly is not in any member's moveset` (src
    `generated/items.txt:422, res/items/data/hm02.json:1, specs/006-required-hms/spec.md:136`), ILLEGAL.
  - `--require-hm Waterfall` → legal. Positive control: Gyarados carries Waterfall.
  - `--require-hm dig` → argparse error, exit 2.
- `pytest -q tests/unit/test_required_hms.py tests/unit/test_validator.py tests/unit/test_source_preference.py tests/unit/test_optimizer_candidates.py tests/integration/test_web.py`
  → `91 passed, 1 skipped`. That includes the default fingerprint equal to T001 (FR-009).

## T019–T024 US3 web step (2026-10-14)

- **Server**: `GET /api/hms` serves the list from `hm_moves()`; the page's toggles are built by
  `app.js` from it, so the HTML has no hand-typed HM list.
- **Page**: step 3 is a card `#hm-step` with an `#hm-list` grid (4 per row), and Optimize is
  renamed "4. Optimize". The request sends `required_hms` only when some HM is checked, and the
  summary has a "Required HMs" row (names, or "none").
- **Scope fix not needed**: `test_legality_options_page_search_and_jobs` counts checkboxes in the
  static HTML. The HM boxes are added by JS, so the count stays 5.
- **Problems found and fixed**:
  1. `test_required_hms_web` first failed because its team (Garchomp ×6) can't learn Waterfall.
     The 422 was correct; the test team now includes Gyarados.
  2. The browser walkthrough failed on 002 SC-003: `#optimize` was at y=1201, below the 1080p
     fold. Fix: a compact 4-column HM grid.
  3. Two browser runs then hit my timeouts (exit 124).
     - The first was CPU starvation: a faulthandler dump showed `build_ledger` still running after
       5 minutes, with the 005 full suite loading the machine (load ~15 on 16 cores).
     - The second was not a hang. With `DEBUG=pw:api`, the last call was a click on
       `#require-hm-strength`. The 003 wording test iterates every subset of
       `#setup .rules input[type=checkbox]`, and the HM fieldset reused class `rules`, so it went
       from 2^5 to 2^13 subsets.
     - Fix: the HM fieldset's class is now `hm-rules`, with the same look.
- `uv run pytest -q tests/integration/test_web.py` → `17 passed`, plus `test_required_hms_web`
  passed separately (1 passed).
- `uv run pytest -q -m browser tests/browser/` → `5 passed in 62.87s`. That includes the 1080p
  check in `test_page_walkthrough` and the new `test_required_hms_step`.

## T026 End-to-end (2026-10-14)

- **First run crashed** (01:10–01:26, exit 1). `NameError: name 'required_hms' is not defined`
  in `evaluate.evaluate_team`.
  - Cause: I had put the provenance line in the shared `evaluate_team`, which the optimizer's
    confirm stage also calls, instead of in `evaluate`. No unit test runs that path.
  - Fix: `evaluate()` sets `report.provenance["required_hms"]` after `evaluate_team` returns. The
    optimizer path already sets it in `_report`.
- **Static check** over all 11 changed modules: a `symtable` scan for undefined global names
  found only interpreter dunders (`__file__`, `__conditional_annotations__`). Positive control: a
  planted `required_hms_typo` in `evaluate` is reported.
- **Rerun** (01:26–01:48, exit 0):
  `platsim optimize garchomp gyarados staraptor lucario infernape chatot --budget quick --require-hm surf --require-hm waterfall`.
  - `provenance.required_hms == ["surf","waterfall"]`, and so does
    `provenance.optimizer.request.required_hms`. The clear rate is 0.8.
  - Movesets: Garchomp `[earthquake, dragon_claw, rock_slide, surf]` (Surf placed); Gyarados
    `[aqua_tail, waterfall, stone_edge, ice_fang]`.
  - `platsim validate <team> --require-hm surf --require-hm waterfall` → legal, exit 0.
    Control: `--require-hm fly` → ILLEGAL, exit 2.

## T027 Full suite (2026-10-14)

Started 01:50 and ended 04:13. Local CPU only. Browser tests included.

`uv run pytest -q` in the worktree:
```
2 failed, 488 passed, 1 skipped, 4 xfailed, 1 warning in 8596.65s (2:23:16)
exit=1
FAILED tests/integration/test_web_eta.py::test_history_from_real_runs
FAILED tests/integration/test_web_result_view.py::test_result_view
```
1. **`test_result_view`**: an exact key-set assertion on the job summary, which now deliberately
   has `required_hms` (contract: `null` for runs without it). Updated `SUMMARY_KEYS`, and added
   `assert s["required_hms"] is None` for the frozen default run.
2. **`test_history_from_real_runs`**: it reads the repo's real `runs/`, which is git-ignored and
   absent in the worktree, so the history is empty. This is environmental, not 006 code: it passed
   in the 005 full suite in the main checkout (490 passed).
   - Check: with `runs` temporarily symlinked from the main checkout (removed afterwards; not
     committed), `pytest -q tests/integration/test_web_eta.py::test_history_from_real_runs tests/integration/test_web_result_view.py`
     → `5 passed`.
   - After the merge into the main checkout it runs against the real `runs/` again.

Only a test file changed after the full run, so the whole suite was not run again (the same
practice as the 003 T058 rerun).

## T029–T030 Convergence: step 3 labels (2026-10-14, after the user's hands-on test)

- **User report**: "the HM names overlap the next one. Remove HM0X from the name and just use the
  move name." Recorded in spec FR-006 and Clarifications, and in the contract.
  `/speckit-converge` found 2 contradicts gaps (F1 labels, F2 overlap) and appended T029–T030.
- **Cause of the overlap**: `.hm-list` used `repeat(4, minmax(0, 1fr))`, and `.check` used
  `white-space: nowrap`, so text spilled past narrow columns.
- **Tests first**:
  - `test_required_hms_step` now expects the move names and no "HM0", plus a no-overlap check at
    1920×1080.
  - New `test_hm_labels_do_not_overlap_on_a_phone` (390 px), with a positive control that forces
    the old layout.
  - The first version of the overlap check measured `<label>` boxes, which hide spilled text, so
    the control found nothing. It now measures each label's content range, and the control
    detects the old overlap.
  - Before the fix: `1 failed` (labels "HM01 Cut", …).
- **Fix**: `app.js` labels use `h.name`. `style.css` grid is now
  `repeat(auto-fill, minmax(7.5em, 1fr))`, with labels `min-width: max-content`; the phone
  media rule was dropped.
- `uv run pytest -q -m browser tests/browser/` → `6 passed in 63.16s`. That includes the 1080p
  fold check (002 SC-003).
- **Screenshots** (session scratchpad): desktop shows 3 columns × 3 rows; phone shows 2 columns ×
  4 rows. No label touches another.
