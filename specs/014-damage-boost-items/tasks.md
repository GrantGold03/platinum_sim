# Tasks: Damage-Boosting Held Items (held items, slice H3)

**Input**: Design documents from `specs/014-damage-boost-items/` (spec.md, plan.md, research.md,
contracts/held-item-candidates.md, quickstart.md).

**Tests**: Required by the spec (FR-006, SC-002, SC-003) and Constitution V. Tests are written first and shown to
fail before the code.

## Conventions

- Temp files and scripts go in the session scratchpad; evidence in `runs/014-evidence/` (git-ignored). Never `/tmp`.
- Never `git commit -a`; stage paths by name (the user's `.claude/scheduled_tasks.lock` deletion and untracked
  Spec Kit files stay out).
- `data/generated/` is shared: `uv run platsim extract` after every branch switch.
- Never commit, switch branches or run `extract` while an optimization, the comparison or a suite is running
  (`repo_commit` is cached per process; the source tree is shared).
- Record every result (command, exit code, summary lines, Eastern times) in
  `specs/014-damage-boost-items/validation-log.md`.
- Items are chosen by hold effect, never by name, in `src/` (FR-001). Tests may name the expected items as check
  values.
- Push every commit touching `src/` or `tests/`. Do not merge.
- Ledger fixture: the module-scoped `led` in `tests/unit/test_optimizer_candidates.py`.

## Phase 1: Setup (baseline, code = `main` `3078dad`)

- [ ] T001 Create `specs/014-damage-boost-items/validation-log.md` (branch, base, `git diff --stat main HEAD -- src tests sim` expected empty)
- [ ] T002 `git switch main`, `uv run platsim extract`; run the 013 scratchpad `candidates_snapshot.py` (recreate it from `specs/013-no-single-use-items/tasks.md` T002 if the scratchpad copy is gone) → `runs/014-evidence/main-candidates.json`. **Positive control:** equal to `runs/013-evidence/branch-candidates.json` (93 keys, 0 differ)
- [ ] T003 On `main`, in the background: `/usr/bin/time -f "wall %e s" uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --out runs/014-evidence/b2-main`; record start/end (Eastern), wall time, exit code, `result.json` sha256, clear rate, average final level, each member's item, `repo_commit`
- [ ] T004 After T003: `git switch 014-damage-boost-items`, `uv run platsim extract`

## Phase 2: Foundational

None: the change is one function plus tests. The copy accounting and report sources already exist (research R3, R6).

## Phase 3: User Story 1 - The optimizer can give a team Expert Belt or Wise Glasses (P1) 🎯 MVP

**Goal**: `held_item_candidates` adds the damage boosters by hold effect, after the existing items (FR-001 to FR-006).

**Independent Test**: The contract cases pass; Muscle Band appears only when a copy is stubbed in; two Expert Belt
holders are refused.

- [ ] T005 [US1] On the branch, before any code change, print the real current output of `C.held_item_candidates` for the contract cases (Empoleon `(MOVE_SURF,)`; Garchomp `(MOVE_EARTHQUAKE,)`; Snorlax `(MOVE_BODY_SLAM,)` with team `("SPECIES_SNORLAX", "SPECIES_GARCHOMP")`; and a status-only moveset, e.g. Garchomp `(MOVE_SWORDS_DANCE,)`) with a scratchpad script. Record them in the log. The expected post-change lists are these plus the boosters per `contracts/held-item-candidates.md`. Fix any wrong example in the contract file before writing tests
- [ ] T006 [US1] Add tests to `tests/unit/test_optimizer_candidates.py` (section comment "Feature 014: damage boosters"):
  - special: Empoleon/Surf → existing items unchanged as a prefix, then `expert_belt`, `wise_glasses`;
  - physical: Garchomp/Earthquake → existing prefix, then `expert_belt` only (no `wise_glasses`, no `muscle_band`);
  - no attack: the status-only moveset → no `expert_belt` / `wise_glasses` / `muscle_band`;
  - Muscle Band copy control: wrap `led` in a stub whose `item_copies("ITEM_MUSCLE_BAND")` returns 1 (others delegate; clear `C._ITEM_COPIES` via monkeypatch so the memo does not hide it). Garchomp/Earthquake then includes `muscle_band`; with the real `led` it does not;
  - group from data: the set of items whose `hold_effect` is one of the three `HOLD_EFFECT_POWER_UP_*` (read from `load_items()`) equals `{expert_belt, muscle_band, wise_glasses}` (check value, research R1);
  - H2 still holds: no candidate in these cases has `is_excluded_single_use` True.
  Run `uv run pytest -q tests/unit/test_optimizer_candidates.py -k "booster or damage"` and record the expected failures
- [ ] T007 [US1] Add the Expert Belt copy test to `tests/unit/test_optimizer_candidates.py`, modelled on `test_single_copy_tm_is_never_given_twice`: assert `led.item_copies("ITEM_EXPERT_BELT") == 1`. Realize `(a,)` with `a` = Garchomp `("MOVE_EARTHQUAKE", "MOVE_DRAGON_CLAW")`, item `expert_belt`, at Lv 55 → not a Refusal, `uses` includes the Expert Belt resource. Realize `(a, b)` with `b` = Empoleon `("MOVE_SURF",)`, item `expert_belt` → Refusal at slot 1. Also run the validator on a hand-built two-holder team and assert a copy violation (positive control). This test may pass before T008 (existing accounting); record that
- [ ] T008 [US1] Implement in `src/platsim/optimizer/candidates.py` `held_item_candidates`: module-level hold-effect names `POWER_UP_SE = "HOLD_EFFECT_POWER_UP_SE"`, `POWER_UP_BY_CLASS = {"CLASS_PHYSICAL": "HOLD_EFFECT_POWER_UP_PHYS", "CLASS_SPECIAL": "HOLD_EFFECT_POWER_UP_SPEC"}` (comment citing `sim/damage.mjs:381-382,639` and research R1). After the existing items and before the H2 filter, when `attacks` is non-empty: append every item with `hold_effect == POWER_UP_SE` and `_item_copies(led, const) != 0` (sorted by key), then every item with the hold effect for `load_moves()[best].category` that has a copy (sorted by key). Skip items already in `out`. Update the docstring (item order; 014)
- [ ] T009 [US1] Run `uv run pytest -q tests/unit/test_optimizer_candidates.py tests/unit/test_item_use.py`; record all passing (SC-002, SC-003)

