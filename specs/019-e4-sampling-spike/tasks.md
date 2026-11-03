# Tasks: Elite Four Sampling Spike

**Input**: Design documents from `/specs/019-e4-sampling-spike/`

**Prerequisites**: plan.md, spec.md, research.md (R1-R8), data-model.md, contracts/scripts.md, quickstart.md

**Tests**: requested by the spec (FR-006, SC-002): fast-mode unit tests of the pure functions, written before the
scripts that use them. No `battle_sim` tests are added; the measurements are tasks, not tests.

**Organization**: by user story. US1 (estimator on stored evidence) is the MVP and needs no new battles. US2 (two
recordings and the replay) and US3 (time share, projection, go / no-go) each run alone on the machine.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T014, T015, T020, T021) never run in parallel with anything: machine idle, Eastern start and end
  times in the validation log, raw output under `runs/019-evidence/`.

## Path Conventions

- Scripts: `specs/019-e4-sampling-spike/scripts/` (never `src/` or `sim/`; FR-001)
- Tests: `tests/unit/test_e4_estimator.py` (fast mode, imports the scripts by path; 018 precedent)
- Evidence: `runs/019-evidence/`; log: `specs/019-e4-sampling-spike/validation-log.md`

---

## Phase 1: Setup

**Purpose**: the evidence and script directories, and the before-hashes the whole feature is checked against.

- [X] T001 Create `specs/019-e4-sampling-spike/scripts/hooks/` and `runs/019-evidence/timing/` (with a `.gitkeep`), and start `specs/019-e4-sampling-spike/validation-log.md` with the branch point (`main` 1ca9bb3), the Eastern start time, and the output of `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` as the before-hashes (FR-001, SC-007)
- [X] T002 [P] Write `specs/019-e4-sampling-spike/scripts/common.py`: `load_stored(dir) -> StoredEvaluation` reading `result.json` (fields per data-model.md: n_runs, clear_rate, clear_ci95, per_battle battles and rate per trainer, champion_rate, champion_battles, champion_ci95, budget_preset, threshold, qualified, borderline, final_level_gap_max, provenance.champion.status) with the validations `per_battle.cynthia.battles <= n_runs` and `champion_battles >= per_battle.cynthia.battles`; `dedup(stored_list)` grouping by (species+levels, master seed, n_runs, clear_rate) and filling `duplicate_of` (R8); `assert_idle()` (`pgrep -x node`, `pgrep pytest`, raise with the offending lines); `eastern_now()`; `SPEC_DIRS` = the ten directories from the spec

---

## Phase 2: Foundational

**Purpose**: the statistics every story uses, tested before any script calls them.

- [X] T003 Write the pure functions in `specs/019-e4-sampling-spike/scripts/e4_estimator.py`: `wilson_bounds(k, n, level)` (reuses `platsim.stats.wilson_ci` with z for 95% and 97.5%: 1.95996 and 2.24140), `product_interval(e4_bounds, cyn_bounds) -> (L_e4*L_cyn, U_e4*U_cyn)` (R1), `delta_interval(p1, n1, p2, n2)` (log-scale delta method, informational), `verdict(estimate, interval, preset, threshold, gap) -> (threshold_verdict, full_verdict)` applying exactly the `evaluate.py` rule: borderline when lower < threshold <= upper; qualified when not borderline, `preset.qualifying`, estimate >= threshold, half-width <= `preset.ci_half_width`, gap <= 10 (R2), plus `disagreement_kind(stored_full, composite_full, composite_threshold)` returning `agree`, `threshold` or `half-width only` and `runs_needed` via `platsim.stats.runs_needed` for the half-width-only case
- [X] T004 Write `tests/unit/test_e4_estimator.py` for T003 (loaded by path like `tests/unit/test_paired_policies.py`): Wilson bounds at both levels against `platsim.stats.wilson_ci`; product interval is contained in the product of 95% intervals' complement direction (wider) and ordered; delta interval narrower than Bonferroni on a sample; verdict rule reproduces three hand cases (qualified, borderline, below) and the gap rule; `disagreement_kind` classifies a same-side wide interval as `half-width only` with a positive `runs_needed`; run `uv run pytest -q tests/unit/test_e4_estimator.py` and record the output in the log

**Checkpoint**: the interval and verdict functions are tested; stories can start.

---

## Phase 3: User Story 1 - The composite estimate reproduces the stored verdicts (Priority: P1) 🎯 MVP

**Goal**: one table over the ten stored evaluations with the composite estimate, Bonferroni and delta intervals,
half-width ratio, containment and verdict agreement, plus the positive control and the not-estimable case.

**Independent Test**: `uv run python specs/019-e4-sampling-spike/scripts/e4_estimator.py --out runs/019-evidence/estimator.json` exits 0 with
`contains_stored` and `agreement` true on every row, or exits 1 listing each disagreement's kind and `runs_needed`;
`--control` prints the synthetic case with a differing verdict.

