# Research: Status Moves and Held Items (007)

Observed on 2026-10-14 on branch `007-status-moves-items`, whose code equals `main` at `f88cdd0`. Four read-only research passes were made: the battle player, the optimizer pipeline and timings, the ledger sources, and the move/item data flow. Their scratch scripts are in the session scratchpad. Paths are relative to the repository root. Anything not observed is marked **unverified**.

Decomp shorthand: BL = `pokeplatinum/src/battle/battle_lib.c`, BS = `battle_script.c`, BCP = `battle_controller_player.c`, ES = `pokeplatinum/res/battle/scripts/effects/effect_script_NNNN.s`.

---

## R1. Classify status moves from the decomp's effect scripts (FR-001 to FR-004)

**Decision.** A new module `src/platsim/optimizer/move_classes.py` classifies every move effect into these categories:
- in scope: `recovery`, `inflict_status`, `leech_seed`, `self_boost`, `protection`, `screen`, `weather`, `other`;
- excluded: `foe_drop`, `fixed_damage`, `no_effect_singles`, `sacrifice`, `reactive`.

Most of it is **derived from the effect scripts**:
- `CURRENT_MOVE_DATA.effect` indexes `pokeplatinum/generated/move_battle_effects.txt`, and line N is `ES` N (BS:2084).
- Status scripts are mostly one `UpdateVar … BTLVAR_SIDE_EFFECT_FLAGS_DIRECT, MOVE_SIDE_EFFECT_{TO_ATTACKER|TO_DEFENDER}|MOVE_SUBSCRIPT_PTR_X`. The pointer names come from `include/data/move_side_effect_subscripts.h`.

| Category | Rule (over decomp constants) |
|---|---|
| foe_drop | every side effect is `TO_DEFENDER` and the pointer matches `*_DOWN_*` (11 effects, Captivate included) |
| self_boost | `TO_ATTACKER` and the pointer matches `*_UP_*`, plus a rule table for Focus Energy, Minimize, Stockpile, Belly Drum, Acupressure and Curse (non-Ghost branch) |
| inflict_status | `TO_DEFENDER` with pointer ∈ {SLEEP, POISON, BADLY_POISON, PARALYZE, BURN, YAWN} |
| leech_seed | pointer LEECH_SEED_START |
| recovery | pointer ∈ {RECOVER_HALF_MAX_HP, REST, ROOST}, or script commands TryWish / Ingrain / Aqua Ring; plus Swallow |
| protection | pointer PROTECT (Protect, Detect, Endure) and TRY_SUBSTITUTE |
| screen | pointer ∈ {REFLECT, LIGHT_SCREEN, SAFEGUARD_START} |
| weather | pointer WEATHER_START (ES 0115/0136/0137/0164) |
| fixed_damage | script writes `BTLVAR_DAMAGE` without `CalcDamage`: exactly 6 effects, covering the 7 FR-003 moves |
| no_effect_singles | `range == RANGE_ALLY` (Helping Hand); script fails in `BATTLE_TYPE_TRAINER` (Teleport, ES 0153); Splash (ES 0085); rule-table entry for Follow Me |
| sacrifice | rule table: Memento, Healing Wish, Lunar Dance (the user faints) |
| reactive | rule table: Counter, Mirror Coat, Metal Burst, Bide, Spit Up (needs Stockpile), Present |
| other | everything else (Taunt, Encore, confusion, Attract, hazards, Baton Pass, Trick, Haze, …) |

- **The rule table is unavoidable** for about 20 pointer/effect constants. It is keyed on `BATTLE_EFFECT_*` / `MOVE_SUBSCRIPT_PTR_*` constants, never on move names, so it is a rule over decomp constants, not game data (Constitution I).
- **Guard tests:**
  1. Every effect of every move in `load_moves()` gets exactly one category. An unknown effect raises; it never falls into `other`.
  2. Every constant named in the table exists in the decomp's generated lists.
  3. Positive controls:
     - Screech and Growl → foe_drop;
     - Seismic Toss → fixed_damage;
     - **Magnitude → not fixed.** Its effect is named `BATTLE_EFFECT_PSYWAVE`, a trap for name rules;
     - Swords Dance → self_boost;
     - Thunder Wave → inflict_status;
     - Reflect → screen;
     - Rain Dance → weather;
     - Helping Hand, Teleport, Splash → no_effect_singles;
     - Defog → other.
  4. The derived foe_drop set equals expectimax2's `FOE_DROPS` plus Captivate.