**Checkpoint**: US1 complete.

## Phase 4: User Story 3 - The player can see where to get the item (P2)

**Goal**: The report and `explain` show where the new items come from (FR-008). Placed before US2 because US2's long
runs need the code committed first.

- [ ] T010 [P] [US3] Add a test to `tests/unit/test_optimizer_candidates.py`: realize Empoleon `("MOVE_SURF",)` with `wise_glasses` at Lv 55, call `platsim.report.sources.team_sources(real.team, led)`, and assert the held-item source text names Celestic Town (`MAP_HEADER_CELESTIC_TOWN_NORTHWEST_HOUSE` or its display name) and its refs include `scripts_celestic_town_northwest_house.s`. Do the same for `expert_belt` (Route 221 house). Run it; record
- [ ] T011 [P] [US3] `uv run platsim explain item:expert_belt` and `item:wise_glasses` → `runs/014-evidence/explain-branch.txt`; record the source lines in the log
- [ ] T012 [US1] Commit `src/platsim/optimizer/candidates.py` and `tests/unit/test_optimizer_candidates.py` as "feat(014): offer damage-boosting held items by hold effect"; push

## Phase 5: User Story 2 - Teams do not get worse (P1)

**Goal**: B1-B5 candidates differ only by the added boosters; B2 passes the equal-levels rule; run time reported
(FR-009, FR-010).

- [ ] T013 [P] [US2] Run `candidates_snapshot.py` on the branch → `runs/014-evidence/branch-candidates.json`. Compare with `main-candidates.json`: same keys and movesets; for each list, the `main` list is a prefix and every added item is `expert_belt` or `wise_glasses`. Record counts (lists changed, items added by kind) or each exception (SC-001)
- [ ] T014 [US2] After T012 is pushed, with no commit pending, in the background: the T003 command with `--out runs/014-evidence/b2-branch`; record the same fields as T003, and the wall-time ratio branch/main (SC-005). From `runs/014-evidence/b2-branch/state.json`, record whether the screen stage tried any option with `expert_belt` or `wise_glasses` (count of such options)
- [ ] T015 [US2] Write scratchpad `equal_levels.py` (research R5): load both `result.json` teams with `platsim.evaluate.load_and_validate` (write each `team` to a scratchpad JSON first if it needs a file), set every member of both teams to the branch team's start levels, validate both (stop and report if `main`'s is illegal there), then on one pool (`platsim.sim.pool`) run `platsim.evaluate.run_full_gauntlets` for each, `master="014-equal|B2"`, `min_runs=max_runs=2000`, `target=None`, `player_policy="expectimax2-v2"`. Report `platsim.stats.mcnemar_exact(branch, main)` (a = branch) and the mean final level of each side via `platsim.evaluate.final_level_stats`. **Positive control:** first run it with the `main` team against itself for 200 runs; expect `a_only == b_only == 0` (same seeds, same team). Save output to `runs/014-evidence/equal-levels.txt`
- [ ] T016 [US2] Run `equal_levels.py` (2,000 paired; background; time it). Record rates, `a_only` / `b_only`, p, verdict, mean final levels and wall time. Pass: verdict not "B" (main better) and the branch's mean final level not higher (SC-004). If the two final teams are identical, record that, plus the T014 count of booster options tried. If it fails, stop and report to the user before any further task

## Phase 6: Polish & cross-cutting

- [ ] T017 `git diff --stat main -- sim src/platsim/availability src/platsim/legality src/platsim/explain.py src/platsim/decomp` is empty (FR-007). Control: `git diff --stat main -- src tests` lists the changed files. Record
- [ ] T018 Fast mode `uv run pytest -q -m "not battle_sim"` and `(cd sim && node --test test/*.test.mjs)`, logs to `runs/014-evidence/`; record summary lines and counts against `main` (516 passed, 4 xfailed; Node 314) (SC-006)
- [ ] T019 Update `FUTURE-FEATURES.md` (H3 status; next groups) and `RUN-STATE.md`; mark tasks; commit the docs and the validation log; push

## Dependencies & execution order

- Phase 1 → Phase 3 (US1) → Phase 4 (US3; T012 commits US1 and US3 code together) → Phase 5 (US2) → Phase 6.
- T003 and T014 are long background runs (about 20 min each); nothing is committed, switched or rebuilt during them.
  T015 can be written while T014 runs (scratchpad only). T016 runs after T014. T018 runs after T016.

## Parallel opportunities

- T010 ∥ T011. T013 ∥ T015 (writing), both while T014 runs.

## Implementation strategy

MVP = US1 (the candidate rule with its tests). US3 is a check that the existing source reporting covers the new
items. US2 is the acceptance evidence. Then the user's hands-on test; merge only on the user's go.
