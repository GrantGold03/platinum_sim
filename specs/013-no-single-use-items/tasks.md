# Tasks: No Single-Use Held Items (held items, slice H2)

**Input**: Design documents from `specs/013-no-single-use-items/` (spec.md, plan.md, research.md, data-model.md,
contracts/item-use.md, quickstart.md).

**Tests**: Required by the spec (FR-006, SC-003, SC-004) and Constitution V: classifier positive and negative
controls, a completeness gate, and a guard test with a filter-off control. Tests are written first and shown to fail
before the code exists.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence worth keeping goes in `runs/013-evidence/`
  (git-ignored). Never `/tmp`.
- Never `git commit -a`: the user's uncommitted deletion of `.claude/scheduled_tasks.lock` and the untracked Spec Kit
  files stay out. Stage paths by name.
- `data/generated/` is shared between branches: run `uv run platsim extract` after every branch switch.
- Record every result with real output (command, exit code, summary lines, Eastern times) in
  `specs/013-no-single-use-items/validation-log.md`.
- No hand-typed item or hold-effect list in `src/` (FR-001). Tests may name the expected items from research R4.
  These are check values, not inputs.
- Push every commit that touches `src/` or `tests/`. Do not merge (the user tests first).
- No commits while the B2 run or the test suites are running (`repo_commit` is cached per process).
- Decomp root: `platsim.pins.DECOMP_ROOT`. File refs via `platsim.decomp._util.ref` / `line_of`.

## Phase 1: Setup (baseline, code = `main` `cbb0580`)

- [X] T001 Create `specs/013-no-single-use-items/validation-log.md`: branch, base commit, `git diff --stat main HEAD -- src tests sim` (expected empty), date
- [X] T002 `git switch main`, `uv run platsim extract`; write a scratchpad script `candidates_snapshot.py` that, for each team in `tests/fixtures/bench_007.json` read via `git show 007-status-moves-items:tests/fixtures/bench_007.json` (B1-B5), for every member, every variant, and levels 45/55/65, calls `platsim.optimizer.candidates.member_candidates(..., team=<the six SPECIES_*>)` and writes `{"<B>|<SPECIES>|<variant>|<level>": {"items": {"<moves joined by />": [items]}, "movesets": [...]}}`. Save to `runs/013-evidence/main-candidates.json`. **Positive control:** the result equals `runs/011-evidence/main-candidates.json` (93 keys). If it differs, find out why before going on: either the script or `main`'s candidates changed
- [X] T003 On `main`: `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 013-sc005 --out runs/013-evidence/sc005-main` (about 25 min, local, run in the background); record start/end times (Eastern), wall time, exit code, `result.json` sha256, clear rate, `repo_commit`
- [X] T004 After T003 finishes: `git switch 013-no-single-use-items`, `uv run platsim extract`

## Phase 2: Foundational (the classifier; blocks both stories)

**Goal**: `platsim.decomp.item_use` classifies every item as single-use or not, and berry or not, from the decomp
(research R1-R3, contract `contracts/item-use.md`).

- [X] T005 Write `tests/unit/test_item_use.py` first (contract table in `contracts/item-use.md`):
  - positive controls: `ITEM_FOCUS_SASH` single-use, not berry, evidence includes a `subscript_move_followup_message.s` ref; `ITEM_SITRUS_BERRY` single-use and berry; `ITEM_BERRY_JUICE`, `ITEM_WHITE_HERB`, `ITEM_MENTAL_HERB`, `ITEM_POWER_HERB` single-use, not berry;
  - negative controls: `ITEM_LEFTOVERS`, `ITEM_FOCUS_BAND`, `ITEM_QUICK_CLAW`, `ITEM_STICKY_BARB`, `ITEM_SILK_SCARF`, `ITEM_NONE` not single-use;
  - berry rule: the berry set has 64 items and equals the set of data files whose JSON `fieldPocket` is `POCKET_BERRIES` (read with `json`, independently of the reader); `ITEM_BERRY_JUICE` not a berry;
  - evidence: every single-use item has a non-empty `evidence` whose refs point at real lines (`file:line` exists and the line contains `RemoveItem`, a `case HOLD_EFFECT_`, or `CheckItemHoldEffect`); every non-single-use item has empty evidence (FR-005);
  - same hold effect → same verdict for all items;
  - completeness gate: running the site reader over a scratch copy of `res/battle/scripts/` (pytest `tmp_path`) with one extra unattributed `RemoveItem BTLSCR_ATTACKER` line added to a subscript raises `ItemUseReadError`; on the real decomp it does not raise;
  - `is_excluded_single_use` accepts both `ITEM_FOCUS_SASH` and `focus_sash`; `None` and an unknown key → False.
  Run `uv run pytest -q tests/unit/test_item_use.py`; record that it fails on import (module absent)
