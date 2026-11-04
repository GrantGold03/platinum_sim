# Contract: CLI flag, result fields, report rows, web view

## CLI

`platsim evaluate TEAM [--sampling {full,adaptive}] [--floor F]`: `--sampling` default `full` (R12); `--floor` default
0.99, usage error (exit 2) outside [0.9, 1.0] or with `--sampling full` given explicitly together with a non-default
floor (the floor applies to adaptive only; a warning, not an error, is acceptable).

## result.json

New top-level keys: `"sampling": "full" | "adaptive"`, `"sampling_detail": null | {floor, full_runs, cynthia_only_runs,
switch_run, discarded, banked_states, e4_pass_rate, e4_pass_ci95, cynthia_rate, cynthia_battles, composite_ci95,
extension: {full, cynthia_only}}`. Under adaptive: `n_runs` = full + Cynthia-only runs; `clear_rate` = the composite;
`clear_ci95` = its delta interval; `per_battle` from full runs; `champion_*` over all Cynthia battles; `loss_causes`
include Cynthia-only losses; `provenance.sampling` mirrors `sampling_detail` with the seed note; `seeds.cynthia_only_seed`.
A result.json without the keys reads as `sampling: "full"`.

## xlsx (Evaluation sheet) and csv

Rows after "Runs (full gauntlets)" (renamed "Runs" with the kind in the next rows): "Sampling method"; when adaptive:
"Full runs", "Cynthia-only runs", "Switch run", "Banked states", "Elite Four pass rate", "Elite Four pass 95% CI low/high",
"Composite 95% CI low/high". csv: the same keys in the evaluation block.

## Web result view

`sampling` and, when adaptive, "full / Cynthia-only" counts beside the runs figure; nothing else changes.
