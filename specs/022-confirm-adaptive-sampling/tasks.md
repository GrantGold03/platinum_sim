# Tasks: Adaptive Sampling in the Optimizer's Confirmation Stage

**Input**: Design documents from `/specs/022-confirm-adaptive-sampling/`

**Prerequisites**: plan.md, spec.md (one clarification), research.md (R1-R9), data-model.md, contracts/optimize-cli-and-state.md,
contracts/pairing-api.md, quickstart.md

**Tests**: requested by the spec (FR-010): fast-mode unit tests for the pairing rule (with controls), the request fields and
fingerprint rule, and the borderline extension on the 021 fake pool, written before the optimizer is wired; a `battle_sim`
integration test; the existing optimize and resume tests kept green.

**Organization**: by user story. US1 is the confirmation on the 021 method behind the flag (the MVP); US2 the paired
runner-up comparison; US3 the acceptance, docs and the default flip on the owner's go.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- Measurements (T011, T017, T020, T021) run alone on the machine with Eastern start and end times in the validation log;
  no commit or suite while one runs; raw evidence under `runs/022-evidence/` (local, gitignored), small files copied to
  `specs/022-confirm-adaptive-sampling/evidence/`.

## Path Conventions

- Package: `src/platsim/` (behaviour change: `platsim_code_hash` changes; `sim/` untouched)
- Tests: `tests/unit/`, `tests/integration/` (battle_sim marker on the integration test only)
- Feature scripts: `specs/022-confirm-adaptive-sampling/scripts/`; log: `specs/022-confirm-adaptive-sampling/validation-log.md`
- The B2 quick request (018 validation log T030): `platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2`

---

## Phase 1: Setup

- [X] T001 Create `specs/022-confirm-adaptive-sampling/scripts/`, `specs/022-confirm-adaptive-sampling/evidence/`, `runs/022-evidence/`, and start `specs/022-confirm-adaptive-sampling/validation-log.md` with the branch point (`main` 93ac7c8), the Eastern start time and the before-hashes from `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` (sim hash must be unchanged at the end, FR-011)

---

## Phase 2: Foundational

**Purpose**: the pure pairing function, the borderline extension in `run_adaptive`, and their tests, before the optimizer is touched.

- [X] T002 Write `src/platsim/optimizer/pairing.py` (contracts/pairing-api.md, R4): `PairedOutcomes` (frozen dataclass: `a_flags`, `b_flags`, `full_pairs`, `cynthia_only_pairs`, `excluded`, property `pairs`) and `paired_outcomes(a_full, a_cyn, b_full, b_cyn)`: full runs paired by run index for `i < min(len(a_full), len(b_full))` with flags `cleared`; Cynthia-only runs paired by ordinal for `j < min(len(a_cyn), len(b_cyn))` with flags `battles[0]["won"]`; `excluded = (len(a_full) + len(b_full) - 2 * full_pairs) + (len(a_cyn) + len(b_cyn) - 2 * cynthia_only_pairs)`; a module docstring stating why ordinal pairing is seed-faithful (021 seeds Cynthia-only run j with `derive_seed(master, j, 98)`)
- [X] T003 Extend `src/platsim/sampling.py` (contracts/pairing-api.md, R2): `run_adaptive(..., borderline_threshold: float | None = None, borderline_max_runs: int | None = None)`; after the half-width phase, while `straddles()` (the composite interval once `switch` is set, the Wilson interval otherwise: `lo < borderline_threshold <= hi`) and `n < min(max_runs, borderline_max_runs or max_runs)`: `kind = extension_kind(...)`, batch size `min(max(n // 2, MIN_BATCH), room)` as `run_full_gauntlets` does, consume in order (full runs continue the index sequence and grow the bank; Cynthia-only runs use the next ordinals), stop at the first run after which the interval no longer straddles and discard the rest (counted); set `AdaptiveRuns.borderline_extended` (new field, default False) and add the batches' kinds to `extension`; log the straddle messages as the full method does
- [X] T004 Write `tests/unit/test_confirm_pairing.py`: `paired_outcomes` with neither team switched (all full pairs, excluded 0: today's pairing), both switched at different k (full pairs = min k, Cynthia-only pairs = min c, excluded = |k_a − k_b| + |c_a − c_b|), one switched (Cynthia-only pairs 0, that team's Cynthia-only runs excluded); the **positive control** (team A clears every full pair, B none: McNemar verdict A on the paired flags) and the **negative control** (identical outcomes: 0 discordant); and `run_adaptive`'s borderline extension on the 021 `_FakePool` pattern from `tests/unit/test_sampling.py` (a scripted stream straddling 0.75 at first and resolving later: `borderline_extended` True, the extension counts, the loop stops at the first non-straddling run, byte-equal results for pool sizes 4 and 16; the cap reached while still straddling leaves `borderline_extended` True and the straddle unresolved); run `uv run pytest -q tests/unit/test_confirm_pairing.py` and record the output

