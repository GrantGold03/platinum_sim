# Tasks: Adaptive Elite Four Sampling in evaluate

**Input**: Design documents from `/specs/021-adaptive-e4-sampling/`

**Prerequisites**: plan.md, spec.md (two clarifications), research.md (R1-R12), data-model.md, contracts/sampling-api.md,
contracts/cli-and-report.md, quickstart.md

**Tests**: requested by the spec (FR-014): fast-mode unit tests of the new module's pure functions written before the
module is wired into evaluate; a `battle_sim` integration test; the existing evaluate tests unchanged under
`--sampling full`; report round-trip tests for the new fields.

**Organization**: by user story. US1 is the method in `evaluate` behind the flag (the MVP); US2 the paired acceptance;
US3 the documentation and the default flip that only the owner's go can trigger.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T017, T018, T022) run alone on the machine with Eastern start and end times in the validation log;
  no commit or suite while one runs; raw evidence under `runs/021-evidence/` (local, gitignored), small files
  copied to `specs/021-adaptive-e4-sampling/evidence/`.

## Path Conventions

- Package: `src/platsim/` (behaviour change: `platsim_code_hash` changes; `sim/` untouched, `sim_code_hash` unchanged)
- Tests: `tests/unit/`, `tests/integration/` (battle_sim marker on the integration test)
- Feature scripts: `specs/021-adaptive-e4-sampling/scripts/`; log: `specs/021-adaptive-e4-sampling/validation-log.md`

---

## Phase 1: Setup

- [X] T001 Create `specs/021-adaptive-e4-sampling/scripts/`, `specs/021-adaptive-e4-sampling/evidence/`, `runs/021-evidence/`, and start `specs/021-adaptive-e4-sampling/validation-log.md` with the branch point (`main` c7cb162), the Eastern start time and the before-hashes from `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` (sim hash must be unchanged at the end, FR-015)

---

## Phase 2: Foundational

**Purpose**: the pure functions and their tests, before anything touches evaluate.

