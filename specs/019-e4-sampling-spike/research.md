# Research: Elite Four Sampling Spike

All decisions below resolve the plan's open points; none changes behaviour under `sim/` or `src/platsim`.

## R1. Conservative interval for the product of two proportions

- **Decision**: the pass-criterion interval is the product of per-factor Wilson bounds at 97.5% each (z = 2.2414):
  lower = L_e4 × L_cyn, upper = U_e4 × U_cyn, where (L_e4, U_e4) is the Wilson interval of the Elite Four pass count
  over the run count and (L_cyn, U_cyn) the Wilson interval of Cynthia's wins over her battles (top-up-inclusive for
  the pass criterion, per the clarification; full-run-only as the input check). Both bounds are products of monotone
  bounds, so the joint coverage is at least 95% by the Bonferroni argument (two 97.5% events). A second,
  less conservative interval is reported for information only: the delta method on the log scale
  (var(log p) ≈ var(p1)/p1² + var(p2)/p2², back-transformed), so the follow-on can see what the conservatism costs.
- **Rationale**: the spec asks for a documented, simple method with no new statistics; Wilson intervals and their
  half-widths already exist in `platsim.stats`; Bonferroni is the simplest argument that makes "conservative" a
  provable statement rather than a hope.
- **Alternatives considered**: product of two 95% Wilson intervals (joint coverage only ≥ 90.25%, rejected as not
  conservative); exact or bootstrap intervals for the product (more machinery than the spike warrants; the delta
  interval is reported instead); Fieller-type intervals (for ratios, not products).

## R2. Verdict rule applied to the composite

- **Decision**: the estimator applies the project's rule exactly as `evaluate.py` does, on the composite interval:
  `borderline` when lower < threshold ≤ upper; `qualified` when not borderline, the preset is qualifying, the
  estimate ≥ threshold, the composite half-width ≤ the preset's target (0.02 standard, 0.015 thorough) and the
  stored `final_level_gap_max` ≤ 10; otherwise not qualified. Two verdicts are reported per stored result: the
  **threshold verdict** (qualified / borderline / below, ignoring the half-width target) and the **full verdict**
  (with the half-width target). SC-001's pass check is on the threshold verdict; the full verdict is reported, and every full-verdict
  disagreement is classified: "threshold" (the composite puts the team on the other side of 0.75 or straddling when the stored
  result did not) versus "half-width only" (same side, interval too wide), and the table reports, for half-width-only
  cases, the run count at which the composite would meet the target (`platsim.stats.runs_needed` on the composite's
  effective proportion). A half-width-only disagreement is a cost, not a wrong answer; the go record states which
  kind occurred.
- **Rationale**: the composite interval is wider than the binomial one by construction (R1), so some stored
  `qualified` results may fail the 0.02 target under the composite at the same run count. Reporting the two layers
  keeps the spec's strict check while telling the follow-on how many more (cheap, Cynthia-only) runs the method needs
  for the same certainty.
- **Alternatives considered**: threshold verdict only (hides the run-budget cost); scaling the target for the
  composite (an invented rule).

## R3. The replay rule and how the Cynthia-only phase is valued offline

- **Decision**: for a recording (per-run, per-battle outcomes in run index order, stop-on-loss) and a run order
  (a permutation), the replay walks runs in that order. After each full run it updates, per Elite Four member, the
  battles faced and won so far (a member not reached in a lost run is not counted). The switch point k is the first
  run after which every member's Wilson 95% lower bound (platsim.stats.wilson_ci) is at or above the floor; floors
  0.98, 0.99, 0.995. Runs 1..k are full; runs k+1..2000 are Cynthia-only. The composite estimate at the end is
  (Elite Four pass count over the k full runs) × (Cynthia wins over Cynthia battles), where Cynthia's battles are:
  the Cynthia battles among the k full runs, plus, for each remaining run that reached Cynthia in the recording, its
  recorded Cynthia outcome (a real Cynthia battle from a real post-Lucian state, which is what the Cynthia-only phase
  would play). Remaining runs that lost before Cynthia in the recording contribute no Cynthia battle; their count is
  reported as "unvalued Cynthia-only battles" per order. The number of banked states at the switch is the number of
  distinct `state_before` among Cynthia battles in runs 1..k. 200 orders are permutations from a fixed seed
  (`random.Random("019-replay")`); the identity order is reported separately as order 0.
