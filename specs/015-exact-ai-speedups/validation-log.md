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

## T020-T025 Commit 3: constants resolved once (US2) (2026-10-31)

- T020/T021 appended, then T022/T023 implemented, then both files run: 27/27, exit 0. (Process note: the pre-
  implementation failing run was not taken for this story; T020 could only have failed on the missing `effectSet`
  export, and T021 is an equivalence test that passes on both sides by design.) `effectSet` equals the
  name-by-name scan for every move effect value (+0, -1) on the two effect tables and every move number on the
  two battle_lib move lists, with hits and misses on each; same Set object on repeat; a cold `Constants` with the
  same definitions gets an equal Set. Cold vs warmed `Constants.get` agree on every one of >1000 symbols (same
  values, same thrown messages); the memo holds numbers only; unknown-symbol and recursive-definition errors
  unchanged.
- T022: `Constants.get` memo fast path (one `Map.get`, `stack` allocated only on the slow path). T023: `effectSet`
  (WeakMap per table per constants instance) exported from `calcdamage.mjs`; `effectIn` and the gravity /
  heal-block checks in `choose.mjs` use it.
- **T024 gates**: `(cd sim && node --test test/*.test.mjs)` 4:20:54 to 4:23:44 PM EDT: **326/326, exit 0** (replay
  33.8 s). `runs/015-evidence/node-suite-c3.log`. `PLATSIM_AI_FREEZE=1 … replay + ai_*`: **154/154, exit 0**
  (`node-freeze-c3.log`). Attribution, machine idle: `node sim/bench.mjs --policy expectimax2-v2 --json` 4:24:38
  to 4:25:30 PM EDT, exit 0: **wall 51.330 s, 0.7793 gauntlets/s, 16.573 ms/decision** (commit 2: 65.773 s,
  0.6081, 21.535; commit 1: 103.644 s, 0.3859, 34.197), 44.69 AI calls/decision, ai_draws 849962 (unchanged),
  `digest_full` `db6d20cf…`, `digest_logs` `be27826f…`, `sim_code_hash` `sha256:719e63b0…`.
  `--policy expectimax2-v1 --json` 4:25:30 to 4:26:47 PM EDT, exit 0: wall 76.437 s, **0.5233 gauntlets/s** (commit 1:
  0.2726), 21.796 ms/decision (42.336), ai_draws 1206240 (unchanged), `digest_full` `1273b694…` (= `main`),
  `digest_logs` `bd80333d…`. **SC-002: 0.7793 ≥ 0.579 (1.5 x 0.386); v2 single-process gain 2.02x, v1 1.92x.**
  `runs/015-evidence/bench-c3-v2.json`, `bench-c3-v1.json`.

## T026-T031 Commit 4a: `platsim bench` (US3) (2026-10-31)

- T026/T027 written, then T028/T029: `uv run pytest -q tests/unit/test_bench_cli.py tests/integration/test_bench.py -s`:
  **5 passed, exit 0** (battle split: 3 worker starts, both integration tests marked and reached the worker,
  0 under/over-marked). The digest-line vector is shared with `sim/test/bench.test.mjs`.
- **T030**, machine idle: `uv run platsim bench --policy expectimax2-v2 --workers 16 --json` 4:28:45 to 4:29:51 PM EDT,
  exit 0 (`runs/015-evidence/bench-c4-pool.json`): single process wall 51.095 s, **0.7829 gauntlets/s**, 16.503
  ms/decision, ai_draws 849962, `digest_full` `db6d20cf…`; **pool (16 workers) wall 12.423 s, 3.2199 gauntlets/s**,
  cleared 36/40, `pool_digest_logs` = `be27826f…` = single-process `digest_logs` = `main` pool (T003):
  `digests_agree: true`. `sim_code_hash` single = pool = `sha256:719e63b0…`.

### Before / after (same 40 gauntlets, seeds prof-a-*, both fixture teams, all five trainers)

| Measure | `main` c751fb2 | branch (commits 1-3) | ratio |
|---|---|---|---|
| expectimax2-v2 single process, gauntlets/s | 0.3859 (T008; 0.3895 T002) | 0.7793 (T024; 0.7829 T030) | **2.02x** |
| expectimax2-v2 single process, ms/decision | 34.197 | 16.573 | 0.48x |
| expectimax2-v2 single process, wall | 103.644 s | 51.330 s | |
| expectimax2-v1 single process, gauntlets/s | 0.2726 | 0.5233 | 1.92x |
| expectimax2-v2 16-worker pool, wall | 20.917 s (T003) | 12.423 s (T030) | **1.68x** |
| expectimax2-v2 16-worker pool, gauntlets/s | 1.9124 | 3.2199 | 1.68x |
| US1 alone (commit 2), single process | | 0.6081 gauntlets/s, 21.535 ms/decision | 1.58x |

Results unchanged throughout: `digest_full` v2 `db6d20cf…`, v1 `1273b694…`; `digest_logs` v2 `be27826f…`; AI draws
849962 (v2) and 1206240 (v1). SC-002 met (0.7793 ≥ 0.579). SC-003: 1.68x on the pool (40 jobs on 16 workers is
tail-bound; the per-job gain is the single-process 2.02x).

## T032-T034 Docs and gates (2026-10-31)

- T032: `specs/001-champion-team-optimizer/contracts/cli.md` bench row; `README.md` command table row, 015 speed
  table and the `sim_code_hash` / checkpoint note; `FUTURE-FEATURES.md` section 7 (follow-ons, killed hypotheses,
  feature 016). T033: `RUN-STATE.md` START HERE.
- **T034 gates**: `git diff --stat main HEAD -- pokemon-showdown`: empty, exit 0 (FR-008; `git status` of the tree
  also clean). `(cd sim && node --test test/*.test.mjs)`: first run 4:31:19 to 4:34:09 PM EDT **325/326**: the one
  failure was `seeds.test.mjs` "Showdown accepts a derived seed and replays identically", which compares two raw
  logs including their `|t:|` timestamp lines and straddled a second boundary (…681 vs …682); it is a pre-existing
  flake unrelated to 015 (passed in the commit 1-3 suite runs, passed 3/3 alone right after; a `stripTimestamps`
  in that test would remove it, left for a later test-only change). Clean rerun 4:44:14 to 4:47:04 PM EDT:
  **326 tests, 326 pass, 0 fail, exit 0** (replay 34.5 s). `runs/015-evidence/node-suite.log`.
  `uv run pytest -q -m "not battle_sim"` 4:34:09 to 4:44:04 PM EDT: **528 passed, 28 deselected, 4 xfailed, exit 0**
  (591.94 s; battle split: 0 worker starts). `runs/015-evidence/fast.log`.
- **T035 merge gate (2026-11-01, user's go)**: `uv run pytest -q --durations=25 > runs/015-evidence/full.log 2>&1`,
  nothing else running, 16 workers: 10:40:06 AM to 12:00:44 PM EST, **556 passed, 4 xfailed, 1 warning, exit 0**
  (4834.93 s = 1:20:34; `main` c751fb2 on 2026-10-30 was 551 passed, 4 xfailed in 7760.06 s = 2:09:20, so 1.61x
  faster end to end; the 5 extra tests are the bench tests). Slowest three: `test_optimize_quick_deterministic_and_legal`
  1917.9 s, `test_expectimax2_beats_greedy_paired` 1034.1 s, `test_v7_reference_team_2000_runs` 925.8 s (no
  per-test durations exist for the `main` run; these are the first recorded). `runs/015-evidence/full.log`,
  `full.start`. Not merged: waits for the user's go.