- **Category boundaries chosen here:**
  - Pain Split, Heal Bell, Aromatherapy and Refresh go to `other`, not `recovery`. They don't restore the user's HP by a fixed fraction.
  - Sacrifice and reactive moves are excluded as conditional (spec FR-003 extended to say so).
- **Rationale.** Deriving from the scripts keeps the classification tied to the decomp. Earlier hand tables went stale without anyone noticing: `EXP_HOLD_EFFECTS` names an effect that no longer exists, and `EXCLUDED_ATTACK_EFFECTS` has no test.
- **Alternatives rejected.**
  - A hand list of move names (violates I).
  - Classification by effect *name* (breaks on Magnitude/Psywave).

## R2. Held-item filter and pairings (FR-006, FR-009, FR-011)

**Decision.** A new module `src/platsim/optimizer/item_classes.py`.

1. **An item has an in-battle effect** if its `HOLD_EFFECT_*` is referenced in `pokeplatinum/src/battle/*.c` or `res/battle/scripts/**`, by name **or by number**.
   - The type-resist berries are compared numerically (`subscript_type_resist_berry.s:20-38`, literals 19-35). A name-only grep wrongly marks all 17 as unused; this is the method's positive control.
   - Unreferenced effects: NONE, ENCOUNTERS_DOWN, NO_EVOLVE and the 7 EVOLVE_* effects.
2. **Excluded although referenced:**
   - `no_outcome`, a rule table guarded by "every reference lies in the named function": MONEY_UP (BL:4122), FLEE (BL:3192, 3275; Run is blocked in trainer battles, BCP:605) and FRIENDSHIP_UP.
   - Experience and EV items, derived from the functions that reference them: `BtlCmd_CalcExpGain` / `BattleScript_GetExpTask` → EXP_SHARE, EXP_UP; `BattleScript_CalcEffortValues` → EVS_UP_SPEED_DOWN and LVLUP_*_EV_UP. This replaces the stale `EXP_HOLD_EFFECTS`.
3. **Species-gated items** (Light Ball, Thick Club, Metal Powder, Quick Powder, Lucky Punch, Stick, DeepSea Tooth/Scale, the three Orbs, Soul Dew) are offered only to their species. The gates are parsed from the `heldItemEffect == … && species == …` conditions (BL:1252, 6730-6772, 7127).
4. **Copies:** `team_item_copies(led, const, team) != 0`, not `led.item_copies`, because Leftovers is team-gated (ledger.py:466).
   - Measured under default options before species gates: **87 items qualify**, and 48 more have an eligible effect but 0 copies.
5. **Pairings (FR-006), each derived or tied to a decomp constant:**

   | Item | Paired with | Source |
   |---|---|---|
   | Light Clay | Reflect, Light Screen | referenced only from `BtlCmd_TryLightScreen`/`TryReflect` (BS:4229, 4272) |
   | Damp/Heat/Smooth/Icy Rock | their weather move | the item's `CheckItemHoldEffect` appears in ES 0136/0137/0115/0164; derived by scanning effect scripts for `HOLD_EFFECT_*` |
   | Chesto, Lum | Rest | Rest puts sleep on the user (`subscript_rest.s:32`) ∩ the status the berry cures (BL:4608, 4662) |
   | Big Root | Leech Seed, drain moves, Ingrain, Aqua Ring | the subscripts that reference LEECH_BOOST |
   | Power Herb | the 9 charge effects | CHARGE_SKIP; equals expectimax2's `CHARGE_EFFECTS` |
   | Black Sludge | Poison-type members only | BL:4939-4948 |
   | Choice Specs | all-attack movesets only | lock at BCP:3923, 4492 |
   | Type-resist berry | members weak to that type, when some League mon carries a move of that type | `type_chart()` and `trainers.json` |
   | Drawback items (Iron Ball, Lagging Tail, Full Incense, Sticky Barb, Toxic/Flame Orb) | only with Trick or Switcheroo | — |
   | Everything else | any moveset | its effect is not tied to a move |

