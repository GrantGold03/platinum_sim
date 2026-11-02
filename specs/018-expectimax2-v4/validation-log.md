# Validation log: feature 018 (expectimax2-v4, reference-first approximations)

Times are US Eastern. Evidence files (pairs cache, optimizer outputs, bench JSON, suite logs) live in
`runs/018-evidence/` (git-ignored, local). Branch `018-expectimax2-v4` from `main` 7a88ae6 (2026-11-02). Every
measurement and ladder run is alone on the machine (`pgrep -a -x node; pgrep -a pytest` empty first). Commit hashes are
recorded as they land.

## T001 Setup (3:24 PM EST)

- `git diff --stat main HEAD -- sim src tests`: empty (the Spec Kit 1.2.6 upgrade commit `875080a` touched no `sim/`, `src/` or `tests/` file; exit 0).
- `mkdir -p runs/018-evidence/pairs` done.

## T002 The four fixed teams (present, loaded)

| Team | Source | Members (species, start level, held item) |
|---|---|---|
| bench | `tests/fixtures/policy_benchmark_team.json` `.team` | infernape 57, staraptor 57, luxray 57, garchomp 57, gyarados 57, alakazam 57; no items |
| ref | `tests/fixtures/reference_team.json` `.builds` | infernape 60, staraptor 60, luxray 60, garchomp 60, gyarados 60, gardevoir 60; no items |
| b2main | `runs/014-evidence/b2-main/result.json` `.team.builds` | garchomp 52 sitrus_berry, infernape 54 sitrus_berry, staraptor 53 sitrus_berry, rotom 55 zap_plate, floatzel 55 sitrus_berry, weavile 53 sitrus_berry |
| b2branch | `runs/014-evidence/b2-branch/result.json` `.team.builds` | garchomp 51 earth_plate, infernape 53 sitrus_berry, staraptor 53 sitrus_berry, rotom 53 expert_belt, floatzel 53 sitrus_berry, weavile 54 sitrus_berry |

No regeneration needed.

## T003 Replay gate on unchanged code, branch at bbe3bbe (3:24:39 to 3:25:00 PM EST)

`(cd sim && node --test test/replay.test.mjs)`: 3 tests, 3 pass, exit 0; `replay: 80 gauntlets, 6144 player decisions,
16 workers, 20.2 s` (`runs/018-evidence/t003-replay.log`). The 015 fixture is the v1/v2 reference for this base.

## T004-T010 US1: expectimax2-v4, per-version search budget, candidate names (3:26 to 3:34:23 PM EST)

- Tests first: the new `expectimax2.test.mjs` and `gauntlet.test.mjs` tests failed on the missing exports
  (`EXPECTIMAX2_V4`, `V4_OPTS`) before T007/T008. One test assumption corrected after implementation: on the Spiritomb
  position v4 floors no branch (every first-ply weight is above 0.02 there), so the floor check now runs one Aaron
  battle (v4 floors > 0 branches, v2 floors 0). Not a behaviour issue.
- After T007/T008: `expectimax2 + gauntlet + determinism + replay + ai_golden`: **45 pass, 0 fail**: v1/v2 options
  unchanged, `V4_OPTS` provisional `{ kRoot 4, kPly2 1, beam 1, floor 0.02 }`, beam and root-sample bounds hold on the
  Spiritomb position; candidate names resolve, cache, reject nine malformed forms with `invalid_policy`, and a candidate
  spelling out `V4_OPTS` equals `expectimax2-v4` byte for byte on two Aaron gauntlets (shared seeding) while a
  different knob changes the result (positive control); determinism holds for v4 (200 gauntlets); **replay for v1/v2
  unchanged** (digests `db6d20cf…` / `1273b694…`, every choice and draw count).
- Full Node suite 3:32:01 to 3:34:23 PM EST: **351 pass, 0 fail, exit 0**, 142.0 s (`runs/018-evidence/node-suite-c1.log`).

## T011-T015 US3 code half: one default constant, `optimize --player-policy` (3:35 to 4:13:38 PM EST)

