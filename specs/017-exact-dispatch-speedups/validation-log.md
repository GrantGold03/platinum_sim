# Validation log: feature 017 (exact dispatch, damage-input and speed speedups)

Times are US Eastern. Evidence files (bench JSON, suite logs) live in `runs/017-evidence/` (git-ignored, local).
Branch `017-exact-dispatch-speedups` from `main` f6d845c (2026-11-02). Every measurement runs alone on the machine
(`pgrep -a -x node; pgrep -a pytest` empty first). Commit hashes are recorded as they land.

## T001 Setup (10:52 AM EST)

- `git diff --stat main HEAD -- sim src tests`: empty (exit 0), as expected (only spec commits on the branch).
- `mkdir -p runs/017-evidence` done.

## T002 Baseline on `main` f6d845c, single process, alone (10:52:22 to 10:54:00 AM EST)

`node sim/bench.mjs --policy <p> --json > runs/017-evidence/main_<p>.json`, exit 0 both.

| Policy | gauntlets/s | ms/decision | ai_draws | wall s | cleared | digest_full | sim_code_hash |
|---|---|---|---|---|---|---|---|
| expectimax2-v2 | **1.0140** | 12.438 | 849,962 | 39.449 | 36/40 | `db6d20cf…` (expected) | sha256:c0780523… |
| expectimax2-v1 | 0.6999 | 15.980 | 1,206,240 | 57.154 | 28/40 | `1273b694…` (expected) | sha256:c0780523… |

## T003 Baseline pool on `main`, alone (10:54:00 to 10:54:51 AM EST)

`uv run platsim bench --workers 16 --json > runs/017-evidence/main_pool.json`, exit 0: `pool_wall_s` **9.820**,
`pool_gauntlets_per_s` 4.0732, `digests_agree` true, `pool_digest_logs` `be27826f…` (same as the 016 log); the single
half inside it 1.0406 gauntlets/s. Switched back to `017-exact-dispatch-speedups`.

## T004 Replay gate on unchanged code, branch at db43551 (10:55:06 to 10:55:29 AM EST)

`(cd sim && node --test test/replay.test.mjs)`: 3 tests, 3 pass, exit 0; `replay: 80 gauntlets, 6144 player decisions,
16 workers, 23.4 s` (`runs/017-evidence/t004-replay.log`). The 015 fixture is the reference for this base.

## T005-T007 Instrumentation commit (10:56:30 to 10:57:34 AM EST)

- `INTERP_STATS { steps, dispatches }` in `sim/ai/interp.mjs` (one increment per loop iteration, also in the tracing loop
  of `choose.mjs` until T012 merges them); `sim/bench.mjs` reports `interp_steps` / `interp_dispatches` (JSON and table);
  `platsim bench` prints the two rows; `sim/test/bench.test.mjs` gains the "017 interpreter steps" test.
- Gate: `(cd sim && node --test test/bench.test.mjs test/replay.test.mjs test/ai_golden.test.mjs)`: **26 pass, 0 fail, exit 0**
  (`runs/017-evidence/t007-node.log`); `uv run pytest -q tests/unit/test_bench_cli.py`: 3 passed, exit 0.
