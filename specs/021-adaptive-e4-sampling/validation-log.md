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

## T013-T016 Acceptance script and controls

`scripts/acceptance.py` (paired full then adaptive per team on one pool, same master seed `021-acc`, the table, the floor-0.98 alternative
for teams whose switch run at 0.99 is above 1,000 or absent, `--control`); its pure helpers are tested in `tests/unit/test_sampling.py`.
**Deviation from FR-012 (six teams):** the policy benchmark fixture (`tests/fixtures/policy_benchmark_team.json`) cannot be evaluated
through `evaluate` at all: its builds carry placeholder sources (`reference-fixture`) that the report writer refuses
(`report/sources.py`), and it fails in-game legality (15 violations). It exists for the simulator-side benchmark tools, which never
write reports. A bypass was tried (8:20 PM EST, `bench-smoke`) and failed in the report writer, so the acceptance runs on the five
legal teams. **Second finding:** the 018 v2 B2 team (`runs/018-evidence/b2-expectimax2-v2`) is the same team at the same levels as the
014 `b2-branch` result (the 018 run reproduced it), so its rows are identical to b2branch's on the same seed: four distinct teams.

Controls (8:21:28 PM EST, reference team, 200 runs, quick, exit 0):
```
control 1: adaptive floor 1.0 vs full, identical after removing the sampling keys: True; switch_run None
control 2: Cynthia-only sampling 159/165 = 0.9636363636363636 vs top-up 154/165 = 0.9333333333333333; z 1.2451748631284518; within noise: True
```
Control 1 (floor 1.0 never switches, identical to full after removing the four sampling keys): **PASS**. Control 2 (165 Cynthia-only
sampling runs, seed index 98, vs 165 top-up draws, index 99, on the same bank: 0.9636 vs 0.9333, z 1.25): **within noise, PASS**. A first
attempt compared against a top-up that stopped after one battle (its rules were already met); the control now draws explicitly.

## T017 Acceptance (8:22:59 to 8:50:19 PM EST, alone, 16 workers, standard budget, 2,000 runs, master `021-acc`; exit 0)

```
ref       floor 0.99  full 0.9360 [0.9244, 0.9459] n 2000  adaptive 0.9343 [0.9232, 0.9456] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.04  switch 563  full/cyn 563/1437 (share 0.719)  discarded 77  ext {'full': 0, 'cynthia_only': 0}  wall 142s/73s = 1.94x
b2main    floor 0.99  full 0.9055 [0.8919, 0.9176] n 2000  adaptive 0.9055 [0.8919, 0.9176] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.00  switch None  full/cyn 2000/0 (share 0.000)  discarded 0  ext {'full': 0, 'cynthia_only': 0}  wall 124s/123s = 1.00x
  alt: b2main    floor 0.98  full 0.9055 [0.8919, 0.9176] n 2000  adaptive 0.8998 [0.8857, 0.9142] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.11  switch 650  full/cyn 650/1350 (share 0.675)  discarded 118  ext {'full': 0, 'cynthia_only': 0}  wall 124s/73s = 1.70x
b2branch  floor 0.99  full 0.7785 [0.7598, 0.7962] n 2000  adaptive 0.7785 [0.7598, 0.7962] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.00  switch None  full/cyn 2000/0 (share 0.000)  discarded 0  ext {'full': 0, 'cynthia_only': 0}  wall 128s/128s = 1.00x
  alt: b2branch  floor 0.98  full 0.7785 [0.7598, 0.7962] n 2000  adaptive 0.7901 [0.7717, 0.8088] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.02  switch 280  full/cyn 280/1720 (share 0.860)  discarded 104  ext {'full': 0, 'cynthia_only': 0}  wall 128s/62s = 2.06x
b2v2      floor 0.99  full 0.7785 [0.7598, 0.7962] n 2000  adaptive 0.7785 [0.7598, 0.7962] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.00  switch None  full/cyn 2000/0 (share 0.000)  discarded 0  ext {'full': 0, 'cynthia_only': 0}  wall 127s/128s = 1.00x
  alt: b2v2      floor 0.98  full 0.7785 [0.7598, 0.7962] n 2000  adaptive 0.7901 [0.7717, 0.8088] n 2000  contained True  verdicts qualified/qualified agree True  hw x1.02  switch 280  full/cyn 280/1720 (share 0.860)  discarded 104  ext {'full': 0, 'cynthia_only': 0}  wall 127s/62s = 2.05x
b3        floor 0.99  full 0.7550 [0.7357, 0.7733] n 2000  adaptive 0.7550 [0.7357, 0.7733] n 2000  contained True  verdicts borderline/borderline agree True  hw x1.00  switch None  full/cyn 2000/0 (share 0.000)  discarded 0  ext {'full': 0, 'cynthia_only': 0}  wall 143s/146s = 0.98x
  alt: b3        floor 0.98  full 0.7550 [0.7357, 0.7733] n 2000  adaptive 0.7550 [0.7357, 0.7733] n 2000  contained True  verdicts borderline/borderline agree True  hw x1.00  switch None  full/cyn 2000/0 (share 0.000)  discarded 0  ext {'full': 0, 'cynthia_only': 0}  wall 143s/140s = 1.02x
{"all_contained": true, "all_agree": true, "ratios": {"ref": 1.9408592057993932, "b2main": 1.0047402828731713, "b2branch": 0.9998131745000735, "b2v2": 0.997305579999281, "b3": 0.9829747021553404}, "start": "2026-11-03 8:22:59 PM EST", "end": "2026-11-03 8:50:18 PM EST", "sim_code_hash": "sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b", "platsim_code_hash": "sha256:d7fe0dfb6553b78648793c63933d970d01cb8ab5ee61cf367df3aafac9288732"}
```