**Checkpoint**: the pairing and the borderline extension are tested; the optimizer can be wired.

---

## Phase 3: User Story 1 - The confirmation stage on adaptive sampling (Priority: P1) 🎯 MVP

**Goal**: `platsim optimize --sampling adaptive --floor F` runs the confirmation on the 021 method; state.json and
result.json carry the run mix and the sampling per stage; the fingerprint rule and determinism hold.

**Independent Test**: quickstart step 2 (the hand check on the reference species with floor 0.9 at two worker counts) and
the battle_sim integration test.

- [X] T005 [US1] `src/platsim/optimizer/api.py`: `OptimizeRequest.sampling: str = "full"` and `floor: float = DEFAULT_FLOOR` (import from `platsim.sampling`), validated in `__post_init__` (`sampling in ("full", "adaptive")`, `FLOOR_MIN <= floor <= FLOOR_MAX`); `src/platsim/optimizer/run.py` `job_fingerprint`: `fp["sampling"] = req.sampling` only when it differs from `OptimizeRequest.sampling`'s default, `fp["floor"] = req.floor` only when it differs from `DEFAULT_FLOOR` (R1)
- [X] T006 [US1] `src/platsim/evaluate.py`: remove the 021 guard (`adaptive sampling is not available in the optimizer's confirm stage`); pass `borderline_threshold=threshold if extend_borderline else None` and `borderline_max_runs` to `run_adaptive`; add `adaptive_runs: AdaptiveRuns | None = None` to `evaluate_team` (reused like `full=`: when given with `sampling="adaptive"`, no runs are made); set `full.extended` from the half-width and borderline extensions; provenance `runs_extended_while_borderline` as for the full path
- [X] T007 [US1] `src/platsim/optimizer/run.py` `_confirm`: call `evaluate_team(..., sampling=req.sampling, floor=req.floor)` for the winner (and for every bump); each attempt record gains `sampling`, `full_runs`, `cynthia_only_runs`, `switch_run`, `banked_states`, `discarded`, `extension` from `rep.sampling_detail` (None/0 for full); `prog("confirm", ...)` detail names the method; provenance in the result gains `"sampling_per_stage": {"level_search": "full", "setup_check": "full", "confirm": req.sampling, "floor": req.floor}` beside `policy_per_stage` (R5); the level search and the setup check are untouched (FR-007)
- [X] T008 [P] [US1] `src/platsim/cli.py`: `optimize --sampling {full,adaptive}` (default `OptimizeRequest.sampling`'s default) and `--floor` (default `DEFAULT_FLOOR`; usage error exit 2 outside [0.9, 1.0]); `optimize_request` passes both (R6)
- [X] T009 [P] [US1] Extend `tests/unit/test_optimizer_resume.py`: the fingerprint carries `sampling` and `floor` only when they differ from the defaults (default request unchanged from before this feature, apart from nothing); a request with `sampling="adaptive"` is a different job from the default (refused in the same out dir, as the 018 policy test); the `--sampling` and `--floor` CLI defaults match the request's (parse `["optimize", *species]`)
- [X] T010 [US1] Write `tests/integration/test_optimize_adaptive.py` (`@pytest.mark.battle_sim` on the one test): `platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed t022 --sampling adaptive --floor 0.9 --workers 8` and `--workers 3` into two directories (the `test_optimize_small.py` helper pattern, `platsim.cli`): byte-identical result.json; state.json's last confirm attempt has `sampling == "adaptive"`, a `switch_run` and `cynthia_only_runs > 0`; result.json has `sampling == "adaptive"` and `provenance.sampling_per_stage` with `confirm == "adaptive"`; run it (about 20 min, alone) and record the output
- [X] T011 [US1] Hand check per quickstart step 2 (alone, about 10 min): the quick optimize on the reference species with floor 0.9 at 8 workers into `runs/022-evidence/hand/a`; log the confirm attempt's run mix, the comparison record and `sampling_per_stage` (the 3-worker byte check is T010's)
- [X] T012 [US1] Commit 1: `feat(022): adaptive sampling in the optimizer's confirmation stage behind --sampling (default full)` (pairing module, sampling extension, evaluate, api, run, cli, tests, log); push

