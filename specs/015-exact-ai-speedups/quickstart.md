# Quickstart: validating feature 015 (exact AI-prediction speedups)

From the repo root. Evidence goes in `runs/015-evidence/` (git-ignored); numbers go in `validation-log.md` with
commit hash and Eastern time. Do not commit, switch branches or run `extract` while a measurement or a suite is
running. Measurements that feed SC-002/SC-003 run with nothing else on the machine.

## 1. Baseline on `main` (before commit 1)

Already recorded (`runs/015-evidence/scratchpad/prof/plain_a.log`): v2 `digest_full` = `db6d20cf…`, 103.75 s,
0.386 gauntlets/s, 34.2 ms/decision. Still needed from `main` c751fb2:

1. `git switch main && uv run platsim extract` (if `data/generated/` was built from another branch).
2. v1 digest: `node runs/015-evidence/scratchpad/prof/run_gauntlets.mjs --policy expectimax2-v1` → record
   `digest` (about 2 min).
3. `main` pool figure: a scratchpad script that builds the 40 requests (`op: gauntlet`, seeds `prof-a-<team>-<i>`,
   fixtures as in `contracts/bench-tool.md`) and times `WorkerPool(16).map(...)`; record wall and gauntlets/s.
4. `git switch 015-exact-ai-speedups && uv run platsim extract`.

## 2. Commit 1: instrumentation and fixture (no behaviour change)

- `node sim/bench.mjs --policy expectimax2-v2 --json` → `digest_full` equals `db6d20cf…`; same for `-v1` against
  step 1.2 (positive control that the tool and the wrappers change nothing).
- `node sim/bench.mjs --policy expectimax2-v2 --record sim/test/replay_prof_a.json`, then `--policy expectimax2-v1
  --record` into the same file. Commit the fixture.
- `(cd sim && node --test test/replay.test.mjs)` passes; the altered-fixture control test fails as expected
  (it is written as a test that expects the failure).

## 3. Commit 2: memoised damage inputs (US1)

- `(cd sim && node --test test/*.test.mjs)` passes (replay, golden, determinism, adapter tests: `damageInput`
  deep-equals `fromShowdown`; stale-without-`beginDecision` / fresh-after control; one build per Pokemon per
  decision across K samples).
- `(cd sim && PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs test/ai_*.test.mjs)` passes (no consumer
  writes through the cache); the freeze-guard unit test shows a deliberate write throws.
- Attribution: `node sim/bench.mjs --policy expectimax2-v2 --json` alone on the machine → record
  gauntlets/s and ms/decision.

## 4. Commit 3: resolved constants (US2)

- Node suite passes; `effectSet` equivalence test over every effect value passes; constants fast-path
  equivalence (fresh vs warmed instance) passes.
- `node sim/bench.mjs --policy expectimax2-v2 --json` alone → record. SC-002: gauntlets/s ≥ 1.5 × 0.386 = 0.579.

## 5. Commit 4: `platsim bench`, docs

- `uv run platsim bench --policy expectimax2-v2 --workers 16` → single and pool figures, pool digest equals the
  single-process digest (exit 0). Record wall, gauntlets/s, ratio against step 1.3.
- `uv run pytest -q tests/integration/test_bench.py -s` (battle_sim) passes.
- Docs: `specs/001-*/contracts/cli.md` row, README command table and speed table, `sim/ai/INTERFACE.md`
  (`beginDecision`, `damageInput`, `PLATSIM_AI_FREEZE`), FUTURE-FEATURES follow-ons (research R7).

## 6. Gates (SC-004) and merge

- `(cd sim && node --test test/*.test.mjs)` and `uv run pytest -q -m "not battle_sim"` pass; output recorded.
- Before merge: `uv run pytest -q` (about 2 h 10 min; run in the background, nothing else running) passes.
- The user tests the branch; merge only after their go. After merge: `data/generated/` rebuilt on `main`;
  RUN-STATE.md updated. Note for users of checkpoints: `sim_code_hash` changed, so optimizer checkpoints made
  before 015 will not resume.
