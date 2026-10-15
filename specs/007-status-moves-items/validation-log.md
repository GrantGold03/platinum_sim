# Validation log: 007 status moves and held items

Real output is pasted for each checkpoint. Times are wall-clock on this machine (16 threads).

## One-time hours (budget: 100 h for every one-time run, spec FR-017)

| Run | Task | Budget h | Used h | Running total h |
|---|---|---|---|---|
| Golden v1/v2 record + verify (9.4 min) and positive control (2 × 4.6 min) | T004 | (suites, 8) | 0.31 | 0.31 |
| Suite baseline + B1–B5 baseline | T002, T005 | 8 + 11 | running | |

## T001 Setup (2026-10-14)

- Branch `007-status-moves-items`, HEAD `2fa6059` (docs only since `f88cdd0`).
  - `git diff --stat f88cdd0 HEAD -- src sim tests pyproject.toml uv.lock` prints nothing, so the code is equal to `f88cdd0`.
- `nproc` = 16.
- **Baseline runs use a snapshot.** T002 and T005 run on `git archive f88cdd0`, extracted to the session scratchpad (`baseline-f88cdd0/`, with symlinks to `pokeplatinum`, `pokemon-showdown`, the ROM and `runs/`). Code edits on the branch therefore can't leak into the baseline while it runs. In the snapshot:
  - `uv sync`;
  - `uv run platsim extract` (45 s);
  - `uv run platsim extract --check`: "data/generated is up to date (11 files)".
- The chain script (`baseline_chain.sh`) runs, in order: `uv run pytest -q`, `node --test sim/test`, then standard optimizations of B4, B5, B3, B1 and B2. Seed is `bench-007`; output goes to `runs/bench-007-baseline/<B>`. Results are recorded below when it finishes.

## T003 Benchmark teams

`tests/fixtures/bench_007.json`. All resolve under `DEFAULT_LEGALITY` (engine, 2026-10-14):

```
B1 ['SPECIES_INFERNAPE', 'SPECIES_STARAPTOR', 'SPECIES_LUXRAY', 'SPECIES_GARCHOMP', 'SPECIES_GYARADOS', 'SPECIES_GARDEVOIR'] required_hms () group conflicts {}
B2 ['SPECIES_GARCHOMP', 'SPECIES_INFERNAPE', 'SPECIES_STARAPTOR', 'SPECIES_ROTOM', 'SPECIES_FLOATZEL', 'SPECIES_WEAVILE'] required_hms () group conflicts {}
B3 ['SPECIES_INFERNAPE', 'SPECIES_GARCHOMP', 'SPECIES_GYARADOS', 'SPECIES_LUCARIO', 'SPECIES_CHATOT', 'SPECIES_STARAPTOR'] required_hms ('surf', 'waterfall') group conflicts {}
B4 ['SPECIES_ROSERADE', 'SPECIES_BLISSEY', 'SPECIES_GLISCOR', 'SPECIES_MILOTIC', 'SPECIES_BRONZONG', 'SPECIES_LUCARIO'] required_hms () group conflicts {}
B5 ['SPECIES_TORTERRA', 'SPECIES_MAGNEZONE', 'SPECIES_CLEFABLE', 'SPECIES_LUMINEON', 'SPECIES_GALLADE', 'SPECIES_SPIRITOMB'] required_hms () group conflicts {}
```

## T004 Golden v1/v2 player logs

- `sim/test/golden_v1_v2.test.mjs` with `sim/test/fixtures/golden_v1_v2.json`, recorded before any `sim/` edit.
  - Teams: `policy_benchmark_team.json` and `reference_team.json` (the B1 six).
  - Policies: greedy-v1, expectimax2-v1, expectimax2-v2.
  - 20 seeds (`golden-007|0..19`), `stop_on_loss: false`, so every battle is played.
  - Per battle it records (trainer, won, turns, log_hash).
- Record and verify in one run: `# pass 1 # fail 0`, real 9m23s. Verifying alone takes about 4.7 min.
- **Positive control** (scratchpad `golden_pc.mjs`):

```
matches own key: true
matches seed 1 key (must be false): false
v1 differs from v2 on same seed: true
```

## T006 Friendship in battle

A Node probe through `sim/test/ai_fixtures.mjs` `leagueBattle('champion_cynthia', reference_team builds)`:

```
p1 happiness infernape:255 staraptor:255 luxray:255 garchomp:255 gyarados:255 gardevoir:255
Return basePowerCallback for p1[0] = 102
p2 happiness spiritomb:255 roserade:255 togekiss:255 lucario:255 milotic:255 garchomp:255
```

Battles already use 255 and Return 102 (R3). T016 makes this explicit for player builds.
- **Note:** opponents also get 255 from Showdown. In the decomp, trainer mons get their species' base friendship (research R4.6). No League mon carries Return or Frustration, so this has no effect today; it is recorded for the divergence pass (T044).
