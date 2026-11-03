# Validation log: feature 019 Elite Four sampling spike

Branch `019-e4-sampling-spike` from `main` 1ca9bb3. All times US Eastern. Measurements run alone on the machine
(`pgrep -a -x node; pgrep -a pytest` empty before each). Evidence under `runs/019-evidence/`.

## T001 Setup (2026-11-03 4:13 PM EST)

Before-hashes (`uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"`):

```
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3
```

These must be identical at T025 (FR-001, SC-007).

## T002-T006 Scripts and tests (4:16 PM EST)

`scripts/common.py` (stored-result loader with validations, duplicate grouping, idle check, Eastern clock), `scripts/e4_estimator.py`
(Wilson bounds at 95% and 97.5%, Bonferroni product interval R1, delta interval informational, the evaluate verdict rule R2 as
threshold and full verdicts, disagreement kinds, runs needed by the 1/sqrt(n) scaling of the half-width or of the lower margin), `scripts/record_runs.py`,
`scripts/e4_replay.py` (R3), `tests/unit/test_e4_estimator.py`. Python 3.14 note: a module loaded by path must be registered in
`sys.modules` before exec for dataclasses with postponed annotations.

`uv run pytest -q tests/unit/test_e4_estimator.py`: **12 passed in 0.04s** (12 tests: bounds, product and delta intervals, verdict rule incl. gap and quick,
disagreement kinds and runs needed, positive control, not-estimable, fullrun identity, dedup, replay switch-point for 0.90 and all-wins, composite_after, banked states, orders).

## T007 Question (1): estimator over the ten stored evaluations (4:16 PM EST)

`uv run python specs/019-e4-sampling-spike/scripts/e4_estimator.py --out runs/019-evidence/estimator.json` exit **1**; `--control` exit **0** (`runs/019-evidence/estimator.txt`, `estimator_control.txt`).

