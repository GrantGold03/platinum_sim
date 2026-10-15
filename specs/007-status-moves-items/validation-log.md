# Validation log: 007 status moves and held items

Real output is pasted for each checkpoint. Times are wall-clock on this machine (16 threads).

## One-time hours (budget: 100 h for every one-time run, spec FR-017)

| Run | Task | Budget h | Used h | Running total h |
|---|---|---|---|---|
| Golden v1/v2 record + verify (9.4 min) and positive control (2 × 4.6 min) | T004 | (suites, 8) | 0.31 | 0.31 |
| Suite baseline (pytest 2.49 h + node 0.07 h, rerun) | T002 | (suites, 8) | 2.56 | 2.87 |
| Baseline B4, B5, B3, B1, B2 (standard) | T005 | 11 | 8.20 | 11.07 |
| T020 node + unit checkpoint and fix rerun | T020 | (suites, 8) | 0.20 | 11.27 |
| Speed probe | T028b | (player, 15) | 0.30 | 11.57 |
| Player comparison, policy benchmark team (400 paired x 7 policies) | T063/T064 | (player, 15) | 3.71 | 15.28 |

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

## T030-T035 Alternatives stage (2026-10-15)

- **Measured N** (alternatives per team; offered status moves with v3 MODELLED; Lv 55; member's first moveset):
  - **All-slot 1-2 replacements:** B1 3,136, B2 3,260, B3 2,922, B4 4,794, B5 4,966. At the 25-run minimum, B4 alone is about 22 h, over its 10 h share. Per T031 the user was asked.
  - **User decision (2026-10-15):** weakest two slots. The new N is B1 667, B2 682, B3 612, B4 984, B5 1,039. Per member: B4 Roserade 18 status moves → 204; Blissey 19 → 224; Milotic 13 → 119.
- **Per-category order for structured sets.** The first version broke ties alphabetically and chose Endure over Protect, Aqua Ring over Recover and Double Team as the boost. That is replaced by an explicit effect preference (`EFFECT_RANK`, a policy heuristic checked by T066). The test `test_structured_stall_set_for_milotic` caught it.
- **`tests/unit/test_alternatives.py`: 7 passed** (generation sorted, unique and without excluded moves; the weakest-two-slots rule; a structured Toxic + Recover set; determinism across PYTHONHASHSEED; Holm; adopted moves survive Waterfall placement with a positive control; the stage records every alternative exactly once and adopts a clear winner (fake pool)).
- **Fingerprints:** `STATE_VERSION` 4 and `candidates` were added, and the pinned fingerprints in `test_required_hms.py` and `test_legality_options.py` were updated to `"state_version": 4, "candidates": "reference"`.

## T037-T045 Held items (2026-10-15)

- **Pairings.** Derived from the effect scripts: the weather rocks ↔ their weather moves, and Power Herb ↔ the 9 charge effects (`effect_script_items()`). The rule table `PAIRED_EFFECTS` covers Light Clay ↔ screens, Big Root ↔ drain/seed/Ingrain/Aqua Ring, and Chesto ↔ Rest. Further rules:
  - Choice items only with all-attack sets.
  - Black Sludge only for Poison types.
  - Resist berries only for members weak to a type some League move carries.
  - Type boosts only with an attack of that type.
  - Drawback items only with Trick.
- **Tie rule (FR-011):** `ITEM_TIE_RULE` = more copies; higher effect_param; classic before ARCEUS_*; item key.
- **Deviation from T039 as written.** The greedy screen keeps `held_item_candidates` (Sitrus, the type booster, Leftovers). Greedy can't value most items, and putting them into its 81-team random combinations would dilute the screen. The new items reach the strong player through the alternatives stage (`item`, `status+item`, `structured+item` kinds), as FR-007 asks.
- **N with items** (v3 MODELLED items as of T041, Lv 55): B4 1,030 (46 item swaps), B5 1,085, B3 656, B1 712, B2 724. Move-item pairs appear only for items that v3 models.
- **Player items (T041), all in `sim/test/expectimax2_v3_mechanics.test.mjs`: 17 passed in total.**
  - Light Clay at 8 turns.
  - Chesto after Rest, and Lum.
  - Resist berries (halve once, then eaten).
  - Shell Bell dealt/8.
  - Black Sludge +1/16 or -1/8.
  - Choice lock.
  - Power Herb.
  - Big Root ×1.3.
  - Wide Lens (already in the damage port).
  - Also implemented, without a dedicated test: Zoom Lens (+20% if the target moved), Quick Claw (20% order branch), King's Rock / Razor Fang (10% flinch branch).
- **SC-008 for items (T043), `expectimax2_v3_positions.test.mjs`: 6 passed in total.**
  - Light Clay raises Reflect and Light Screen (+0.03) and leaves Gyro Ball unchanged.
  - Chesto: Rest gains 0.56; the other actions move at most 0.15, which is AI-sampling noise because the AI sees the item.
  - **Finding:** Damp Rock shows no gain at the 2-ply reference (−54.2 vs −50.0 for Rain Dance, inside the noise). Its extra 3 turns lie past the horizon.
- **`tests/unit/test_item_pairings.py`: 7 passed.**
  - Clay, rock, Chesto, Sludge and Choice pairings; no post-Champion item.
  - Tie rule: Splash Plate by copies; Mystic Water when both are unlimited (post-game items option).
  - Offered items are modelled, and skipped ones are listed. Skipped for B4 Roserade: aguav, figy, iapapa, mago, wiki, oran, leppa berries; full incense, grip claw, iron ball, lagging tail, mental herb, shed shell, sticky barb — not modelled by v3.

## T052-T058 Item sources (2026-10-15)

- **Tests first.** The 5 new and changed tests in `tests/integration/test_availability_controls.py` failed before the change: "5 failed, 55 deselected".
- **`sources.py`:**
  - a Return-aware dataflow with a call stack;
  - `GetRandom V, N` + `AddVar V, ITEM_X` as an item-id range;
  - save-var literals;
  - the Amity C table;
  - `AddItem VAR_0x8004, VAR_0x8005`;
  - the daily-random-level rule (1 copy of each item, with a per-item once flag);
  - "repeatable" for flagless new sites;
  - the CheckPartyHasSpecies party condition put in `requires_any`.
- **Give sites tagged by the new dataflow** (sentinel), exactly as expected:

  | Site | Items | Copies |
  |---|---|---|
  | Route 221 house | 3 | 1 each |
  | Pastoria SW house | 17 berries | unlimited |
  | Amity Square | 9 berries (pickup + Gift Man) | unlimited, plus the partner condition |
  | News Press | 12 balls | unlimited |
  | Flower Shop | 5 | unlimited |
  | Route 208 | 26 | unlimited |

- `uv run platsim extract` and `--check`: "up to date (11 files)".
- **`test_availability_controls.py` + `test_extract.py`: 63 passed.**
  - Counts: held_items_unlimited 74, finite 40, unavailable 44.
  - Focus Sash / Expert Belt / Black Belt = 1; Occa unlimited; Liechi 0 (negative control); Choice Band 0.
  - One fixture fix: Route 221 line 39 reads `Common_GiveItemQuantityNoLineFeed`, which is the macro the parser shows as CallCommonScript.
- **`test_validator.py::test_route_221_focus_sash_accepted_once`:** one Focus Sash holder passes, two give ITEM_COPIES, and Choice Band gives ITEM_UNAVAILABLE.
- **T058:** `held_items.md` (an untracked analysis note) is marked superseded in its header and was not regenerated.

## T044 Mechanics divergence pass (2026-10-15)

A read-only comparison of every offered status effect and held item, decomp vs Showdown gen4, with file:line evidence on both sides (agent report, summarised here).

- **Agree:**
  - Encore: both force 3-7 later turns; the "Encore 3-7 vs 4-8" candidate was a counting difference, not a divergence.
  - Taunt 3-5; confusion 2-5 and 50%; sleep 2-5; the Toxic counter; Leech Seed 1/8; Ingrain and Aqua Ring 1/16; Wish; Safeguard 5.
  - Substitute (cost and what it blocks for the offered moves); Endure; Spikes; Stealth Rock; Toxic Spikes.
  - Weather 5 turns, rocks 8; end-of-turn order; Synthesis fractions; Thunder/Blizzard.
  - Attract 50%; Swagger/Flatter; Light Clay 8; status berries; Black Sludge.
  - Quick Claw 20%; the King's Rock move list (202 moves); Choice lock; Big Root ×1.3 (floor(x×1.3) = floor(x×130/100) for x = 1..5000); Power Herb.
  - Resist berries are already covered by `mech-resist-berry-order`.
- **Disagree.** Added to `src/platsim/divergence/mechanics.py` as **accepted**, with their impact, and required by `test_divergences.py`:
  - `mech-baton-pass-taunt`
  - `mech-kings-rock-serene-grace`
  - `mech-shell-bell-substitute`
  - `mech-accuracy-stages-rounding` (covers Wide Lens, Zoom Lens, BrightPowder and accuracy/evasion stage combining)
  - `mech-trainer-friendship`

  Possible corrections (JSON patch Moves.taunt.condition.noCopy; Items.kingsrock priority; code patches for Shell Bell and accuracy) are untested, so none is applied.
- `uv run platsim divergences`: 78 entries (mechanics/accepted=15), 5 Dex patches (unchanged), version sha256:da89b0e14e9826a9. `--check` up to date. `tests/integration/test_divergences.py`: 5 passed.
- **Not checked** (unverified):
  - the confusion self-hit with items or burn;
  - Endure vs Future Sight;
  - the Quick Claw speedRand width;
  - berry timing mid multi-hit;
  - Rain Dish / Ice Body / Dry Skin order;
  - choice-lock edge cases;
  - the Encore failure list;
  - Zoom Lens when the target switched in.

## T059-T062 Variable-power attacks (2026-10-15)

- **Where the code lives.** `weight_hg` (speciesproc.c conversion, with the rounding-override list parsed from `species_weight_rounding_override`) is in `optimizer/candidates.py` and reads `res/pokemon/<sp>/data.json`. The task named `decomp/species.py`; this way no generated-data change is needed. The JS port `sim/ai/calcdamage.mjs speciesWeightHg` uses the same rule.
- **Formulas:**
  - `hidden_power` from BtlCmd_CalcHiddenPowerParams;
  - Low Kick / Grass Knot from `weight_to_power.h`;
  - Gyro Ball min(150, 1+25·foeSpe/userSpe), with the member's stats at its reference level and the foe's from trainers.json (iv, level, nature);
  - Wring Out 121;
  - Magnitude expected 71.0, parsed from BtlCmd_CalcMagnitudePower;
  - Punishment 60;
  - Return 102.
- `is_attack` now = move_classes category attack or variable_attack. For fixed-power moves this is the same set as before.
- **Positive controls (`tests/unit/test_variable_power.py`, 11 passed; plus `test_optimizer_candidates.py` 5 passed):**
  - Return 102;
  - Hidden Power Dark 70 at IV 15 / 31, and Fighting 30 at IV 0;
  - Low Kick 120 vs Hippowdon, 40 vs Roserade;
  - Garchomp 950 hg;
  - the Snowpoint NPC-trade Haunter's fixed IVs give its own Hidden Power;
  - Frustration, Seismic Toss, Flail, Natural Gift and Fling are not in pools;
  - Return enters Snorlax's pool.
  - **Cross-check note:** Mr. Mime comes out at 544 hg from the decomp formula; Showdown says 54.5 kg. The decomp value is used, and the JS port agrees with it.
- **B1 pools at Lv 55, compared with the `f88cdd0` snapshot.** Only variable-power attacks were added:

  | Member | Added | Removed | Best set changed |
  |---|---|---|---|
  | Infernape | Grass Knot | Rock Slide | yes |
  | Staraptor | Return | U-turn | yes |
  | Luxray | Return | Bite | yes |
  | Garchomp | Return | Fire Blast | no |
  | Gyarados | Return | Strength | no |
  | Gardevoir | Grass Knot, Hidden Power | Ice Punch, Shock Wave | yes |

- **Known limitation, recorded:** greedy-v1 scores power-1 moves as 0 (`sim/policy/greedy.mjs`), so the greedy screen undervalues sets that carry Return or Hidden Power. The level search, alternatives and confirm stages use expectimax2, which models these powers (`variablePower`). greedy-v1 is pinned by the golden test and is not changed here.

## T047-T051 Report (2026-10-15)

- **`provenance.optimizer` gains:**
  - `candidate_tests` (every alternative record);
  - `excluded_moves` and `excluded_items` per slot (from the prune-stage summaries);
  - `item_tie_rule`;
  - `alternatives_levels`, `_level_rule` and `_round_size`;
  - `assumptions` (friendship 255, IVs 15, Hidden Power "Dark 70", computed, not typed);
  - `candidate_mode`, and `alternatives` in policy_per_stage and seeds (T033).
- **Warning:** a final member carrying a move the player doesn't model gets the contract's warning. Only a required HM can do that (Defog). Unit check: `not_modelled(v3, Defog, Surf) == [Defog]`.
- **xlsx:** the "Candidates" sheet comes after "Resources" (`SHEET_NAMES`, `CANDIDATE_HEADERS`, `candidate_rows`). The 001 spreadsheet contract is amended. `report --rerender` keeps provenance as is (`rerender.py:110`), so candidate_tests carry over.
- **Web:** the summary gains "Status moves and items: offered N / tested M / adopted K (details: Candidates sheet in result.xlsx)". The row is absent for runs without the stage.
- **Tests:** `test_reports.py` 14 passed (new sheet tuple; Candidates rows equal candidate_tests); browser 6 passed (the 1080p fit still holds); `test_web.py` 20 passed; `test_modelled_table.py` 5 passed.


## T002 / T005 Baseline on `f88cdd0` (2026-10-15)

**T002 suite** (snapshot, 00:04-02:33Z): `1 failed, 503 passed, 4 xfailed, 1 warning in 8965.26s (2:29:25)`.

- The failure is `tests/integration/test_evaluate.py::test_determinism_fast`, at `assert r["repo_commit"] == version.repo_commit()`: both sides are None, because the snapshot is a `git archive` export with no `.git`. It is an environment artifact, not a code result. The early `F` in the progress line was this test, not contention.
- **Node:** `node --test sim/test` exits at once on Node 22 (a directory argument isn't supported). Re-run as `node --test sim/test/*.test.mjs`: `# tests 314 # pass 314 # fail 0`, 260 s.

**T005 baseline benchmark** (standard budget, seed bench-007, `runs/bench-007-baseline/<B>`; minutes per stage from state.json):

| Team | Wall | screen | level_search | confirm | Clear rate (95% CI), n=2000 | Expected avg final level | Start levels |
|---|---|---|---|---|---|---|---|
| B4 | 116.8 min | 8.2 | 53.7 | 53.3 | 0.822 (0.805-0.838) | 59.41 | 58,59,57,60,59,60 |
| B5 | 100.2 min | 4.5 | 48.1 | 46.3 | 0.849 (0.832-0.864) | 64.18 | 63,64,64,63,64,65 |
| B3 | 95.2 min | 4.9 | 41.6 | 47.5 | 0.889 (0.874-0.902) | 59.09 | 58,58,59,59,59,59 |
| B1 | 85.6 min | 6.3 | 51.7 | 26.3 | 0.787 (0.769-0.804) | 56.93 | 56,56,57,57,56,57 |
| B2 | 94.1 min | 4.2 | 44.1 | 44.8 | 0.900 (0.886-0.912) | 53.88 | 53,53,54,54,52,54 |

- All five qualified. Total 8.20 h, against an 11 h budget.
- **SC-006 limit (2.0× baseline per team):** B4 233.6 min, B5 200.4, B3 190.4, B1 171.2, B2 188.2.

## T020 Checkpoint on the 007 code (2026-10-15, machine otherwise idle)

- `node --test sim/test/*.test.mjs`: `# tests 342 # pass 342 # fail 0` (396 s), golden v1/v2 included.
- `uv run pytest -q tests/unit`: `1 failed, 487 passed, 4 xfailed` (224 s). The failure was in `test_alternatives.py::test_run_stage...`: the test generated alternatives without the US2 item swaps, while the stage now includes them (334 vs 204). Test fixed, then `1 passed`.


## T028b Speed probe and T031 round sizes (2026-10-15)

Worker pool, 16 workers, `tests/fixtures/policy_benchmark_team.json`, `stop_on_loss`:

```
expectimax2-v2 n 64 cleared 58 sec 31.5 gauntlets/s 2.034
expectimax2-v3 n 64 cleared 58 sec 27.2 gauntlets/s 2.356
expectimax2-v3-ref n 32 cleared 28 sec 1015.2 gauntlets/s 0.032
```

- **v3 is as fast as v2.** v3-ref is about 74× slower than v3: K_ROOT 32, K_PLY2 8, switch beam 6, ply-2 switches, full damage rolls.
- **Consequence for T063.** About 400 v3-ref gauntlets per team is about 3.5 h. The 15 h player budget allows the policy benchmark team plus 2 teams (about 10.5 h of reference) plus the cheap candidates (about 3 min each per 400 at v3 speed).

**Round sizes (research R5).**
- Share per reference team: 10 h.
- "The rest of the run" is that team's baseline wall time × (2.034 / 2.356).
- Screening cost is 1.96·r·N gauntlets at v3's 2.356/s, with N measured with items (T040).

| Team | N | Rest (h) | Cap (gauntlets) | r | Cost (gauntlets) | Estimated team hours |
|---|---|---|---|---|---|---|
| B4 | 1,030 | 1.68 | 70,561 | **25** | 50,470 | 7.63 |
| B5 | 1,085 | 1.44 | 72,587 | **25** | 53,165 | 7.71 |
| B3 | 656 | 1.37 | 73,197 | **50** | 64,288 | 8.95 |

- The estimates total about 24.3 h against 31 h.
- **Unverified:** stop_on_loss gauntlets near the threshold (U-1) end earlier, so real throughput should be at least the probe's. N was measured with each member's first moveset at Lv 55, while the run uses the winner's sets at the reference level.


## T036 / T046 Alternatives smoke test (2026-10-15, outside the 100 h budget)

- `tests/integration/test_alternatives_quick.py`: B4, quick budget, `candidates=reference`, `alternatives_round=5`, `alternatives_members=2`.
  - Result: `1 passed in 11056.27s (3:04:16)`. Run 1 with 16 workers took 5,210 s; run 2 with 7 workers took 5,811 s.
  - result.json is byte-identical across the two (SC-005).
- **Comparison level:** "U - 1 (first failing neighbour)", which was 58 for all six members.
- **690 alternatives recorded** (slot 1 Roserade 333, slot 2 Blissey 357): 684 dropped in screening and 6 finalists tested in full. All six were "indistinguishable" after Holm (quick: 100 paired runs), so nothing was adopted. The finalists against the current team's 57%:

  | Slot | Kind | Alternative | Clear rate | p (Holm) |
  |---|---|---|---|---|
  | 1 | item | Aspear Berry | 65% | 0.215 |
  | 1 | status | Swagger + Grass Whistle | 72% | 0.105 |
  | 1 | status+item | Ingrain + Big Root | 70% | 0.105 |
  | 2 | status | Rest + Attract | 60% | 0.999 |
  | 2 | status | Protect | 62% | 0.999 |
  | 2 | status+item | Rest + Light Screen + Light Clay | 68% | 0.297 |

- The final team (clear rate 0.822) passed the validator.
- **Timing:** a quick run with 2 members' alternatives at r = 5 took 87 min. The stage dominates level_search time (3,981 s).
- **T046 (deviation, recorded):** the task named a B1 quick run. This B4 run already shows `item` and `status+item` alternatives among the recorded and fully tested candidates, and a validator pass, which is everything T046 checks. A second 3 h smoke run was not made.


## T063 / T064 Player comparison: policy benchmark team (2026-10-15)

400 paired gauntlets per policy (seeds `v3-accept|policy_benchmark|i`), `tests/fixtures/policy_benchmark_team.json`; script `scratchpad/t063.py`:

```
policy_benchmark expectimax2-v3-ref cleared 336/400 in 12914s
policy_benchmark expectimax2-v3 cleared 342/400 in 186s
policy_benchmark expectimax2-v3-c1 cleared 353/400 in 188s
policy_benchmark expectimax2-v3-c2 cleared 336/400 in 188s
policy_benchmark expectimax2-v3-c3 cleared 347/400 in 190s
policy_benchmark expectimax2-v2 cleared 333/400 in 164s
policy_benchmark greedy-v1 cleared 47/400 in 8s
policy_benchmark expectimax2-v3 vs ref: rate 0.855 vs 0.840, only 49/43, p 0.6024, verdict indistinguishable
policy_benchmark expectimax2-v3-c1 vs ref: rate 0.882 vs 0.840, only 53/36, p 0.0893, verdict indistinguishable
policy_benchmark expectimax2-v3-c2 vs ref: rate 0.840 vs 0.840, only 48/48, p 1.0000, verdict indistinguishable
policy_benchmark expectimax2-v3-c3 vs ref: rate 0.868 vs 0.840, only 48/37, p 0.2780, verdict indistinguishable
policy_benchmark expectimax2-v2 vs ref: rate 0.833 vs 0.840, only 53/56, p 0.8482, verdict indistinguishable
policy_benchmark greedy-v1 vs ref: rate 0.117 vs 0.840, only 4/293, p 0.0000, verdict B
policy_benchmark v3 vs expectimax2-v2: 0.855 vs 0.833, only 53/44, p 0.4168, verdict indistinguishable
policy_benchmark v3 vs greedy-v1: 0.855 vs 0.117, only 304/9, p 0.0000, verdict A
```

- **Every cheap v3 setting is not worse than the reference on this team.**
- **The expensive reference is not measurably better than plain v3** (0.840 vs 0.855), at 70× the cost: 12,914 s against 186 s.
- **Reading, unverified until B4 and B5:** on an all-attack team the extra search width buys nothing measurable, and the leaf terms don't hurt. c1 (residual leaf) has the highest point estimate but is not significant.
- **v3 vs v2:** indistinguishable here. **v3 vs greedy-v1:** better (p ≈ 0).