- Tests first: `tests/unit/test_default_policy.py` (new) and the resume test addition failed before T013 (4 failures);
  after: 17 passed. Two corrections while gating, both test-side or precedent: (1) the first fingerprint version added
  `player_policy` unconditionally and broke the two tests that pin the recorded default fingerprint
  (`test_required_hms`, `test_legality_options`); changed to the feature-006 `required_hms` rule (the key joins the
  fingerprint only when the policy differs from the default), contract and data model updated; (2) a missing
  module-level import in `run.py` (my guard mistook a comment for the import) made the first fast-mode rerun fail 14
  tests with `NameError`; fixed. Deviation from T017's wording: the script's unit test lives in its own file
  `tests/unit/test_paired_policies.py` (the existing `test_scripts.py` covers the decomp field-script parser, not the
  014 scripts).
- Smoke (3:37 PM EST): `optimize … --player-policy expectimax2-v9` exits 1 at once with `worker does not offer
  'expectimax2-v9' (policies: [... 'expectimax2-v4'])`; `--player-policy expectimax2-v4` runs (stopped after 75 s in the
  calibrate stage) and `state.json` records `fingerprint.player_policy = expectimax2-v4` (`runs/018-evidence/smoke-*`).
- Gates: targeted unit files **47 passed** (45.8 s); fast mode 4:03:23 to 4:13:38 PM EST: **535 passed, 28 deselected,
  4 xfailed, exit 0**, 612.4 s (`runs/018-evidence/fast-c2.log`; 528 + 7 new).

## Commit 2 (4:14 PM EST)

`412783d feat(018): one default player constant; optimize --player-policy (default unchanged)`, pushed.

## T018 Pairing control (4:14:15 to 4:15:11 PM EST)

`paired_policies.py --a expectimax2-v2 --b expectimax2-v2 --self --teams bench --runs 200 --workers 16`: exit 0,
pool 16 workers, `sim_code_hash` sha256:f4a1eaa5…; two independent passes of v2 on `bench`: 160/200 and 160/200,
**0 discordant pairs** (`runs/018-evidence/pairs/control.txt`). The pairing works; the cache for the second pass is
`bench__expectimax2-v2__200__self2.json`.

## T019 Single knob 1 and the v2 sides (4:15:11 to 4:39:42 PM EST)

`--a 'expectimax2-v4?kRoot=8&kPly2=1&beam=2&floor=0' --b expectimax2-v2 --runs 2000 --workers 16`, exit 0. The v2 sides
are now cached for all four teams (`<team>__expectimax2-v2__2000.json`). Pool throughput here is with `stop_on_loss`
(a lost gauntlet ends early), so it is higher than the bench tool's.

| candidate | team | A cleared / rate | B (v2) cleared / rate | only A / only B | p | verdict | A / B gauntlets/s |
|---|---|---|---|---|---|---|---|
| kPly2 1 (8/1/2/0) | bench | 1695 / 0.8475 | 1719 / 0.8595 | 182 / 206 | 0.243 | indistinguishable | 10.57 / 9.15 |
| kPly2 1 | ref | 1881 / 0.9405 | 1892 / 0.9460 | 88 / 99 | 0.465 | indistinguishable | 12.19 / 9.83 |
| kPly2 1 | b2main | 1820 / 0.9100 | 1830 / 0.9150 | 107 / 117 | 0.548 | indistinguishable | 13.75 / 10.95 |
| kPly2 1 | b2branch | 1552 / 0.7760 | 1590 / 0.7950 | 169 / 207 | 0.0562 | indistinguishable | 13.90 / 11.02 |

**kPly2 1: passes** (no team with verdict B), with a consistent small deficit (0.5 to 1.9 points) and b2branch at
p 0.056, close to the line; worth watching in the combinations.

## T020 Single knobs 2 to 5 (4:40:22 to 5:30:40 PM EST; v2 sides from the cache)