```
dir | kind | n | stored clear [ci] | composite [bonferroni] | [delta] | hw ratio | contains | stored tv/full | composite tv/full | kind | runs_needed | note
runs/t076/v7-w16 | fullrun | 2000 | 0.9445 [0.9344, 0.9546] | 0.9445 [0.9292, 0.9553] | [0.9345, 0.9546] | 1.30 | True | above/qualified | above/qualified | agree | - | 
runs/t076/v7-w16 | topup | 2000 | 0.9445 [0.9344, 0.9546] | 0.9446 [0.9293, 0.9553] | [0.9346, 0.9546] | 1.29 | True | above/qualified | above/qualified | agree | - | 
runs/final-defaults | fullrun | 2000 | 0.8645 [0.8495, 0.8795] | 0.8645 [0.8425, 0.8827] | [0.8496, 0.8796] | 1.34 | True | above/qualified | above/not_qualified | half-width only | 2022 | 
runs/final-defaults | topup | 2000 | 0.8645 [0.8495, 0.8795] | 0.8632 [0.8412, 0.8814] | [0.8483, 0.8784] | 1.34 | True | above/qualified | above/not_qualified | half-width only | 2026 | 
runs/bench-007-baseline/B5 | fullrun | 2000 | 0.8485 [0.8328, 0.8642] | 0.8485 [0.8264, 0.8668] | [0.8329, 0.8644] | 1.29 | True | above/qualified | above/not_qualified | half-width only | 2039 | 
runs/bench-007-baseline/B5 | topup | 2000 | 0.8485 [0.8328, 0.8642] | 0.8484 [0.8264, 0.8667] | [0.8329, 0.8643] | 1.28 | True | above/qualified | above/not_qualified | half-width only | 2034 | 
runs/bench-010/B1 | fullrun | 2150 | 0.7995 [0.7826, 0.8165] | 0.7995 [0.7742, 0.8218] | [0.7828, 0.8166] | 1.41 | True | above/qualified | above/not_qualified | half-width only | 3050 | 
runs/bench-010/B1 | topup | 2150 | 0.7995 [0.7826, 0.8165] | 0.7991 [0.7739, 0.8213] | [0.7825, 0.8161] | 1.40 | True | above/qualified | above/not_qualified | half-width only | 3012 | 
runs/bench-010/B2 | fullrun | 2000 | 0.7730 [0.7547, 0.7913] | 0.7730 [0.7442, 0.7988] | [0.7549, 0.7916] | 1.49 | True | above/qualified | borderline/borderline | threshold | 3141 | 
runs/bench-010/B2 | topup | 2000 | 0.7730 [0.7547, 0.7913] | 0.7695 [0.7410, 0.7950] | [0.7515, 0.7878] | 1.47 | True | above/qualified | borderline/borderline | threshold | 4288 | 
runs/bench-010/B3 | fullrun | 2000 | 0.7715 [0.7531, 0.7899] | 0.7715 [0.7404, 0.7996] | [0.7533, 0.7901] | 1.61 | True | above/qualified | borderline/borderline | threshold | 4175 | 
runs/bench-010/B3 | topup | 2000 | 0.7715 [0.7531, 0.7899] | 0.7756 [0.7456, 0.8027] | [0.7581, 0.7935] | 1.55 | True | above/qualified | borderline/borderline | threshold | 2743 | 
runs/bench-010/B4 | fullrun | 2345 | 0.8081 [0.7922, 0.8240] | 0.8081 [0.7830, 0.8304] | [0.7923, 0.8242] | 1.49 | True | above/qualified | above/not_qualified | half-width only | 3285 | 
runs/bench-010/B4 | topup | 2345 | 0.8081 [0.7922, 0.8240] | 0.8074 [0.7826, 0.8294] | [0.7918, 0.8233] | 1.47 | True | above/qualified | above/not_qualified | half-width only | 3218 | 
runs/bench-010/B5 | fullrun | 2000 | 0.7785 [0.7603, 0.7967] | 0.7785 [0.7537, 0.8000] | [0.7605, 0.7969] | 1.27 | True | above/qualified | above/not_qualified | half-width only | 2679 | 
runs/bench-010/B5 | topup | 2000 | 0.7785 [0.7603, 0.7967] | 0.7784 [0.7537, 0.7999] | [0.7604, 0.7968] | 1.27 | True | above/qualified | above/not_qualified | half-width only | 2671 | 
runs/t076/v8 | fullrun | 2796 | 0.7661 [0.7504, 0.7818] | 0.7661 [0.7418, 0.7883] | [0.7506, 0.7819] | 1.48 | True | above/qualified | borderline/borderline | threshold | 6384 | 
runs/t076/v8 | topup | 2796 | 0.7661 [0.7504, 0.7818] | 0.7669 [0.7430, 0.7888] | [0.7517, 0.7825] | 1.46 | True | above/qualified | borderline/borderline | threshold | 5585 | 
runs/job-20261008T235244Z-2d8f18 | fullrun | 2000 | 0.7735 [0.7552, 0.7918] | 0.7735 [0.7466, 0.7973] | [0.7554, 0.7921] | 1.38 | True | above/qualified | borderline/borderline | threshold | 2612 | 
runs/job-20261008T235244Z-2d8f18 | topup | 2000 | 0.7735 [0.7552, 0.7918] | 0.7720 [0.7452, 0.7956] | [0.7539, 0.7904] | 1.37 | True | above/qualified | borderline/borderline | threshold | 2962 | 
{"judged": 10, "pass": false, "fullrun_identity_ok": true, "failures": ["runs/bench-010/B2", "runs/bench-010/B3", "runs/t076/v8", "runs/job-20261008T235244Z-2d8f18"], "half_width_only": [["runs/final-defaults", 2026], ["runs/bench-007-baseline/B5", 2034], ["runs/bench-010/B1", 3012], ["runs/bench-010/B4", 3218], ["runs/bench-010/B5", 2671]], "threshold_runs_to_clear": [["runs/bench-010/B2", 4288], ["runs/bench-010/B3", 2743], ["runs/t076/v8", 5585], ["runs/job-20261008T235244Z-2d8f18", 2962]], "max_half_width_ratio": 1.5523720180726903}
```

**Result: question (1) FAILS the strict criterion.** Point estimates: the fullrun identity holds on all ten (composite == stored clear rate), every
topup composite differs from the stored rate by at most 0.004 and every Bonferroni interval contains the stored rate. The interval is 1.27 to 1.55x
wider than the stored binomial one (R1, by construction). Threshold verdicts: 6 of 10 agree; the four teams within about two points of 0.75
(bench-010 B2 0.7730, B3 0.7715, t076/v8 0.7661, job-2d8f18 0.7735) become **borderline** under the composite where the stored interval sits above:
a threshold-kind disagreement caused by interval width, not bias. Runs at which the composite lower bound would reach 0.75 (lower-margin
scaling): B2 4,288, B3 2,743, v8 5,585, job 2,962. The five other qualified teams agree on the threshold verdict and differ on the full verdict only
by the 0.02 half-width target (half-width only): runs needed 2,026 / 2,034 / 3,012 / 3,218 / 2,671. The informational delta interval agrees on
the threshold verdict on all ten (e.g. B3 [0.7581, 0.7935]). Positive control: Elite Four pass 0.70 with Cynthia 0.95 gives **below** where a
Cynthia-only rule would say above (ok). Per tasks.md, US2 and US3 continue for the record; the go rule (FR-013) cannot be met by question (1) as
specified unless the interval choice is revisited (a spec decision, recorded in the closing section).
