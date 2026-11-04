# Validation log: feature 022 adaptive sampling in the optimizer's confirmation stage

Branch `022-confirm-adaptive-sampling` from `main` 93ac7c8. All times US Eastern. Measurements run alone on the machine.
Raw evidence under `runs/022-evidence/` (local, gitignored); small files copied to `specs/022-confirm-adaptive-sampling/evidence/`.

## T001 Setup (2026-11-04 11:17 AM EST)

Before-hashes:

```
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:f9128d6b68f493ce5d1beeb3d4f15053e5b6936e411b9cfbce5ef8215e6748c8
```

`sim_code_hash` must be unchanged at T021 (FR-011).

## T002-T009, T013-T014 Code and tests (12:26 PM EST)

- `src/platsim/optimizer/pairing.py` (new): `paired_outcomes`, full runs by run index, Cynthia-only runs by ordinal, surplus excluded (R4).
- `src/platsim/sampling.py`: `run_adaptive(..., borderline_threshold, borderline_max_runs)`, the borderline loop by the extension rule
  (the needed half-width is the estimate's distance from the threshold), consumed in order, stopping at the first non-straddling run;
  `AdaptiveRuns.borderline_extended`. `src/platsim/evaluate.py`: the 021 guard removed, the borderline arguments passed through,
  `evaluate_team(..., adaptive_runs=)` for a precomputed run. **Correction to 021 found by T010:** the discard counts depend on the
  chunk size (16 workers give a 128-run chunk, 3 workers a 64-run chunk), so `discarded` was a worker-count-dependent field in
  result.json; it is now logged only (`sampling_detail` and the xlsx row dropped; README's 021 block corrected).
- `src/platsim/optimizer/api.py`: `OptimizeRequest.sampling` (default full) and `.floor` (0.98) with validation; `run.py`: the
  fingerprint rule (only when non-default), `_confirm` on `evaluate_team(sampling, floor)` with the run mix in every attempt
  (`_run_mix`), the runner-up on the same method with `paired_outcomes` and `_comparison_record` (pairs, full and Cynthia-only pairs,
  excluded, p), confirmed from its own runs when better, `sampling_per_stage` in provenance; `cli.py`: `optimize --sampling`, `--floor`.
- Tests: `tests/unit/test_confirm_pairing.py` (pairing: neither / both / one switched, controls, the comparison record incl. the
  no-pairs case; the borderline extension on a scripted pool: seed 5 straddles at 200 and resolves with 389 Cynthia-only runs at 589
  total, chunk sizes 4 and 16 identical; the cap case), `tests/unit/test_optimizer_resume.py` (+2: fingerprint rule, CLI defaults and
  the floor usage error), `tests/integration/test_optimize_adaptive.py` (battle_sim).
- `uv run pytest -q tests/unit/test_reports.py tests/unit/test_sampling.py tests/unit/test_confirm_pairing.py tests/unit/test_optimizer_resume.py`: **49 passed**.

## T010 Integration test

First run 11:19:30 to 11:42:42 AM EST: **failed**, result.json differed between 16 and 3 workers at one byte: the `discarded` field (see
above). Rerun after the fix 11:53:03 AM to 12:16:27 PM EST: **1 passed in 1,404.1 s (23 min 24 s)**: byte-identical result.json across
worker counts, `sampling_per_stage.confirm == adaptive`, the confirm attempt with a switch run and Cynthia-only runs, the comparison's
pair counts consistent (`specs/022-confirm-adaptive-sampling/evidence/t010.log`).

## T011 Hand check (12:16:27 to 12:24:56 PM EST, alone, 8 workers)

`uv run platsim optimize infernape staraptor luxray garchomp gyarados gardevoir --budget quick --seed q022 --sampling adaptive --floor 0.9 --workers 8`
exit 0, 507.6 s (confirm 94.1 s). Three confirm attempts: at [54, 56, 56, 55, 56, 55] the switch came after 280 full runs (Lucian cost
runs; 220 Cynthia-only) and the checks failed; at [55, 57, 57, 56, 57, 56] switch 127 / 373, failed; at [56, 58, 58, 57, 58, 57] switch
35 / 465, passed (clear 0.876 [0.8476, 0.9054]). Runner-up at the same levels switched at 35 too: 500 pairs (35 full + 465
Cynthia-only), 0 excluded, winner-only 101 vs runner-up-only 51, p 6.1e-5, winner better. `sampling_per_stage`: level search and setup
check full, confirm adaptive, floor 0.9. Copies under `evidence/hand/`. Note: commits 1 and 2 of the task plan are one commit, since
the runner-up branch lives in the same files as the confirm wiring.
