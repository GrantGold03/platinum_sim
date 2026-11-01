# Quickstart: validating feature 016 (exact damage-path speedups, round two)

From the repo root. Evidence goes in `runs/016-evidence/` (git-ignored); numbers go in `validation-log.md` with
commit hash and Eastern time. Do not commit, switch branches or run `extract` while a measurement or a suite is
running. Measurements that feed SC-002/SC-003 run with nothing else on the machine. `data/generated/` needs no
rebuild for this feature (no extractor change).

## 0. Baseline on `main` 19519ed (before commit 1)

1. `git switch main`; `node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/main_v2.json` and the
   same for `expectimax2-v1` (about 1 min each; digests must be `db6d20cf…` and `1273b694…`).
2. `uv run platsim bench --workers 16 --json > runs/016-evidence/main_pool.json` (about 2 min; `digests_agree`
   true). Record gauntlets/s, ms/decision, pool wall.
3. `git switch 016-exact-damage-speedups`.

## 1. Commit 1: type-chart plan (US1)

- `(cd sim && node --test test/damage_typechart.test.mjs)`: 0 mismatches over >= 10,000 synthetic and >= 1,000
  real-data matchups x 16 rolls (normal and critical for the `calcDamage` subset); every coverage counter >= 100;
  the positive control reports mismatches; `DAMAGE_STATS` deltas around one `calcDamage`: plans +1, replays +16.
- `(cd sim && node --test test/damage.test.mjs test/replay.test.mjs test/ai_golden.test.mjs test/ai_gauntlet.test.mjs)`
  green; the replay test matches the unchanged fixture for v1 and v2.
- `PLATSIM_AI_FREEZE=1 node --test sim/test/replay.test.mjs sim/test/ai_*.test.mjs` green.
- Full Node suite green. Commit, push.

## 2. Commit 2: AI pre-variance memo and control mode (US2)

- `(cd sim && node --test test/ai_adapter.test.mjs test/ai_cmds_damage.test.mjs)`: preVariance builds independent of
  K (deltas), hits grow with K; `beginDecision()` drops the memos; the frozen child throws on a write to a plan or a
  pre-variance entry; the CHECK child (one Aaron battle per policy) exits 0 with `checks > 0`; the corrupted-memo
  child exits non-zero with `CHECK mismatch`.
- Replay, golden, freeze run green.
- `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/check_v2.json` and
  `-v1`: exit 0, digests `db6d20cf…` / `1273b694…` (about 2 min each; the control roughly doubles the AI damage work).
  Record in the validation log.
- Full Node suite green. Commit, push.

## 3. Commit 3: shared mappers (US3)

- `(cd sim && node --test test/ai_adapter.test.mjs)`: shared == fresh over every engine identifier the decomp knows;
  same error messages for unknown ids; two adapters share one set.
- Replay, golden green. Full Node suite green. Commit, push.

## 4. Commit 4: measurement, docs, validation log (US4)

- Branch, nothing else running: `node sim/bench.mjs --policy expectimax2-v2 --json > runs/016-evidence/branch_v2.json`,
  `-v1`, `uv run platsim bench --workers 16 --json > runs/016-evidence/branch_pool.json`. Table in the validation log:
  gauntlets/s, ms/decision, pool wall, ratios vs step 0; SC-002 >= 1.2x for v2; digests unchanged and agreeing.
- Docs: `sim/ai/INTERFACE.md` (016 section), README speed table and the `PLATSIM_AI_CHECK` note, FUTURE-FEATURES
  section 7 (items done, items remaining), RUN-STATE START HERE.
- Gates: `git diff --stat main HEAD -- pokemon-showdown` empty; Node suite; `uv run pytest -q -m "not battle_sim"`.
  Record outputs. Commit, push.

## 5. Before the merge (after the user's hands-on testing and go)

- `uv run pytest -q --durations=25 > runs/016-evidence/full.log 2>&1` (about 1 h 20 min on `main` today; nothing
  else running). Record the summary line, exit code and Eastern start/end.
- Merge only on the user's second go.