- [X] T002 Write the pure part of `src/platsim/sampling.py` (contracts/sampling-api.md): `E4 = ("aaron", "bertha", "flint", "lucian")`, `CYNTHIA_ONLY_BATTLE_INDEX = 98`, `switch_index(results, floor, members=E4)` (R3: per member faced/won over the runs in order; first k, as a 1-based run count, after which all four have faced ≥ 1 and `wilson_ci(won, faced, Z95)[0] >= floor`; None if never), `start_index(master, k, battle_index, n)` (R2: `int(sha256(f"{master}|{k}|{battle_index}|start_state").hexdigest(), 16) % n`), `e4_pass_stats(full_results)` → (reached, full_runs), `delta_interval(p1, n1, p2, n2, z=Z95)` (R4, [0, 0] when a proportion is 0, upper clamped to 1), `CompositeEstimate` dataclass (reached, full_runs, cyn_wins, cyn_battles, e4_pass, e4_ci95, cyn_rate, estimate, ci95, half_width) and `composite_estimate(reached, full_runs, cyn_wins, cyn_battles)`, `extension_kind(reached, full_runs, cyn_wins, cyn_battles, target, floor_met)` (R5: `"full"` when the floor is unmet or the half-width with Cynthia's variance term set to zero is ≥ target, else `"cynthia_only"`), `cynthia_only_request(team, master, k, bank, player_policy, opponent_policy)` (`{"op": "gauntlet", "team", "seed": derive_seed(master, k, 98), "trainers": ["cynthia"], "start_state": bank[start_index(master, k, 98, len(bank))], "player_policy", "opponent_policy", "stop_on_loss": True, "log": "summary"}`)
- [X] T003 Write `tests/unit/test_sampling.py` (no battle marker): `switch_index` never switches with a member at 0.90 over 2,000 synthetic runs, switches at the exact first n where `wilson_ci(n, n)[0] >= floor` for 0.9 / 0.98 / 0.99 / 0.995 when all win, treats a member never faced as unproven; `start_index` is deterministic and in range and equals the top-up's `_start_index` for battle index 99; `delta_interval` is narrower than the Bonferroni product and ordered, [0, 0] at a zero proportion; `composite_estimate` reproduces the full clear rate when every run is full (identity) and the **positive control**: Elite Four pass 0.70 (1,400 of 2,000) with Cynthia 0.95 gives an interval entirely below 0.75; `extension_kind` returns `"cynthia_only"` when Cynthia's term dominates and `"full"` when the Elite Four term alone exceeds the target or the floor is unmet; `cynthia_only_request` has the right trainers, seed index and log mode; run `uv run pytest -q tests/unit/test_sampling.py` and record the output
- [X] T004 Generalise `src/platsim/sim/champion.py`: `_start_index(master, k, n)` delegates to `sampling.start_index(master, k, TOPUP_BATTLE_INDEX, n)` (same hash, same results), and `champion_topup(..., extra_cynthia: tuple[int, int] = (0, 0))` starts its `n, w` counters at `reached + extra_battles, full_wins + extra_wins` so the count and half-width rules see the sampling runs (R6); `ChampionResult` gains `extra_battles: int = 0`; document battle index 98 in `src/platsim/sim/seeds.py`'s docstring; run `uv run pytest -q tests/unit -k "champion or topup or seeds"` and `tests/integration/test_champion_topup.py` is left for the full suite

**Checkpoint**: the estimator, the switch rule and the top-up change are tested; evaluate can be wired.

---

## Phase 3: User Story 1 - Evaluate a team faster with the same answer (Priority: P1) 🎯 MVP

**Goal**: `platsim evaluate --sampling adaptive --floor F` runs the method, writes the new fields in every report,
is byte-identical across worker counts, and equals `--sampling full` at floor 1.0.

**Independent Test**: quickstart steps 2 to 4 (hand check at 80 runs with floor 0.9, the floor-1.0 control, the
integration test).

- [X] T005 [US1] Write `run_adaptive(pool, team, *, master, min_runs, max_runs, target, player_policy, floor, on_batch=None) -> AdaptiveRuns` in `src/platsim/sampling.py` (R3, R5): request full runs in chunks (`MIN_BATCH` or `pool.size * 8`) in index order with `log: "summary"`, check `ok` and policies as `run_full_gauntlets` does, scan each chunk in order updating the member counts and the bank (every run that reached Cynthia appends its Cynthia `state_before`), stop at the switch index k, **discard** full results with index ≥ k (count them in `discarded`), then request Cynthia-only runs k.. until `min_runs` total; when the floor is never reached run full gauntlets to `min_runs` exactly as today; then the extension loop: while the composite half-width > target and total < max_runs, `extension_kind` decides the kind of the next batch (sizes: Cynthia-only from the Cynthia term needed, full from `runs_needed`, both at least `MIN_BATCH` and capped by `max_runs`), full batches are consumed in order with the first index meeting the target ending the loop (rest discarded), full runs added by the extension also feed the bank and use indices continuing from the switch run (k, k+1, …), recomputed in order; return `AdaptiveRuns(full_results, cynthia_only_results, switch_run, discarded, bank, extension, target_met)`
- [X] T006 [US1] Wire `src/platsim/evaluate.py`: `evaluate_team(..., sampling: str = "full", floor: float = 0.99)`; `sampling == "full"` is the existing path untouched; for `adaptive`: `run_adaptive`, then `champion_topup(..., extra_cynthia=(cynthia_only_battles, cynthia_only_wins))`, `collect_loss_causes(pool.map, wteam, full_results + cynthia_only_results, GAUNTLET)`, `per_battle_stats(full_results)`, `final_level_stats(full_results, ...)`, the composite from `composite_estimate(reached, full_runs, cyn_wins_all, cyn_battles_all)` (Cynthia battles = full-run + sampling + top-up), `clear_rate = estimate`, `clear_ci95 = delta interval`, `hw = half_width`, `n = full_runs + cynthia_only_runs`, the same borderline / qualified rule, warnings as today plus one when `discarded > 0`; `report.sampling`, `report.sampling_detail` (data-model.md keys), `provenance["sampling"]`, `seeds["cynthia_only_seed"] = "derive_seed(master, k, 98)"`; when `switch_run` is None use the full path's statistics (Wilson interval, today's rule) and fill `sampling_detail` with `switch_run: null`; `TeamEvaluation` gains `cynthia_only_results: list[dict] = []`; `evaluate(...)` passes the two new arguments through; the optimizer's two `evaluate_team` calls in `src/platsim/optimizer/run.py` are untouched (default `full`)
- [X] T007 [P] [US1] Report fields in `src/platsim/report/json_report.py`: `EvaluationReport.sampling: str = "full"`, `sampling_detail: dict | None = None`, included in `to_dict`, defaulted in `from_dict` so old JSON reads as full; `src/platsim/report/xlsx.py`: after "Runs (full gauntlets)" (renamed "Runs") add "Sampling method" and, when adaptive, "Full runs", "Cynthia-only runs", "Switch run", "Discarded past switch", "Banked states", "Elite Four pass rate", "Elite Four pass 95% CI low", "… high", "Composite 95% CI low", "… high"; `src/platsim/report/csv_report.py`: the same keys in the evaluation block; `src/platsim/web/result_view.py`: `sampling` and `sampling_detail` (full / Cynthia-only counts) in the view dict
- [X] T008 [P] [US1] CLI in `src/platsim/cli.py`: `evaluate --sampling {full,adaptive}` (default `full`, help names the reference) and `--floor` (float, default 0.99; usage error exit 2 outside [0.9, 1.0]); pass both to `evaluate(...)`; `summary_text` in `evaluate.py` prints the method and, when adaptive, "full F / Cynthia-only C runs, switch at S"
- [X] T009 [P] [US1] Extend `tests/unit/test_reports.py`: a round trip with `sampling="adaptive"` and a full `sampling_detail`; a JSON without the two keys reads as `sampling == "full"` and `sampling_detail is None`; the xlsx Evaluation sheet carries "Sampling method" and the adaptive rows when present; csv likewise
- [X] T010 [US1] Write `tests/integration/test_evaluate_adaptive.py` (`pytestmark = pytest.mark.battle_sim`, env `PLATSIM_EVALUATE_FAST_N` default 80): `platsim evaluate tests/fixtures/reference_team.json --runs 80 --seed t021 --budget quick --sampling adaptive --floor 0.9` with `--workers 8` and `--workers 3` → byte-identical result.json; `sampling == "adaptive"`, `switch_run` not None and below 80, `cynthia_only_runs > 0`, `n_runs == 80`, `sampling_detail` keys present, `provenance.sampling` present, loss causes present when any run lost; the same command with `--floor 1.0` → result.json identical to `--sampling full` on the same seed and count after removing the four sampling keys; run it with `uv run pytest -q tests/integration/test_evaluate_adaptive.py` and record the output
- [X] T011 [US1] Hand check per quickstart step 2 (alone): the 80-run adaptive evaluation into `runs/021-evidence/hand/` with 8 and 3 workers, the floor-1.0 control, and `uv run pytest -q tests/integration/test_evaluate.py -k determinism_fast` to show the full path is untouched; log the summary lines, the switch run, the run mix and the byte-equality checks
- [X] T012 [US1] Commit 1: `feat(021): adaptive Elite Four sampling in evaluate behind --sampling (reference: full)` (module, evaluate, champion, seeds docstring, reports, web view, CLI, tests, log); push

