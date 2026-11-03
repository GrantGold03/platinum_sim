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

## T008-T010 Recordings (alone, 16 workers, stop-on-loss on, expectimax2-v4 vs decomp-ai, 2,000 runs per lead, identical seeds per team)

- b2main 5:33:27 to 5:46:51 PM EST, exit 0 (six leads, 128.9 to 140.3 s each, 14.3 to 15.5 gauntlets/s)
- b2branch 5:46:51 to 6:00:36 PM EST, exit 0
- b2v2 6:00:36 to 6:14:17 PM EST, exit 0

Per-lead summary lines (`runs/020-evidence/record-<team>.log`; headers copied to `evidence/`):
```
{'team': 'b2main', 'lead': 0, 'species': 'garchomp', 'cleared': 1827, 'clear_rate': 0.9135, 'per_trainer': {'aaron': 1.0, 'bertha': 0.9975, 'flint': 1.0, 'lucian': 0.993, 'cynthia': 0.9223}, 'wall_s': 128.9, 'gauntlets_per_s': 15.51}
{'team': 'b2main', 'lead': 1, 'species': 'infernape', 'cleared': 1727, 'clear_rate': 0.8635, 'per_trainer': {'aaron': 1.0, 'bertha': 0.9985, 'flint': 1.0, 'lucian': 0.9745, 'cynthia': 0.8875}, 'wall_s': 131.3, 'gauntlets_per_s': 15.24}
{'team': 'b2main', 'lead': 2, 'species': 'staraptor', 'cleared': 1859, 'clear_rate': 0.9295, 'per_trainer': {'aaron': 0.9995, 'bertha': 0.9975, 'flint': 1.0, 'lucian': 0.9855, 'cynthia': 0.9461}, 'wall_s': 131.1, 'gauntlets_per_s': 15.25}
{'team': 'b2main', 'lead': 3, 'species': 'rotom', 'cleared': 1716, 'clear_rate': 0.858, 'per_trainer': {'aaron': 1.0, 'bertha': 0.998, 'flint': 1.0, 'lucian': 0.9624, 'cynthia': 0.8933}, 'wall_s': 137.9, 'gauntlets_per_s': 14.5}
{'team': 'b2main', 'lead': 4, 'species': 'floatzel', 'cleared': 1676, 'clear_rate': 0.838, 'per_trainer': {'aaron': 1.0, 'bertha': 0.9975, 'flint': 1.0, 'lucian': 0.9694, 'cynthia': 0.8666}, 'wall_s': 140.3, 'gauntlets_per_s': 14.26}
{'team': 'b2main', 'lead': 5, 'species': 'weavile', 'cleared': 1748, 'clear_rate': 0.874, 'per_trainer': {'aaron': 1.0, 'bertha': 0.997, 'flint': 1.0, 'lucian': 0.9679, 'cynthia': 0.9057}, 'wall_s': 134.3, 'gauntlets_per_s': 14.89}
{'team': 'b2branch', 'lead': 0, 'species': 'garchomp', 'cleared': 1586, 'clear_rate': 0.793, 'per_trainer': {'aaron': 1.0, 'bertha': 1.0, 'flint': 1.0, 'lucian': 0.997, 'cynthia': 0.7954}, 'wall_s': 128.0, 'gauntlets_per_s': 15.62}
{'team': 'b2branch', 'lead': 1, 'species': 'infernape', 'cleared': 1471, 'clear_rate': 0.7355, 'per_trainer': {'aaron': 1.0, 'bertha': 0.9985, 'flint': 1.0, 'lucian': 0.979, 'cynthia': 0.7524}, 'wall_s': 135.3, 'gauntlets_per_s': 14.78}
{'team': 'b2branch', 'lead': 2, 'species': 'staraptor', 'cleared': 1444, 'clear_rate': 0.722, 'per_trainer': {'aaron': 0.9975, 'bertha': 0.9995, 'flint': 1.0, 'lucian': 0.988, 'cynthia': 0.733}, 'wall_s': 136.6, 'gauntlets_per_s': 14.64}
{'team': 'b2branch', 'lead': 3, 'species': 'rotom', 'cleared': 1383, 'clear_rate': 0.6915, 'per_trainer': {'aaron': 1.0, 'bertha': 0.9975, 'flint': 1.0, 'lucian': 0.9724, 'cynthia': 0.7129}, 'wall_s': 138.5, 'gauntlets_per_s': 14.44}
{'team': 'b2branch', 'lead': 4, 'species': 'floatzel', 'cleared': 1477, 'clear_rate': 0.7385, 'per_trainer': {'aaron': 0.9995, 'bertha': 0.999, 'flint': 1.0, 'lucian': 0.972, 'cynthia': 0.7609}, 'wall_s': 144.6, 'gauntlets_per_s': 13.83}
{'team': 'b2branch', 'lead': 5, 'species': 'weavile', 'cleared': 1419, 'clear_rate': 0.7095, 'per_trainer': {'aaron': 0.9995, 'bertha': 0.998, 'flint': 1.0, 'lucian': 0.9774, 'cynthia': 0.7277}, 'wall_s': 141.2, 'gauntlets_per_s': 14.16}
{'team': 'b2v2', 'lead': 0, 'species': 'garchomp', 'cleared': 1542, 'clear_rate': 0.771, 'per_trainer': {'aaron': 1.0, 'bertha': 1.0, 'flint': 1.0, 'lucian': 0.996, 'cynthia': 0.7741}, 'wall_s': 127.6, 'gauntlets_per_s': 15.68}
{'team': 'b2v2', 'lead': 1, 'species': 'infernape', 'cleared': 1482, 'clear_rate': 0.741, 'per_trainer': {'aaron': 0.999, 'bertha': 0.9985, 'flint': 0.9995, 'lucian': 0.9814, 'cynthia': 0.7573}, 'wall_s': 134.0, 'gauntlets_per_s': 14.93}
{'team': 'b2v2', 'lead': 2, 'species': 'staraptor', 'cleared': 1483, 'clear_rate': 0.7415, 'per_trainer': {'aaron': 0.9995, 'bertha': 0.9995, 'flint': 0.9995, 'lucian': 0.9845, 'cynthia': 0.7543}, 'wall_s': 135.5, 'gauntlets_per_s': 14.76}
{'team': 'b2v2', 'lead': 3, 'species': 'rotom', 'cleared': 1369, 'clear_rate': 0.6845, 'per_trainer': {'aaron': 1.0, 'bertha': 0.998, 'flint': 1.0, 'lucian': 0.9765, 'cynthia': 0.7024}, 'wall_s': 138.0, 'gauntlets_per_s': 14.49}
{'team': 'b2v2', 'lead': 4, 'species': 'floatzel', 'cleared': 1479, 'clear_rate': 0.7395, 'per_trainer': {'aaron': 0.999, 'bertha': 0.9965, 'flint': 1.0, 'lucian': 0.9804, 'cynthia': 0.7577}, 'wall_s': 144.4, 'gauntlets_per_s': 13.85}
{'team': 'b2v2', 'lead': 5, 'species': 'weavile', 'cleared': 1432, 'clear_rate': 0.716, 'per_trainer': {'aaron': 0.999, 'bertha': 0.999, 'flint': 1.0, 'lucian': 0.9734, 'cynthia': 0.737}, 'wall_s': 140.8, 'gauntlets_per_s': 14.21}
```

