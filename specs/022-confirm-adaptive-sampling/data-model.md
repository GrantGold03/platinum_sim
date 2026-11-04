# Data Model: Adaptive Sampling in the Optimizer's Confirmation Stage

## OptimizeRequest (changed)

| Field | Default | Fingerprint |
|---|---|---|
| sampling | "full" (DEFAULT_SAMPLING after the owner's go) | only when != default |
| floor | DEFAULT_FLOOR (0.98) | only when != default |

## Confirm attempt (state.json `stages.confirm_attempts[]`, extended)

| Field | Notes |
|---|---|
| levels, runs, clear_rate, ci95, borderline, final_level_gap_max, expected_avg_final_level, passes_confirm_checks | as today |
| sampling | "full" / "adaptive" |
| full_runs, cynthia_only_runs, switch_run, banked_states, discarded, extension | from `sampling_detail`; None/0 for full |

## PairedOutcomes (pure, `optimizer/pairing.py`)

| Field | Notes |
|---|---|
| a_flags, b_flags | aligned boolean lists: full pairs (by run index below min(k_a, k_b)) then Cynthia-only pairs (by ordinal below min(c_a, c_b)) |
| full_pairs, cynthia_only_pairs, pairs | counts |
| excluded | runs on either side with no same-kind, same-seed partner |

The comparison record in state.json gains `pairs`, `excluded`, `full_pairs`, `cynthia_only_pairs` beside `n_paired`,
the counts and p.

## provenance.sampling_per_stage

`{"level_search": "full", "setup_check": "full", "confirm": "full" | "adaptive", "floor": float}`

## AdaptiveRuns (021, extended)

`run_adaptive(..., borderline_threshold=None, borderline_max_runs=None)`; `extension` gains the borderline batches'
kinds; `target_met` unchanged; a new `borderline_extended: bool`.

## Acceptance blocks

| Block | Output |
|---|---|
| b2quick | species/moves/items/levels equality, containment both ways, verdicts, equal-levels comparison, runner-up record, wall times and ratios (confirm stage, whole run) |
| confirm | per team: full vs adaptive estimate and interval, containment, verdict, run mix, wall ratio |
| resume | byte equality of the interrupted-and-resumed result.json with the uninterrupted one |
| pairing | McNemar counts on full-kind pairs: adaptive vs full exact equality; excluded counts |
