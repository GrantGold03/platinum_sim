# Tasks: Variable-Power Moves Offered by the Optimizer

**Input**: Design documents from `/specs/024-variable-power-moves/`

**Prerequisites**: plan.md, spec.md (two clarifications), research.md (R1-R9), data-model.md, contracts/sim-helper-and-greedy.md,
contracts/candidates-api.md, quickstart.md

**Tests**: requested by the spec (FR-001, FR-003, FR-006, SC-001 to SC-003): Node tests of the shared helper against the
decomp tables and of greedy's scoring; Python tests of the weight reader (with Node parity), the per-opponent values and the
additive prefix against a pre-feature snapshot; the existing replay, determinism and `ai_cmds_damage` tests as the
unchanged-behaviour guard.

**Organization**: by user story. US1 is the shared helper and the screening player (the MVP: the screen can value the
moves, nothing else changes); US2 the optimizer offering them additively; US3 the acceptance on both codes and the docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T002, T019, T023) run alone on the machine with Eastern start and end times in the validation log; no
  commit or suite while one runs; raw evidence under `runs/024-evidence/` (local, gitignored), small files copied to
  `specs/024-variable-power-moves/evidence/`. Never pipe a gating command into `tail`.

## Path Conventions

- Battle code: `sim/` (behaviour change: `sim_code_hash` changes); package: `src/platsim/` (`platsim_code_hash` changes);
  ledger: `src/platsim/divergence/mechanics.py` + `data/divergences.json`
- Tests: `sim/test/`, `tests/unit/`, `tests/integration/`
- Feature scripts: `specs/024-variable-power-moves/scripts/`; log: `specs/024-variable-power-moves/validation-log.md`
- The B2 quick request: `platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16`

---

## Phase 1: Setup and the pre-feature side

**Purpose**: record today's behaviour while the branch's code still equals `main` (R8), before any code change.

- [X] T001 Create `specs/024-variable-power-moves/scripts/`, `specs/024-variable-power-moves/evidence/`, `runs/024-evidence/`; start `specs/024-variable-power-moves/validation-log.md` with the branch point (`main` cf4a9ff), the Eastern start time, `git diff --stat main -- src sim tests pyproject.toml` (must be empty) and the before-values of `sim_code_hash`, `platsim_code_hash` and the ledger version
- [X] T002 Write `specs/024-variable-power-moves/scripts/acceptance.py --side main` (contracts/candidates-api.md): `assert_idle` (019 helpers via `sys.path`), then (a) `optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16 --force-new --out runs/024-evidence/b2-main` as a subprocess with wall time; (c) the 014 b2-main team written from `runs/014-evidence/b2-main/result.json` to `runs/024-evidence/teams/b2main.json` (022 pattern) and `evaluate` of `tests/fixtures/reference_team.json` and of that team with `--runs 200 --budget quick --seed 024-ident --workers 16` into `runs/024-evidence/ident-main/{ref,b2main}` (compared later with the code-version and ledger fields removed: `sim_code_hash`, `platsim_code_hash`, `repo_commit`, `repo_dirty`, `divergence_ledger_version`, `divergence_ledger_file_version`, `provenance.worker.divergence_ledger_version`, `divergences`); the candidate snapshot: for each of the six B2 species, `candidates.member_candidates(...)` with exactly the arguments the optimizer uses in `run._build_cands` for the B2 quick job (species constant, variant key, `ref_level`, legality options, `k`), serialised as `{"call": {species, variant, ref_level, legality, k}, "movesets": [[move...]], "setup_moveset": [...], "ranked_prefix": first 210, "pool": [...]}` per species to `specs/024-variable-power-moves/evidence/b2-candidates-main.json` (T013 reproduces the call from the recorded arguments); record `platsim_code_hash`, `sim_code_hash` and `repo_commit` from each result.json in the log; **run it now, alone** (about 12 min), log Eastern times; commit `docs(024): pre-feature evidence (B2 quick on main's code, identity evaluations, candidate snapshot)` and push

---

## Phase 2: Foundational

**Purpose**: the shared helper in `sim/` with the two existing callers moved onto it, behaviour unchanged.