- [X] T006 Create `src/platsim/decomp/item_use.py` (module docstring in the style of `platsim/decomp/items.py`, citing the decomp files): `ItemUseReadError`, `ItemUse` dataclass (`const`, `hold_effect`, `berry`, `single_use`, `evidence`), comment stripping for `.s` and `.c`, and a site scanner that lists every `RemoveItem` line under `res/battle/scripts/` as a `RemoveSite` (research R1: 11 sites). Allow the scripts root to be passed in (for T005's scratch copy)
- [X] T007 In `src/platsim/decomp/item_use.py`: subscript call graph. Map `Call BATTLE_SUBSCRIPT_<NAME>` and C `subscript_<name>` to `subscripts/subscript_<name>.s`, failing on an unresolved name. Compute which subscripts reach `RemoveItem` transitively, and note when the reaching path passes a guard (rules 2-4 in research R2)
- [X] T008 In `src/platsim/decomp/item_use.py`: rule 1. Parse the five trigger functions in `src/battle/battle_lib.c` (`BattleSystem_TriggerHeldItem`, `BattleSystem_TriggerLeftovers`, `BattleSystem_TriggerHeldItemOnStatus`, `BattleSystem_TriggerDetrimentalHeldItem`, `BattleSystem_TriggerHeldItemOnHit`, located by name, not line). Map each `case HOLD_EFFECT_X:` block to the subscripts it assigns. X is single-use if one reaches an unguarded `RemoveItem`. Evidence: the `case` line and the `RemoveItem` line. `BattleSystem_PluckBerry` and `BattleSystem_FlingItem` are not read
- [X] T009 In `src/platsim/decomp/item_use.py`: rules 2-4. A `CheckItemHoldEffect CHECK_NOT_HAVE ... HOLD_EFFECT_X` guarding a `RemoveItem` → X. A `CheckItemHoldEffect CHECK_HAVE ... HOLD_EFFECT_X, <label>` whose label calls a removing subscript → X. `GetItemHoldEffect` + compares with `HOLD_EFFECT_*` on the path to `RemoveItem` → those effects. The `BATTLEMON_CUSTAP_BERRY` guard → the `HOLD_EFFECT_*` that sets `custapBerry` in `battle_lib.c`. Mark move-driven sites (`subscript_pluck.s`, the Natural Gift and Fling effect scripts: reached only from move effect scripts). Completeness gate: raise `ItemUseReadError` if any site is neither attributed nor move-driven, or if no effect is single-use. If a rule cannot be parsed generally, use the research R2 fallback (a pinned line assertion) and add it to Complexity Tracking in `plan.md`
- [X] T010 In `src/platsim/decomp/item_use.py`: berry flag from `res/items/data/<key>.json` `fieldPocket` (research R3; do not change `platsim/decomp/items.py`). Add `item_uses()` (cached, every item from `load_items()`) and `is_excluded_single_use(item)` per `contracts/item-use.md`
- [X] T011 Run `uv run pytest -q tests/unit/test_item_use.py` until it passes. Record the output, the reader's run time (cold, in one process), and the full excluded set (`single_use and not berry`) with each item's evidence. Compare with research R4. For each extra item, check the cited decomp lines by hand and record the verdict (SC-002). If the reader is wrong, fix the reader, not the test

**Checkpoint**: the classifier is complete and verified; both stories can start.

## Phase 3: User Story 1 - The optimizer never gives a team a single-use non-berry item (P1) 🎯 MVP

**Goal**: `held_item_candidates` never proposes an item that is single-use and not a berry (FR-003, FR-004).

**Independent Test**: The guard test filters an injected `focus_sash`, and the filter-off control shows it would
otherwise appear. No candidate list for the B1-B5 members or the extra test teams contains an excluded item.

- [X] T012 [US1] Add to `tests/unit/test_optimizer_candidates.py`:
  - guard test: monkeypatch `held_item_candidates`'s type-boost lookup (`C.type_boost_items`) so a type maps to `HOLD_EFFECT_ENDURE`, so the existing code would propose `focus_sash` for a member whose best attack has that type, and give the ledger a copy of Focus Sash (it has 1). Assert `focus_sash` is not in the result and the HP berry still is;
  - filter-off control: the same setup with `is_excluded_single_use` monkeypatched to always return False. Assert `focus_sash` **is** in the result, so the guard test can fail;
  - sweep: for a Snorlax team and two other teams over several movesets, no result item has `is_excluded_single_use` True, and `sitrus_berry` is still offered.
  Run them; record that the guard test fails before T013 and the filter-off control passes
- [X] T013 [US1] In `src/platsim/optimizer/candidates.py` `held_item_candidates`: apply one final filter `[it for it in out if not is_excluded_single_use(it)]` before the `out or [None]` return. Update the docstring to state the rule (single-use non-berry items never offered; berries allowed; the decomp reader decides). Import from `platsim.decomp.item_use`
- [X] T014 [US1] Run `uv run pytest -q tests/unit/test_optimizer_candidates.py tests/unit/test_item_use.py`; record that all pass (SC-001, SC-004)
- [ ] T015 [US1] Commit `src/platsim/decomp/item_use.py`, `src/platsim/optimizer/candidates.py`, `tests/unit/test_item_use.py`, `tests/unit/test_optimizer_candidates.py` as "feat(013): never offer single-use non-berry held items"; push

**Checkpoint**: US1 is done and testable alone.

## Phase 4: User Story 2 - Nothing else changes (P1)

**Goal**: B1-B5 candidates are identical to `main`'s; the same-seed B2 run is identical apart from provenance
(FR-007, FR-008, SC-005).

**Independent Test**: diffs against the T002/T003 baselines.

- [ ] T016 [P] [US2] On the branch (after T015, extract rebuilt): run `candidates_snapshot.py` to `runs/013-evidence/branch-candidates.json`; compare with `main-candidates.json`; record the same keys and 0 entries differing, or explain each difference
- [ ] T017 [US2] After T015 is pushed and with no commit pending: the same command as T003 to `runs/013-evidence/sc005-branch`; diff `result.json` field by field against `sc005-main`; record that only `/platsim_code_hash` and `/repo_commit` differ (`/provenance/worker/decomp_data_hash` must match), or explain each difference
- [ ] T018 [P] [US2] Show `git diff main -- sim src/platsim/web src/platsim/availability src/platsim/legality src/platsim/explain.py src/platsim/decomp/items.py` is empty (FR-008); record

## Phase 5: Polish & cross-cutting

- [ ] T019 Fast mode: `uv run pytest -q -m "not battle_sim"` (about 10 min) and `(cd sim && node --test test/*.test.mjs)`; logs to `runs/013-evidence/`; record the summary lines, exit codes and test counts against `main` (fast mode 504 passed, 4 xfailed; Node 314) (SC-006)
- [ ] T020 [P] Update `FUTURE-FEATURES.md` (H2 done on the branch, the rule for H3+: candidates pass the single-use filter automatically) and `RUN-STATE.md` (state, evidence paths, next: user's hands-on test). Commit the docs and the validation log; push

## Dependencies & execution order

- Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5.
- T003 runs in the background (about 25 min). Do not switch branches or rebuild while it runs: `data/generated/` and the source tree are shared, and the run may import modules late. T004 and everything after it wait for T003. The reader design can be studied in the meantime without editing files.
- T016 and T018 can run in parallel. T017 needs T015 pushed, and nothing may be committed while it runs. T019 runs after T017 (both are long; they are not run together).

## Parallel opportunities

- T016 ∥ T018; T020 ∥ T019 log reading. The reader tasks T006-T010 are in one file and are sequential.

## Implementation strategy

MVP = Phases 1-3 (classifier and filter, with tests). Phase 4 proves nothing else changed; Phase 5 runs the gates.
Then the user's hands-on test, and merge only on the user's go.
