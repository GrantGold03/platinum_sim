# Data Model: Adaptive Elite Four Sampling in evaluate

## AdaptiveRuns (in memory, returned by `run_adaptive`)

| Field | Notes |
|---|---|
| full_results | worker responses of the counted full runs, in run order (indices 0..switch_run-1, plus extension full runs) |
| cynthia_only_results | worker responses of Cynthia-only sampling runs, in k order; each has one battle with `state_before` and its seed |
| switch_run | first run index after which every Elite Four member's Wilson 95% lower bound >= floor; None if never |
| discarded | full results computed past the switch and not counted (batch independence, R3) |
| bank | list of `state_before` of full runs that reached Cynthia, in run order |
| extension | {"full": int, "cynthia_only": int} runs added for the half-width target |
| target_met | True / False / None as `_Runs.target_met` |

Validation: `switch_run is None` implies `cynthia_only_results == []`; every Cynthia-only battle's trainer is Cynthia;
policies equal across all responses.

## Composite estimate (fields written into the report)

| Field | Notes |
|---|---|
| e4_pass_rate, e4_pass_ci95 | reached_full / full_runs, Wilson 95% |
| cynthia_rate, cynthia_battles | over full-run Cynthia battles + sampling runs + top-up battles |
| clear_rate | e4_pass_rate × cynthia_rate (the report's `clear_rate` under adaptive) |
| clear_ci95 | delta-method interval (the report's `clear_ci95` under adaptive) |
| half-width | half the interval; compared with the preset's target |

## EvaluationReport (changed fields)

| Field | Change |
|---|---|
| sampling | NEW, `"full"` (default, also for old JSON) or `"adaptive"` |
| sampling_detail | NEW, None for full; for adaptive: floor, full_runs, cynthia_only_runs, switch_run, discarded, banked_states, e4_pass_rate, e4_pass_ci95, cynthia_rate, cynthia_battles, composite_ci95, extension |
| n_runs | full + Cynthia-only runs under adaptive |
| clear_rate, clear_ci95 | the composite and its delta interval under adaptive; unchanged under full |
| per_battle | from full runs only (Cynthia's row keeps its full-run meaning) |
| champion_rate, champion_battles | over all Cynthia battles (full, sampling, top-up) |
| loss_causes | include Cynthia-only losses |
| provenance.sampling | the same detail plus the seed index note |
| seeds.cynthia_only_seed | `"derive_seed(master, k, 98)"` |

## CLI

| Flag | Values | Default |
|---|---|---|
| --sampling | full, adaptive | full (flipped only on the owner's go, R12) |
| --floor | 0.9 ≤ x ≤ 1.0 | 0.99 |

## Acceptance table (per team)

full estimate [ci], adaptive estimate [ci], contained, verdict_full, verdict_adaptive, agree, hw_ratio,
cynthia_only_share, wall_full_s, wall_adaptive_s, ratio; plus the two controls.