- [X] T003 Write `sim/variable_power.mjs` (contracts/sim-helper-and-greedy.md): move `parseWeightToPower`/`WEIGHT_TO_POWER` and `parseWeightOverrides`/`speciesWeightHg` from `sim/ai/calcdamage.mjs` (same code, same caching), add `weightTierPower(weightHg)` (loop: first `WEIGHT_TO_POWER[i][0] >= weight`, else 120), `returnPower(f)` (`Math.trunc(f * 10 / 25)`), `frustrationPower(f)`, `gyroBallPower(a, d)` (`a === 0 ? 0 : Math.min(150, 1 + Math.floor(25 * d / a))`); header citing `battle_script.c:6808-6828, 7123-7133`, `weight_to_power.h`, `effect_script_0121.s`
- [X] T004 `sim/ai/calcdamage.mjs`: import and re-export `WEIGHT_TO_POWER` and `speciesWeightHg` from the helper; the AI switch's Return/Frustration, Low Kick/Grass Knot and Gyro Ball cases call `returnPower`/`frustrationPower`, `weightTierPower(speciesWeightHg(...))`, and `gyroBallPower` **after** its existing throw on missing speeds or zero attacker speed (u32 semantics preserved: compare the old and new expressions on the test values); `sim/policy/expectimax2.mjs` `variablePower`: the same four cases call the helper (Gyro Ball keeps returning 0 on zero speed); run `(cd sim && node --test test/ai_cmds_damage.test.mjs test/ai_adapter.test.mjs test/expectimax2.test.mjs)` and record

**Checkpoint**: one source of truth; existing tests green.

---

## Phase 3: User Story 1 - The screening player values the four moves (Priority: P1) 🎯 MVP

**Goal**: greedy-v1 scores Return, Grass Knot, Low Kick and Gyro Ball at their computed power; recorded results
byte-identical; the ledger records the weight-tier boundary.

**Independent Test**: `sim/test/variable_power.test.mjs` (helper vs decomp tables; greedy scoring) and the replay,
determinism and `ai_cmds_damage` tests unchanged.