6. **Type-boost tie-break (FR-011).** Every Plate/classic pair has effect_param 20 (`sTypeBoostingItems`, BL:6514-6547). Order:
   1. more copies first (unlimited > n);
   2. higher effect_param;
   3. classic `STRENGTHEN_*` before `ARCEUS_*` (Plates also change Arceus/Judgment, ES 0268, BL:6399);
   4. item key.

   The rule is stated in the result. **Default chosen in planning. The user can override it.** Today the alphabetical key decides, which gives an inconsistent mix of Plates and classic items.
- **Alternatives rejected.**
  - A hand list of "useful items".
  - A name-only grep (misses the resist berries).

## R3. Variable-power attacks (US4, FR-012)

**Decision.** `move_value` scores each one by its decomp power formula, per member variant and per League foe. `league_opponents()` gains each foe's level, stats and weight.

| Effect | Moves | Power used | Source |
|---|---|---|---|
| POWER_BASED_ON_FRIENDSHIP | Return | 102 (friendship 255) | ES 0121; `trainer_ai.c:3019` |
| POWER_BASED_ON_LOW_FRIENDSHIP | Frustration | 0 at 255, so **never offered** | |
| RANDOM_POWER_BASED_ON_IVS | Hidden Power | from the variant's IVs; default IVs 15 give **Dark, 70** | BS:6007-6031; NPC trades use `fixed_mon["ivs"]` |
| INCREASE_POWER_WITH_WEIGHT | Low Kick, Grass Knot | from the foe's weight | BS:6808-6829 and `include/data/battle/weight_to_power.h`; weight from `res/pokemon/<sp>/data.json` `weight_pounds` converted to hg as in `tools/dataproc/src/speciesproc.c:696-751` (must be extracted) |
| POWER_BASED_ON_LOW_SPEED | Gyro Ball | min(150, 1 + 25·foeSpe/userSpe), with stats at the member's reference level and each foe's level | BS:7123-7131 |
| INCREASE_POWER_WITH_MORE_HP | Wring Out, Crush Grip | 121 against a foe at full HP | BS:7261 |
| PSYWAVE effect | Magnitude | expected power 71 | BS:5820-5850 |
| INCREASE_POWER_WITH_MORE_STAT_UP | Punishment | base 60 | BS:7354 |

- **Excluded as conditional (recorded):**
  - Flail/Reversal: 20 at full HP;
  - Trump Card: depends on PP;
  - Natural Gift and Fling: consume the item, and their power fields aren't extracted today.

  These go in the `reactive`/conditional exclusion with reasons.
- **Friendship in battle.** `sim/team.mjs` sends no `happiness`. Showdown defaults to 255 (`pokemon-showdown/sim/pokemon.ts:342`), and a Node probe showed p1 happiness 255 and Return base power 102. The decision is to set `happiness: 255` **explicitly** in `memberSet`, so the assumption is visible and fixed, and to state it in the result.
- The player's `variablePower` (`sim/policy/expectimax2.mjs:436-461`) already covers friendship, weight, IVs and Gyro Ball. The Python scorer ports the same formulas.
- **Positive controls:** Low Kick vs Hippowdon = 120 and vs Roserade = 40; default Hidden Power = Dark 70; Return = 102; Frustration not offered.

## R4. Battle player: expectimax2-v3, built reference-first (FR-016, FR-019)

**Facts.**
- **Versions.** They live in `sim/policy/expectimax2.mjs`:
  - names at :161-162 and option sets `V1_OPTS`/`V2_OPTS` at :168-169;
  - registered in `sim/gauntlet.mjs:31,41-42`, and listed by the worker `hello` (`sim/worker.mjs:38`).
  - The Python side names the policy in `optimizer/run.py:77`, `optimizer/levels.py:55`, `evaluate.py:54` and `cli.py:140`.
  - The version name also seeds the AI sample streams (:301-313), so v3 draws different samples from v2.
- **Search.**
  - 2 plies;
  - K_ROOT 8 / K_PLY2 2 AI samples;
  - a switch beam of 2;
  - the damage-roll buckets are compressed;
  - koStop is on in v2.
  - **Measured 2026-10-14:** 37-49 ms per decision, 75-80% of it in the AI, 350-420 leaves, about 45 AI calls, 2.7-3.8 s per 5-battle gauntlet on 16 workers.