## T011-T015 Analysis: questions (1), (2) and (3) (6:14 PM EST; `uv run python specs/020-lead-spike/scripts/lead_analysis.py --out runs/020-evidence/lead_analysis.json`, exit 0)

```
== team b2main  builds [['garchomp', 52], ['infernape', 54], ['staraptor', 53], ['rotom', 55], ['floatzel', 55], ['weavile', 53]]
lead species       cleared  clear [ci95]             aaron  bertha   flint  lucian  cynthi   expected final levels (member order)   lead gain
   0 garchomp     1827/2000  0.9135 [0.9004, 0.9250]   1.000   0.998   1.000   0.993   0.922   [53.73, 54.71, 53.07, 55.09, 55.56, 53.14]   1.73
   1 infernape    1727/2000  0.8635 [0.8478, 0.8779]   1.000   0.999   1.000   0.974   0.887   [52.97, 55.32, 53.14, 55.04, 55.55, 53.27]   1.32
   2 staraptor    1859/2000  0.9295 [0.9174, 0.9399]   1.000   0.997   1.000   0.985   0.946   [52.90, 54.50, 53.96, 55.19, 55.54, 53.12]   0.96
   3 rotom        1716/2000  0.8580 [0.8420, 0.8726]   1.000   0.998   1.000   0.962   0.893   [52.95, 54.68, 53.08, 55.91, 55.55, 53.24]   0.91
   4 floatzel     1676/2000  0.8380 [0.8212, 0.8535]   1.000   0.998   1.000   0.969   0.867   [52.94, 54.62, 53.07, 55.19, 56.13, 53.32]   1.13
   5 weavile      1748/2000  0.8740 [0.8587, 0.8878]   1.000   0.997   1.000   0.968   0.906   [52.99, 54.59, 53.07, 55.16, 55.64, 53.90]   0.90
spread: best lead 2 (staraptor) 0.9295, worst lead 4 (floatzel) 0.8380: 9.2 points (vs (12, 8, 15) at n 100)
split-sample: chosen on pairs 0..999 = lead 2 (staraptor)
  held-out pairs 1000..1999: chosen 0.9260 vs first-listed 0.9060; only-chosen 85 only-first 65; p 0.121; verdict indistinguishable; supported gain: False
  naive all 2,000 pairs [selection-biased]: chosen 0.9295 vs first 0.9135; only-chosen 162 only-first 130; p 0.0695; verdict indistinguishable
  control (first-listed vs itself): discordant 0
  level gains: chosen lead 0.96 vs others' mean 1.20 (difference -0.24)
screening: chosen at 200 = 2, at 400 = 0, at 1000 = 2; agree 200 True, 400 False

== team b2branch  builds [['garchomp', 51], ['infernape', 53], ['staraptor', 53], ['rotom', 53], ['floatzel', 53], ['weavile', 54]]
lead species       cleared  clear [ci95]             aaron  bertha   flint  lucian  cynthi   expected final levels (member order)   lead gain
   0 garchomp     1586/2000  0.7930 [0.7747, 0.8102]   1.000   1.000   1.000   0.997   0.795   [52.99, 53.16, 53.35, 53.03, 53.10, 54.43]   1.99
   1 infernape    1471/2000  0.7355 [0.7157, 0.7544]   1.000   0.999   1.000   0.979   0.752   [52.01, 54.47, 53.16, 53.04, 53.17, 54.44]   1.47
   2 staraptor    1444/2000  0.7220 [0.7020, 0.7412]   0.998   0.999   1.000   0.988   0.733   [51.93, 53.64, 54.01, 53.33, 53.25, 54.43]   1.01
   3 rotom        1383/2000  0.6915 [0.6709, 0.7114]   1.000   0.998   1.000   0.972   0.713   [51.98, 53.90, 53.11, 53.92, 53.20, 54.43]   0.92
   4 floatzel     1477/2000  0.7385 [0.7188, 0.7573]   1.000   0.999   1.000   0.972   0.761   [51.98, 53.52, 53.18, 53.18, 54.26, 54.40]   1.26
   5 weavile      1419/2000  0.7095 [0.6892, 0.7290]   1.000   0.998   1.000   0.977   0.728   [51.98, 53.75, 53.11, 53.27, 53.32, 55.05]   1.05
spread: best lead 0 (garchomp) 0.7930, worst lead 3 (rotom) 0.6915: 10.2 points (vs (12, 8, 15) at n 100)
split-sample: chosen on pairs 0..999 = lead 0 (garchomp); first-listed already best (0 discordant; no gain)
  held-out pairs 1000..1999: chosen 0.8030 vs first-listed 0.8030; only-chosen 0 only-first 0; p 1; verdict indistinguishable; supported gain: False
  naive all 2,000 pairs [selection-biased]: chosen 0.7930 vs first 0.7930; only-chosen 0 only-first 0; p 1; verdict indistinguishable
  control (first-listed vs itself): discordant 0
  level gains: chosen lead 1.99 vs others' mean 1.14 (difference +0.85)
screening: chosen at 200 = 0, at 400 = 0, at 1000 = 0; agree 200 True, 400 True

== team b2v2  builds [['garchomp', 51], ['infernape', 53], ['staraptor', 53], ['rotom', 53], ['floatzel', 53], ['weavile', 54]]
lead species       cleared  clear [ci95]             aaron  bertha   flint  lucian  cynthi   expected final levels (member order)   lead gain
   0 garchomp     1542/2000  0.7710 [0.7521, 0.7889]   1.000   1.000   1.000   0.996   0.774   [53.00, 53.16, 53.36, 53.03, 53.09, 54.43]   2.00
   1 infernape    1482/2000  0.7410 [0.7214, 0.7597]   0.999   0.998   0.999   0.981   0.757   [52.01, 54.47, 53.16, 53.05, 53.18, 54.45]   1.47
   2 staraptor    1483/2000  0.7415 [0.7219, 0.7602]   1.000   0.999   0.999   0.984   0.754   [51.93, 53.66, 54.00, 53.33, 53.24, 54.46]   1.00
   3 rotom        1369/2000  0.6845 [0.6638, 0.7045]   1.000   0.998   1.000   0.976   0.702   [51.98, 53.91, 53.11, 53.93, 53.20, 54.39]   0.93
   4 floatzel     1479/2000  0.7395 [0.7198, 0.7583]   0.999   0.996   1.000   0.980   0.758   [51.97, 53.56, 53.16, 53.18, 54.24, 54.43]   1.24
   5 weavile      1432/2000  0.7160 [0.6958, 0.7353]   0.999   0.999   1.000   0.973   0.737   [52.00, 53.73, 53.11, 53.28, 53.33, 55.04]   1.04
spread: best lead 0 (garchomp) 0.7710, worst lead 3 (rotom) 0.6845: 8.7 points (vs (12, 8, 15) at n 100)
split-sample: chosen on pairs 0..999 = lead 0 (garchomp); first-listed already best (0 discordant; no gain)
  held-out pairs 1000..1999: chosen 0.7770 vs first-listed 0.7770; only-chosen 0 only-first 0; p 1; verdict indistinguishable; supported gain: False
  naive all 2,000 pairs [selection-biased]: chosen 0.7710 vs first 0.7710; only-chosen 0 only-first 0; p 1; verdict indistinguishable
  control (first-listed vs itself): discordant 0
  level gains: chosen lead 2.00 vs others' mean 1.14 (difference +0.86)
screening: chosen at 200 = 0, at 400 = 0, at 1000 = 0; agree 200 True, 400 True

{"supported_gain": {"b2main": false, "b2branch": false, "b2v2": false}, "not_judged": [], "confirmation_stage_check": "no-go (reporting follow-on only)"}
```

