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