- **State gaps:**
  - weather is read once and never set or expired;
  - `signature()` and the damage cache key have no weather and no new volatiles;
  - `battle.field` isn't shadowed;
  - Light Clay is ignored (hard 5 turns, :778-779);
  - weather heals always give 1/2 (a model bug: decomp BS:5966-5978 gives 1/2, 2/3 or 1/4);
  - weather abilities on switch-in aren't applied;
  - Thunder/Blizzard weather accuracy is missing.
- **Already modelled through the damage port** (they need positive-control tests only): Wise Glasses, Expert Belt, Razor Claw/Scope Lens, Wide Lens.
- **Leaf value:** a flat status penalty (tox 0.12 whatever the counter), and no projection of residual damage. Stall lines (Toxic + Protect + Recover) and hazards fall outside the 2-ply horizon.
- **No test pins v1/v2 output across code changes.** `determinism.test.mjs` only compares runs of the same code.

**Decisions.**
1. **Groundwork.**
   - Before any player edit, record per-battle `log_hash` for fixed-seed v1 and v2 gauntlets on 2 teams as a **golden test**. v1 and v2 must stay byte-identical after every v3 change. Constitution IV: earlier results must reproduce.
   - All v3 behaviour sits behind option flags in `V3_OPTS`.
   - Add a machine-readable table, `MODELLED`, of the effects and items each version models. The optimizer reads it the same way `SELF_BOOSTS` is parsed, or the worker `hello` reports it, to flag "not modelled" (FR-013).
2. **State plumbing.** Weather and its turns; volatiles (Leech Seed, substitute HP, Taunt, Encore, confusion, Attract, Aqua Ring, Ingrain, choice lock); side conditions (Spikes, Toxic Spikes, Stealth Rock, Safeguard, Wish, screen turns).
   - All of these are read at the root from the live battle; the AI adapter already reads them (`sim/ai/adapter.mjs`).
   - They are materialised on the shadow: `field` is shadowed for the first time.
   - They are added to `signature` and to the damage cache key.
3. **Mechanics.** One decomp-cited unit test per effect:
   - Light Clay / rocks (8 turns);
   - Wish, Aqua Ring, Ingrain, Safeguard, Endure;
   - Shell Bell, Black Sludge, Zoom Lens, Quick Claw;
   - status berries and Lum; resist berries;
   - weather-dependent heals; Thunder/Blizzard accuracy;
   - setting and expiring weather, including Sand Stream on switch-in. This also fixes the opponent side: Whiscash/Golem Sandstorm, Hippowdon, and Sunny Day users;
   - Leech Seed; Substitute (damage routed to the sub's HP);
   - Taunt, Encore, confusion, Swagger/Flatter, Attract; King's Rock/Razor Fang flinch;
   - choice lock;
   - hazards; Baton Pass.

   The effect locations are listed in the player research notes: BCP:1085-1110, 1311-1392, 1591-1645, 2617-2668; BS:4725, 5149, 5211, 5388-5450, 7592-7650, 8302-8335; BL:1278-1284, 2055-2110, 4608, 4662, 4939.
4. **Reference player (Principle VI).**
   - **Settings:** v3 with every mechanic exact, no roll-bucket compression, K_ROOT 32 and K_PLY2 8, all switches at the root and switches at ply 2. A depth-3 search is also tried, or rollouts to the end of the battle with v2 as the rollout policy, whichever finishes first on the benchmark.
   - **Cheaper candidates:**
     - today's knobs (2-ply, K 8/2, beam 2, compression), plus a **residual-projection leaf**: per-turn HP drift from tox n/16, psn/brn 1/8, Leech Seed ±1/8, weather 1/16, Leftovers/Black Sludge, Aqua Ring/Ingrain and a pending Wish, projected over H turns; plus a hazard term per remaining foe switch-in;
     - state-dependent status penalties;
     - leaf weights re-fitted by logistic regression on reference-played games, as was done for v2 (header :20-26).
   - **Acceptance:** paired gauntlets (McNemar) of each candidate against the reference on the benchmark teams. The production v3 is the cheapest candidate that isn't significantly worse. Run times are recorded in `validation-log.md`.
   - **Overall acceptance:** v3 vs v2 and vs greedy-v1 using the `test_policy_strength` pattern.
5. **Positive-control positions (SC-008).** For each newly modelled category or item, build a position with `leagueBattle` (`sim/test/ai_fixtures.mjs`) where v3 chooses the move or gains from the item and v2 doesn't, and a matching position where it doesn't help and v3 doesn't choose it.
   - **Unverified:** whether Showdown's `field.setWeather`, `addVolatile` and `addSideCondition` work on these fixtures. Checked first in the tasks.
6. **Switch-over.** `POLICY` in `run.py`/`levels.py`, `DEFAULT_PLAYER_POLICY` in `evaluate.py` and the CLI default change to `expectimax2-v3` **only after** acceptance. `STATE_VERSION` goes 3 → 4.

**Alternatives rejected.**
- A new player from scratch: everything that has been validated would be lost.
- Leaving the player alone: withdrawn by the user.

## R5. Where status and item candidates enter the optimizer (FR-007, FR-008, FR-017)

**Facts.** Today's setup check (`run.py:485-519`):
- runs once at the uniform bisection levels;
- slots in order, moves only (the item is kept; the paired setup items at `candidates.py:487` are never used);
- skips an alternative that can't be built **without repair** (Infernape's Swords Dance set was skipped this way in all 4 recorded standard runs);
- uses McNemar with no multiplicity control and greedy adoption;
- checkpoints only at the end.

