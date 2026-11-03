# Validation log: feature 020 lead spike

Branch `020-lead-spike` from `main` ade9f9d. All times US Eastern. Measurements run alone on the machine
(`pgrep -a -x node; pgrep -a pytest` empty before each). Raw evidence under `runs/020-evidence/` (local, gitignored);
small result files copied to `specs/020-lead-spike/evidence/`.

## T001 Setup (2026-11-03 5:32 PM EST)

Before-hashes:

```
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3
```

These must be identical at T019 (FR-001, SC-006).

## T002-T006 Scripts, tests and smoke (5:33 PM EST)

`scripts/lead_analysis.py` (rotate, load_recording, check_paired, lead_row, choose_best, held_out, naive, control, screening, level_gains,
split_sample, the CLI with the six-row table, the split-sample and screening blocks, partial lead sets marked not judged),
`scripts/lead_runs.py` (019 helpers by path, run_full_gauntlets unchanged, one file per lead), `tests/unit/test_lead_spike.py`.

`uv run pytest -q tests/unit/test_lead_spike.py`: **7 passed in 0.20s** (rotation, pairing refusal, lead_row reconciliation incl. level mapping, choose_best
ties, the 10-point positive control [verdict A, control 0 discordant] with the 5-point informational print, the identical-leads negative control,
screening and level gains).

Recorder smoke (b2main, leads 0 and 1, 20 runs; then the analysis on the partial set):
```
{"team": "b2main", "lead": 0, "species": "garchomp", "cleared": 18, "clear_rate": 0.9, "per_trainer": {"aaron": 1.0, "bertha": 1.0, "flint": 1.0, "lucian": 1.0, "cynthia": 0.9}, "wall_s": 5.9, "gauntlets_per_s": 3.37, "file": "runs/020-evidence/smoke/b2main-lead0.jsonl"}
{"team": "b2main", "lead": 1, "species": "infernape", "cleared": 18, "clear_rate": 0.9, "per_trainer": {"aaron": 1.0, "bertha": 1.0, "flint": 1.0, "lucian": 1.0, "cynthia": 0.9}, "wall_s": 6.0, "gauntlets_per_s": 3.34, "file": "runs/020-evidence/smoke/b2main-lead1.jsonl"}
== team b2main  builds [['garchomp', 52], ['infernape', 54], ['staraptor', 53], ['rotom', 55], ['floatzel', 55], ['weavile', 53]]
lead species       cleared  clear [ci95]             aaron  bertha   flint  lucian  cynthi   expected final levels (member order)   lead gain
   0 garchomp       18/20  0.9000 [0.6990, 0.9721]   1.000   1.000   1.000   1.000   0.900   [53.67, 54.89, 53.11, 55.11, 55.67, 53.17]   1.67
   1 infernape      18/20  0.9000 [0.6990, 0.9721]   1.000   1.000   1.000   1.000   0.900   [53.00, 55.22, 53.28, 55.00, 55.50, 53.17]   1.22
spread: best lead 0 (garchomp) 0.9000, worst lead 0 (garchomp) 0.9000: 0.0 points (vs (12, 8, 15) at n 100)
only 2 of 6 leads present: split-sample and screening skipped; team not judged

{"supported_gain": {}, "not_judged": ["b2main"], "confirmation_stage_check": "no-go (reporting follow-on only)"}
```
Smoke directory deleted afterwards. Exit codes: see `runs/020-evidence/smoke.start`.
