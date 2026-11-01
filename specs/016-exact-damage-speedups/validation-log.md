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

## T009 Commit 1 (6:11 PM)

`ba9fd21 perf(016): type-chart plan replayed per roll (exact; equivalence test vs the kept reference; replay digest
unchanged)`, pushed. Files: `sim/damage.mjs`, `sim/test/damage_typechart.test.mjs`, this log, tasks.md.

## T010-T014 US2: pre-variance memo and CHECK mode (6:11 to 6:14 PM)

- Tests first (T010 `ai_adapter.test.mjs`: "016 preVariance / typeChartPlan" and the freeze-guard child extended to
  the plan and the entry; T011 "016 CHECK mode" child processes; T012 `ai_cmds_damage.test.mjs` "016 preVariance
  per decision"). Red run: 30 tests, 26 pass, **4 fail** (the three new tests and the extended freeze test), as
  expected before T013.
- T013 `sim/ai/adapter.mjs`: `CHECK`, `CHECK_STATS`, `plans` / `pre` maps in the decision cache (cleared by
  `beginDecision`), `cacheStats` fields, `typeChartPlan` (memo) and `preVariance` on the api, `memoKey` / `slotFor` /
  `checkSame` / `planFor` / `computePreVariance`; header paragraph. T014 `sim/ai/calcdamage.mjs`: `calcDamage` uses
  `ai.preVariance`, `applyTypeChart` replays `ai.typeChartPlan`; `portInput` replaced by `battlerPair` + `portOpts`;
  imports trimmed (`calcBaseDamage`, `applyTypeChart` no longer imported there); header note. Analysis finding V1:
  `sim/bench.mjs` imports `CHECK_STATS` and reports `check_stats` (deltas) when `PLATSIM_AI_CHECK=1`.
  `sim/ai/INTERFACE.md`: "Decision memos (feature 016)" section.
- First green run: 29/30; the one failure was the by-hand check in T012 picking Explosion (power 250), whose effect
  is on the AI's no-damage-calc list (TAI:31-45), so the AI returns 0 for it; the test now selects the move with the
  AI's own eligibility (`damageCheckApplies`, excluding alt-power moves) — Earthquake. Then **30/30**.

## T015 US2 gate (6:14:42 to 6:21:12 PM, `runs/016-evidence/gate-c2.status`)

- Targeted (`ai_adapter`, `ai_cmds_damage`, `replay`, `ai_golden`): **51 pass, exit 0**; replay digests, choices and
  per-decision draws equal to the fixture (`t015-targeted.log`).
- Freeze run: **157 pass, exit 0** (`t015-freeze.log`). Full Node suite: **333 tests, 333 pass, exit 0**
  (`node-suite-c2.log`; 326 + 4 US1 + 3 US2).
- **Full-set CHECK runs** (`PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy <p> --json`): v2 `check_v2.json` exit 0,
  digest `db6d20cf…`, `ai_draws` 849,962, **5,587,041 checks, 0 mismatches** (55.13 s); v1 `check_v1.json` exit 0,
  digest `1273b694…`, `ai_draws` 1,206,240, **7,901,536 checks, 0 mismatches** (80.45 s). Both stderr empty (SC-005).
- **US2 attribution** (alone, 6:20:29 to 6:21:12 PM): `bench-c2-v2.json`: digest `db6d20cf…`, `ai_draws` 849,962,
  wall 42.039 s, **0.9515 gauntlets/s, 13.312 ms/decision** (`main` T002 0.7251 / 17.800 → **1.312x**; US1 alone
  1.084x). SC-002's 1.2x bar is already met.

## T016 Commit 2 (6:22 PM)

`d4e6276 perf(016): memoise the trainer AI's pre-variance damage per decision (exact; CHECK mode; replay digest
unchanged)`, pushed. Files: `sim/ai/adapter.mjs`, `sim/ai/calcdamage.mjs`, `sim/ai/INTERFACE.md`, `sim/bench.mjs`,
`sim/test/ai_adapter.test.mjs`, `sim/test/ai_cmds_damage.test.mjs`, this log, tasks.md.

## T017-T018 US3: shared mappers (6:22 to 6:23 PM)

- T017 test "016 shared mappers" appended to `sim/test/ai_adapter.test.mjs`; red run 11 tests, 10 pass, 1 fail (no
  `makeMappers` export / `ai.mappers`), as expected.
- T018 `sim/ai/adapter.mjs`: `makeMappers(dex, T)` exported, five per-kind Maps with a `caches` diagnostic object,
  same validation and error messages; module-level `MAPPERS` WeakMap + `mappersFor(dex, T)`; `createAdapter` uses
  `mappersFor`; `api.mappers` alias of `map`. First run failed on the test side only: the types enum ends with a count
  sentinel (not a `TYPE_*` constant), filtered in the test. Then **11/11** (over 700 identifiers compared, shared ==
  fresh, same four error messages, two adapters share one set, shared caches populated).

## T019 US3 gate (6:23:41 to 6:27:15 PM, `runs/016-evidence/gate-c3.status`)

- Targeted (`ai_adapter`, `replay`, `ai_golden`): **32 pass, exit 0** (`t019-targeted.log`); replay digests, choices,
  draws equal to the fixture. Full Node suite: **334 tests, 334 pass, exit 0** (`node-suite-c3.log`).
- **US3 attribution** (alone, 6:26:36 to 6:27:15 PM): `bench-c3-v2.json`: digest `db6d20cf…`, `ai_draws` 849,962,
  36/40 cleared, wall 38.44 s, **1.0406 gauntlets/s, 12.136 ms/decision** (`main` T002 0.7251 / 17.800 →
  **1.435x**; US1 1.084x, US1+US2 1.312x).

## T020 Commit 3 (6:27 PM)

`a9ddfcf perf(016): share the Showdown-to-decomp id mappers across adapters (exact; replay digest unchanged)`,
pushed. Files: `sim/ai/adapter.mjs`, `sim/test/ai_adapter.test.mjs`, this log, tasks.md.

## T021 Before/after on the same seeds (FR-011, SC-002, SC-003), branch at a9ddfcf, alone, 6:27:49 to 6:30:17 PM

`node sim/bench.mjs --policy <p> --json` → `runs/016-evidence/branch_v2.json`, `branch_v1.json`;
`uv run platsim bench --workers 16 --json` → `branch_pool.json`. All exit 0. Every digest equals `main`'s
(`db6d20cf…`, `1273b694…`, pool `digest_logs` `be27826f…`), `ai_draws` equal, `digests_agree` true;
`pool_sim_code_hash` sha256:c0780523… (changed from `main`'s 719e63b0…, as expected).

| Measure, same 40 gauntlets, same session | `main` 19519ed (T002/T003) | branch a9ddfcf | ratio |
|---|---|---|---|
| expectimax2-v2 single process, gauntlets/s | 0.7251 | **1.0488** | **1.446x** |
| expectimax2-v2 single process, ms/decision | 17.800 | 11.999 | |
| expectimax2-v2 single process, wall | 55.168 s | 38.141 s | |
| expectimax2-v1 single process, gauntlets/s | 0.4746 | 0.7058 | 1.487x |
| expectimax2-v1 single process, ms/decision | 23.987 | 15.843 | |
| expectimax2-v2 16-worker pool, wall | 13.725 s | **10.031 s** | **1.368x** |
| expectimax2-v2 16-worker pool, gauntlets/s | 2.9144 | 3.9878 | 1.368x |
| Attribution (single process, v2): US1 / +US2 / +US3 | | 1.084x / 1.312x / 1.435x | |

**SC-002 met**: 1.0488 >= 0.935 (1.2x of 0.7251); the measured gain, 1.45x, is above the plan's 1.25x to 1.35x
estimate. SC-003: 1.37x on the pool (40 jobs on 16 workers is tail-bound, as in 015). Combined with 015 on the
same set: v2 0.386 (`main` c751fb2, 2026-10-30) → 1.049 gauntlets/s, about 2.7x in two features (different days,
so the cross-feature ratio is indicative only).

## T022-T023 Docs (6:31 to 6:36 PM)

- `README.md`: feature 016 speed table (single process v2/v1, 16 workers) after the 015 table, `sim_code_hash` note
  extended, one line on the three changes and `PLATSIM_AI_CHECK=1`. `FUTURE-FEATURES.md` section 7: the three items
  marked done with attribution, the remaining exact items re-stated with post-015 shares, the approximations
  renumbered to feature 017. `sim/ai/INTERFACE.md`: "Decision memos (feature 016)" section (committed with US2).
  `RUN-STATE.md` START HERE: 016 state, commits, numbers, remaining steps, hand checks.

## T024 Gates (SC-006, FR-010), `runs/016-evidence/gate-c4.status`

- `git diff --stat main HEAD -- pokemon-showdown`: **empty, exit 0** (`showdown-diff.txt`, 0 bytes).
- Full Node suite `(cd sim && node --test test/*.test.mjs)` 6:31:26 to 6:33:41 PM: **334 tests, 334 pass, 0 fail,
  exit 0** (`node-suite.log`; 326 on `main` + 4 US1 + 3 US2 + 1 US3).
- Fast mode `uv run pytest -q -m "not battle_sim"` 6:33:41 to 6:43:35 PM: **528 passed, 28 deselected, 4 xfailed,
  1 warning, exit 0** (590.65 s; `fast.log`).
- Commit 4 (docs + log) below. T025 (full suite, about 1 h 20 min) waits for the user's hands-on testing and go.
