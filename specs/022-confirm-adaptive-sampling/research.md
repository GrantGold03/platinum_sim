# Research: Adaptive Sampling in the Optimizer's Confirmation Stage

## R1. Request fields, fingerprint and pre-feature checkpoints

- **Decision**: `OptimizeRequest.sampling: str = "full"` and `floor: float = DEFAULT_FLOOR` (0.98); `job_fingerprint`
  adds `"sampling"` only when it differs from `"full"` and `"floor"` only when it differs from `DEFAULT_FLOOR` (the 006
  and 018 precedent). Pre-feature checkpoints are refused without any new rule: state.json stores the code fingerprint
  (`version.code_fingerprint`, which includes `platsim_code_hash`) and `_State` refuses a differing one
  (`test_resume_refused_when_platsim_code_differs`). When the default later flips to adaptive, the same refusal applies
  because the flip is a code change.
- **Alternatives considered**: always writing both keys (changes every existing fingerprint; rejected).

## R2. The confirmation call and the borderline extension

- **Decision**: `_confirm` calls `evaluate_team(..., sampling=req.sampling, floor=req.floor)` with the same other
  arguments as today. The 021 guard ("adaptive sampling is not available in the optimizer's confirm stage") is removed;
  `evaluate_team` passes `extend_borderline` through to `run_adaptive(borderline_threshold, borderline_max_runs)`,
  which, after the min-runs and half-width phases, loops while the current interval straddles the threshold (the
  composite interval once a switch happened, the Wilson interval otherwise) and the total is below the cap
  (`min(max_runs, borderline_max_runs)`): each batch's kind comes from `extension_kind` (Cynthia-only while the
  Cynthia term limits, full gauntlets otherwise), batches are consumed in order and the loop stops at the first run
  after which the interval no longer straddles (the rest discarded and counted). Full runs added this way continue
  the full-run index sequence and grow the bank.
- **Rationale**: the same discipline as the full method's borderline loop and 021's half-width extension.

## R3. The runner-up on the same method

- **Decision**: under adaptive, the runner-up is run with `run_adaptive` at `min_runs = n_runs of the winner`, `target
  None`, the request's floor, master `f"{seed}|confirm"` (the same seeds as the winner), `log "summary"`; if it is
  better, it is confirmed with `evaluate_team(..., adaptive_runs=<those runs>)` (a new optional argument mirroring the
  existing `full=` reuse), so no battle is replayed. Under full, the code path is exactly today's.

## R4. Pairing (FR-004, the precise reading)

- **Decision**: `paired_outcomes(a, b)` takes the two evaluations' full results and Cynthia-only results and returns
  `(a_flags, b_flags, pairs, excluded)`: full runs are paired by run index for indices below `min(k_a, k_b)` (the same
  request seed `derive_seed(master, i, 0)` on both sides); Cynthia-only runs are paired by their ordinal for ordinals
  below `min(c_a, c_b)` where `c = n − k` (the same seed `derive_seed(master, j, 98)` on both sides, each team from its
  own banked state); every other run is excluded and counted (`|k_a − k_b|` full runs of the later-switching team and
  `|c_a − c_b|` Cynthia-only runs of the other). When neither switched, this is today's pairing exactly. The
  comparison record carries `pairs`, `excluded`, `full_pairs`, `cynthia_only_pairs`, the McNemar counts and p.
- **Rationale**: the spec's "same kind, same seed" principle; 021 seeds Cynthia-only runs by ordinal, so ordinal pairing
  is the seed-faithful one. The pairing control (R7) checks the full-kind half against the full method exactly.
- **Alternatives considered**: reseeding Cynthia-only runs by run index (a 021 behaviour change for no gain); pairing
  only full runs (throws away most pairs on strong teams).

## R5. Attempts, provenance, web

- **Decision**: each confirm attempt gains `sampling`, `full_runs`, `cynthia_only_runs`, `switch_run`, `banked_states`,
  `discarded` and `extension` from `rep.sampling_detail` (None for full). `provenance["sampling_per_stage"] =
  {"level_search": "full", "setup_check": "full", "confirm": req.sampling, "floor": req.floor}` beside
  `policy_per_stage`. The winner's result.json already carries the 021 fields through `evaluate_team`; the web result
  view shows them as for evaluate (no change).

## R6. CLI

- **Decision**: `optimize --sampling {full,adaptive}` (default from `OptimizeRequest`) and `--floor` (default 0.98,
  usage error outside [0.9, 1.0]); `optimize_request` passes both.

## R7. Acceptance script

- **Decision**: `specs/022-confirm-adaptive-sampling/scripts/acceptance.py` with four blocks: (1) `b2quick`: two
  `platsim optimize` runs (the 014 B2 species, quick, the 018 B2 seed, 16 workers) with `--sampling full` and
  `--sampling adaptive`, into `runs/022-evidence/b2quick-{full,adaptive}/`; compares team species, moves, items and
  levels, the confirmation's estimate/interval containment both ways, the verdict, the 010 equal-levels comparison
  (`specs/018-expectimax2-v4/scripts/equal_levels.py` by path), the runner-up record (pairs, excluded, p) and the wall
  times (confirm stage from state.json timing, whole run); (2) `confirm`: the confirmation call as `_confirm` makes it
  (`evaluate_team` with `extend_borderline`, the standard preset, master `021-acc|confirm`) on the 014 b2-main and
  bench-010 B3 teams, full then adaptive, with containment, verdict, run mix and wall ratio; (3) `resume`: a quick optimize started as a subprocess on the same request into a fresh directory, killed (SIGTERM) once
  state.json shows stage `confirm` with runs_done > 0, then rerun to completion and compared byte for byte with block (1)'s
  adaptive result.json. The confirm stage checkpoints after each attempt, not after each batch, so the kill discards the
  attempt in progress and the resumed run recomputes it from its start with the same seeds; the control proves that the
  recomputation and the level-search checkpoint give the same result, which is what FR-006's "inside the stage" means; (4) `pairing`: the 014 b2-main and b2-branch teams run with `run_full_gauntlets` (2,000 paired) and with
  `run_adaptive` (2,000, floor 0.98), the McNemar counts on the full-kind pairs compared with the full method's counts
  on the same indices (exact equality), plus the excluded counts.

## R8. Tests

- **Decision**: `tests/unit/test_confirm_pairing.py`: `paired_outcomes` on synthetic evaluations (neither switched,
  both switched at different k, one switched; exclusion counts; a positive control where team A wins every full pair
  and a negative control with identical outcomes), and `run_adaptive`'s borderline extension on the 021 fake pool
  (straddling then resolved; cap reached; batch independence). `test_optimizer_resume.py`: sampling and floor in the
  fingerprint only when non-default; another sampling is a different job. `tests/integration/test_optimize_adaptive.py`
  (battle_sim): quick optimize on the reference-team species with `--sampling adaptive --floor 0.9`, 8 and 3 workers:
  byte-identical result.json, `sampling == "adaptive"` with a switch run in the confirm attempt, `sampling_per_stage`
  present; about 20 minutes, like `test_optimize_small`.

## R9. Merge gate and the default flip

- **Decision**: the full pytest suite and the Node suite before merge. The default flip, only on the owner's go after
  the acceptance table: `OptimizeRequest.sampling` default → `DEFAULT_SAMPLING`, the CLI default, README and the tests
  that pin the default (the existing optimize tests pass `--sampling full` explicitly from then on).