| candidate | team | A cleared / rate | B (v2) cleared / rate | only A / only B | p | verdict | A / B gauntlets/s |
|---|---|---|---|---|---|---|---|
| beam 1 (8/2/1/0) | bench | 1743 / 0.8715 | 1719 / 0.8595 | 234 / 210 | 0.275 | indistinguishable | 9.89 / 9.15 |
| beam 1 | ref | 1876 / 0.9380 | 1892 / 0.9460 | 88 / 104 | 0.279 | indistinguishable | 11.52 / 9.83 |
| beam 1 | b2main | 1783 / 0.8915 | 1830 / 0.9150 | 120 / 167 | **0.00652** | **B** | 12.06 / 10.95 |
| beam 1 | b2branch | 1587 / 0.7935 | 1590 / 0.7950 | 253 / 256 | 0.929 | indistinguishable | 12.06 / 11.02 |
| kRoot 4 (4/2/2/0) | bench | 1699 / 0.8495 | 1719 / 0.8595 | 198 / 218 | 0.352 | indistinguishable | 9.72 / 9.15 |
| kRoot 4 | ref | 1887 / 0.9435 | 1892 / 0.9460 | 90 / 95 | 0.769 | indistinguishable | 10.74 / 9.83 |
| kRoot 4 | b2main | 1831 / 0.9155 | 1830 / 0.9150 | 109 / 108 | 1 | indistinguishable | 12.03 / 10.95 |
| kRoot 4 | b2branch | 1591 / 0.7955 | 1590 / 0.7950 | 178 / 177 | 1 | indistinguishable | 12.03 / 11.02 |
| floor 0.02 (8/2/2/0.02) | bench | 1699 / 0.8495 | 1719 / 0.8595 | 184 / 204 | 0.335 | indistinguishable | 9.52 / 9.15 |
| floor 0.02 | ref | 1885 / 0.9425 | 1892 / 0.9460 | 87 / 94 | 0.656 | indistinguishable | 10.42 / 9.83 |
| floor 0.02 | b2main | 1810 / 0.9050 | 1830 / 0.9150 | 111 / 131 | 0.222 | indistinguishable | 11.50 / 10.95 |
| floor 0.02 | b2branch | 1597 / 0.7985 | 1590 / 0.7950 | 169 / 162 | 0.742 | indistinguishable | 11.51 / 11.02 |
| floor 0.05 (8/2/2/0.05) | bench | 1712 / 0.8560 | 1719 / 0.8595 | 191 / 198 | 0.761 | indistinguishable | 10.47 / 9.15 |
| floor 0.05 | ref | 1884 / 0.9420 | 1892 / 0.9460 | 84 / 92 | 0.598 | indistinguishable | 11.60 / 9.83 |
| floor 0.05 | b2main | 1805 / 0.9025 | 1830 / 0.9150 | 120 / 145 | 0.14 | indistinguishable | 12.91 / 10.95 |
| floor 0.05 | b2branch | 1611 / 0.8055 | 1590 / 0.7950 | 191 / 170 | 0.292 | indistinguishable | 13.01 / 11.02 |

**Verdicts per knob**: kPly2 1 pass; **beam 1 FAIL** (b2main worse, p 0.0065; excluded from every combination);
kRoot 4 pass; floor 0.02 pass; floor 0.05 pass. The beam was the second-largest sizing gain (1.22x); it goes.

**Combination order (T021)**, fastest first by the sizing figures, beam fixed at 2: C1 = kRoot 4 + kPly2 1 + floor 0.05;
C2 = kRoot 4 + kPly2 1 + floor 0.02; C3 = kPly2 1 + floor 0.05; C4 = kPly2 1 + kRoot 4; C5 = kRoot 4 + floor 0.05;
C6 = kPly2 1 + floor 0.02; stop at the first pass. Each is 4 teams x 2,000 paired runs (about 12 min).

## T021 Combination 1 (5:31:28 to 5:40:30 PM EST)

`--a 'expectimax2-v4?kRoot=4&kPly2=1&beam=2&floor=0.05' --b expectimax2-v2 --runs 2000 --workers 16`, exit 0:

| candidate | team | A cleared / rate | B (v2) cleared / rate | only A / only B | p | verdict | A / B gauntlets/s |
|---|---|---|---|---|---|---|---|
| C1 (4/1/2/0.05) | bench | 1701 / 0.8505 | 1719 / 0.8595 | 200 / 218 | 0.406 | indistinguishable | 13.98 / 9.15 |
| C1 | ref | 1886 / 0.9430 | 1892 / 0.9460 | 87 / 93 | 0.709 | indistinguishable | 15.57 / 9.83 |
| C1 | b2main | 1822 / 0.9110 | 1830 / 0.9150 | 120 / 128 | 0.657 | indistinguishable | 17.36 / 10.95 |
| C1 | b2branch | 1569 / 0.7845 | 1590 / 0.7950 | 197 / 218 | 0.326 | indistinguishable | 17.53 / 11.02 |