- Alone: `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c1_v2.json`: digest `db6d20cf…`, `ai_draws`
  849,962 (= T002), **`interp_steps` 142,966,719** (the SC-004 before figure; equal to the 2026-11-02 profiling harness
  count), `interp_dispatches` 0, 1.0301 gauntlets/s, 12.224 ms/decision (within noise of T002's 1.0140).

## T008-T013 US1: effect dispatch, argument index, one interpreter loop (11:02:00 to 11:09:08 AM EST)

- Tests first: `ai_interp.test.mjs` (6 tests) and the golden full-trace test failed on the missing `effectRuns` export
  before T010; after T010-T012 all pass. Structure (real script): **13 runs**, lengths 178, 152, 5, 5, 5, 5, 4, 3, 2, 2,
  1, 1, 1 (= 364 checks; the tasks' "11 heads" guess was wrong: **10** runs of length >= 2 carry a table), 0 splits,
  one repeated value (first wins). Exhaustive equivalence: **10 tables x 279 effect values = 2,790 comparisons,
  0 mismatches**; positive controls (retargeted / deleted entry) detected; synthetic split script yields runs
  `[0,1,false]`, `[2,3,true]` with agreeing tables; argument errors unchanged; one Aaron decision: **151 interpreter
  steps, 10 dispatched runs** (a stepped evaluation of the two long runs alone is 330 per visit).
- Test-side fix (not a behaviour change): four tests in `sim/test/ai_cmds_misc.test.mjs` hand-edited a copied
  instruction's `args` array (`{ ...ins, args: … }`); handlers now read the parse-time index `ins.a`, so the copies
  read stale values (two failed: IfSideCondition 825 vs 827, LoadSpikesLayers 2 vs 0; two passed by coincidence). A
  `withArg(ins, name, value)` helper rebuilds `args` and `a` together. Recorded here because FR-005 keeps the handler
  API, which these tests bypassed.
- Gates: `PLATSIM_AI_FREEZE=1` run **169 pass, 0 fail, exit 0** (`t013-freeze.log`); full Node suite **342 pass, 0 fail,
  exit 0**, 130.6 s (`node-suite-c2.log`; 334 + 6 interp + 1 golden + 1 bench); `ai_cmds_misc.test.mjs` re-run after
  the fourth helper site: green (below).
- Alone (11:04:48 to 11:05:27 AM EST): `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c2_v2.json`:
  digest `db6d20cf…`, `ai_draws` 849,962 (= T002), **`interp_steps` 15,893,649** (< 20 M, SC-004; 142,966,719 before,
  9.0x fewer), `interp_dispatches` 1,204,945, **1.1080 gauntlets/s, 11.303 ms/decision** (US1 attribution: 1.093x vs
  T002 1.0140, 1.076x vs the instrumentation commit's 1.0301 taken 7 minutes earlier).

## T015-T019 US2: policy damage inputs from the root adapter's memo (11:10 to 11:23:02 AM EST)

- Tests first: the new `expectimax2.test.mjs` test (builds per decision, `fromShowdown` import) and the new
  `ai_adapter.test.mjs` CHECK test (corrupted battler struct, changed side) failed before T017/T018 (3 failures incl.
  the extended 016 CHECK test's `structChecks > 0`); after, `expectimax2 + ai_adapter + replay + ai_golden`: 39 pass.
- Gates: `PLATSIM_AI_FREEZE=1` run **171 pass, 0 fail, exit 0** (`t019-freeze.log`: the copies absorb `fix()`); full Node
  suite **344 pass, 0 fail, exit 0**, 123.2 s (`node-suite-c3.log`).
- Full-set control runs, alone (SC-005): `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2 --json`
  (11:15:10 to 11:18:11 AM EST): exit 0, **35,247,740 checks, 0 mismatches**, digest `db6d20cf…`, `ai_draws` 849,962,
  181.4 s wall (`check_v2.json`); `-v1` (11:18:11 to 11:22:29): exit 0, **50,183,315 checks, 0 mismatches**, digest
  `1273b694…`, `ai_draws` 1,206,240, 256.1 s (`check_v1.json`).
- Alone (11:22:29 to 11:23:02 AM EST): `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c3_v2.json`:
  digest `db6d20cf…`, `ai_draws` 849,962, `interp_steps` 15,893,649 (unchanged), **1.2044 gauntlets/s, 10.242 ms/decision**
  (US2 attribution: 1.087x vs commit 2's 1.1080; cumulative 1.188x vs T002's 1.0140).

## T021-T027 US3: one speed pair per view, speedInfo once per state (11:24 to 11:34:50 AM EST)

- Tests first: the three new tests (`ai_cmds_battler`, `ai_adapter`, `expectimax2`) failed before T024-T026 (missing
  `compareBattlerSpeedDirect` / `speedPair`); after, the targeted set `ai_cmds_battler + ai_adapter + expectimax2 +
  replay + ai_golden`: **61 pass**. Speed-pair equivalence: **1,001 real views** (harvested from expectimax2-v2
  decisions on the benchmark team vs Aaron, plus two fainted-active views per decision; 91 fainted-active, 1
  both-fainted), **3 caller shapes x 1,001 = 3,003 comparisons, 0 differences** in result, `monSpeedValues` and draw
  counts; every shadow view built its pair at most once; positive control 20/20 tampered pairs detected. Coverage of
  the harvested set: 119 views with speed stages, 287 with weather, 0 with paralysis / speed items / Quick Claw /
  Trick Room / tie draws; those paths are exercised by the existing `IfSpeedCompareEqualTo` tests in the same file
  (tie draws one RandNext, Quick Claw with `speedRand`), which now run through the memo and pass.
- Test-side fix (not a behaviour change): the Quick Claw test changes the adapter's `speedRand` input between two
  comparisons on the same adapter; `speedRand` is fixed per decision in the game and the port (drawn per turn,
  battle_context.h:293), so the test now calls `beginDecision()` after changing it. My own fainted-active assertion
  was too strict for the both-fainted case, where the game (and both versions) compute the speeds; corrected.
- Gates: `PLATSIM_AI_FREEZE=1` run **174 pass, 0 fail, exit 0** (`t027-freeze.log`); full Node suite first run 346/347:
  the one failure is the known `seeds.test.mjs` `|t:|` timestamp flake (`|t:|1793636996` vs `…997`, README "Node suite"),
  rerun **347 pass, 0 fail, exit 0**, 120.9 s (`node-suite-c4b.log`; 334 + 6 interp + 1 golden + 1 bench + 1 + 2 + 1 + 1).
- Alone (11:31:52 to 11:32:24 AM EST): `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c4_v2.json`:
  digest `db6d20cf…`, `ai_draws` 849,962, `interp_steps` 15,893,649, `stats.speedInfo` **59,584** calls (246,632 before
  the hoist, from the 2026-11-02 profile), **1.2493 gauntlets/s, 9.806 ms/decision** (US3 attribution: 1.037x vs commit
  3's 1.2044; cumulative 1.232x vs T002's 1.0140).

## T029 Before/after on the same seeds (FR-011, SC-002, SC-003, SC-004), branch at 3d3cb09, alone, 11:35:25 to 11:37:29 AM EST

`node sim/bench.mjs --policy <p> --json` → `runs/017-evidence/branch_v2.json`, `branch_v1.json`;
`uv run platsim bench --workers 16 --json` → `branch_pool.json`. All exit 0. Every digest equals `main`'s
(`db6d20cf…`, `1273b694…`, pool `digest_logs` `be27826f…`), `ai_draws` equal (849,962 / 1,206,240), `digests_agree` true;
`pool_sim_code_hash` sha256:fe7908cb… (changed from `main`'s c0780523…, as expected).

| Measure, same 40 gauntlets, same session | `main` f6d845c (T002/T003) | branch 3d3cb09 | ratio |
|---|---|---|---|
| expectimax2-v2 single process, gauntlets/s | 1.0140 | **1.2439** | **1.227x** |
| expectimax2-v2 single process, ms/decision | 12.438 | 9.843 | |
| expectimax2-v2 single process, wall | 39.449 s | 32.2 s | |
| expectimax2-v2 interpreter steps per run | 142,966,719 (commit 1, T007) | **15,893,649** (1,204,945 dispatches) | 9.0x fewer |
| expectimax2-v1 single process, gauntlets/s | 0.6999 | 0.8563 | 1.223x |
| expectimax2-v1 single process, ms/decision | 15.980 | 12.743 | |
| expectimax2-v1 interpreter steps per run | n/a on `main` | 21,736,818 (1,636,821 dispatches) | |
| expectimax2-v2 16-worker pool, wall | 9.820 s | **8.788 s** | **1.117x** |
| expectimax2-v2 16-worker pool, gauntlets/s | 4.0732 | 4.5518 | 1.117x |
| Attribution (single process, v2, gauntlets/s): instrumentation / US1 / US2 / US3 | 1.0301 (T007) | 1.1080 / 1.2044 / 1.2493 (T013 / T019 / T027) | 1.076x / 1.087x / 1.037x per story |

**SC-002 met**: 1.2439 >= 1.1661 (1.15x of 1.0140); the measured gain, 1.23x, is at the top of the plan's 1.2x estimate.
**SC-003**: 1.12x on the pool (40 jobs on 16 workers is tail-bound, as in 015/016). **SC-004 met**: 15.9 M < 20 M
interpreter steps (143.0 M before). Combined with 015 and 016 on the same set: v2 0.386 (`main` c751fb2, 2026-10-30)
→ 1.244 gauntlets/s, about 3.2x in three features (different days, so the cross-feature ratio is indicative only).

## T030-T032 Docs and gates (11:38 to 11:51:11 AM EST)

- Docs: `README.md` feature 017 speed table (single process v2/v1, 16 workers, interpreter steps), the bench command
  row, the Node-suite and control-mode notes; `FUTURE-FEATURES.md` section 7 (A-C done with attribution, D-G next,
  approximations renumbered 018); `RUN-STATE.md` START HERE; `sim/ai/INTERFACE.md` 017 section and `OPCODES.md` note
  (committed with US2 / US1).
- Gates (`runs/017-evidence/`): `git diff --stat main HEAD -- pokemon-showdown` **empty, exit 0** (`showdown-diff.txt`,
  0 bytes; FR-010). Full Node suite 11:39:06 to 11:41:10 AM EST: **347 pass, 0 fail, exit 0**, 123.7 s
  (`node-suite.log`). Fast mode `uv run pytest -q -m "not battle_sim"` 11:41:10 to 11:51:11 AM EST: **528 passed,
  28 deselected, 4 xfailed, 1 warning, exit 0**, 598.78 s (`fast.log`; battle split clean: 0 worker starts).
- Commit 5 below. T033 (full suite, about 1 h 05 min) waits for the user's hands-on testing and go.