At the bisection levels the team cleared 0.825-0.885, well above the 0.75 threshold, while the objective is decided near the threshold. Putting status sets into the greedy-v1 screen would require running the whole screen on expectimax2: about 17,100 gauntlets ≈ 105 min, against about 5 min today.

**Decision: a new `alternatives` stage**, which replaces and generalises the setup check, in the same place: after bisection, before descent.
1. **Candidates per member, deterministic and sorted:**
   - the member's current set with 1 or 2 slots replaced by offered status moves (R1 categories in scope);
   - **structured 3-4-status sets** (spec FR-005, analysis I1): one move per category, from inflict-status, protection, recovery, Leech Seed, self-boost and screen. For each choice of 3 or 4 categories the member can fill, take each category's best move under a deterministic per-category order (decomp-derived values: boost stages, heal fraction, status accuracy). The member's best attack fills the 4th slot of a 3-status set.
   - **Offered moves only.** A move is offered only if the player version in use models its effect (`MODELLED`, analysis U2). The rest are listed as "not offered: not modelled".
   - each with its paired items (R2);
   - item-only swaps on the current set;
   - all copy conflicts **repaired** (`resources.repair`), not skipped.
2. **Comparison level.** Each alternative is compared with the current team at the current team's **first failing neighbour level** from the bisection (`fail_u`). "The alternative passes the PASS rule where the current team fails" means strictly better under the objective, which is lower levels. When no failing neighbour exists, the bisection levels are used. Paired seeds come from the namespace `f"{seed}|alternatives"`.
3. **Statistics.** McNemar exact per alternative, with Holm correction within each member. The winner is confirmed on a fresh seed block before adoption, so it isn't greedy on noise. Adoption is slot by slot, as today.
4. **Checkpointing.** After each alternative, in `state.json` under `level_search.alternatives`.
5. **Two modes, FR-017:**
   - **`reference`, two levels (analysis C1, user 2026-10-14):** every alternative of a member reaches the strong player.
     - Successive halving, keeping the top third each round, narrows them. Round sizes are set by the budget below (user revision, 2026-10-14).
     - The finalists, the last round's top 3, get the full paired test against the current team with Holm correction, plus the confirm block.
     - Budget: part of the 100 h one-time development budget (see the cost note).
     - Why two levels: a probe (2026-10-14, Lv 55, default options) counted 5,604 (B1), 8,540 (B4) and 9,554 (B5) 1-2-slot alternatives per team, before items. A flat 200-run test of each would take about 115-196 h per team.
   - **`prefilter`:** a cheaper path that must be validated against `reference` on the benchmark before it becomes the default. Shapes to try:
     - smaller successive-halving rounds (e.g. 25/50/100/200);
     - a static pre-score (R3 values plus category priors) that keeps the top N per member;
     - a combination.

   The mode is recorded in `job_fingerprint` and provenance. Users can choose `reference` (CLI flag `--candidates reference|prefilter`; the web keeps the default).