- **Rationale**: the replay must not simulate new battles (the spec's "offline"), and the recording's own Cynthia
  battles are the best available stand-in for the Cynthia-only phase: same team, same states, same opponent. The
  limitation is stated: the method would play a banked state again for runs that the recording lost early, and those
  outcomes are not in the recording. This is why the spike is a replay and feature 021 has a paired acceptance.
- **Alternatives considered**: valuing unvalued runs by drawing a banked state and re-using another run's Cynthia
  outcome (invents data); running real Cynthia-only battles from banked states (new battles; that is feature 021's
  job, and the existing top-up already shows the mechanism works).

## R4. The timing harness and its control

- **Decision**: `hooks/register.mjs` registers `hooks/hooks.mjs` through `node:module`'s `register` (the prof3/prof4
  mechanism); the `load` hook rewrites the source of `sim/gauntlet.mjs` in memory to wrap each battle's loop with
  `process.hrtime.bigint()` timing and a decision counter (the player policy's `choose` calls), and appends one JSON
  line per battle `{pid, seed, battle_index, trainer, turns, decisions, ns}` to a side file named by the worker's pid
  under the evidence directory. The worker's stdout response is untouched. The pool is started by `time_share.py`
  with `WorkerPool(env={**os.environ, "NODE_OPTIONS": "--import <abs path>/register.mjs"})`. Control: the same
  requests are run once plain and once hooked; `platsim.bench`'s pool-side `digest_logs` over both result lists must
  be identical before any share is computed, and the comparison is written to the evidence.
- **Rationale**: the hook never touches committed code (FR-001, FR-010), the worker protocol is unchanged, and the
  digest check is the positive control that the harness changed nothing but timing.
- **Alternatives considered**: adding timing fields to the worker response (changes `digest_full`; rejected);
  timing in the Python pool around each request (cannot split a gauntlet into battles; rejected); a single-process
  run with `bench.mjs` (not the pool setting the spec asks for).

## R5. Time-share measurement design

- **Decision**: for each of the three teams (reference fixture at its levels, B3 at its recorded levels, the 018 v2
  B2 team) and each batch size (50, 100, 200), submit that many requests in index order with `stop_on_loss: true`,
  `log: "summary"`, the default player, seeds `derive_seed("019-time-<team>", i, 0)`, on a 16-worker pool. Report per
  team and batch: wall time of the batch, summed battle time per trainer from the side files, Elite Four share of
  summed battle time and of wall time, turns and decisions per battle per trainer, and the pool overhead (wall minus
  summed battle time divided by 16). The 40% kill criterion is evaluated on the strong team's Elite Four share of
  summed battle time at batch 200.
- **Rationale**: matches the level search's batch sizes and stop-on-loss; the share of summed battle time is the
  quantity that the method can remove, the wall share shows what the user would see.

## R6. Projection

- **Decision**: with t_full (mean wall per full gauntlet) and t_cyn (mean wall per Cynthia battle) from R5 on the
  reference team, and the switch point k and Cynthia-only share from R3 at each floor: projected evaluate time =
  k × t_full + (2000 − k) × t_cyn + top-up time as today (computed from the same inputs: the top-up battle count
  implied by the count and half-width rules, times t_cyn; no external constant), over 16 workers, as a range across the three floors and the
  5th to 95th percentile of k over orders; ratio against 769 s. For B2 quick: the level search's batches (50 → 100 →
  200 at the quick preset) rarely reach the floor on a threshold team, so the projection uses the B2-team replay
  switch distribution (from the B3 recording as the Lucian-heavy stand-in and the reference recording as the strong
  stand-in, bracketing) and the confirmation stage's 500 runs; ratio against 350 s, reported as a range. The go rule
  from the clarification applies to the reference-team evaluation ratio.
- **Rationale**: a projection with named inputs and a range is what the spec asks for; it is labelled a projection.

## R7. Script layout and tests

- **Decision**: Python scripts under `specs/019-e4-sampling-spike/scripts/`, run with `uv run python`; pure
  functions (interval, verdict, replay step, switch-point search) in `e4_estimator.py` and `e4_replay.py`, imported
  by path in `tests/unit/test_e4_estimator.py` (the 018 `test_paired_policies.py` precedent), no `battle_sim` marker.
  The recording script reuses `platsim.evaluate.run_full_gauntlets` unchanged (team, master, min_runs = max_runs =
  2000, no CI extension) and writes the worker responses as JSON lines.
- **Rationale**: no change to the package; fast-mode tests cover everything the feature can break.

## R8. The ten stored evaluations

- **Decision**: the table lists each directory and groups duplicates by (team species and levels, master seed,
  run count, clear rate): `runs/job-20261008T235244Z-2d8f18` and `-c86e64` are one result; `runs/t076/v8` and
  `v8-rerendered` are one result (only v8 is in the spec's list); but neither partner is in the spec's list, so the ten listed directories are ten distinct results; the grouping
  is a guard, not a reduction. `runs/t076/v7-w16` (and `v7-w8`, not listed) is the reference fixture at level 60.
- **Rationale**: the spec's "all ten" is met by checking every directory; the duplicate grouping stops a repeated
  result from counting twice.