**Checkpoint**: the confirmation works on the 021 method behind the flag; `full` is unchanged and the default.

---

## Phase 4: User Story 2 - The runner-up comparison stays paired (Priority: P2)

**Goal**: under adaptive, the runner-up runs on the same method and the comparison pairs by kind and seed, with the
counts reported; a better runner-up is confirmed from its own runs.

**Independent Test**: the pairing unit tests (T004) plus, on real runs, the pairing control in the acceptance (block 4).

- [X] T013 [US2] `src/platsim/optimizer/run.py` `_confirm`, runner-up branch: under `req.sampling == "adaptive"` run the runner-up with `run_adaptive(pool, worker_team(ru_real.team, led), master=master, min_runs=rep.n_runs, max_runs=rep.n_runs, target=None, player_policy=req.player_policy, floor=req.floor)`; build the flags with `paired_outcomes(ev.results, ev.cynthia_only_results, ru.full_results, ru.cynthia_only_results)`; `mcnemar_exact` on the flags; the comparison record gains `pairs`, `excluded`, `full_pairs`, `cynthia_only_pairs` (and keeps `n_paired = pairs`); when the runner-up is better, confirm it with `evaluate_team(..., sampling=req.sampling, floor=req.floor, adaptive_runs=ru)` (no new battles); under `full` the branch is today's code (R3, R4)
- [X] T014 [US2] Add to `tests/unit/test_confirm_pairing.py` a test that the comparison record built by a small helper in `run.py` (`_comparison_record(cmp, paired)`) carries the four new keys and `n_paired == pairs`; run the file
- [X] T015 [US2] Commit 2: `feat(022): runner-up comparison paired by kind and seed under adaptive sampling`; push

---

## Phase 5: User Story 3 - Acceptance, docs and the default (Priority: P3)

**Goal**: the four acceptance blocks with their numbers, the docs, and the default flip only on the owner's go.

**Independent Test**: the acceptance script prints pass or fail per block; `optimize --help` and the README state the
current default; the existing optimize tests pass unchanged.

