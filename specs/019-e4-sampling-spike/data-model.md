# Data Model: Elite Four Sampling Spike

All entities are files or in-memory records produced by the feature's scripts; nothing is added to the package.

## StoredEvaluation (input, read from `runs/<dir>/result.json`)

| Field | Source | Notes |
|---|---|---|
| dir | path | the directory listed in the spec |
| n_runs | `n_runs` | may exceed 2,000 (extended runs) |
| clear_rate, clear_ci95 | stored | Wilson 95% over full runs |
| per_battle[trainer].battles, .rate | `per_battle` | battles faced and clear rate per trainer; Cynthia's battles over n_runs is the Elite Four pass rate |
| champion_rate, champion_battles, champion_ci95 | stored | top-up-inclusive Cynthia rate and count |
| cynthia_full_rate | `per_battle.cynthia.rate` | full-run-only Cynthia rate |
| budget_preset, threshold, qualified, borderline, final_level_gap_max | stored | inputs to the verdict rule |
| champion_status | `provenance.champion.status` | `met` / `cap_hit` / `no_reach`; not estimable unless `met` or count > 0 |
| duplicate_of | derived (R8) | directory of the first identical result, or none |

Validation: `per_battle.cynthia.battles ≤ n_runs`; `champion_battles ≥ per_battle.cynthia.battles`.

## CompositeEstimate (output of the estimator, one per StoredEvaluation and per Cynthia-rate kind)

| Field | Notes |
|---|---|
| kind | `topup` (pass criterion) or `fullrun` (input check) |
| e4_pass | Cynthia battles / n_runs, with Wilson 97.5% bounds |
| cyn_rate | Cynthia wins / Cynthia battles (by kind), with Wilson 97.5% bounds |
| estimate | e4_pass × cyn_rate |
| interval_bonferroni | (L_e4 × L_cyn, U_e4 × U_cyn); the pass-criterion interval (R1) |
| interval_delta | log-scale delta method; informational |
| half_width, half_width_ratio | half of the Bonferroni interval; ratio to the stored half-width |
| contains_stored | stored clear_rate within interval_bonferroni |
| threshold_verdict, full_verdict | per R2 |
| agreement, disagreement_kind | full verdicts equal; else `threshold` or `half-width only` with `runs_needed` |

Invariant: for kind `fullrun`, estimate == stored clear_rate to within floating error (input consistency check).

## Recording (output of `record_runs.py`, one file per team, JSON lines)

| Field | Notes |
|---|---|
| header line | team name, species and levels, master seed, player and opponent policy, sim_code_hash, platsim_code_hash, run count, start/end times (Eastern), worker hello provenance |
| run line (×2000) | run index, request seed, cleared, battles: [{trainer, won, end, turns, log_hash, state_before (Cynthia only)}], final_levels |

Validation: run indices 0..1999 in order; every run has at least one battle; `state_before` present on every Cynthia
battle.

## ReplayResult (output of `e4_replay.py`, one file per team)

| Field | Notes |
|---|---|
| floor | 0.98, 0.99 or 0.995 |
| order_id | 0 = identity, 1..200 = seeded permutations |
| switch_k | first run after which every member's Wilson 95% lower bound ≥ floor; null if never |
| cynthia_only_runs, cynthia_only_share | 2000 − switch_k, or 0 if never |
| unvalued | remaining runs that lost before Cynthia in the recording (R3 limitation) |
| banked_states | distinct `state_before` among Cynthia battles in runs 1..switch_k |
| e4_pass_k, cyn_rate, estimate, interval_bonferroni, verdict | the composite at the end of the order (R3) |
| full_clear_rate, full_verdict | the recording's full result for comparison |
| contains_full, verdict_agrees | the two pass checks |
| per-floor summary | distribution (min, p5, median, p95, max) of switch_k and share; fraction of orders with contains_full and verdict_agrees; cost of a Cynthia battle vs a full gauntlet in turns (and decisions, from the timing run) |

## TimeShareMeasurement (output of `time_share.py`)

| Field | Notes |
|---|---|
| team, batch_size | three teams × 50 / 100 / 200 |
| digest_plain, digest_hooked, digests_equal | `platsim.bench` pool-side `digest_logs`; a share is only reported when equal |
| wall_s | batch wall time (hooked run) |
| per_trainer: battles, turns, decisions, battle_s | summed from the side files |
| e4_share_battle, e4_share_wall | Elite Four summed battle time over total battle time, and over wall × 16 |
| overhead_s | wall − total battle time / 16 |
| kill_flag | strong team, batch 200: e4_share_battle < 0.40 |

## Projection (output of `projection.py`)

| Field | Notes |
|---|---|
| inputs | t_full, t_cyn (from TimeShareMeasurement), switch_k distribution and shares (from ReplayResult), baselines 769 s and 350 s |
| evaluate_ref_range_s, evaluate_ref_ratio_range | per floor, p5..p95 of k |
| b2_quick_range_s, b2_quick_ratio_range | bracketed as in R6 |
| decision_figure | the reference-team evaluation ratio (the clarified go rule) |

## GoNoGoRecord (FUTURE-FEATURES section 8 and the validation log)

| Field | Notes |
|---|---|
| q1_pass, q1_numbers | agreement count out of ten, disagreement kinds |
| q2_pass, q2_numbers | reference team: best floor's Cynthia-only share and agreement fractions; B3: never switches |
| q3_share, q3_kill | strong team batch-200 share, kill flag |
| projection | both ratio ranges |
| verdict | go / no-go for feature 021 per the go rule; on no-go the fallback order |