- [X] T005 [P] [US1] Write `sim/test/variable_power.test.mjs` part 1: `weightTierPower` for weights 1, 100 (20), 101 (40), 250 (40), 251 (60), 500 (60), 1000 (80), 2000 (100), 2001 (120), 4600 (120); `speciesWeightHg` Snorlax 4600, Pikachu 60, Flareon 250 (the boundary case, R7); `returnPower(255)` 102, `(0)` 0; `frustrationPower(255)` 0; `gyroBallPower` (100, 436) = 109, (100, 516) = 129, a cap case = 150, attacker faster = 1, `a = 0` → 0; `WEIGHT_TO_POWER` deep-equal to the decomp table; run and record
- [X] T006 [US1] `sim/policy/greedy.mjs` `expectedDamage` (contracts/sim-helper-and-greedy.md): resolve the decomp move constant of `sdId` (the existing `decompMove` gives the record; the constant via `gd.fromSdMove.get(sdId)`); for `MOVE_RETURN`, `MOVE_GRASS_KNOT`, `MOVE_LOW_KICK`, `MOVE_GYRO_BALL` compute `power` (`returnPower(attacker.happiness ?? 255)`; `weightTierPower(speciesWeightHg(ENUMS.species[foe.species.num]))`, the `ENUMS` import as expectimax2 does; `gyroBallPower(attacker.storedStats.spe, foe.storedStats.spe)`) and return the mean roll × accuracy of `calcDamage(fromShowdown(battle, attacker, foe, sdId, { power }))`; every other move with `md.power <= 1` still returns 0; header note: the four moves, the stat-at-level speed approximation (R2), friendship 255
- [X] T007 [US1] `sim/test/variable_power.test.mjs` part 2: on a `leagueBattle` (`sim/test/ai_fixtures.mjs`) with a player build carrying `return`, `grass_knot`, `low_kick` and `gyro_ball` (Snorlax 60 vs Flint, then vs Bertha for Rhyperior), `expectedDamage` for each equals the mean roll × accuracy of `calcDamage(fromShowdown(..., { power: <helper value> }))` and is > 0; `expectedDamage` for Frustration and Magnitude is 0; `greedy.choose` on a move request for a Snorlax 60 with `return`, `tackle`, `rest`, `yawn` against Flint's lead picks `move 1` (Return, 102 with STAB, the only strong attack by construction); run and record
- [X] T008 [P] [US1] Ledger: add `mech-weight-tier-boundary` (data-model.md: area mechanics, accepted, `decomp_ref` `pokeplatinum/src/battle/battle_script.c:6815` + `pokeplatinum/include/data/battle/weight_to_power.h:1`, `showdown_ref` `pokemon-showdown/data/moves.ts:10449` + `:7541`, impact: Flareon 250 hg game 40 vs engine 60, the player's model and the optimizer follow the decomp, `test_id` `sim/test/variable_power.test.mjs`) to `src/platsim/divergence/mechanics.py`; `uv run platsim divergences`; add the id to `tests/integration/test_divergences.py`; run `uv run pytest -q tests/integration/test_divergences.py -m "not battle_sim"` (exit code kept) and record
- [X] T009 [US1] Set guard: `(cd sim && node --test test/replay.test.mjs test/determinism.test.mjs test/gauntlet.test.mjs test/bench.test.mjs test/ai_cmds_damage.test.mjs)` green (digests, choices and draw counts unchanged); then the whole Node suite; record counts; Commit 2 `feat(024): shared variable-power helper in sim/; greedy-v1 scores Return, Grass Knot, Low Kick, Gyro Ball; weight-tier ledger entry`; push

**Checkpoint**: the screen can value the four moves; nothing recorded changed.

---

## Phase 4: User Story 2 - The optimizer offers the four moves additively (Priority: P2)

**Goal**: per-opponent power in candidate scoring; today's sets first and unchanged; up to K extra sets; the not-offered
list stated.

**Independent Test**: `tests/unit/test_variable_power.py`: weight pins and Node parity, per-opponent values, the additive
prefix against `evidence/b2-candidates-main.json`.

- [X] T010 [P] [US2] Write `src/platsim/decomp/weights.py`: `species_weight_hg(species_const)` reading `pokeplatinum/res/pokemon/<lower>/data.json` (`pokedex_data.weight_kilograms`, else `weight_pounds` minus the `species_weight_rounding_override` entry parsed from `pokeplatinum/tools/dataproc/src/speciesproc.c`, × 0.45359237; `round(kg * 10)`), cached; `weight_tier_power(weight_hg)` (the decomp loop); `gyro_ball_power(atk_spe, def_spe)` (`0 if atk_spe == 0 else min(150, 1 + 25 * def_spe // atk_spe)`); module doc citing the decomp lines and the Node mirror
- [X] T011 [US2] `src/platsim/optimizer/candidates.py` (contracts/candidates-api.md, R4): `LeagueOpponent` named tuple `(species, types, weight, level, iv, nature)` and `league_opponents()` returning them from `trainers.json` party entries (`level`, `iv`, `nature`); `FRIENDSHIP = 255`, `OFFERED_VARIABLE`, `NOT_OFFERED_VARIABLE` reason table (Hidden Power: IVs uniform 15 by assumption; Frustration: 1 at friendship 255; Magnitude, Wring Out, Crush Grip, Punishment, Flail, Reversal, Fling, Trump Card, Natural Gift, Present, Spit Up: no player computes them; fixed-damage and counter moves); `variable_power(move_const, member_species, member_level, opp)`: Return 102, Grass Knot / Low Kick `weight_tier_power(species_weight_hg(opp.species))`, Gyro Ball `gyro_ball_power(member_spe, opp_spe)` with `calc_stats` (member: base stats, IV 15, EV 85, `NATURE_HARDY`, `member_level`; opponent: its base stats, `iv` for every stat, EV 0, its nature, its level); `move_value(const_member, move_const, member_level)` uses the per-opponent power for offered variable moves and `m.power` otherwise; update the callers (`held_item_candidates` passes its level; `src/platsim/optimizer/resources.py` `_slot_cost` passes the reference level it knows, else the build's level) and let `held_item_candidates`'s best-attack pick accept the four moves
- [X] T012 [US2] `member_candidates` (R5, FR-006, FR-006a): after today's `pool`, `chosen`, setup variant and `ranked` are computed unchanged, `variable = [m for m in legal if m in OFFERED_VARIABLE]`; if any: `extra_combos` = `itertools.combinations(sorted(set(pool) | set(variable)), 4)` filtered to those containing >= 1 variable move, sorted by `(-coverage, -sum score, combo)` with per-opponent values; `extras` = up to `k` in rank order each differing from every other extra by >= 2 moves (`len(set(a) ^ set(b)) // 2 >= 2`); `movesets = chosen + extras`; `ranked = today's ranked + extra_combos` (prefix unchanged); items computed for every set; `summary()` gains `variable_offered` and `extras`; the B2 species with no legal variable move get exactly today's output
- [X] T013 [US2] Write `tests/unit/test_variable_power.py`: `species_weight_hg` Snorlax 4600, Pikachu 60, Flareon 250; Node parity for every League party species (`node -e` importing `sim/variable_power.mjs` and printing `speciesWeightHg` for the list; compare); `weight_tier_power` on the T005 values; `gyro_ball_power` (100, 436) = 109, cap, zero; `variable_power` for Grass Knot against Bertha's Rhyperior = 120 and Flint's Flareon = 40, Return = 102, Gyro Ball for a slow member vs a fast opponent > a fast member vs a slow one; `move_value(..., level)` returns one value per League opponent; every move in `NOT_OFFERED_VARIABLE` is absent from every B2 species' candidate lists; **the additive prefix**: for each of the six B2 species, `member_candidates(...)` called with the `call` arguments recorded in `evidence/b2-candidates-main.json` gives `movesets[:len(snapshot.movesets)] == snapshot.movesets`, `setup_moveset == snapshot`, `ranked[:210] == snapshot.ranked_prefix`, `pool == snapshot.pool`, and `extras >= 1` where a variable move is legal; run with the exit code kept and record
- [X] T014 [US2] Hand check (quickstart step 4): print the six B2 species' candidate lists on the branch (today's sets, then the extras naming their variable move) into `runs/024-evidence/b2-candidates-branch.txt` and copy to `evidence/`; run `uv run pytest -q -m "not battle_sim" > runs/024-evidence/fast.log 2>&1; echo exit=$?` (about 10 min) and record the summary line; Commit 3 `feat(024): optimizer offers Return, Grass Knot, Low Kick, Gyro Ball in an additive candidate list (per-opponent power; today's sets unchanged)`; push

**Checkpoint**: the optimizer offers the moves; today's lists are a prefix.

---

## Phase 5: User Story 3 - The B2 winner is not worse at equal levels (Priority: P3)

**Goal**: the acceptance table on both codes; the equal-levels verdict; docs.

**Independent Test**: the table is complete; the identity rows are byte-identical; the equal-levels row passes FR-009 or the
cause is recorded and the merge is blocked.

- [X] T015 [P] [US3] Write `specs/024-variable-power-moves/scripts/equal_levels.py` (adapted from `specs/018-expectimax2-v4/scripts/equal_levels.py`, not called by path): `<b_dir> <a_dir> <runs> [--self]`; B = the first dir's `result.json["team"]`, A = the second's; both at A's `start_level`s, written to `<a_dir>/equal_{a,b}.json` and validated with `load_and_validate`; `WorkerPool(None)`; `run_full_gauntlets(..., master="024-equal|B2", min_runs=max_runs=runs, target=None, player_policy="expectimax2-v4")` for both (today's default style); `mcnemar_exact(A, B)`, `final_level_stats` means; JSON on stdout with n, rates, only-A/only-B, p, verdict, mean final levels, wall; `--self` exits 1 on discordant pairs
- [X] T016 [US3] `acceptance.py --side branch`: (a) B2 quick into `runs/024-evidence/b2-branch` (`--force-new`); (d) members of both winners whose set carries one of the four moves (from `team.builds[*].moves`); (c) the identity evaluations into `runs/024-evidence/ident-branch/{ref,b2main}` with the same requests as the main side, compared with `ident-main` after removing the code-version and ledger fields listed in T002 (a JSON comparison, not `cmp`; the removed fields are printed with both values); (b) `equal_levels.py runs/024-evidence/b2-main runs/024-evidence/b2-branch 2000`; the pass rule (FR-009): `verdict != "B"` (no supported loss at alpha 0.05) and `b2-branch result.json expected_avg_final_level - b2-main result.json expected_avg_final_level <= 1.0` (the two optimizer winners' own values; the equal-levels run supplies only the paired clear-rate test, its mean final levels are reported for information); print the table (both winners' species, moves, items, levels, confirmation clear rate and interval, n, wall, code hashes; the equal-levels row; the identity rows) and write `runs/024-evidence/acceptance.json`
- [X] T017 [US3] Acceptance run alone (about 15 min, Eastern times): `uv run python specs/024-variable-power-moves/scripts/acceptance.py --side branch --workers 16 > runs/024-evidence/acceptance.txt 2> runs/024-evidence/acceptance.err; echo exit=$?`; copy `acceptance.txt`, `acceptance.json`, both winners' `result.json` and `team.txt`, and the equal-levels JSON to `specs/024-variable-power-moves/evidence/acceptance/`
- [X] T018 [US3] If the equal-levels row fails FR-009: no merge; inspect both winners' candidate lists per member (`summary()` in state.json's `prune` stage) for the displaced set, record the finding in the validation log and FUTURE-FEATURES section 1 as the open cause, and stop at the report to the user (the fix is a new decision); if it passes: continue
- [ ] T019 [US3] Validation log: the acceptance table with the reading (which members took a variable move, the paired verdict and level difference, wall times); README: the rule (the four moves, their formulas and sources), the offered and not-offered lists with reasons, the friendship assumption, the weight-tier ledger entry, a feature-024 block with the numbers, the `candidates` note in the optimizer description; FUTURE-FEATURES section 1 (slice 3 built; the archived regression's cause as measured) and section 6 (Magnitude group still open); RUN-STATE START HERE; Commit 4 `feat(024): acceptance (B2 quick on both codes, equal-levels paired check, identity evaluations); docs`; push

---

## Phase 5b: The screen superset (user's decision after the first acceptance, 2026-11-09)

- [X] T022 [US3] `src/platsim/optimizer/run.py` screen stage (FR-006b): `_member_options` splits each member's options into today's (movesets before the `extras` suffix) and the extras; the baseline, the single-slot deviations and the RNG fill use today's options only (identical combos to today's for the same request); after the cap, append one single-slot deviation per extra set with its first item, repaired / validated / deduplicated as the others; `state.json` screen stage records `extras_screened`; provenance notes the rule
- [ ] T023 [US3] `acceptance.py --side branch`: after the run, compare the first 81 screened teams of `b2-branch/state.json` with `b2-main/state.json` (`screen.candidates`, as specs) and report `screen_prefix_identical` and the number of appended teams; rerun the acceptance alone (T017 again, about 15 min) and record; the FR-009 rule decides
- [X] T024 [US3] Fast tests touched by the screen change (`uv run pytest -q tests/unit/test_optimizer_resume.py tests/unit/test_required_hms.py tests/unit/test_legality_options.py -m "not battle_sim"`) green before the rerun

## Phase 6: Gates and close

- [ ] T020 Gates, in order, nothing else running: `git diff --stat main -- pokemon-showdown` empty; after-values of `sim_code_hash`, `platsim_code_hash` and the ledger version recorded and asserted different from the T001 before-values (FR-007: pre-feature checkpoints are refused by the code fingerprint); `(cd sim && node --test test/*.test.mjs)` green; the full pytest suite `uv run pytest -q --durations=25 > runs/024-evidence/full.log 2>&1; echo full exit=$?` green (about 1 h 25 min); each output with Eastern times into the log; copy a gates summary to `specs/024-variable-power-moves/evidence/gates.txt`
- [ ] T021 Closing commit `docs(024): gates recorded; feature closed on its branch`; push; report to the user with the merge command (`git checkout main && git merge --ff-only 024-variable-power-moves && git push`, or a merge commit if `main` moved). Merge only on the user's go

---

## Dependencies and execution order

- Phase 1 (T001 → T002, **before any code change**) → Phase 2 (T003 → T004) → US1 (T005 ∥ T008 → T006 → T007 → T009)
  → US2 (T010 → T011 → T012 → T013 → T014) → US3 (T015 ∥ T016 → T017 → T018 → T019) → T020 → T021.
- T002 must run while `git diff --stat main -- src sim tests pyproject.toml` is empty (the pre-feature side); T017 after
  T014's commit (the branch side); no commit during T002, T017 or T020's measured steps.
- T018 blocks the feature on a failed FR-009 (the user decides the next step).

## Parallel opportunities

- T005 ∥ T008; T010 can start while T005-T009 run (different files); T015 ∥ T016.

## Implementation strategy

- MVP = Phase 2 + US1: the screen values the moves with recorded results unchanged.
- US2 adds the offering; US3 measures it and writes the docs; the merge is conditional on the equal-levels check.
- Size: 21 tasks, three stories, two layers (sim helper and greedy; Python candidates and reader). Within the limits.