**Question (1), SC-001: PASS.** Eighteen recordings, identical seed lists per team (check_paired), three complete tables. Spread (best minus worst
lead): b2main 9.2 points (Staraptor 0.9295 vs Floatzel 0.8380), b2branch 10.2 (Garchomp 0.7930 vs Rotom 0.6915), b2v2 8.7 (Garchomp 0.7710 vs
Rotom 0.6845), against 12 / 8 / 15 at n 100. Aaron, Bertha and Flint at 0.996 or better under every lead; the lead moves Lucian by up to 3.5
points and Cynthia by up to 8 points. The lead's own level gain is 0.9 to 2.0 levels; Garchomp leading gains the most (1.7 to 2.0).
**Question (2), SC-002 / SC-003: no supported gain on any team.** b2main: chosen on the first half Staraptor; held-out 0.9260 vs 0.9060,
only-chosen 85 / only-first 65, p 0.121 (indistinguishable); naive 2,000-pair p 0.0695 (selection-biased). b2branch and b2v2: the first-listed
Garchomp is already the best lead on the first half (held-out lead vs itself, 0 discordant). Pairing control 0 discordant on all three.
**Question (3), SC-004.** 200 pairs chose the same lead as 1,000 on all three teams; 400 pairs disagreed on b2main (chose Garchomp) and
agreed on the other two. Level gains: chosen lead versus the others' mean -0.24 (b2main, Staraptor) and +0.85 / +0.86 (Garchomp).
**Verdict for the confirmation-stage check: no-go** (question 2's rule); the reporting follow-on (the lead named in every output) stands.
Note for the follow-on: on all three optimizer-built teams (the same six species at different levels) Garchomp first was the best or within
the noise of the best lead, and Garchomp leading also levels the most; a lead choice bundles matchup and exp (research R6).

## T019 Gates (6:15:34 to 6:28:02 PM EST, nothing else running)

```
=== gates start 6:15:34 PM EST
sha256:299b1b556a0066a2d004e6026d9e2c12fd7bb47fa04c6446e34c24565301b59b sha256:e01c1cfd882af6859226bcf65e3327a259f1860c2796f8fe8d500f3400ee50c3
diff main -- sim src/platsim lines=0
node exit=0
# tests 351
# pass 351
# fail 0
# duration_ms 146432.689156
fast start 6:18:01 PM EST
fast exit=0
================================= battle split =================================
0 battle worker starts; 0 marked tests reached it; under-marked 0, started outside a test 0, over-marked 0
554 passed, 28 deselected, 4 xfailed, 1 warning in 598.35s (0:09:58)
=== gates end 6:28:02 PM EST
```

(a) Code hashes equal the T001 before-hashes. (b) `git diff --stat main -- sim src/platsim`: empty. (c) Node suite 351 pass, 0 fail, 146.4 s.
(d) Fast-mode pytest 554 passed, 28 deselected, 4 xfailed, exit 0, 598.4 s (547 after 019; the 7 new tests are the lead-spike tests); battle
split clean. The full pytest suite is skipped for this merge because (a) and (b) hold (FR-012, SC-006).

## T020 Close

Commits on the branch: 45ca503 (scripts and tests), abb375c (recordings and the split-sample test), 14d047d (records and docs), then this
one (gates). Merge to `main` only on the user's go: `git checkout main && git merge --ff-only 020-lead-spike && git push`.
