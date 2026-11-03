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

## T009-T011 Recording and replay scripts

`scripts/record_runs.py` (reuses `platsim.evaluate.run_full_gauntlets` unchanged; JSON lines, header + one line per run, Cynthia `state_before` kept),
`scripts/e4_replay.py` (R3: switch point on each member's Wilson 95% lower bound, composite after k, unvalued count, banked states, seeded orders),
tests in `tests/unit/test_e4_estimator.py` (12 passed, see T002-T006). Also written while the recordings ran (no commit, no suite): `scripts/hooks/register.mjs`,
`scripts/hooks/hooks.mjs`, `scripts/time_share.py`, `scripts/projection.py` (US3; smoke-checked at T018).

Process note: the first chain's `git add runs/019-evidence/...` failed because `/runs/` is gitignored for every feature (the 018 evidence is
local-only too), which skipped commit 1 and the reference recording and started the B3 recording first. Raw evidence stays local under
`runs/019-evidence/`; the small result files are copied to `specs/019-e4-sampling-spike/evidence/` (this corrects the plan's "committed" note).

## T013 B3 recording (4:16:58 to 4:19:45 PM EST, alone, 16 workers)

`uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team b3 --out runs/019-evidence/recording-b3.jsonl` exit 0; 2,000 runs in 167.0 s (11.97 gauntlets/s); 2.8 MB.
```
{'team': 'b3', 'builds': [['infernape', 57], ['garchomp', 58], ['gyarados', 58], ['lucario', 58], ['chatot', 58], ['staraptor', 57]], 'master': '019-record-b3', 'cleared': 1486, 'clear_rate': 0.743, 'per_trainer': {'aaron': {'battles': 2000, 'rate': 1.0}, 'bertha': {'battles': 2000, 'rate': 0.9995}, 'flint': {'battles': 1999, 'rate': 1.0}, 'lucian': {'battles': 1999, 'rate': 0.8814}, 'cynthia': {'battles': 1762, 'rate': 0.8434}}, 'sim_code_hash': 'sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b', 'platsim_code_hash': 'sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3', 'start': '2026-11-03 4:16:58 PM EST', 'end': '2026-11-03 4:19:45 PM EST', 'wall_s': 167.0}
```

## T012 Reference recording (4:20:16 to 4:23:01 PM EST, alone, 16 workers)

`uv run python specs/019-e4-sampling-spike/scripts/record_runs.py --team ref --out runs/019-evidence/recording-ref.jsonl` exit 0.
```
{'team': 'ref', 'builds': [['infernape', 60], ['staraptor', 60], ['luxray', 60], ['garchomp', 60], ['gyarados', 60], ['gardevoir', 60]], 'master': '019-record-ref', 'cleared': 1869, 'clear_rate': 0.9345, 'per_trainer': {'aaron': {'battles': 2000, 'rate': 0.999}, 'bertha': {'battles': 1998, 'rate': 1.0}, 'flint': {'battles': 1998, 'rate': 1.0}, 'lucian': {'battles': 1998, 'rate': 0.9995}, 'cynthia': {'battles': 1997, 'rate': 0.9359}}, 'sim_code_hash': 'sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b', 'platsim_code_hash': 'sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3', 'start': '2026-11-03 4:20:16 PM EST', 'end': '2026-11-03 4:23:00 PM EST', 'wall_s': 164.2, 'gauntlets_per_s': 12.18}
```

## T014 Question (2): replay (4:23:01 to 4:23:17 PM EST; floors 0.98 / 0.99 / 0.995; 200 seeded orders + identity)

```
team ref  runs 2000  full clear 0.9345 [0.9228, 0.9445] above  Cynthia turns/battle 18.49  turns/full gauntlet 63.97
floor 0.98: switched 200/200 orders; switch_k {'min': 189, 'p5': 189, 'median': 189.0, 'p95': 280, 'max': 361}; cynthia-only share {'min': 0.8195, 'p5': 0.86, 'median': 0.9055, 'p95': 0.9055, 'max': 0.9055}; unvalued {'min': 0, 'p5': 2, 'median': 3.0, 'p95': 3, 'max': 3}; banked {'min': 189, 'p5': 189, 'median': 189.0, 'p95': 279, 'max': 359}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.9281262614142821, 'p5': 0.9325613420130195, 'median': 0.9359038557836755, 'p95': 0.9359038557836755, 'max': 0.9359038557836755}; identity order: k 189 share 0.905 est 0.9359 [0.8986, 0.9471] above
floor 0.99: switched 200/200 orders; switch_k {'min': 381, 'p5': 381, 'median': 381.0, 'p95': 726, 'max': 726}; cynthia-only share {'min': 0.637, 'p5': 0.637, 'median': 0.8095, 'p95': 0.8095, 'max': 0.8095}; unvalued {'min': 0, 'p5': 0, 'median': 3.0, 'p95': 3, 'max': 3}; banked {'min': 381, 'p5': 381, 'median': 381.0, 'p95': 723, 'max': 724}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.9320364844787843, 'p5': 0.9320364844787843, 'median': 0.9359038557836755, 'p95': 0.9359038557836755, 'max': 0.9359038557836755}; identity order: k 381 share 0.809 est 0.9359 [0.9105, 0.9471] above
floor 0.995: switched 200/200 orders; switch_k {'min': 765, 'p5': 765, 'median': 1131.0, 'p95': 1455, 'max': 1455}; cynthia-only share {'min': 0.2725, 'p5': 0.2725, 'median': 0.4345, 'p95': 0.6175, 'max': 0.6175}; unvalued {'min': 0, 'p5': 0, 'median': 1.0, 'p95': 3, 'max': 3}; banked {'min': 765, 'p5': 765, 'median': 1129.0, 'p95': 1453, 'max': 1453}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.9339741571119566, 'p5': 0.9339741571119566, 'median': 0.9346173900025295, 'p95': 0.9359038557836755, 'max': 0.9359038557836755}; identity order: k 1131 share 0.434 est 0.9342 [0.9155, 0.9467] above

team b3  runs 2000  full clear 0.7430 [0.7234, 0.7617] borderline  Cynthia turns/battle 18.93  turns/full gauntlet 57.21
floor 0.98: switched 0/200 orders; switch_k {}; cynthia-only share {'min': 0.0, 'p5': 0.0, 'median': 0.0, 'p95': 0.0, 'max': 0.0}; unvalued {'min': 0, 'p5': 0, 'median': 0.0, 'p95': 0, 'max': 0}; banked {}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.743, 'p5': 0.743, 'median': 0.743, 'p95': 0.743, 'max': 0.743}; identity order: k None share 0.000 est 0.7430 [0.7109, 0.7724] borderline
floor 0.99: switched 0/200 orders; switch_k {}; cynthia-only share {'min': 0.0, 'p5': 0.0, 'median': 0.0, 'p95': 0.0, 'max': 0.0}; unvalued {'min': 0, 'p5': 0, 'median': 0.0, 'p95': 0, 'max': 0}; banked {}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.743, 'p5': 0.743, 'median': 0.743, 'p95': 0.743, 'max': 0.743}; identity order: k None share 0.000 est 0.7430 [0.7109, 0.7724] borderline
floor 0.995: switched 0/200 orders; switch_k {}; cynthia-only share {'min': 0.0, 'p5': 0.0, 'median': 0.0, 'p95': 0.0, 'max': 0.0}; unvalued {'min': 0, 'p5': 0, 'median': 0.0, 'p95': 0, 'max': 0}; banked {}; contains_full 1.000; verdict_agrees 1.000; estimate {'min': 0.743, 'p5': 0.743, 'median': 0.743, 'p95': 0.743, 'max': 0.743}; identity order: k None share 0.000 est 0.7430 [0.7109, 0.7724] borderline
```

**SC-003 (reference team): PASS.** Every order switches at every floor; Cynthia-only share median 0.9055 at floor 0.98 (switch after 189 full runs,
p95 280), 0.8095 at 0.99 (k 381, p95 726), 0.4345 at 0.995 (k 1131, p95 1455); threshold verdict unchanged in 100% of orders and the full
clear rate (0.9345 with v4) inside the composite interval in 100% of orders at every floor; 0 to 3 unvalued runs per order; banked post-Lucian
states at the switch equal k (every state distinct). Cynthia battle 18.5 turns vs 64.0 turns per full gauntlet (0.29).
**SC-004 (B3): PASS.** Lucian never clears any floor in any order; Cynthia-only share 0; estimate 0.7430 equals the full clear rate. Side
finding: at its recorded levels under v4 the B3 team clears 0.7430 [0.7234, 0.7617] (borderline), below the stored v2 result 0.7715; the
near-threshold v4 caveat (018) again. Composite interval at the full gauntlet [0.7109, 0.7724].

## T016-T018 Timing harness and smoke (4:24:36 to 4:24:44 PM EST)

`scripts/hooks/register.mjs` + `hooks/hooks.mjs`: a `load` hook rewrites `sim/gauntlet.mjs` in memory (three patterns, each must match exactly once,
else the worker fails at start): hrtime around each battle's turn loop, a counter on the player's `choose`, one JSON line per battle to
`$PLATSIM_TIMING_DIR/<pid>.jsonl`. Loaded into the pool's workers through `NODE_OPTIONS=--import=<abs>/register.mjs` (`scripts/time_share.py`);
the worker's stdout response is untouched. Smoke `time_share.py --teams ref --batches 5` exit 0: digests equal True, 25 battles recorded,
side files removed, wall 3.8 s plain vs 3.9 s hooked (`runs/019-evidence/time_share_smoke.txt`).

## T019 Question (3): in-stage time share (4:24:55 to 4:29:50 PM EST, alone, 16 workers, stop_on_loss on)

`uv run python specs/019-e4-sampling-spike/scripts/time_share.py --out runs/019-evidence/time_share.json` exit 0 (`runs/019-evidence/time_share.txt`, copied to `evidence/`).
```
ref batch 50: digests equal True; wall plain 10.3s hooked 10.4s; E4 share of battle time 0.772, of wall x workers 0.554; overhead 2.9s; cleared 47/50; battles recorded 250; aaron 0.724s/13.4t/13.8d; bertha 0.417s/9.9t/10.3d; flint 0.354s/11.3t/11.7d; lucian 0.355s/11.3t/11.6d; cynthia 0.548s/19.0t/21.0d
ref batch 100: digests equal True; wall plain 14.9s hooked 15.2s; E4 share of battle time 0.748, of wall x workers 0.599; overhead 3.0s; cleared 95/100; battles recorded 500; aaron 0.521s/12.9t/13.3d; bertha 0.337s/9.9t/10.3d; flint 0.297s/11.2t/11.6d; lucian 0.304s/11.2t/11.5d; cynthia 0.491s/18.8t/20.6d
ref batch 200: digests equal True; wall plain 24.2s hooked 25.5s; E4 share of battle time 0.720, of wall x workers 0.617; overhead 3.7s; cleared 189/200; battles recorded 1000; aaron 0.440s/13.1t/13.6d; bertha 0.298s/10.1t/10.5d; flint 0.256s/11.2t/11.6d; lucian 0.266s/11.2t/11.6d; cynthia 0.490s/19.0t/20.8d
b3 batch 50: digests equal True; wall plain 9.9s hooked 10.0s; E4 share of battle time 0.808, of wall x workers 0.580; overhead 2.8s; cleared 39/50; battles recorded 243; aaron 0.631s/8.0t/8.0d; bertha 0.491s/10.8t/10.9d; flint 0.236s/6.3t/6.3d; lucian 0.500s/14.8t/16.3d; cynthia 0.514s/18.0t/20.5d
b3 batch 100: digests equal True; wall plain 15.0s hooked 15.2s; E4 share of battle time 0.756, of wall x workers 0.593; overhead 3.3s; cleared 77/100; battles recorded 492; aaron 0.459s/8.1t/8.1d; bertha 0.376s/11.0t/11.2d; flint 0.198s/6.5t/6.5d; lucian 0.408s/14.4t/15.8d; cynthia 0.506s/18.6t/21.1d
b3 batch 200: digests equal True; wall plain 23.6s hooked 24.8s; E4 share of battle time 0.752, of wall x workers 0.638; overhead 3.8s; cleared 143/200; battles recorded 975; aaron 0.375s/8.2t/8.2d; bertha 0.334s/11.0t/11.2d; flint 0.190s/6.5t/6.5d; lucian 0.369s/14.7t/16.3d; cynthia 0.477s/18.7t/21.3d
b2v2 batch 50: digests equal True; wall plain 9.6s hooked 10.1s; E4 share of battle time 0.779, of wall x workers 0.557; overhead 2.9s; cleared 36/50; battles recorded 250; aaron 0.581s/8.4t/8.6d; bertha 0.479s/9.1t/9.3d; flint 0.306s/6.4t/6.5d; lucian 0.432s/11.4t/12.4d; cynthia 0.509s/16.5t/19.5d
b2v2 batch 100: digests equal True; wall plain 14.7s hooked 14.9s; E4 share of battle time 0.748, of wall x workers 0.583; overhead 3.3s; cleared 78/100; battles recorded 500; aaron 0.421s/8.5t/8.7d; bertha 0.341s/9.1t/9.2d; flint 0.268s/6.4t/6.4d; lucian 0.362s/11.5t/12.3d; cynthia 0.468s/16.7t/19.5d
b2v2 batch 200: digests equal True; wall plain 23.0s hooked 22.9s; E4 share of battle time 0.726, of wall x workers 0.611; overhead 3.6s; cleared 159/200; battles recorded 1000; aaron 0.309s/8.6t/8.7d; bertha 0.286s/9.1t/9.3d; flint 0.214s/6.4t/6.4d; lucian 0.309s/11.7t/12.6d; cynthia 0.422s/16.8t/19.5d
```

**SC-005: PASS.** `digests_equal` True for all nine team x batch runs (the harness changes nothing but timing). Elite Four share of
battle time at batch 200: reference 0.720, B3 0.752, B2 (018 v2 team) 0.726; at batch 50 (JIT warm-up inside the batch) 0.77 to 0.81.
Share of wall x workers 0.55 to 0.64 (pool start and idle slots: overhead 2.8 to 3.8 s per batch). **Kill flag: not raised** (0.720 >= 0.40).
Cynthia 0.42 to 0.51 s per battle vs 1.46 to 1.75 CPU s per full gauntlet; decisions per battle: Cynthia 19.5 to 21.3, Elite Four 6.4 to 16.3.

## T020-T021 Projection (4:29:50 PM EST)

`uv run python specs/019-e4-sampling-spike/scripts/projection.py --out runs/019-evidence/projection.json` exit 0 (`projection.txt`). Model (R6): w_full 0.1277 s per full gauntlet at the pool
(reference, batch 200), w_cyn 0.0358 s per Cynthia-only battle (w_full x 0.490 / 1.750 CPU s); n 2,000; top-ups from the count rule.
```
{"inputs": {"w_full_s": 0.12765235293998559, "w_cyn_s": 0.035758169820912566, "cpu_s_per_gauntlet": 1.7501664106200001, "cynthia_s_per_battle": 0.4902592571500001, "n": 2000}}
evaluate reference, floor 0.98: model ratio (p95 of k .. p5 of k) 2.63 .. 2.87; projected median 89 s vs model baseline 255 s; vs README 769 s: 8.65x
evaluate reference, floor 0.99: model ratio (p95 of k .. p5 of k) 1.85 .. 2.40; projected median 107 s vs model baseline 255 s; vs README 769 s: 7.22x
evaluate reference, floor 0.995: model ratio (p95 of k .. p5 of k) 1.24 .. 1.80; projected median 175 s vs model baseline 255 s; vs README 769 s: 4.38x
B2 quick bracket, strong_ref, floor 0.98: model ratio 1.38 (median k 189)  [bracket, not a measurement]
B2 quick bracket, strong_ref, floor 0.99: model ratio 1.11 (median k 381)  [bracket, not a measurement]
B2 quick bracket, strong_ref, floor 0.995: model ratio 1.00 (median k 1131)  [bracket, not a measurement]
B2 quick bracket, lucian_heavy_b3, floor 0.98: floor never reached  [bracket, not a measurement]
B2 quick bracket, lucian_heavy_b3, floor 0.99: floor never reached  [bracket, not a measurement]
B2 quick bracket, lucian_heavy_b3, floor 0.995: floor never reached  [bracket, not a measurement]
```

**SC-006.** Deciding figure (reference-team evaluation, model ratio over p95..p5 of the switch point): **2.63 to 2.87x at floor 0.98, 1.85 to
2.40x at 0.99, 1.24 to 1.80x at 0.995**; projected median 89 / 107 / 175 s against a model baseline of 255 s. The README's 769 s is not
comparable (v2 player, top-up and loss-cause replays included) and the 'vs 769 s' column is reported only as such. B2 quick bracket
(not a measurement): 1.00x on the Lucian-heavy stand-in (floor never reached) to 1.38x on the strong stand-in at floor 0.98 (1.11x at 0.99).

## T022 Go / no-go for feature 021 (the clarified rule, FR-013)

| Question | Criterion | Result |
|---|---|---|
| (1) estimator vs ten stored verdicts | threshold verdict agrees on all ten | **FAIL as specified**: 6 of 10; B2, B3, v8 and job-2d8f18 become borderline under the Bonferroni interval (1.3 to 1.6x wider); point estimates agree within 0.004 on all ten; the delta-method interval agrees on all ten |
| (2) replay on recordings | reference >= 50% Cynthia-only with the verdict unchanged in 100% and containment >= 95%; B3 never switches | **PASS**: 0.91 / 0.81 / 0.43 at floors 0.98 / 0.99 / 0.995, 100% / 100%; B3 0 switches, estimate = full |
| (3) in-stage share | reported; kill if < 0.40 on the strong team | **PASS**: 0.720 at batch 200 (B3 0.752, B2 0.726); digests identical |
| projection | reference evaluation >= 1.5x | **PASS at floors 0.98 and 0.99**: 2.63 to 2.87x and 1.85 to 2.40x (model); B2 quick 1.00 to 1.38x reported, not deciding |

**Verdict: no-go as specified, conditional go.** By the rule's letter the method is not built, because question (1) fails. The failure is
attributable to the plan's interval choice (R1: two 97.5% Wilson factors multiplied, joint coverage >= 95%), not to the estimator: the
composite point estimates equal or sit within 0.004 of the stored clear rates, every interval contains them, and the standard delta-method
interval reproduces the threshold verdict on all ten. Keeping the Bonferroni interval would cost threshold teams (where the level search
sits and where the rule never switches, so nothing is saved) 2,700 to 5,600 full runs instead of 2,000 to resolve the verdict. **If the
owner amends feature 021's interval to the delta method (or any interval no wider than about 1.1x the binomial at 2,000 runs) through a
clarification on its spec, every criterion is met and the verdict is go**, with the projected 1.85 to 2.87x on evaluations of strong teams
and no change on threshold teams. Otherwise the fallback order from the concept note applies: a cheaper player for Aaron, Bertha and Flint
only after its per-trainer rates are measured; else nothing. Side findings for the record: B3 at its stored levels clears 0.7430 under v4
(borderline) against 0.7715 under v2; the reference team 0.9345 under v4 against 0.9445 under v2.