**Checkpoint**: the method works end to end behind the flag; `full` is unchanged and the default.

---

## Phase 4: User Story 2 - Reference-first acceptance on six teams (Priority: P2)

**Goal**: the paired table on six teams, the two controls, and the recorded wall-time ratios.

**Independent Test**: `acceptance.py` prints the table with containment and verdict agreement per team and the
controls pass.

- [ ] T013 [US2] Write `specs/021-adaptive-e4-sampling/scripts/acceptance.py` (R11): teams `bench` (`tests/fixtures/policy_benchmark_team.json` team), `ref` (`tests/fixtures/reference_team.json` builds), `b2main`, `b2branch` (014 result.json team.builds), `b2v2` (018 v2 result.json), `b3` (bench-010 B3 result.json); the 019 `common.assert_idle` by path; for each team, through one `WorkerPool(16)`, `evaluate_team(team_candidate, led, pool, runs=2000, seed="021-acc", budget="standard", sampling="full")` timed, then the same with `sampling="adaptive"` (floor from `--floor`, default 0.99), writing both result.json files under `runs/021-evidence/<team>/{full,adaptive}/`; table columns: full estimate [ci], adaptive estimate [ci], contained (adaptive estimate inside the full ci), verdict_full, verdict_adaptive (qualified / borderline / not_qualified), agree, hw_ratio, cynthia_only_share, switch_run, wall_full_s, wall_adaptive_s, ratio; summary: all contained, all agree, ratios; exit 1 on any team failing; `--control`: the reference team at 200 runs, floor 1.0 vs full identical after removing the four sampling keys, and the top-up control (the Cynthia rate of the sampling runs vs the top-up's rate on the same bank at the same count, within the binomial 95% noise); the team loader must build a validated TeamCandidate from each stored result the way `evaluate` does for a JSON team file (reuse `load_and_validate` on a temporary JSON written from `team.builds`)
- [ ] T014 [P] [US2] Add a fast-mode unit test to `tests/unit/test_sampling.py` for the acceptance script's pure helpers (table formatting, containment and agreement logic) loaded by path
- [ ] T015 [US2] Commit 2: `feat(021): acceptance script` (script, test); push
- [ ] T016 [US2] Run the controls alone: `uv run python specs/021-adaptive-e4-sampling/scripts/acceptance.py --control` (about 2 min); log the byte-equality and the top-up control numbers (SC-003)
- [ ] T017 [US2] Run the acceptance alone (about 40 min): `uv run python specs/021-adaptive-e4-sampling/scripts/acceptance.py --out runs/021-evidence/acceptance.json > runs/021-evidence/acceptance.txt`; copy the table into the validation log with Eastern start and end; state SC-001 and SC-002 per team; copy `acceptance.json`, `acceptance.txt` and the twelve result.json files to `specs/021-adaptive-e4-sampling/evidence/`; then, for any team whose switch run at 0.99 is above 1,000 or None, rerun that team's adaptive side with `--floor 0.98` and add the row
- [ ] T018 [US2] If any team fails containment or agreement: record the failure with its numbers (Principle V), do not flip the default, and continue to US3 with `full` as the default; if the floor-0.98 alternative is wanted for the record, run it on the two fixture teams only and log it
- [ ] T019 [US2] Commit 3: `feat(021): paired acceptance on six teams` (evidence, log); push

**Checkpoint**: the acceptance table exists; the owner can decide the default.

---

## Phase 5: User Story 3 - The default and the documentation (Priority: P3)

**Goal**: README, RUN-STATE, FUTURE-FEATURES and the help text describe the method, the flag, the fields and the
acceptance numbers; the default flips only on the owner's go.

**Independent Test**: `platsim evaluate --help` and the README state the current default; the existing evaluate
tests pass unchanged under `--sampling full`.

- [ ] T020 [P] [US3] Docs: `README.md` (the evaluate command row gains `--sampling` and `--floor`; a feature-021 block after 020's with the method, the fields, the acceptance table summary and the current default), `FUTURE-FEATURES.md` section 8 (021 done, numbers, default status, the optimizer stages as the next follow-on), `RUN-STATE.md` START HERE
- [ ] T021 [US3] Present the acceptance table to the owner and ask for the default decision (the only question in this feature); on "go": flip `--sampling`'s default and `evaluate_team`'s default to `adaptive` in `src/platsim/cli.py` and `src/platsim/evaluate.py`, update `tests/integration/test_evaluate.py` and `test_evaluate_adaptive.py` for the new default (the full-path tests pass `--sampling full` explicitly), README's default statement, and log the decision; on "no": leave `full`, log the decision
- [ ] T022 Gates, in order, nothing else running: `sim_code_hash` equals the T001 before-hash and `git diff --stat main -- sim` is empty; `(cd sim && node --test test/*.test.mjs)` green; the full pytest suite `uv run pytest -q --durations=25 > runs/021-evidence/full.log 2>&1` green (about 1 h; includes the new battle_sim test); log each output with Eastern times
- [ ] T023 Commit 4: `docs(021): README, RUN-STATE, FUTURE-FEATURES, gates recorded` (plus the default flip if the owner said go, as its own commit `feat(021): adaptive sampling is evaluate's default (user's go)`); push; report to the user. Merge to `main` only on the user's go (`git checkout main && git merge --ff-only 021-adaptive-e4-sampling && git push`)

---

## Dependencies

- Setup → Foundational (T002 → T003 → T004) → US1 (T005 → T006; T007, T008, T009 in parallel with T006; T010 after
  T006–T008; T011 after T010; T012) → US2 (T013 ∥ T014 → T015 → T016 → T017 → T018 → T019) → US3 (T020 ∥ T021 →
  T022 → T023).
- T021 blocks on the owner's answer; T022 after T021 so the gate runs on the final code; no commit during T016,
  T017 or T022.

## Parallel execution examples

- Foundational: none (T003 tests T002; T004 depends on T002's `start_index`).
- US1: T007 (reports), T008 (CLI), T009 (report tests) in parallel with each other once T006's field names exist.
- US2: T013 and T014 in parallel; T016 and T017 strictly sequential and alone.
- US3: T020 beside T021's question.

## Implementation strategy

- **MVP = US1** (T001–T012): the method behind the flag, verified by the integration test and the floor-1.0
  control; `full` untouched and the default.
- **Increment 2 = US2**: the paired acceptance (about 45 minutes of measurement) and the table.
- **Increment 3 = US3**: docs, the owner's decision on the default, the full-suite gate, merge on the owner's go.
- Size: 23 tasks, three stories, four or five commits, about 50 minutes of measurement plus the hour-long full suite;
  one package module plus edits to the evaluate pipeline and the report writers; within the project's size rule.
