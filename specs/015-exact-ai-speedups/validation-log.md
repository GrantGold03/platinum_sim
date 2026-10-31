# Validation log: 015 exact AI-prediction speedups

Times are US Eastern. Evidence under `runs/015-evidence/` (git-ignored). Numbers that feed SC-002/SC-003 were
taken with nothing else running on the machine (checked with `pgrep -a node; pgrep -a pytest` before each run).

## T001 Setup (2026-10-31)

- Branch `015-exact-ai-speedups`, base `main` = `c751fb2`. Spec/plan/tasks commits: `c31f8be`, `42f453c`, `02c2263`,
  `92af92b`, `e867a09`, `b2a69d4`. `git diff --stat main HEAD -- src tests sim`: empty (0 lines), exit 0.

## T002 Baseline digests on `main` `c751fb2` (2026-10-31)

- `git switch main && uv run platsim extract`: exit 0 (manifest sha256 f222234e0fc51d82).
- `node runs/015-evidence/scratchpad/prof/run_gauntlets.mjs --policy expectimax2-v1` (3:49:10 to 3:51:36 PM EDT), exit 0:
  40 gauntlets, cleared 28, wall 145.818 s, **0.2743 gauntlets/s**, 42.07 ms/decision, 55.2 AI calls/decision,
  decisions 3297, aiCalls 182021. **v1 `digest` = `1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178`.**
  Output `runs/015-evidence/main_v1.json`.
