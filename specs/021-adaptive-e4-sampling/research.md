# Research: Adaptive Elite Four Sampling in evaluate

## R1. Where the method lives

- **Decision**: a new module `src/platsim/sampling.py` with pure functions (`switch_index`, `e4_pass_stats`,
  `composite_estimate`, `delta_interval`, `extension_kind`, `start_index`) and one pool function
  `run_adaptive(pool, team, *, master, min_runs, max_runs, target, player_policy, floor, log="summary", on_batch)`
  returning an `AdaptiveRuns` record (full results, Cynthia-only results, switch_run, banked states, extension
  mix, target_met). `evaluate_team` gains `sampling: str = "full"` and `floor: float = 0.99`; `full` takes the
  existing path untouched.
- **Rationale**: the estimator and the switch rule are testable without battles; `evaluate.py` stays readable; the
  optimizer's calls keep the default and are unaffected.

## R2. Reserved battle index and the banked-state draw

- **Decision**: Cynthia-only sampling run k uses request seed `derive_seed(master, k, 98)` and the banked state
  `states[start_index(master, k, 98, len(states))]` with `start_index(master, k, battle_index, n) =
  int(sha256(f"{master}|{k}|{battle_index}|start_state")) % n`, the top-up's rule generalised (the top-up keeps 99).
  `seeds.py`'s docstring reserves 98. `k` counts Cynthia-only runs from 0; the bank is the list of `state_before` of
  every full run that reached Cynthia, in run order, as it stood at the switch (later full runs added by the
  extension append to it, and runs drawn after that use the grown bank: the draw index is a function of k and the
  bank size at the time of the draw, both determined by run order alone).
- **Rationale**: the same deterministic scheme the top-up has used since feature 001; no collision with full-run
  battles (index 0..4) or top-ups (99).

## R3. The switch rule and batch independence

- **Decision**: full runs are requested in chunks (`MIN_BATCH` or `pool.size * 8`, as `run_full_gauntlets`) and
  consumed in index order; after each run the per-member (faced, won) counts are updated for the four Elite Four
  members from that run's battles; `switch_index` is the first run index k after which every member has faced ≥ 1
  and `wilson_ci(won, faced, Z95)[0] >= floor`. Full results with index ≥ k are **discarded** (not counted anywhere)
  so that the result cannot depend on chunk size; the number discarded is reported in `sampling_detail.discarded`.
  Runs k.. are Cynthia-only until `min_runs` total runs (full + Cynthia-only) exist.
- **Rationale**: the same "consume in order, stop at the first index meeting the rule" discipline evaluate already
  uses for the CI extension; the waste is bounded by one chunk (at most 128 gauntlets).
- **Alternatives considered**: keeping the overshoot as extra full runs (result would depend on chunk size and
  worker count; rejected); chunk sizes of 1 near the predicted switch (slower; rejected).

## R4. The composite estimate and the delta interval

- **Decision**: `e4_pass = reached_full / full_runs` (Wilson 95% interval reported); `cyn = wins / battles` over all
  Cynthia battles: full-run Cynthia battles, Cynthia-only sampling runs and top-up battles; `estimate = e4_pass * cyn`;
  interval: `var = (1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2)` on the log scale, `[est * exp(-z s), min(1, est *
  exp(z s))]` with z = 1.96 (feature 019's `delta_interval`, moved into the package); when p1 or p2 is 0 the interval
  is [0, 0] and the verdict is not qualified. `borderline` = lower < threshold ≤ upper; `qualified` = not borderline,
  preset qualifying, estimate ≥ threshold, half-width (half the interval) ≤ target, gap ≤ 10. The reported `clear_rate` is the estimate and `clear_ci95` the delta interval; `n_runs` is full + Cynthia-only runs. When
  `switch_run` is None (the floor was never reached) the report keeps the full method's statistics: `clear_ci95` is the
  Wilson interval, `n_runs` the full-run count, and `sampling_detail` records the method with `switch_run: null`.
- **Rationale**: the owner's decision after the spike; today's rules apply unchanged to the new interval.

## R5. Run accounting and the extension rule (clarification 2)

- **Decision**: `n_runs = full_runs + cynthia_only_runs`; `min_runs` is met by that total. While the composite
  half-width > target and n < max_runs: if the floor is not met, add full gauntlets (chunk by `runs_needed` as today);
  if it is met, compute the half-width the composite would have with Cynthia's variance term removed (the Elite Four
  part alone, `hw_floor`); if `hw_floor < target`, add Cynthia-only runs (size from the Cynthia term needed, at least
  MIN_BATCH, capped); otherwise add a chunk of full gauntlets (which also bank states and add Cynthia battles) and
  re-evaluate. Each added full run is checked in order and the loop stops at the first n meeting the target (discarding the rest of
  the chunk), as today. Full gauntlets added after the switch continue the full-run index sequence from the switch run
  (k, k+1, …), requested and consumed in order and recomputed rather than taken from the discarded set, so the mix never
  depends on chunk size; Cynthia-only runs keep their own counter from 0 and later draws use the bank as grown by those
  full runs. `sampling_detail.extension` records the counts of each kind.