6. **The structured 3-4-status rule is itself a cap** (Principle VI). It is validated against **full 3-4-slot generation on two members**, B4 Milotic and B4 Roserade, at the same levels and seeds, through the same two-level reference. The rule is accepted if no full-generation set beats the best structured or 1-2-slot set significantly. This is recorded in Complexity Tracking.
- **Estimated cost (unverified; from recorded throughput of about 2.7 v2 gauntlets/s, v3 cost unknown).** Successive halving over N alternatives costs about N×100 + (N/3)×200 + (N/9)×400 + (N/27)×800 ≈ 196·N gauntlets. For N ≈ 8,000 per team that is about 1.6 M gauntlets, roughly 160 h at v2 speed. That is still too much, so the first round's size is the main cost driver.
  - **The user's revision (2026-10-14):** that is not feasible.
    - The finished tool MUST take at most 2.0× each team's baseline, which is about 8-11 h for all five teams.
    - One-time reference runs MAY take up to 100 h **in total**.
  - **Allocation of the 100 h** (a planning decision, adjusted only with a record in the validation log):
    - about 20 h for the player reference comparisons (T063, T064);
    - about 10 h for the generation-rule reference (T066);
    - about 70 h for the candidate reference benchmark (T067), so about 14 h per team.
  - **Round sizes.** With round sizes r, 2r, 4r, 8r and keeping a third each round, the cost is about 1.96·r·N gauntlets for N alternatives. For each team, r = the largest of {100, 50, 25} with 1.96·r·N plus the rest of the run within 14 h, at the v3 throughput measured in T063.
  - **Example.** At v2 speed (2.7 gauntlets/s, so about 136k gauntlets in 14 h) and N ≈ 2,800, r = 25 just fits; at N ≈ 8,000 nothing fits.
  - **If r = 25 doesn't fit a team,** stop and ask the user before running it.
  - **What reduces N:** dropping unmodelled moves (U2) and counting only offered moves. The real N is measured first (task T031).
  - **The production budget is the binding constraint.** At most 2× the baseline leaves about 1.5-2 h per team for alternatives, about 15-20k gauntlets. Production therefore can't screen thousands of alternatives. The prefilter has to pick a few dozen per member before the strong player sees them, which is why the reference matters.
  - Excluding unmodelled moves (U2) and counting only offered moves will reduce N. The real N per team is measured first (task T031) and recorded.

**Alternatives rejected.**
- Status sets in the greedy screen: the screen scores them 0, which violates FR-007.
- The whole screen on expectimax2: about 105 min for the screen alone, with few status options inside the 81-team cap.
- A full level search per alternative: 15-60 min each.

## R6. Required HMs and adopted moves (FR-014)

**Facts.** `_slot_cost` (`resources.py:201-207`) protects any modelled self-boost, adopted or not. Every other status move costs (0, 0) and is displaced first. `MemberSpec` is rebuilt positionally in `_apply_abilities` (`run.py:185-194`), in the screen combos (:410), in the setup alternative (:497) and in `repair` (`resources.py:332`). Any new field would be silently dropped at those points.

**Decision.**
- Add `adopted: tuple[str, ...] = ()` to `MemberSpec`. It is serialised only when non-empty, so existing `spec_to_json` and level-memo keys are unchanged.
- Rebuild specs with `dataclasses.replace` everywhere.
- Slot cost tiers, lowest is displaced first:
  1. non-adopted status;
  2. attacks by League value;
  3. non-adopted modelled boost;
  4. adopted.
- The moves of the alternative **under test** are treated as adopted while it is tested, so an HM can't displace the move being measured. This is a real risk in benchmark B3.

## R7. Missing ledger sources (FR-018, US5, SC-009)

**Facts.** All three maps are pre-Champion in the mapgraph, and `site_gates` returns no gate for any give node. The project already treats daily gifts, even random ones, as UNLIMITED `npc_item_gift` entries (`_daily_guard`, `sources.py:984`). Precedents: Great Marsh shard, Celestic Great Ball, News Press Heart Scale.