- **Positive control**: `--policy expectimax2-v2` (3:51:43 to 3:53:26 PM EDT), exit 0: cleared 36, wall 102.696 s,
  0.3895 gauntlets/s, 33.87 ms/decision, 44.7 AI calls/decision, decisions 2847, aiCalls 127219,
  `digest` = `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` (equals the spec's FR-001 digest).
  Output `runs/015-evidence/main_v2.json`.

## T003 Baseline 16-worker pool on `main` `c751fb2` (2026-10-31)

- `uv run python <scratchpad>/bench_pool_main.py expectimax2-v2 16` (copy: `runs/015-evidence/bench_pool_main.py`),
  3:53:35 to 3:53:58 PM EDT, exit 0, machine otherwise idle: 40 gauntlets, 0 errors, cleared 36,
  **wall 20.917 s, 1.9124 gauntlets/s**, hello `sim_code_hash`
  `sha256:77802319924e485fa5b06763b41d2a98f42fa0ed4b73df59c0398f2b38abf563`,
  **`digest_logs` = `be27826f63904c3c124a84d780071753fe587ceda84d61fbf680c6d41abe809a`** (the cross-language
  digest the branch's fixture and `platsim bench` must reproduce). Output `runs/015-evidence/main_pool.json`.
  Note: 40 jobs on 16 workers is tail-bound (the longest gauntlet sets the wall), so this figure is below the
  README's long-run 2.1-2.8 gauntlets/s; the branch is compared on the same 40 jobs.

## T004 Switch back (2026-10-31)

- `git switch 015-exact-ai-speedups && uv run platsim extract`: exit 0.

## T005-T011 Commit 1: instrumentation, bench tool, fixture, replay test (2026-10-31, no behaviour change)

- T005: `STATS.aiDraws` (sum of every prediction sample's `AIRng.draws`, added in `predictOpponent`);
  `mirror.ai.beginDecision?.()` in `makeContext` (a no-op until US1 adds the method).
- T006/T007: `sim/bench.mjs`, `sim/test/bench.test.mjs`: `node --test test/bench.test.mjs` 4/4 pass, exit 0.
- **T008 gate** (machine idle): `node sim/bench.mjs --policy expectimax2-v2 --json` 3:57:49 to 3:59:34 PM EDT, exit 0:
  40 gauntlets, cleared 36, wall 103.644 s, 0.3859 gauntlets/s, 2847 decisions, 34.197 ms/decision, 44.69 AI
  calls/decision, ai_draws 849962, **`digest_full` = `db6d20cf…` (equals `main`)**, **`digest_logs` =
  `be27826f…` (equals the `main` pool's T003 value: cross-language digest control passes)**,
  `sim_code_hash` `sha256:b50ff420…`. `runs/015-evidence/bench-c1-v2.json`.
  `--policy expectimax2-v1 --json --record sim/test/replay_prof_a.json` 3:59:44 to 4:02:12 PM EDT, exit 0: cleared 28,
  wall 146.714 s, 0.2726 gauntlets/s, 3297 decisions, 42.336 ms/decision, 55.21 AI calls/decision, ai_draws
  1206240, **`digest_full` = `1273b694…` (equals T002's `main` v1 digest)**, `digest_logs` `bd80333d…`.
  `runs/015-evidence/bench-c1-v1.json`.
- T009: `--policy expectimax2-v2 --json --record sim/test/replay_prof_a.json` 4:02:45 to 4:04:30 PM EDT, exit 0, same
  digest and ai_draws as T008. Fixture: 149333 bytes, `recorded.commit` b2a69d4, both policies x 40 gauntlets;
  v2: 2847 choices, 849962 policy draws, 3522 live-AI decisions / 19168 draws; v1: 3297 choices, 1206240 policy
  draws, 3882 live-AI decisions / 22060 draws.
- T010: `node --test test/replay.test.mjs` 3/3 pass, exit 0, 4:04:37 to 4:05:23 PM EDT: "80 gauntlets, 6144 player
  decisions, 16 workers, 45.7 s" (above the 15-30 s estimate; the fixture's longest gauntlets bound the wall).
  The positive-control test alters one choice, one policy draw count and one live draw count and sees each.
- T011: `(cd sim && node --test test/*.test.mjs)` 4:05:31 to 4:10:23 PM EDT: **321 tests, 321 pass, 0 fail, exit 0**
  (314 + 4 bench + 3 replay). `runs/015-evidence/node-suite-c1.log`.

## T012-T019 Commit 2: memoised damage-formula inputs (US1) (2026-10-31)

- T012-T014 written first: with the methods missing, 3 of 25 tests in `ai_adapter.test.mjs` + `ai_cmds_damage.test.mjs`
  failed (`ai.damageInput is not a function`, `s.ai.beginDecision is not a function`), 22 passed. After T015-T017:
  25/25, exit 0. `damageInput` deep-equals `fromShowdown` for all 16 Pokemon pairs x 4 moves (64 cases); the
  stale-without-`beginDecision` control shows the cache caches (stage 0 cached vs 2 fresh) and `beginDecision`
  refreshes; the freeze child process reports `TypeError,TypeError,TypeError` with `PLATSIM_AI_FREEZE=1` and
  `no throw,no throw,no throw` without; builds per decision equal for K = 1, 2, 4 samples while hits grow.
- T015-T017: `sim/ai/adapter.mjs` (`beginDecision`, `damageInput`, `cacheStats`, freeze guard), `calcdamage.mjs`
  `portInput` and `switch.mjs:499` → `ai.damageInput`, `opponent.mjs` `decide()` first statement
  `st.ai.beginDecision()`, `expectimax2.mjs` `makeContext` call made unconditional, `sim/ai/INTERFACE.md` section.
- **T018 gates**: `(cd sim && node --test test/*.test.mjs)` 4:13:45 to 4:17:00 PM EDT: **324/324, exit 0** (replay
  38.0 s). `runs/015-evidence/node-suite-c2.log`. `PLATSIM_AI_FREEZE=1 node --test test/replay.test.mjs
  test/ai_*.test.mjs` 4:17:07 to 4:17:58 PM EDT: **152/152, exit 0** (no consumer writes through the cache; the
  replay reproduces the fixture with every struct frozen). `runs/015-evidence/node-freeze-c2.log`.
  Attribution, machine idle: `node sim/bench.mjs --policy expectimax2-v2 --json` 4:18:07 to 4:19:14 PM EDT, exit 0:
  **wall 65.773 s, 0.6081 gauntlets/s, 21.535 ms/decision** (commit 1: 103.644 s, 0.3859, 34.197), 44.69 AI
  calls/decision, ai_draws 849962 (= commit 1), `digest_full` `db6d20cf…`, `digest_logs` `be27826f…`,
  `sim_code_hash` `sha256:ab6b3149…`. US1 alone: **1.58x** single-process. `runs/015-evidence/bench-c2-v2.json`.
