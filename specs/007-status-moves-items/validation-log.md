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

## T007-T014 Classification, items, adopted moves (2026-10-14/15)

- **`tests/unit/test_move_classes.py`: 70 passed.** Every move classifies. Positive controls include Magnitude → variable_attack (its effect is named PSYWAVE). The derived foe_drop set equals expectimax2 FOE_DROPS plus Captivate. Fixed damage is exactly 6 effects.
- **`tests/unit/test_item_classes.py`: 44 passed.**
  - All 17 resist berries are found through the numeric reference.
  - NO_OUTCOME references lie in their named functions: MONEY_UP in BattleSystem_TriggerEffectOnSwitch; FLEE in Battler_IsTrappedMsg / Battler_CanEscape / subscript_escape.s, reached only from Run and Teleport; FRIENDSHIP_UP in BattleSystem_UseBagItem.
  - Exp/EV effects are derived: EXP_SHARE, EXP_UP, EVS_UP_SPEED_DOWN, LVLUP_*_EV_UP.
  - 83 items are offerable to some B1 member under default options.
  - Every candidate item maps to Showdown. Positive control: amulet_coin is unmapped.
- **T011:** the held-item candidates for B1 and B4 (all variants, Lv 55) are byte-identical to `f88cdd0` (`cmp` on JSON dumps: IDENTICAL).
- **`tests/unit/test_required_hms_adopted.py` + `test_required_hms.py`: 13 passed.**
- **T017 `test_modelled_table.py`: 4 passed.** The MODELLED entries now use `extends`, and the Python parser merges them.

## T015-T028 Player v3 (2026-10-15)

- **`sim/test/expectimax2_v3_state.test.mjs`: 4 passed.**
  - Hand-set round trip.
  - v1/v2 states carry no v3 fields.
  - Gauntlets: "v3 shadow==live 402/402; rain control changed the AI field mask in 134/134".
  - MODELLED v1 equals the statusMove tables.
- **`sim/test/expectimax2_v3_mechanics.test.mjs`: 10 passed.** Covers weather 5/8 turns and expiry; Thunder/Blizzard accuracy; Synthesis 1/2, 2/3, 1/4; Leech Seed 1/8 with the Grass immunity; Substitute cost; Wish; Aqua Ring; Taunt/Encore/confusion counters; Spikes, Stealth Rock and Flying; Baton Pass; and v2 unaffected.
  - Fixture correction: Stealth Rock on Garchomp is 1/16, because Rock is ×0.5 against Ground.
- **Smoke test, 4 gauntlets each, policy benchmark team, machine loaded by the baseline suite:**

  | Policy | Cleared | ms/decision |
  |---|---|---|
  | v2 | 3/4 | 49.8 |
  | v3 | 4/4 | 43.9 |

- **Model choices that are not game facts:**
  - Random durations use their mean: Taunt 4 (3-5), Encore 5 (3-7), confusion 3 (2-5).
  - The confusion self-hit uses no random factor.
  - Attacks into a substitute use the existing damage buckets.
  - Liquid Ooze, Rain Dish, Ice Body and Dry Skin are not modelled.
  - Baton Pass inside the search picks the bench member by the damage-race heuristic.

## T029 SC-008 positions (2026-10-15)

`sim/test/expectimax2_v3_positions.test.mjs`: 4 passed. Each is a helps / doesn't-help pair against the reference, and v2 never chooses the move:

| Category | Helps (ref chooses) | Doesn't help (ref doesn't) |
|---|---|---|
| Leech Seed | Torterra vs Spiritomb | vs Roserade (Grass) |
| Confusion | Gengar vs Garchomp | vs an already-confused Garchomp |
| Baton Pass | 1-HP Ninjask at +4 Atk / +2 Spe to Scizor | no bench member |
| Hazards | Skarmory vs a full bench | the last foe |

- The hazards pair needs the hazard leaf term; the plain 2-ply reference picks Peck.
- Without boosts, Baton Pass is still chosen. It works like a switch to a better matchup, so the doesn't-help case uses no bench member.

**Findings: no helps-position found at the 2-ply reference** (probe: scratchpad `positions.mjs`, v2 / v3 / v3+leaf / v3-ref / v3-ref+leaf):
- weather (Rain Dance Ludicolo vs Garchomp);
- Substitute;
- Wish (Vaporeon at 30%);
- Taunt (Weavile vs Roserade's Toxic);
- Endure.

  Endure has no value while Reversal/Flail are not modelled (excluded, research R3).

These payoffs lie beyond 2 plies. A deeper reference (T063: depth 3 or rollouts) is the way to test them. Until a position passes, they stay listed here and are not claimed.