- [X] T005 [US1] Add `composite(stored, kind)` to `specs/019-e4-sampling-spike/scripts/e4_estimator.py` (kind `topup` uses champion_rate and champion_battles, kind `fullrun` uses per_battle.cynthia; e4_pass = per_battle.cynthia.battles / n_runs; returns a CompositeEstimate per data-model.md with `contains_stored`, both verdicts, `agreement`, `disagreement_kind`, `half_width_ratio`; raises or marks `not_estimable` when champion_status is `no_reach` or the Cynthia count is 0), the CLI (`--dirs`, `--threshold`, `--out`, `--control`), the printed table (one row per directory, duplicates marked from `common.dedup`, the `fullrun` identity check shown as a column), and the exit-code rule from contracts/scripts.md
- [X] T006 [P] [US1] Extend `tests/unit/test_e4_estimator.py`: the positive control (synthetic stored result with Elite Four pass 0.70 over 2,000 and Cynthia 0.95 over 1,400 must give threshold verdict `below` while a naive Cynthia-only rule would qualify, SC-002), the not-estimable case (`no_reach`, Cynthia battles 0) reported not guessed, and the `fullrun` identity (`estimate == clear_rate` within 1e-9 on a synthetic result built from consistent counts); run the file and record the output
- [X] T007 [US1] Run the estimator over the ten spec directories: `uv run python specs/019-e4-sampling-spike/scripts/e4_estimator.py --out runs/019-evidence/estimator.json` and `--control`; copy the table and exit code into the validation log; state per row the disagreement kind if any and `runs_needed` (R2); note the duplicate groups (R8)
- [ ] T008 [US1] Commit 1 on the branch: `feat(019): composite Elite Four estimator checked against ten stored evaluations` (scripts, test, evidence, log); push

**Checkpoint**: question (1) is answered with numbers. If any `threshold` disagreement occurred, record it as the
kill of the follow-on's statistic and still complete US2 and US3 for the record (Principle V).

---

## Phase 4: User Story 2 - The adaptive rule replayed on recorded runs (Priority: P2)

**Goal**: two 2,000-run recordings (reference fixture, bench-010 B3) and the offline replay at floors 0.98, 0.99,
0.995 over 200 orders, with the Cynthia-only share, agreement fractions, banked states and the unvalued count.

**Independent Test**: `e4_replay.py` on each recording prints the per-floor summary; reference: at least one floor
with median Cynthia-only share >= 0.5, verdict_agrees 100%, contains_full >= 95%; B3: switch_k null everywhere,
estimate equals the full clear rate.