**C1 passes on all four teams**: the ladder stops at its first combination (FR-005). No other combination was run
(C2-C6 were not needed; the order is recorded above should C1 ever be revisited).

## T022 Ladder summary (SC-002, SC-003)

Every candidate x team row is in T019-T021 (28 rows plus the control). Chosen set: **`V4_OPTS = { kRoot: 4, kPly2: 1,
beam: 2, floor: 0.05 }`** (koStop and the v2 leaf weights unchanged). Per team vs v2: bench -0.9 pt (p 0.41), ref -0.3 pt
(p 0.71), b2main -0.4 pt (p 0.66), b2branch -1.05 pt (p 0.33); none statistically supported at alpha 0.05, so "not worse"
by the 014 rule, with a consistent small deficit a reader should know about. Excluded: switch beam 1 (worse on b2main,
p 0.0065). Pool speed of C1 vs v2 with `stop_on_loss`: 1.53x, 1.58x, 1.59x, 1.59x on the four teams. Pairing control:
0 discordant pairs. Total ladder wall: 4:14 to 5:40 PM EST (1 h 26 min; under the 5 to 6 h estimate because the pool
with `stop_on_loss` runs 9 to 17 gauntlets/s rather than the 4.5 estimated from the bench tool's full gauntlets).
`runs/018-evidence/pairs/summary.json` holds the 29 rows.

## Commit 3 (5:41 PM EST)

`6e00512 test(018): paired policy comparison script; ladder recorded (v4 = kRoot 4, kPly2 1, beam 2, floor 0.05)`, pushed.

## T024 Final `V4_OPTS` (5:41 PM EST)

`sim/policy/expectimax2.mjs`: `V4_OPTS = { ...V2_OPTS, kRoot: 4, kPly2: 1, beam: 2, floor: 0.05 }` with the ladder's
numbers in the VERSIONS entry; `expectimax2.test.mjs` asserts the final set. `expectimax2 + gauntlet` tests: 14 pass.

## T025 The v4 replay-fixture entry (5:41:50 to 5:42:33 PM EST)

`node sim/bench.mjs --policy expectimax2-v4 --record sim/test/replay_prof_a.json` (alone): exit 0, **2.0514 gauntlets/s,
5.447 ms/decision**, AI draws 343,327, interpreter steps 6,526,653, 40 gauntlets, **`digest_full 05fa8cb1…`**. The v1 and
v2 subtrees of the fixture are byte-identical to before (JSON comparison of `policies['expectimax2-v1']` and
`['expectimax2-v2']`; the file-level `recorded` block now says commit 6e00512, `sim_code_hash` sha256:d74ca541…).
`replay.test.mjs` expects three policies; `(cd sim && node --test test/replay.test.mjs)`: **3 pass, exit 0**,
`replay: 120 gauntlets, 8997 player decisions, 16 workers, 22.6 s` (`runs/018-evidence/t025-replay.log`).

## T026 Policy-strength tests cover v4, in-suite smoke (5:43:08 to 5:46:31 PM EST)

`PLATSIM_STRENGTH_N=400 PLATSIM_REVERSAL_N=200 uv run pytest -q tests/integration/test_policy_strength.py -s`: **3 passed**,
202.8 s (`runs/018-evidence/strength-smoke.log`). Benchmark team, 400 paired: greedy 0.1575, v1 0.5000, v2 0.8575,
**v4 0.8450**; v4 vs greedy only 286/11, p 2.7e-70, verdict A; **v4 vs v2 only 44/49, p 0.679, indistinguishable**.
Reversal team, 200 paired: greedy 0.8500, v2 0.8750, v4 0.8700; v4 vs greedy p 0.659, indistinguishable (not worse).
v4 ran 13.7 and 14.2 gauntlets/s on the pool vs v2's 9.0 and 7.9. The full-size run (2,000) is the merge-gate suite (T037).

## T027 Before/after on the same seeds (FR-006, SC-004), alone, 5:46:31 to 5:48:33 PM EST

`node sim/bench.mjs --policy <p> --json` → `runs/018-evidence/bench_v2.json`, `bench_v4.json`; `uv run platsim bench
--policy <p> --workers 16 --json` → `pool_v2.json`, `pool_v4.json`. All exit 0; `digests_agree` true on both sides; v2's
digest is `main`'s `db6d20cf…`; **v4's single-process digest equals its fixture entry `05fa8cb1…`**.

| Measure, same 40 gauntlets, same session | expectimax2-v2 | expectimax2-v4 | ratio |
|---|---|---|---|
| single process, gauntlets/s | 1.2791 | **2.0968** | **1.64x** (target 1.5x) |
| single process, ms/decision | 9.593 | 5.334 | |
| trainer-AI calls per decision | 44.69 | 17.77 | |
| interpreter steps per run | 15,893,649 | 6,526,653 | |
| cleared (sanity) | 36/40 | 37/40 | |
| 16-worker pool, wall | 8.256 s | **6.098 s** | **1.35x** |
| 16-worker pool, gauntlets/s | 4.8451 | 6.5599 | 1.35x |

**SC-004 met**: faster single process (1.64x, above the 1.5x target) and on the pool (1.35x; 40 jobs on 16 workers is
tail-bound, as in 015-017).

## T028 Gate and commit 4 (5:48:33 to 5:50:57 PM EST)

Full Node suite: **351 pass, 0 fail, exit 0**, 143.7 s (`runs/018-evidence/node-suite-c4.log`).

## Commit 4 (5:51 PM EST)

`718002f feat(018): expectimax2-v4 final search budget; replay fixture entry; strength tests cover v4`, pushed.

## T030-T031 B2 end to end (5:51:44 to 6:04:59 PM EST, alone)

`uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --player-policy <p>
--workers 16 --out runs/018-evidence/b2-<p>`, both exit 0 (`b2-expectimax2-v2.log`, `b2-expectimax2-v4.log`).

| | expectimax2-v2 | expectimax2-v4 |
|---|---|---|
| wall | 407 s (6 min 47 s) | **350 s** (5 min 50 s), ratio 0.86 |
| final team (species, start level, item) | garchomp 51 earth_plate, infernape 53 sitrus, staraptor 53 sitrus, rotom 53 expert_belt, floatzel 53 sitrus, weavile 54 sitrus | garchomp **54** earth_plate, infernape **52** sitrus, staraptor **54** sitrus, rotom **54** expert_belt, floatzel **54** sitrus, weavile **55** sitrus |
| mean start level | 52.83 | 53.83 |
| expected average final level (own levels, 500 confirm runs, quick) | 53.34 | 54.30 |
| clear rate at own levels (500 runs) | 0.838 | 0.886 |
| `result.json.player_policy` | expectimax2-v2 | expectimax2-v4 |

Consistency check of 015-017 (exact speedups): the v2 re-run's team is **identical** to the 014 branch result's team
(species, moves, items, levels); the 014 wall was 1198 s on the then-current code, 407 s today. `uv run platsim validate
runs/018-evidence/b2-expectimax2-v4/team.json`: **legal (no violations)** (`validate-v4.txt`). Quick never qualifies
(`qualified false` on both sides, by design).

## T032 Equal-levels comparison (6:04:59 to 6:13:26 PM EST)

Control (`equal_levels.py … 200 --self`): B against itself, 0 discordant pairs, OK. Comparison (`… 2000`): both final
teams at A's (the v4 result's) start levels [54, 52, 54, 54, 54, 55], played by `expectimax2-v2`, master `018-equal|B2`:
**A 0.8595 vs B 0.8595, only 0/0, p 1, indistinguishable; mean final level 54.2955 vs 54.2955** (`equal-levels.txt`,
385 s). FR-007's letter is met (no drop, no higher mean final level).

**Finding (Principle V, stated plainly).** The two optimizer results have the same species, moves and items and differ
ONLY in start levels, so at equal levels they are the same team and the comparison cannot distinguish them (0 discordant
pairs is the identity, not evidence of parity). The real end-to-end difference is in the objective itself: with v4 the
optimizer settled one level higher on five of six members (+0.95 expected average final level on B2 at the quick
budget). The mechanism is the ladder's consistent small deficit (0.3 to 1.05 points of clear rate, never statistically
supported on 2,000 paired runs): the level search bisects on the clear-rate threshold, so a slightly weaker player
crosses it one level later. Whether this is noise of the quick level search or v4's systematic cost cannot be decided
from one seed; it is the question the user must weigh before the default switch (T033).
