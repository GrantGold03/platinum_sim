# Validation log: feature 021 adaptive Elite Four sampling in evaluate

Branch `021-adaptive-e4-sampling` from `main` c7cb162. All times US Eastern. Measurements run alone on the machine.
Raw evidence under `runs/021-evidence/` (local, gitignored); small files copied to `specs/021-adaptive-e4-sampling/evidence/`.

## T001 Setup (2026-11-03 8:03 PM EST)

Before-hashes:

```
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3
```

`sim_code_hash` must be unchanged at T022 (FR-015); `platsim_code_hash` changes (behaviour change under `src/platsim`).

## T002-T009 Code and tests (8:16 PM EST)

- `src/platsim/sampling.py` (new): switch rule, generalised banked-state draw (index 98), Elite Four pass stats, delta interval,
  composite estimate, extension kind, the Cynthia-only request, and `run_adaptive` (chunked full runs consumed in order, results past
  the switch discarded, Cynthia-only runs to min_runs, the mixed extension rule).
- `src/platsim/sim/champion.py`: `_start_index` delegates to `sampling.start_index(…, 99, …)` (same hash); `champion_topup(…, extra_cynthia=(battles, wins))`
  starts its counters from the sampling runs; `ChampionResult.extra_battles`. `src/platsim/sim/seeds.py`: index 98 reserved in the docstring.
- `src/platsim/evaluate.py`: `evaluate_team(…, sampling="full", floor=0.99)` and `evaluate(…)`; the adaptive path, the composite statistic once a
  switch happened and the full method's statistics when the floor was never reached (FR-006), `sampling_detail`, provenance, seeds note,
  `TeamEvaluation.cynthia_only_results`, the summary line. Deviation from T006's wording: a discard count is reported in `sampling_detail`,
  not as a warning (it is normal behaviour, not a problem).
- `src/platsim/report/json_report.py`: `sampling` (default full) and `sampling_detail` (default None) with to/from dict; `xlsx.py`: the
  sampling rows (the label stays "Runs (full gauntlets)" for full, "Runs (full + Cynthia-only)" for adaptive); `web/result_view.py`: the two
  fields. `csv_report.py`: unchanged, because the csv holds the Team sheet only (no evaluation block; the contract's csv line does not apply).
- `src/platsim/cli.py`: `--sampling {full,adaptive}` (default full) and `--floor` (default 0.99; usage error exit 2 outside [0.9, 1.0]).
- Tests: `tests/unit/test_sampling.py` (switch rule incl. the exact n per floor and the never-faced case, draw index vs the top-up's,
  delta interval, composite identity and the positive control, extension kind, request shape, `run_adaptive` on a fake pool: chunk
  independence with sizes 4 and 16, floor 1.0 never switches), `tests/unit/test_reports.py` (+2: round trip and old JSON reads as full;
  xlsx rows), `tests/integration/test_evaluate_adaptive.py` (battle_sim on the main test only).
- `uv run pytest -q tests/unit/test_sampling.py tests/unit/test_reports.py`: **27 passed, 1 skipped** (the acceptance-helper test waits for T013).

## T010 Integration test (8:07:38 to 8:11:00 PM EST, alone)

`uv run pytest -q tests/integration/test_evaluate_adaptive.py`: **2 passed in 201.4 s** (first run; a split-guard complaint about the
usage-error test carrying the battle_sim marker was fixed by marking the battle test only; the unmarked test then passed alone in 0.14 s).
Checks inside: adaptive at 80 runs, floor 0.9, byte-identical result.json for 8 and 3 workers; switch_run < 80, Cynthia-only runs > 0,
every `sampling_detail` key present, provenance and seeds note present; floor 1.0 never switches and equals `--sampling full` once the
four sampling keys are removed (FR-010 as clarified by the analysis); `--floor 0.5` is a usage error (exit 2).

## T011 Hand check (8:11:18 to 8:15:15 PM EST, alone)

```
T011 hand start 8:11:18 PM EST
hand a exit=0
hand b exit=0
a == b byte-identical
full-path determinism exit=0
T011 hand end 8:15:15 PM EST
runs 80  player expectimax2-v4  opponent decomp-ai  budget quick  sampling adaptive
adaptive sampling: full 35 / Cynthia-only 45 runs, switch at 35, banked states 35, floor 0.9; statistic composite (delta interval)
gauntlet clear rate 0.9625  95% CI [0.9218, 1.0000]  half-width 0.0391
  aaron    1.0000  [0.9011, 1.0000]  battles 35
  bertha   1.0000  [0.9011, 1.0000]  battles 35
  flint    1.0000  [0.9011, 1.0000]  battles 35
  lucian   1.0000  [0.9011, 1.0000]  battles 35
  cynthia  0.9714  [0.8547, 0.9949]  battles 35
Cynthia P(win | reached) 0.9625  [0.8955, 0.9872]  battles 80
platsim evaluate [adaptive]: Elite Four proven after 35 full runs (floor 0.9); 35 banked states; 29 results past the switch discarded
```
sampling_detail: floor 0.9, full 35 / Cynthia-only 45, switch 35, discarded 29 (one 64-run chunk overshoot, the price of batch independence),
banked 35, Elite Four pass 1.0 [0.901, 1.0], Cynthia 0.9625 over 80 battles, composite [0.9218, 1.0]; 3 loss causes (Cynthia-only losses
replayed). The full path's own determinism test (`test_evaluate.py -k determinism_fast`) still passes (135 s). Copies in `evidence/hand/`.