| Source | Decomp | Why the ledger misses it today |
|---|---|---|
| Route 221 house | `scripts_route_221_house.s`. Daily flag (:14, :41). A party Pokémon must be at exactly the **daily random level** 2-99 (`GetDailyRandomLevel`; `system_vars.c:267-271`). The reward rotates Black Belt → Expert Belt → Focus Sash (:28-30, :42-44), 1 each. Route 221 needs Surf (5 badges). | `_const_dataflow` doesn't carry the callee's state back across `Call`/`Return` |
| Pastoria SW house | `scripts_pastoria_city_southwest_house.s`. Daily flag (:13, :19). `GetRandom V, 17` + `AddVar V, ITEM_OCCA_BERRY` (:15-16): 17 berries, Occa … Chilan (items.txt ids 184-200). | `AddVar` turns the value into `?` |
| Amity Square pickup | `scripts_amity_square.s:283-375`. Repeatable after 200 steps. 20% of pickups are an item, from a 9-berry table (Magost … Belue). Entry needs an allowed partner species (:646-748), and the starter lines always qualify before the Champion. | Save-var item id |
| Amity Square Gift Man | :917-973. Daily, 5 copies, from `sBerryAndAccessoryManOptions` (`src/scrcmd_amity_square.c:148-187`; the same 9 berries plus accessories) | Non-literal `AddItem` |

**Decision.** Extend `src/platsim/availability/sources.py`, keeping kind `npc_item_gift` and the existing daily convention:
1. Make `_const_dataflow` return-aware with a call stack. Prototyped: over 116 give sites, exactly 2 change, Route 221 and the News Press daily Poké Ball.
2. Support the `GetRandom V, N` + `AddVar V, ITEM_X` idiom, giving the item-id range [id(X), id(X)+N). It also resolves the Flower Shop and the Route 208 Berry Master; those berries are already pre-Champion, so held-item counts don't change.
3. Resolve a save var whose every write is a literal `ITEM_*` (the Amity pickup), with an explicit "repeatable, no flag" rule giving UNLIMITED.
4. Parse the C table `sBerryAndAccessoryManOptions`, keeping `ITEM_*` tokens only, and bind it to the Gift Man's `AddItem`.
5. Put the party conditions in `detail`: the daily random level, and Amity's partner list via `requires_any` parsed from :726-748.

**Copies.**
- **Route 221: 1 copy of each item** (user, 2026-10-14, analysis I2: the conservative reading). The ledger recognises the case from the script's `GetDailyRandomLevel` party check, a rule over a decomp command and not a map name. Such a daily gift counts each possible item once, instead of the usual daily → UNLIMITED.
- **The others: UNLIMITED,** following the daily precedent. Under the replanting rule any berry with a copy is unlimited anyway. The reading and its reason are recorded in each entry's `detail`. An `uncertain` gate is **not** used, because it would force the entry to POST.

**Effect (simulated):**
- `held_items_unlimited` 66 → 74 (8 new berries: Occa, Passho, Kebia, Coba, Payapa, Tanga, Charti, Chilan);
- `held_items_finite` 37 → 40 (Black Belt, Expert Belt, Focus Sash at 1 each);
- `held_items_unavailable_count` 55 → 44;
- the counts were simulated with all three items UNLIMITED (77/37/44) and re-derived by hand for the 1-copy reading, so they are unverified until T057;
- the 9 Amity berries have `HOLD_EFFECT_NONE`;
- TMs and species are unchanged.

**Validator:** no logic change; it already reads `led.item_copies`.

**Tests:**
- Positive controls following `tests/integration/test_availability_controls.py`: Route 221 :39 gives 3 entries, Focus Sash UNLIMITED.
- Pastoria gives exactly the 17-id range; Liechi (id 201) stays 0 as the negative control.
- The Amity C and script berry sets are equal, with accessories excluded.
- A dataflow sentinel: only the expected give sites change.
- The validator accepts Focus Sash; Choice Band stays 0.
- Update `test_availability_controls.py:522,526` (66 → 74, 37 → 40, 55 → 44) and regenerate `data/generated/` with `uv run platsim extract`.

**Recorded, not in scope.** Other unmodelled sources found:
- **The Pickup ability.** Its rare table includes Leftovers and King's Rock (BS:7781-7822, `include/data/pickup.h`). It would bypass the 003 team-gated Leftovers rule.
- Honey Gather.
- Jubilife TV prizes.
- The Pal Park berries.
- Scratch-off cards.

Proposed as a follow-up feature.

## R8. Showdown coverage of the offered moves and items (Constitution II)

