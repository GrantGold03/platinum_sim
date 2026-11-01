# Validation log: feature 016, exact damage-path speedups (round two)

Times are US Eastern (EST). Evidence files in `runs/016-evidence/` (git-ignored, local only). Every number below
was observed in this log's session; "unverified" is written where it was not.

Branch `016-exact-damage-speedups`, base `main` 19519ed (015 merged 2026-11-01). Spec/plan/tasks commits:
5d7c2c3, 8cea2cf, aaeedad, 7b07742, cb17c0e (docs only).

## T001 Log and evidence dir (2026-11-01, 5:55 PM)

- `mkdir -p runs/016-evidence`.
- `git diff --stat main HEAD -- sim src tests`: empty, exit 0 (branch = main + spec docs).

## T002 Baseline on `main` 19519ed, single process (5:54:26 to 5:56:47 PM, alone)

`node sim/bench.mjs --policy <p> --json` → `runs/016-evidence/main_v2.json`, `main_v1.json`, both exit 0.

| policy | digest_full | wall | gauntlets/s | ms/decision | ai_draws | cleared |
|---|---|---|---|---|---|---|
| expectimax2-v2 | db6d20cf… (= fixture) | 55.168 s | 0.7251 | 17.800 | 849,962 | 36/40 |
| expectimax2-v1 | 1273b694… (= fixture) | 84.288 s | 0.4746 | 23.987 | 1,206,240 | 28/40 |

Note: 015's log measured v2 at 0.7793 / 16.57 ms on the same code the day before; today's machine is about 7%
slower on both the single run and the pool (T003). The branch is compared with today's figures (same session,
same conditions), not with 015's.

## T003 Baseline on `main` 19519ed, 16-worker pool (5:56:47 to 5:57:58 PM, alone)

`uv run platsim bench --workers 16 --json` → `runs/016-evidence/main_pool.json`, exit 0, `digests_agree` true.
Single half inside it: 0.7397 gauntlets/s, 17.438 ms/decision (second v2 run of the session). Pool: 16 workers,
**13.725 s, 2.9144 gauntlets/s**, `pool_digest_logs` be27826f… (= 015's cross-language digest),
`pool_sim_code_hash` sha256:719e63b0…. Switched back to the branch (cb17c0e).

## T004 Replay gate on the unchanged branch (5:58:34 to 5:59:06 PM)

`(cd sim && node --test test/replay.test.mjs)`: **3 tests, 3 pass, exit 0**; diagnostic `80 gauntlets, 6144 player
decisions, 16 workers, 31.1 s`. The 015 fixture is the reference for `main` 19519ed on this branch
(`runs/016-evidence/replay-t004.log`).

## T005-T007 US1: type-chart plan (6:00 to 6:04 PM)

- T005 `sim/test/damage_typechart.test.mjs` written first; red run: `SyntaxError: ... does not provide an export
  named 'DAMAGE_STATS'` (1 test, 0 pass, 1 fail), as expected before T006.
- T006/T007 `sim/damage.mjs`: `applyTypeChartDirect` (the former body, verbatim, `DAMAGE_STATS.direct++`),
  `planMultiplier`, `typeChartPlan` / `typeChartPlanP`, `replayTypeChart`, `applyTypeChart` = plan + replay,
  `DAMAGE_STATS`; `calcBaseDamage`, `applyScriptMultipliers`, `critBlocked`, `critMultiplier` split into exported
  wrappers + private `…P(prep, …)` bodies; `calcDamage` prepares once, plans once, replays 16 times. Header map updated.
- First green run: equivalence test **0 mismatches** over 20,000 synthetic + 1,500 real-data matchups x 16 rolls
  in 2.6 s, seed `16c0de`; coverage (all >= 100): wonderGuard 498, notVeryEffective 2653, superEffective 2311,
  seedMask 2428, typeOverride 6447, ignoreTypeChecks 5035, struggle 674, stab 1365, tintedLens 278, normalize 1263,
  foresightScrappy 412, zeroDamage 1253, levitate 183, miracleEye 505, magnetRise 467, immune 779, roost 707,
  filterSolidRock 293, groundedFlying 538, adaptability 344, expertBelt 274. The positive-control test failed once on
  an immune plan (`steps [{mul 0}], mask 8`: a flipped STAB cannot change a zero), fixed by excluding immune plans
  from the control's sample (test-only change); then **4 tests, 4 pass**: control detects a dropped multiplier step
  and a flipped STAB on 200/200 plans; `calcDamage` equals the 16-fold direct computation on 300 matchups x
  {normal, crit}; `DAMAGE_STATS` deltas +1 plan / +16 replays / +0 direct per `calcDamage`, and +1 direct when the
  reference runs.

## T008 US1 gate (6:04:49 PM onward)

- Targeted: `node --test test/damage.test.mjs test/replay.test.mjs test/ai_golden.test.mjs test/ai_gauntlet.test.mjs
  test/damage_typechart.test.mjs`: **140 tests, 140 pass, exit 0**; replay diagnostic 30.4 s, both digests and every
  choice/draw count equal to the fixture (`runs/016-evidence/t008-targeted.log`).
- Freeze run `PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs`: **154 pass, exit 0**
  (`t008-freeze.log`).
- Full Node suite and the US1 attribution bench: below.
- Full Node suite `(cd sim && node --test test/*.test.mjs)` 6:06:48 to 6:09:35 PM: **330 tests, 330 pass, 0 fail,
  exit 0** (326 + the 4 new; `runs/016-evidence/node-suite-c1.log`).
- **US1 attribution** (alone, 6:09:43 to 6:10:34 PM): `node sim/bench.mjs --policy expectimax2-v2 --json` →
  `bench-c1-v2.json`: digest `db6d20cf…`, `ai_draws` 849,962 (= T002), 36/40 cleared, wall 50.913 s,
  **0.7857 gauntlets/s, 16.336 ms/decision** (T002 `main`: 0.7251 / 17.800 → **1.084x**). Expected: US1 removes the
  policy path's 32 chart walks + 36 prepare() per table entry (about 7 points of the profile); the AI path's walk per
  move per sample is replaced by one plan + one replay per call, so its share moves to US2's memo.
