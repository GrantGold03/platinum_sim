# Quickstart: validating feature 017 (exact dispatch, damage-input and speed speedups)

From the repo root. Evidence goes in `runs/017-evidence/` (git-ignored); numbers go in `validation-log.md` with
commit hash and Eastern time. Do not commit, switch branches or run `extract` while a measurement or a suite is
running. Measurements that feed SC-002/SC-003/SC-004 run with nothing else on the machine. `data/generated/` needs
no rebuild for this feature (no extractor change).

## 0. Baseline on `main` f6d845c (before commit 1, same session as the after figures)

1. `git switch main`; `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/main_v2.json` and the
   same for `expectimax2-v1` (about 40 s each; digests must be `db6d20cf…` and `1273b694…`).
2. `uv run platsim bench --workers 16 --json > runs/017-evidence/main_pool.json` (about 1 min; `digests_agree`
   true). Record gauntlets/s, ms/decision, pool wall.
3. `git switch 017-exact-dispatch-speedups`.

## 1. Commit 1: instrumentation (INTERP_STATS, bench fields)

- `(cd sim && node --test test/replay.test.mjs test/bench.test.mjs)` green (fixture unchanged).
- `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c1_v2.json`: `interp_steps` about 143 M,
  `interp_dispatches` 0, digest `db6d20cf…`; throughput within noise of step 0. Record. Commit, push.

## 2. Commit 2: effect dispatch, argument index, one loop (US1)

- `(cd sim && node --test test/ai_interp.test.mjs)`: 13 runs (178, 152, 5, 5, 5, 5, 4, 3, 2, 2, 1, 1), 0 splits on the
  real script, one repeated value; synthetic script with a label inside a run splits into two runs whose tables
  agree with stepping; exhaustive equivalence 0 mismatches over every run x 277 effect values + 2 undefined values;
  positive controls (retargeted entry, deleted entry) report mismatches; `ctx.arg` / `ctx.target` errors unchanged;
  `INTERP_STATS` deltas for one golden decision show `dispatches > 0`.
- `(cd sim && node --test test/ai_golden.test.mjs test/ai_choose.test.mjs test/ai_parse.test.mjs test/ai_gauntlet.test.mjs test/replay.test.mjs)`
  green; the golden traces are unchanged; the full-trace test shows one entry per dispatch.
- `PLATSIM_AI_FREEZE=1 node --test sim/test/replay.test.mjs sim/test/ai_*.test.mjs` green.
- `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c2_v2.json`: `interp_steps` < 20 M,
  digest unchanged; record gauntlets/s (US1 attribution). Full Node suite green. Commit, push.

## 3. Commit 3: policy damage inputs from the root adapter's memo (US2)

- `(cd sim && node --test test/expectimax2.test.mjs test/ai_adapter.test.mjs)`: builds per decision <= Pokemon with
  hp > 0, `fieldBuilds` <= 2, hits > builds, `fromShowdown` not called by the policy; CHECK clean child exits 0 with
  `structChecks > 0`; corrupted-struct child exits non-zero with `CHECK mismatch battler`.
- Replay, golden, freeze run green (the freeze run proves `fix()` writes only to the copies).
- `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/check_v2.json` and
  `-v1`: exit 0, 0 mismatches, digests `db6d20cf…` / `1273b694…` (about 2 min each). Record.
- `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c3_v2.json`: record (US2 attribution).
  Full Node suite green. Commit, push.

## 4. Commit 4: one speed pair per view, speedInfo once per state (US3)

- `(cd sim && node --test test/ai_cmds_battler.test.mjs test/ai_adapter.test.mjs test/expectimax2.test.mjs)`:
  >= 1,000 harvested views x three caller shapes, 0 differences in result, `monSpeedValues` and draw counts,
  exactly one pair build per view, fainted-active cases covered, positive control fires; `beginDecision()` drops
  the pair; frozen pair throws on write; `STATS.speedInfo` per decision <= `X.nodes` + root actions.
- Replay, golden, freeze run green.
- `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/c4_v2.json`: record (US3 attribution).
  Full Node suite green. Commit, push.

## 5. Commit 5: measurement, docs, validation log (US4)

- Branch, nothing else running: `node sim/bench.mjs --policy expectimax2-v2 --json > runs/017-evidence/branch_v2.json`,
  `-v1`, `uv run platsim bench --workers 16 --json > runs/017-evidence/branch_pool.json`. Table in the validation log:
  gauntlets/s, ms/decision, interpreter steps, pool wall, ratios vs step 0 and commit 1; SC-002 >= 1.15x for v2;
  SC-004 steps < 20 M; digests unchanged and agreeing.
- Docs: `sim/ai/INTERFACE.md` (017 section; the 015 sentence about the policy using `fromShowdown`), `sim/ai/OPCODES.md`
  note, README speed table and the two new bench rows, FUTURE-FEATURES section 7 (017 done; approximations = 018),
  RUN-STATE START HERE.
- Gates: `git diff --stat main HEAD -- pokemon-showdown` empty; Node suite; `uv run pytest -q -m "not battle_sim"`.
  Record outputs. Commit, push.

## 6. Before the merge (after the user's hands-on testing and go)

- `uv run pytest -q --durations=25 > runs/017-evidence/full.log 2>&1` (about 1 h 05 min on `main` today; nothing
  else running). Record the summary line, exit code and Eastern start/end.
- Merge only on the user's second go.