**SC-001: PASS** on all five teams (adaptive estimate inside the full run's 95% interval; verdicts agree, including B3 borderline on
both sides). **SC-002:** reference team **1.94x** at floor 0.99 (switch after 563 full runs, 72% Cynthia-only, 77 discarded); the three B2
teams never reach 0.99 (Lucian about 0.99 on them) and sit at 1.00x; at the 0.98 alternative they switch after 650 / 280 / 280 full runs for
**1.70x / 2.06x / 2.05x** with containment and agreement intact (b2main 0.8998 vs 0.9055; b2branch 0.7901 vs 0.7785); B3 never switches at
either floor (0.98 to 1.02x). Half-width ratio 1.00 to 1.11. No extension runs were needed on any team. Code hashes: sim
`299b1b55…` (unchanged), platsim `d7fe0dfb…`. Copies under `evidence/acceptance/` (table, controls, thirteen result.json files).

**Observation for the default decision:** the floor 0.99 is the safe choice on threshold-band teams (no switch, nothing lost) but gives
the saving only on teams whose Elite Four members are at or above about 0.995; 0.98 gives the saving on teams at about 0.99 as well, with
the composite still inside the full interval here. The choice of default floor is part of the default decision (T021).

## T020-T021 Docs and the default decision (9:00 PM EST)

README (command row, the 021 block), FUTURE-FEATURES section 8, RUN-STATE written for the acceptance result. The acceptance table
was presented to the user with three options (adaptive at 0.99, adaptive at 0.98, keep full). **User decision: adaptive is
evaluate's default at floor 0.98.** Applied: `platsim.sampling.DEFAULT_FLOOR = 0.98`, `DEFAULT_SAMPLING = "adaptive"`; the CLI
`--sampling` default and `evaluate()`'s default are adaptive; `evaluate_team` keeps `"full"` so the optimizer's stages are unchanged
(a unit test pins all three). The existing full-path evaluate tests now pass `--sampling full` explicitly (their meaning is unchanged).

## T022 Gates (10:55:26 to 11:54:24 PM EST, nothing else running, on the flipped default)

```
=== gates start 10:55:26 PM EST
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:f9128d6b68f493ce5d1beeb3d4f15053e5b6936e411b9cfbce5ef8215e6748c8
diff main -- sim lines=0
node exit=0
# tests 351
# pass 351
# fail 0
# duration_ms 144724.205914
full start 10:57:51 PM EST
full exit=1
=========================== short test summary info ============================
FAILED tests/integration/test_web_result_view.py::test_result_view - Assertio...
1 failed, 599 passed, 4 xfailed, 1 warning in 3389.89s (0:56:29)
FAILED tests/integration/test_web_result_view.py::test_result_view - Assertio...
=== gates end 11:54:24 PM EST
```

(a) `sim_code_hash` `299b1b55…` unchanged (platsim hash `f9128d6b…`); `git diff --stat main -- sim`: empty. (b) Node suite 351 pass, 0 fail, 144.7 s.
(c) Full pytest suite 10:57:51 to 11:54:20 PM EST: **599 passed, 4 xfailed, 1 failed in 3,389.9 s (56 min 30 s)**. The failure,
`tests/integration/test_web_result_view.py::test_result_view`, pinned the result view's exact summary key set; the two new keys
(`sampling`, `sampling_detail`) are the FR-007 web fields. The pinned set now includes them and the frozen fixture is asserted to read as
`full` / None; rerun: `4 passed, 1 warning in 38.08s`. No file under `src/` or `sim/` changed between the two runs, so the whole
set of 604 tests has passed on this code. Slowest: quick optimize 1,194 s, strength test 734 s, V7 evaluate (full path) 382 s, the new
adaptive integration test 201 s.

## T023 Close

Commits on the branch: 728c914 (method behind the flag), 20ed8a3 (acceptance script), 1a04009 (acceptance), 516d0bc (default flip,
user's go), then this one (gates). Merge to `main` only on the user's go: `git checkout main && git merge --ff-only 021-adaptive-e4-sampling && git push`.
Follow-on recorded in FUTURE-FEATURES section 8: the optimizer's stages on the same method.