- **Rationale**: keeps the promise that the target is met when the cap allows, spends full gauntlets only when
  cheap runs cannot help, stays batch-independent.

## R6. The top-up under adaptive sampling

- **Decision**: `champion_topup(pool, team, full_results, *, master_seed, budget, extra_cynthia=(battles, wins))`:
  the Cynthia-only sampling runs are passed as already-played Cynthia battles so the count rule (her count above
  every other trainer's full-run count) and the half-width rule start from them; top-ups (index 99) are added only
  if those rules are still unmet (under adaptive sampling they almost never are). Top-up battles stay in Cynthia's
  conditional rate as today.
- **Rationale**: FR-011; the top-up's semantics and seeds are unchanged for `full`.

## R7. Loss causes and per-trainer rates

- **Decision**: `collect_loss_causes` runs over `full_results + cynthia_only_results`; Cynthia-only runs are
  requested with `log: "summary"` so each battle carries `state_before` (the banked state) and its own seed, and
  `replay_requests` already builds the one-battle replay from those. Per-trainer rates (`per_battle`) come from the
  full runs only; Cynthia's row in `per_battle` keeps the full-run meaning and the composite's Cynthia rate is
  reported separately in `sampling_detail`. Final levels and the gap come from cleared full runs only.
- **Rationale**: FR-008 and the spec's assumptions; no new replay code.

## R8. Report fields and backward compatibility

- **Decision**: `EvaluationReport.sampling: str = "full"` and `sampling_detail: dict | None = None` with keys
  `floor, full_runs, cynthia_only_runs, switch_run, discarded, banked_states, e4_pass_rate, e4_pass_ci95,
  cynthia_rate, cynthia_battles, composite_ci95, extension {full, cynthia_only}`; `from_dict` defaults them so results
  from before the feature read as `full`; provenance gets `"sampling": {...}` and the seeds block gains
  `"cynthia_only_seed": "derive_seed(master, k, 98)"`. xlsx: rows "Sampling method", and when adaptive, "Full runs",
  "Cynthia-only runs", "Switch run", "Banked states", "Elite Four pass rate [ci]", "Composite 95% CI"; csv: the
  same keys; web result view: `sampling` and the run mix beside `n_runs`. The byte-identity control strips the four sampling keys
  before comparing.
- **Rationale**: FR-007, SC-006; the existing fields keep their meaning.

## R9. CLI

- **Decision**: `evaluate --sampling {full,adaptive}` (default `full` until the owner's go, then flipped in one
  commit) and `--floor` (float in [0.9, 1.0], default 0.99, usage error outside); `platsim bench` and the optimizer
  are untouched.

## R10. Tests

- **Decision**: `tests/unit/test_sampling.py`: switch rule on synthetic runs (never at 0.90; the all-wins n for each
  floor; a member never faced stays unproven), `start_index` determinism and range, composite and delta interval
  (positive control: Elite Four pass 0.70 with Cynthia 0.95 → not qualified; identity when all runs are full),
  extension kind selection (Cynthia term limiting vs Elite Four term limiting), discard count. `tests/integration/
  test_evaluate_adaptive.py` (battle_sim): reference team, 80 runs, floor 0.9 (switch after about 36 full runs):
  fields present, switch happened, Cynthia-only runs > 0, result.json byte-identical for 8 and 3 workers, and
  floor 1.0 byte-identical to `--sampling full`; the existing `test_evaluate.py` unchanged (defaults to full).
  `test_reports.py`: round trip with `sampling_detail`; a JSON without the fields reads as full.

## R11. Acceptance script

- **Decision**: `specs/021-adaptive-e4-sampling/scripts/acceptance.py --teams bench,ref,b2main,b2branch,b2v2,b3
  --runs 2000 --workers 16`: for each team runs `evaluate_team` with `sampling="full"` then `"adaptive"` on the same
  master seed through one pool (refusing to start unless idle), writes both result.json files under
  `runs/021-evidence/<team>/{full,adaptive}/`, and prints the table (full estimate and interval, adaptive estimate
  and interval, containment, both verdicts and agreement, half-width ratio, Cynthia-only share, wall times and
  ratio); `--control` runs the reference team at 200 runs with floor 1.0 and asserts byte equality with full, and
  the top-up control (Cynthia rate from the sampling runs vs the top-up's on the same banked states within the
  binomial noise).

## R12. Merge gate and the default flip

- **Decision**: the full pytest suite and the Node suite before merge (behaviour change). The default flip is a
  separate final commit on the owner's go after the acceptance table: `--sampling` default and
  `evaluate_team`'s default become `adaptive`, README and tests updated accordingly; without the go the feature
  merges with `full` as the default.