- [X] T009 [P] [US2] Write `specs/019-e4-sampling-spike/scripts/record_runs.py` per contracts/scripts.md: `--team ref|b3|file:<json>` (ref = `tests/fixtures/reference_team.json` builds; b3 = `runs/bench-010/B3/result.json` team.builds at their recorded levels), `--runs 2000`, `--workers 16`, `--master 019-record-<team>`, `--out`; `common.assert_idle()` first; `platsim.evaluate.run_full_gauntlets(pool, team, master=..., min_runs=runs, max_runs=runs, target=None, player_policy=DEFAULT_PLAYER_POLICY, log="summary")`; header line with provenance (worker hello fields, both code hashes, policies, Eastern start/end) then one JSON line per run in index order (run index, seed, cleared, battles with trainer/won/end/turns/log_hash/state_before for Cynthia, final_levels); validate 2,000 lines, indices in order, `state_before` on every Cynthia battle
- [X] T010 [P] [US2] Write the pure functions in `specs/019-e4-sampling-spike/scripts/e4_replay.py` (R3): `switch_point(runs_in_order, floor)` (per Elite Four member, battles faced and won so far; a member not reached in a lost run is not counted; k = first run after which every member's Wilson 95% lower bound >= floor; None if never), `composite_after(runs_in_order, k)` (e4 pass over the k full runs; Cynthia wins/battles = Cynthia battles in runs 1..k plus the recorded Cynthia outcome of every later run that reached her; `unvalued` = later runs that lost before Cynthia; Bonferroni interval and verdict from `e4_estimator`), `banked_states(runs_in_order, k)` (distinct `state_before` JSON among Cynthia battles in runs 1..k), `orders(n, count, seed="019-replay")` (identity as order 0, then seeded permutations), and the CLI (`--recording`, `--floors`, `--orders 200`, `--seed`, `--out`) printing the per-floor summary from data-model.md (min/p5/median/p95/max of switch_k and share, fractions contains_full and verdict_agrees, unvalued, banked states, identity row, Cynthia turns per battle vs full-gauntlet turns)
- [X] T011 [P] [US2] Extend `tests/unit/test_e4_estimator.py` for the replay: a synthetic recording with Lucian at 0.90 never switches at floor 0.98 over 2,000 runs; one with every member at 1.0 switches at the first n where the Wilson 95% lower bound of n/n >= floor (assert the exact n for 0.98, 0.99, 0.995 computed from `platsim.stats.wilson_ci`); `composite_after` counts the unvalued runs and reproduces the full clear rate when k = n; `banked_states` counts distinct states; `orders` is deterministic for the seed and order 0 is the identity; run the file and record the output
- [X] T012 [US2] Record the reference team, alone: `uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team ref --out runs/019-evidence/recording-ref.jsonl` (about 13 min); log Eastern start/end, the header line's provenance, clear rate and per-trainer rates (expected near 0.94 clear, Lucian 1.000)
- [X] T013 [US2] Record B3 at its recorded levels, alone: `... --team b3 --out runs/019-evidence/recording-b3.jsonl` (about 13 min); log as T012 (expected near 0.77 clear, Lucian near 0.89)
- [X] T014 [US2] Replay both: `uv run python specs/019-e4-sampling-spike/scripts/e4_replay.py --recording runs/019-evidence/recording-ref.jsonl --out runs/019-evidence/replay-ref.json` and the same for b3; copy both per-floor summaries into the validation log and state the pass / fail of SC-003 (reference) and SC-004 (B3) with the numbers, plus the Cynthia-battle cost in turns relative to a full gauntlet
- [X] T015 [US2] Commit 2: `feat(019): two 2,000-run recordings and the adaptive-rule replay` (scripts, tests, recordings, replay outputs, log); push

**Checkpoint**: question (2) is answered; the switch-point distributions feed the projection.

---

## Phase 5: User Story 3 - In-stage time share, projection, go / no-go (Priority: P3)

**Goal**: the Elite Four share of wall time on the pool at the level search's batch sizes with a digest-checked
harness, the projected savings on the two baselines, and the recorded decision for feature 021.

**Independent Test**: `time_share.py` reports `digests_equal` true for every team and batch and the share per team
and batch with the kill flag; `projection.py` prints the two ratio ranges and the decision figure; FUTURE-FEATURES
section 8 carries the go / no-go with its numbers.

- [X] T016 [P] [US3] Write `specs/019-e4-sampling-spike/scripts/hooks/register.mjs` (`register('./hooks.mjs', import.meta.url)`) and `hooks/hooks.mjs`: a `load` hook that, only for the URL ending in `/sim/gauntlet.mjs`, returns the source with (a) `process.hrtime.bigint()` before and after each battle's `while (!battle.ended)` loop, (b) a counter of the player policy's `choose` calls inside that battle, and (c) `appendFileSync` of one JSON line `{pid, seed, battle_index, trainer, turns, decisions, ns}` to `${process.env.PLATSIM_TIMING_DIR}/${process.pid}.jsonl`; every other module passes through unchanged; the stdout response is untouched (R4, FR-010)
- [X] T017 [P] [US3] Write `specs/019-e4-sampling-spike/scripts/time_share.py` per contracts/scripts.md: `--teams ref,b3,b2v2` (b2v2 = `runs/018-evidence/b2-expectimax2-v2/result.json` team.builds), `--batches 50,100,200`, `--workers 16`, `--out`; `common.assert_idle()`; per team and batch build requests `{"op":"gauntlet","team":..., "seed": derive_seed("019-time-<team>", i, 0), "player_policy": DEFAULT_PLAYER_POLICY, "opponent_policy": "decomp-ai", "stop_on_loss": True, "log": "summary"}`, run them plain (`WorkerPool(workers)`) and hooked (`WorkerPool(workers, env={**os.environ, "NODE_OPTIONS": "--import <abs>/hooks/register.mjs", "PLATSIM_TIMING_DIR": "<abs>/runs/019-evidence/timing"})`), compute `platsim.bench`'s pool-side `digest_logs` for both result lists and stop with exit 2 on inequality; on equality read the side files, aggregate per trainer (battles, turns, decisions, battle_s), compute `e4_share_battle`, `e4_share_wall` (wall × workers), `overhead_s`, and the kill flag (strong team, batch 200, share < 0.40); delete the side files after reading; write the JSON and print the table
- [X] T018 [US3] Smoke the harness, alone: `time_share.py --teams ref --batches 5 --out runs/019-evidence/time_share_smoke.json`; log `digests_equal`, the per-trainer rows and that the side files were written and removed; fix the hook if the digests differ before any larger run
- [X] T019 [US3] Run the measurement, alone: `uv run python specs/019-e4-sampling-spike/scripts/time_share.py --out runs/019-evidence/time_share.json` (three teams × 50/100/200, about 8 min); log Eastern start/end, every `digests_equal`, the share table, overhead, and the kill flag with its number (SC-005, R5)
- [X] T020 [P] [US3] Write `specs/019-e4-sampling-spike/scripts/projection.py` (R6): inputs `--time-share`, `--replay-ref`, `--replay-b3`, `--baseline-eval 769`, `--baseline-b2quick 350`, `--out`; t_full and t_cyn from the reference team's batch-200 rows (mean wall per full gauntlet = wall / batch; Cynthia battle time = cynthia battle_s / cynthia battles); evaluate projection per floor = (k × t_full + (2000 − k) × t_cyn) / 16 + top-up time derived in the script (Cynthia battles needed to meet the preset's count rule, her count above every other trainer's, and half-width target, minus Cynthia battles already reached, times t_cyn), over p5..p95 of k; B2 quick bracketed by the strong (ref) and Lucian-heavy (b3) replays through the quick preset's batches 50 → 100 → 200 and the 500-run confirmation; prints both ratio ranges, the inputs, "bracket, not a measurement" beside the B2 quick range, and the decision figure (reference-team evaluation ratio)
- [X] T021 [US3] Run `uv run python specs/019-e4-sampling-spike/scripts/projection.py --out runs/019-evidence/projection.json`; copy the ranges and inputs into the validation log (SC-006)
- [X] T022 [US3] Write the go / no-go record: in `FUTURE-FEATURES.md` section 8 under the E4 scope bullet, the three answers with their numbers (Q1 agreement count and disagreement kinds; Q2 reference best floor share and agreement fractions, B3 never switching; Q3 strong-team batch-200 share and kill flag), both projection ranges, the verdict for feature 021 by the clarified rule (go iff Q1 and Q2 pass on the threshold verdict, strong-team share >= 0.40, reference evaluation ratio >= 1.5; the B2 quick ratio reported, not deciding), and on no-go the fallback order from the concept note; the same record as the closing section of the validation log (FR-013)
- [X] T023 [US3] Commit 3: `feat(019): in-stage Elite Four time share, projection and the go/no-go record for 021` (scripts, hooks, evidence, FUTURE-FEATURES, log); push

**Checkpoint**: all three questions answered and recorded.

---

## Phase 6: Polish, gates and merge

- [X] T024 [P] Record the feature in `README.md` (one paragraph after the 018 block: what was measured, the three numbers, the decision; no behaviour change) and `RUN-STATE.md` START HERE (state, hashes, next feature)
- [ ] T025 Gates, in order, nothing else running: (a) `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` equals the T001 before-hashes; (b) `git diff --stat main -- sim src/platsim` is empty; (c) `(cd sim && node --test test/*.test.mjs)` green (replay fixture and determinism tests included); (d) `uv run pytest -q -m "not battle_sim"` green with the battle split clean; log each output with Eastern times and the sentence that the full suite is skipped because (a) and (b) hold (clarification 3, SC-007)
- [ ] T026 Commit 4: `docs(019): README, RUN-STATE, gates recorded`; push; report to the user with the go / no-go and the numbers. Merge to `main` only on the user's go (`git checkout main && git merge --ff-only 019-e4-sampling-spike && git push`)

---

## Dependencies

- **Setup → Foundational → US1 → US2 → US3 → Polish** in that order for the measurements and commits; the scripts
  and tests inside US2 and US3 can be written while an earlier measurement runs only if nothing is committed and no
  suite is run during it (the project's rule), so in practice: write T009-T011 before starting T012; write T016, T017
  and T020 before T018.
- US1 depends on T003 (estimator functions); US2's replay depends on `e4_estimator` for the interval and verdict;
  US3's projection depends on US2's replay outputs and US3's own time share.
- T025 depends on everything before it; T026 on T025.

## Parallel execution examples

- Phase 1: T002 beside T001.
- US1: T006 (tests) beside T005 (composite and CLI), different files.
- US2: T009, T010, T011 in parallel (three files); then T012 and T013 strictly sequential and alone; T014 after both.
- US3: T016, T017, T020 in parallel (three files); T018 then T019 alone; T021 after T019 and T014.
- Polish: T024 beside T022/T023 editing different files (README/RUN-STATE vs FUTURE-FEATURES/log).

## Implementation strategy

- **MVP = US1** (T001-T008): no new battles, answers the question that can kill the method. Stop and report if a
  `threshold` disagreement appears, then still complete US2 and US3 for the record.
- **Increment 2 = US2**: the two recordings are the feature's only large battle cost (about 26 min); the replay is
  seconds and can be re-run with other floors or seeds without new battles.
- **Increment 3 = US3**: the harness is smoke-checked on 5 requests before the 8-minute measurement; the projection
  and the go / no-go record close the feature.
- Size: 26 tasks, three stories, four commits, about 35 minutes of measurement in total; within the project's size
  rule.