- [X] T016 [US3] Write `specs/022-confirm-adaptive-sampling/scripts/acceptance.py` (R7): blocks selectable with `--blocks b2quick,confirm,resume,pairing`; the 019 `common.assert_idle` by path; **b2quick**: two `platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16` subprocesses with `--sampling full` and `--sampling adaptive` into `runs/022-evidence/b2quick-{full,adaptive}/`, then compare species, moves, items and levels (a level difference with a borderline flip is recorded, not failed, while containment holds: the clarification), containment of each confirmation's estimate in the other's interval, verdicts, the equal-levels comparison via `specs/018-expectimax2-v4/scripts/equal_levels.py` by path (quick count), the comparison records (pairs, excluded, p) and the wall times (confirm stage from state.json `timing` when it holds a confirm entry, otherwise the whole-run wall only with a note; whole run from the script's clock around each subprocess) with ratios; **confirm**: on the 014 b2-main and bench-010 B3 teams (team.builds through `evaluate.load_and_validate` on a temp JSON, as 021's script does), `evaluate_team(..., runs=2000, seed="022-acc|confirm", budget="standard", extend_borderline=True, borderline_max_runs=4000, sampling=...)` full then adaptive at floor 0.98: containment, verdict, run mix, wall ratio; **resume**: the b2quick adaptive request into a fresh directory as a subprocess, polled every 5 s, SIGTERM once state.json shows stage `confirm` with `runs_done > 0` (the confirm stage checkpoints per attempt, so the resumed run recomputes the interrupted attempt from its start; fall back to killing after the level search if the confirm stage is too short to catch), rerun to completion, byte comparison with the b2quick adaptive result.json; **pairing**: 014 b2-main and b2-branch with `run_full_gauntlets` (2,000, master `022-pair|confirm`) and with `run_adaptive` (2,000, floor 0.98): McNemar counts on the full-kind pairs under adaptive equal the full method's counts on the same indices exactly; excluded counts reported; `--out` JSON and a printed table per block; exit 1 on any failed check
- [X] T017 [US3] Run the acceptance alone (about 1 h): `uv run python specs/022-confirm-adaptive-sampling/scripts/acceptance.py --out runs/022-evidence/acceptance.json > runs/022-evidence/acceptance.txt`; copy the four blocks into the validation log with Eastern start and end; state SC-001 to SC-004 per block; copy `acceptance.json`, `acceptance.txt` and the result.json files to `specs/022-confirm-adaptive-sampling/evidence/`
- [X] T018 [US3] Commit 3: `feat(022): acceptance (B2 quick both ways, confirm alone on two teams, resume control, pairing control)` (script, evidence, log); push
- [X] T019 [P] [US3] Docs: `README.md` (the optimize command row gains `--sampling` and `--floor`; a feature-022 block after 021's with the stage, the pairing rule, the acceptance numbers and the current default), `FUTURE-FEATURES.md` section 8 (022 done, numbers, default status, the level search and setup check as the remaining follow-on if a measurement earns it), `RUN-STATE.md` START HERE
- [ ] T020 [US3] Present the acceptance table to the owner and ask for the default decision (the only question in this feature); on "go": flip `OptimizeRequest.sampling`'s default to `DEFAULT_SAMPLING` in `src/platsim/optimizer/api.py`, the CLI default follows, the fingerprint rule keeps "only when non-default", `tests/integration/test_optimize_small.py` passes `--sampling full` explicitly (its meaning unchanged), `test_optimizer_resume.py`'s default assertions updated, README's default statement; log the decision; on "no": leave `full`, log the decision
- [ ] T021 Gates, in order, nothing else running: `sim_code_hash` equals the T001 before-hash and `git diff --stat main -- sim` is empty; `(cd sim && node --test test/*.test.mjs)` green; the full pytest suite `uv run pytest -q --durations=25 > runs/022-evidence/full.log 2>&1` green (about 1 h 20 min with the new 20-minute test); log each output with Eastern times
- [ ] T022 Commit 4: `docs(022): README, RUN-STATE, FUTURE-FEATURES, gates recorded` (plus, if the owner said go, its own commit `feat(022): adaptive sampling is the optimizer's confirmation default (user's go)` before the gates); push; report to the user. Merge to `main` only on the user's go (`git checkout main && git merge --ff-only 022-confirm-adaptive-sampling && git push`, or a merge commit if `main` moved)

---

## Dependencies

- Setup → Foundational (T002, T003 in parallel → T004) → US1 (T005 → T006 → T007; T008, T009 parallel with T007 once the
  field names exist; T010 after T007-T008; T011 after T010; T012) → US2 (T013 → T014 → T015) → US3 (T016 → T017 → T018;
  T019 ∥ T020 → T021 → T022).
- T020 blocks on the owner's answer; T021 runs on the final code (after the flip, if any); no commit during T010, T011,
  T017 or T021.

## Parallel execution examples

- Foundational: T002 (pairing module) beside T003 (sampling extension); T004 tests both.
- US1: T008 (CLI) and T009 (resume test) beside T007 (confirm wiring).
- US3: T019 (docs) beside T020 (the question).

## Implementation strategy

- **MVP = US1** (T001–T012): the confirmation on the 021 method behind the flag, verified by the integration test and
  the hand check.
- **Increment 2 = US2**: the paired runner-up comparison (small, pure function plus one branch).
- **Increment 3 = US3**: the acceptance (about 1 h alone), docs, the owner's decision, the full-suite gate, merge on the
  owner's go.
- Size: 22 tasks, three stories, four commits plus the optional flip, about 1 h of acceptance plus the 20-minute
  integration test and the 1 h 20 min full suite; one new small module plus edits to the optimizer, the sampling module
  and evaluate; within the project's size rule.