**Facts.**
- Every decomp move maps to a Showdown id.
- 203 items map. Only 9 items with a hold effect don't, and all 9 are excluded by R2: Amulet Coin, Cleanse Tag, Everstone, Exp. Share, Luck Incense, Lucky Egg, Pure Incense, Smoke Ball, Soothe Bell.
- An unmapped item becomes "no item" in Showdown **without any error** (`sim/team.mjs`).
- `data/divergences.json` compares item and move *data* only, not behaviour.
- **Spot checks that agree:** Light Clay and rock durations (8), Grip Claw 6, sleep 2-5, Taunt 3-5, Wish.
- **Candidate divergence (unverified):** Encore lasts 3-7 turns in the decomp (BS:4742) but 4-8 in Showdown gen4 (`random(4,9)`).

**Decision.**
- Add a test asserting that every item the R2 filter offers maps to a Showdown id.
- Run a mechanics-divergence pass over each offered status effect and hold effect, recording each in `data/divergences.json` as corrected or accepted with its impact. Encore goes first.
- Showdown itself isn't modified.

## R9. Benchmark and today's baseline (SC-002, SC-006)

**Facts.**
- 16 workers (`os.cpu_count()`; Ryzen 7 5700X3D).
- Recorded standard runs: about 80 min (`runs/job-20261008T235244Z-2d8f18`) to 2 h 07 min (`runs/t076/v8`). Level search is about 70% of each run.
- **No standard run exists on `f88cdd0`**, so the baseline must be measured.
- Pre-Champion TM copies matter:
  - 1 copy: Toxic, Rain Dance, Sunny Day, Hail, Roost, Rock Polish;
  - **0 copies:** Thunder Wave, Calm Mind, Sandstorm, Will-O-Wisp, Bulk Up;
  - unlimited: Light Screen, Reflect, Swords Dance, Rest, Protect, Substitute.

**Benchmark** (every member resolves under default options; status moves checked legal at Lv 55):

| Id | Team | Exercises |
|---|---|---|
| B1 | Infernape, Staraptor, Luxray, Garchomp, Gyarados, Gardevoir | continuity with past runs; Calm Mind, Wish, screens, Dragon Dance, Roost (1-copy TM) |
| B2 | Garchomp, Infernape, Staraptor, Rotom, Floatzel, Weavile | Rotom Thunder Wave (relearner only); Floatzel Swift Swim + Rain Dance (1-copy TM); Nasty Plot |
| B3 | Infernape, Garchomp, Gyarados, Lucario, Chatot, Staraptor, with `--require-hm surf --require-hm waterfall` | required HMs together with status moves (FR-014); Chatot Sing and Roost |
| B4 | Roserade, Blissey, Gliscor, Milotic, Bronzong, Lucario | stall: Leech Seed, Toxic, Softboiled, Recover, Aqua Ring, Hypnosis, screens; Toxic/Roost 1-copy contention |
| B5 | Torterra, Magnezone, Clefable, Lumineon, Gallade, Spiritomb | Leech Seed, Thunder Wave (level-up), Sing, Moonlight, Rain Dance by level-up + Swift Swim, Hypnosis |

**Decision.**
1. Measure the baseline: a standard run of each benchmark team on `f88cdd0`, seed `bench-007`, recording each stage's time. Estimated total about 8-11 h of local compute.
2. Run the reference and then the prefilter on the same requests and seeds.
3. SC-002 is judged per team against the baseline. SC-006 compares prefilter time with baseline time.

All of this is local compute (Principle VI: encouraged). No paid compute is involved.

## R10. Reporting (FR-013, US3)

**Decision.**
- The per-member records go under `provenance.optimizer.candidate_tests`. No `EvaluationReport` schema change is needed, and `rerender` carries them over.
- A new xlsx sheet, "Candidates", amends `specs/001-*/contracts/spreadsheet.md` and the `SHEET_NAMES` test tuple.
- A warning goes into `rep.warnings` when the final team carries a move or item that the player doesn't model. The web shows warnings already.
- Provenance also gains `candidate_mode`, the item tie rule, the assumptions (friendship 255, IVs 15 giving Hidden Power Dark 70) and the alternatives seed namespace.
- `web/eta.py` `STAGE_ORDER` gains `alternatives`.
- The contract is `contracts/candidate-report.md`.

## R11. Not changed

The objective, the legality options, the 004/005/006 rules, the validator logic, the greedy-v1 screen for attack sets, and Showdown.
