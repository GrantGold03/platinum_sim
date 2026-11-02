# Quickstart: validating feature 018 (expectimax2-v4)

From the repo root. Evidence in `runs/018-evidence/` (git-ignored); numbers in `validation-log.md` with commit hash and
Eastern time. Nothing else runs during measurements. `data/generated/` needs no rebuild (no extractor change).
Long runs go in the background with their start time logged.

## 1. Commit 1: the policy (US1)

- `(cd sim && node --test test/expectimax2.test.mjs test/determinism.test.mjs test/gauntlet.test.mjs test/replay.test.mjs)`:
  v1/v2 options unchanged and the knobs default to `PARAMS`; `V4_OPTS` values; candidate parsing (valid names resolve,
  bad key / value / duplicate throw `invalid_policy`); `expectimax2-v4?<V4_OPTS values>` digest == `expectimax2-v4` on two
  gauntlets; `STATS.floored` > 0 for v4 on a position and 0 for v2; determinism for v4 (200 gauntlets); replay matches
  for v1 and v2 (fixture unchanged).
- Full Node suite green. Commit, push.

## 2. Commit 2: Python plumbing (US3 code)

- `uv run pytest -q tests/unit`: every default equals `DEFAULT_PLAYER_POLICY`; `optimize --player-policy x` parses into
  the request; `OptimizeRequest()` default is the constant. Fast mode green. Commit, push.

## 3. The ladder (US2), background, nothing else running

1. Control: `paired_policies.py --a expectimax2-v2 --b expectimax2-v2 --self --teams bench --runs 200` → 0 discordant.
2. v2 sides (cached): `--a expectimax2-v4?kRoot=8&kPly2=1&beam=2&floor=0 --b expectimax2-v2` on all four teams runs
   v2 once per team and the first single knob (about 40 min).
3. The other singles: `…kRoot=8&kPly2=2&beam=1&floor=0`, `…kRoot=4&kPly2=2&beam=2&floor=0`,
   `…kRoot=8&kPly2=2&beam=2&floor=0.02`, `…floor=0.05` (about 20 min each).
4. Combinations, fastest first, until one passes on all four teams (20 min each).
5. Table in the validation log (candidate x team: rates, discordant, p, verdict, speed); commit the script and the
   log (commit 3).

## 4. Commit 4: final parameters, fixture entry, strength tests (US1)

- Set `V4_OPTS` to the passing set; `node sim/bench.mjs --policy expectimax2-v4 --record sim/test/replay_prof_a.json`;
  `replay.test.mjs` expects three policies; `test_policy_strength.py` covers v4.
- Alone: `node sim/bench.mjs --policy expectimax2-v2 --json`, `--policy expectimax2-v4 --json`,
  `uv run platsim bench --policy expectimax2-v4 --workers 16 --json` (and v2): v4 faster single and pool, digests agree,
  ratio vs the 1.5x target recorded. Node suite green. Commit, push.

## 5. B2 end to end (US3) and the switch (US4)

- `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2
  --player-policy expectimax2-v2 --out runs/018-evidence/b2-v2` (about 15 min) and `… expectimax2-v4 … --out
  runs/018-evidence/b2-v4`; wall times from the logs; `uv run platsim validate` on the v4 result.
- `equal_levels.py runs/018-evidence/b2-v2 runs/018-evidence/b2-v4 2000` (A = v4 team): verdict not B, mean final level
  of A not higher; `--self` control first (200).
- If FR-005 and FR-007 pass: flip `DEFAULT_PLAYER_POLICY`, README / FUTURE-FEATURES / RUN-STATE / policy header; `uv run
  platsim evaluate tests/fixtures/reference_team.json --runs 50` shows `player expectimax2-v4`; fast mode and Node suite
  green. Commit 5, push. If not: no flip; the negative result documented; commit 5 is docs only.

## 6. Before the merge (after the user's hands-on testing and go)

- `uv run pytest -q --durations=25 > runs/018-evidence/full.log 2>&1` (about 1 h; the strength test grows by one policy).
- Merge only on the user's second go.
