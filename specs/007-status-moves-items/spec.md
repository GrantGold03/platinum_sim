# Feature Specification: Status Moves and Held Items in Team Optimization

**Feature Branch**: `007-status-moves-items`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "better status move selection. You will likely be able to ignore foe drop moves, as they are almost strictly worse than self boosts, as the attacker's attack being raised results in more damage than the defender's defense being lowered (double check that is how the math works in gen 4, as I might be thinking of later gen mechanics). Health recovery moves are also incredibly useful when at a level deficit. Stall strats involving toxic or leech seed are also effective at lower levels. Sleep and paralysis are useful to get turns for free. Weather setting can be instrumental in how a team works. Fixed damage moves can still be ignored, but everything else has a place on the right team in the right scenario. Additionally, held items will need a full rework to include other held items than the 3 used right now"

**Scope update (user, 2026-10-14, same session):** "ignore my previous message about expectimax and update the specs to reflect that". An earlier message had deferred changes to the expectimax2 battle player to a separate branch. That deferral is withdrawn: changing the player is in scope for this feature.

## Background

### How moves and items are chosen today (`main` at `f88cdd0`, read 2026-10-14)

- **Moves.** For each member, only **attacks** enter the search. Each attack is scored by a damage formula against the League: power × accuracy × STAB × base attacking stat × type effectiveness, with Cynthia's Pokémon weighted double. The best 4-move combinations by type coverage become the member's candidate movesets.
  - Excluded today:
    - every status move;
    - every move whose data power is 1. That covers fixed-damage moves such as Seismic Toss, and also variable-power attacks such as Return, Hidden Power, Low Kick and Gyro Ball.
- **The one exception.** Each member gets at most one "setup" moveset: its best 3 attacks plus its best self-boosting move.
  - It is tested late, in one slot at a time, and kept only if it is significantly better.
  - Belly Drum and evasion boosts are never offered.
- **Screening player.** Candidate teams are first screened with a simple battle player that scores every status move as worth nothing. A team carrying a status move therefore always looks worse while screening.
- **Held items.** Each moveset is offered at most three items:
  - the best HP-restoring berry (Sitrus Berry);
  - one type-boosting item for its strongest attack. This is always an Arceus Plate when one exists, because Plates have unlimited copies.
  - Leftovers, on a team that can obtain it.

### Gen 4 stat-stage maths (verified in the decomp, 2026-10-14)

- Stat stages use one multiplier table (`pokeplatinum/src/battle/battle_lib.c:6550`, `sStatStageBoosts`).
  - Raises: +1 = ×1.5, +2 = ×2, up to +6 = ×4.
  - Drops: −1 = ×2/3, −2 = ×1/2, down to −6 = ×1/4.
- The damage formula multiplies the attacker's stat by its stage and divides by the defender's stage-adjusted stat (`battle_lib.c:6948-6972`). +1 Attack on the user therefore raises damage by ×1.5, and −1 Defense on the foe raises it by 1 ÷ (2/3) = ×1.5: **the same amount**, apart from integer rounding.
  - On a critical hit, the user's positive stages and the foe's negative stages both still apply, so the two remain equal.
- The user's premise is therefore not right for the maths of a single hit. Their conclusion still holds for this game, for a different reason: **stages reset when a Pokémon faints or leaves the field**.
  - Stages reset when a Pokémon is sent in, unless Baton Pass is used (`battle_lib.c:97-100`), and again when it faints (`BattleSystem_CleanupFaintedMon`, `battle_lib.c:2156-2162`).
  - A drop on a foe is lost when that foe faints, and each League trainer brings a fresh Pokémon after every KO.
  - A boost on the user lasts through every KO it makes until it switches out or faints.
  - Drop moves can also miss, and abilities (Clear Body, Hyper Cutter, Keen Eye) and Mist block them (general game knowledge, not checked in the decomp).
- So excluding moves that lower the foe's stats is justified as *dominated in a League run*, not as mathematically weaker.

### Status moves the final forms can learn (engine, `main` at `f88cdd0`, 2026-10-14)

- This covers the 98 allowed final forms in `allowed_pokemon.md`, with legal moves at Lv 100 under default options. All 98 can learn at least one status move.

| Category | Examples (final forms that learn one) |
|---|---|
| Badly poison / poison / burn | Toxic (97), Will-O-Wisp (1), Poison Powder (2) |
| Sleep | Hypnosis / Sing / Sleep Powder / Grass Whistle (16), Yawn (7) |
| Paralysis | Thunder Wave / Stun Spore (8) |
| Recovery | Rest (97), Roost (15), Synthesis/Moonlight/Morning Sun (14), Recover/Softboiled/Heal Order (7), Wish (2), Aqua Ring (6), Ingrain (4) |
| Leech Seed | 3 |
| Self-boosts | Swords Dance (25), Agility/Rock Polish (23), Nasty Plot (7), Calm Mind (4), Dragon Dance (2), Belly Drum (1), Curse (6), … |
| Protection | Protect/Detect (97), Substitute (97), Endure (97) |
| Screens / Safeguard | Light Screen (28), Reflect (20), Safeguard (25) |
| Weather | Rain Dance (80), Sunny Day (75), Hail (23), Sandstorm (3) |
| Variable-power attacks (data power 1) | Return / Frustration (97), Hidden Power (98), Natural Gift (97), Low Kick / Grass Knot (35), Gyro Ball (7), Flail / Reversal (8), … |
| Lowering the foe's stats (excluded, see above) | Sand Attack / Flash / Smoke Screen (58), Leer / Tail Whip (35), Charm (10), Screech (16), … |
| Fixed damage (excluded by the user) | Seismic Toss / Night Shade (3), Sonic Boom (3), Dragon Rage (2), Super Fang (2), Endeavor (2), Psywave (1) |

### What the strong battle player understands today

- The final battles are played by Showdown, so every move has its real effect in battle. Our side's choices are made by the **expectimax2** player, whose own model is what makes it pick a move.
- **Modelled:**
  - stat raises, including Belly Drum;
  - drops on the foe;
  - sleep, paralysis, poison, badly poison and burn, with immunities;
  - Yawn and Rest;
  - half-HP heals;
  - Reflect and Light Screen;
  - Protect / Detect.
- **Not modelled, treated as having no effect:**
  - weather setting;
  - Leech Seed;
  - hazards;
  - Substitute;
  - Taunt, Encore and confusion;
  - Baton Pass.

  The player will rarely choose these moves, even when they are in the moveset.
- Held items in its model: Sitrus Berry, Leftovers, Focus Sash, Life Orb. Other items still work in battle; the player just doesn't plan around them.
- **Scope (user, 2026-10-14):** changing expectimax2 is **in scope** for this feature. Offering a move the player never chooses gains nothing, so the player must learn the effects of the moves and items this feature offers (FR-016).

### Held items (`held_items.md`, written 2026-10-14 from the engine)

- 191 holdable items: 124 available before the Champion, 1 team-gated (Leftovers), 37 only after the Champion, 29 never in Platinum.
- **Before the Champion and never offered today:**
  - Choice Specs, Wise Glasses and Shell Bell (1 copy each);
  - unlimited copies of Quick Claw, Wide Lens, Zoom Lens, Light Clay, Black Sludge, Damp/Heat/Smooth/Icy Rock and King's Rock / Razor Claw / Razor Fang;
  - Lum Berry, Chesto Berry and the other status berries;
  - 9 type-resist berries.
- **Ledger gaps.** Three in-game sources that may give items before the Champion are not modelled by the availability ledger: Route 221 house (Black Belt, Expert Belt, Focus Sash), the Pastoria City berry house and Amity Square. Whether they are truly pre-Champion is unverified. Modelling them is in scope (FR-018, user 2026-10-14).

## Clarifications

### Session 2026-10-14

- Q: Is the battle player (expectimax2) changed in this feature? → A: Yes, where needed so it can use the offered status moves and items. The user withdrew an earlier deferral to a separate branch.
- Q: Are moves that lower the foe's stats in scope? → A: No, excluded as dominated in a League run. The Gen 4 maths was checked; see Background.
- Q: Are fixed-damage moves in scope? → A: No (user).
- Q: How much longer may an optimization take? → A: First build a reference with no limit (option C). Then add a pre-filter and test it against that reference, so the final result is close to about 2× today (option B) (user). See FR-017.
- Q: Are the three missing item sources in scope? → A: Yes (user). See FR-018 and US5.
- Q: What friendship is assumed for Return? → A: Maximum friendship, 255 (user). By the decomp formula (`pokeplatinum/src/battle/trainer_ai/trainer_ai.c:3019-3024`), that gives Return power 255 × 10 / 25 = 102 and Frustration power 0, so Frustration is never offered. See FR-012.
- Q: How should accuracy and run time be balanced in general? → A: Spend more development time to get higher accuracy and shorter run times in the finished tool (user). The pattern from Q1 is the goal and is encouraged everywhere: first build the expensive, accurate version as a reference, then build cheaper versions and test them against it. See FR-019.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Status moves are offered and tested for every member (Priority: P1)

A player gives the optimizer six Pokémon. It now considers each member's useful status moves alongside its attacks:
- recovery;
- sleep, paralysis and poison (including Toxic stall sets);
- Leech Seed;
- self-boosts beyond the single setup slot;
- protection;
- screens;
- weather.

It tests movesets that contain them with a battle player able to use them. It keeps one in the final moveset only when doing so gives a better result under the optimizer's existing objective: clearing at or above the threshold with the lowest expected average final level. A Pokémon that would struggle at a level deficit can now come out with, for example, Recover or Toxic + Protect.

**Why this priority**: This is the core of the request. Today every status move except one boost per member is invisible to the optimizer.

**Independent Test**: Optimize a team that includes a member with a strong legal status option (for example a Toxic + recovery user). The run's records show that movesets with those moves were generated, evaluated by a player that uses status moves, and either adopted or rejected with the paired statistics.

**Acceptance Scenarios**:

1. **Given** a team where a member can legally learn Toxic and a recovery move, **When** the optimizer runs, **Then** at least one candidate moveset for that member contains them and is evaluated in battle.
2. **Given** a candidate moveset with status moves that is not significantly better than the best alternative on paired runs, **When** the optimizer chooses, **Then** that moveset is not adopted and the comparison is reported.
3. **Given** an offered status move whose effect the battle player did not model before this feature (for example weather or Leech Seed), **When** a battle reaches a position where that move is the best action under the player's model, **Then** the player chooses it.
4. **Given** an offered move or item the player still does not model after this feature, **When** the result is shown, **Then** it is flagged as not modelled by the player.
5. **Given** a member whose only legal status moves lower the foe's stats or deal fixed damage, **When** the optimizer runs, **Then** none of those moves are offered, and the run's records say why.

---

### User Story 2 - Every useful held item is considered (Priority: P1)

Each member's held-item candidates now cover every item that is obtainable under the active options, has an in-battle effect in a single trainer battle, and isn't an experience item. That includes items that only make sense with certain moves, such as:
- Light Clay with screens;
- a weather rock with the matching weather move;
- Chesto or Lum Berry with Rest;
- Black Sludge on a Poison-type;
- Choice Specs on a special attacker.

Team-wide copy limits are still respected.

**Why this priority**: The user asked for a full rework. Several status strategies depend on an item, so items and status moves have to be chosen together.

**Independent Test**: For a fixed moveset, list the member's held-item candidates. Every item in the agreed set that is obtainable under the active options and relevant to that moveset appears, and no post-Champion or unobtainable item appears unless an option allows it.

**Acceptance Scenarios**:

1. **Given** a member whose moveset contains Light Screen or Reflect, **When** item candidates are built, **Then** Light Clay is among them, provided a copy is available.
2. **Given** an item with one copy (for example Choice Specs) chosen for one member, **When** another member also wants it, **Then** only one member receives it, and the other falls back to its next candidate.
3. **Given** default legality options, **When** item candidates are built, **Then** no item that is only after the Champion or never in Platinum is offered.
4. **Given** a moveset whose strongest attack has both an Arceus Plate and a classic type-boost item available, **When** items are built, **Then** the choice between them is documented and deterministic.

---

### User Story 3 - The report explains what was offered, tested and chosen (Priority: P2)

For each member, the result says which status moves and held items were offered and which were tested. It gives the paired outcome (clear rates, run count, p-value) for each test, and what was finally chosen. It lists any offered moves and items that the battle player still does not model.

**Why this priority**: Without it, "never chosen" can't be told apart from "never offered" or "chosen but never used in battle". That evidence shows whether the new options and the player changes are working.

**Independent Test**: Run the optimizer on any team. The result lists, per member, the offered status moves and items with their test outcomes and the "not modelled by the player" flags. The numbers match the run's recorded battles.

**Acceptance Scenarios**:

1. **Given** a finished optimization, **When** the user opens the result, **Then** each member shows its offered status moves and items, whether each was tested, and the paired outcome of each test.
2. **Given** an offered move that the player does not model, **When** the result is shown, **Then** that move is flagged as not modelled by the player.

---

### User Story 4 - Variable-power attacks are considered (Priority: P3)

Attacks whose stored power is 1 because the game computes it during battle are scored by their actual power for the member and against each foe:
- Return (from friendship; maximum friendship assumed, FR-012);
- Hidden Power (from IVs);
- Low Kick and Grass Knot (from the foe's weight);
- Gyro Ball (from speed);
- Flail and Reversal (from HP).

They then compete with ordinary attacks. Fixed-damage moves stay excluded.

**Why this priority**: Return / Hidden Power are learnable by nearly every final form. They are attacks, not status moves, but they are excluded today by the same rule. Lower priority than US1/US2 because they are a refinement of the attack search.

**Independent Test**: For a member that learns Return, the candidate attack list includes Return with a non-zero score that reflects its actual power.

**Acceptance Scenarios**:

1. **Given** a member that can learn Low Kick, **When** candidates are built, **Then** Low Kick's value against each League foe reflects that foe's weight.
2. **Given** a member that can learn Seismic Toss, **When** candidates are built, **Then** Seismic Toss is not offered.

---

### User Story 5 - Missing item sources are recorded (Priority: P2)

Three in-game sources that the availability ledger doesn't model today are added: the Route 221 house, the Pastoria City berry house and Amity Square. Items they give before the Champion, possibly including Focus Sash and Expert Belt, become held-item candidates, and the validator accepts them.

**Why this priority**: The held-item rework (US2) can only offer what the ledger knows about, and these sources may add strong items before the Champion. P2 because US2 still works without them.

**Independent Test**: Look up Focus Sash, Expert Belt and one Pastoria berry in the item catalog under default options. Each shows the new source, its decomp script, and a verdict with a reason.

**Acceptance Scenarios**:

1. **Given** default options, **When** the ledger is built, **Then** the Route 221 house appears as a source of its items, with conditions taken from the decomp script.
2. **Given** a team holding an item that only these sources give, **When** it is validated, **Then** the validator agrees with the ledger's verdict.
3. **Given** a source condition the ledger can't decide (for example a random daily item), **When** copies are counted, **Then** the conservative reading is used and recorded.

---

### Edge Cases

- **Required HMs (006).** A required HM must still end up in a moveset.
  - When a slot has to give way, a status move adopted by testing is protected like today's adopted setup move: replaced only as a last resort.
  - A status move that was offered but not adopted has no protection.
- **No attacks.** A moveset made only of status moves (for example Toxic, Protect, Recover, Leech Seed) is allowed as a candidate. The battle engine's Struggle covers the case where PP runs out.
- **Item consumed or swapped.** Battle-time effects such as a berry being eaten or Trick are left to the battle engine. The optimizer only decides the starting item.
- **Weather on the foe's side.** Some League Pokémon set their own weather. The optimizer does not predict that; it is covered only by battle evaluation.
- **Hard-coded strategies.** No status move or item is ever forced. Each one is adopted only through the existing statistical comparison.
- **Copy conflicts.** A one-copy item, or a TM that teaches a status move, may be wanted by several members. The existing team-wide copy accounting and fallback apply unchanged.
- **Move with no effect in this format.** Moves that do nothing in a single trainer battle (Helping Hand, Follow Me, Teleport, Splash, and so on) are never offered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The optimizer MUST offer status moves as moveset candidates for each member. The categories in scope:
  - recovery (including Rest and Wish);
  - sleep, paralysis, poison, badly poison and burn infliction (including Yawn);
  - Leech Seed;
  - self-stat raises (including Belly Drum);
  - protection (Protect, Detect, Substitute, Endure);
  - Reflect, Light Screen and Safeguard;
  - weather setting;
  - any other status move with an effect in a single trainer battle, except those excluded by FR-002 and FR-003.
- **FR-002**: Moves whose only effect is to lower the foe's stats (including accuracy and evasion) MUST NOT be offered. The exclusion and its reason (Background: stages reset on faint or switch) MUST be recorded in the run's records.
- **FR-003**: Fixed-damage moves (Seismic Toss, Night Shade, Sonic Boom, Dragon Rage, Super Fang, Endeavor, Psywave), moves with no effect in a single trainer battle, and the attacks already excluded today as conditional (one-hit KO, Explosion, Fake Out, and so on) MUST NOT be offered.
- **FR-004**: Each offered move's category MUST be derived from the decomp's move data, by effect name. It MUST NOT come from a hand-typed list of move names (Constitution I).
- **FR-005**: A moveset MAY contain more than one status move, up to all four moves.
- **FR-006**: Moves and held items MUST be chosen together where an item depends on a move: Light Clay with screens, a weather rock with its weather move, Chesto or Lum Berry with Rest. A candidate pairs them as one choice.
- **FR-007**: Every candidate moveset or item that contains a status move, or an item the screening player can't value, MUST be judged by a battle player that can use status moves. It MUST NOT be eliminated by a player that scores status moves as worth nothing.
- **FR-008**: A status-move or new-item candidate MUST replace the attack-only alternative only when it is statistically better on paired runs with the same seeds, under the optimizer's stated objective (Constitution IV). Otherwise the comparison MUST be reported as indistinguishable or worse.
- **FR-009**: Held-item candidates MUST include every item that:
  - has an in-battle effect in a single trainer battle;
  - has at least one copy under the active legality options (including the team-gated rule);
  - is not an experience or EV item.

  Items whose effect is irrelevant to a moveset (for example a weather rock without its weather move) MAY be left out for that moveset.
- **FR-010**: Team-wide copy limits for items and TMs MUST be enforced as today. An optimizer output MUST still pass the independent validator (Constitution III).
- **FR-011**: The choice between items with the same effect (an Arceus Plate and a classic type-boost item) MUST be deterministic. The rule MUST be stated in the result.
- **FR-012**: Variable-power attacks (US4) MUST be scored by the power the game computes for that member and each foe.
  - Every member is assumed to have maximum friendship, 255 (user, 2026-10-14). Return is therefore scored at power 102, and Frustration (power 0 at maximum friendship) is never offered.
  - Battles MUST use the same friendship as scoring, and the result MUST state the assumption.
  - Any other input that isn't known before battle MUST be stated as an assumption in the result.
- **FR-013**: The result MUST list, per member: the offered status moves and items, which were tested, each test's paired outcome (runs, clear rates, p-value, verdict), and the final choice. Offered moves and items that the battle player does not model MUST be flagged.
- **FR-014**: Required HMs (006) MUST still be carried. When a slot must give way, an adopted status move MUST be replaced only after every non-adopted move. The order MUST be documented.
- **FR-015**: Results MUST stay reproducible: the same request, seed and pinned commits give the same result (Constitution IV).
- **FR-016**: The strong battle player MUST model the in-battle effect of every offered status-move category and every offered held item, well enough to choose them when they help (user, 2026-10-14). This covers the categories it treats as having no effect today, such as weather, Leech Seed and Substitute. A changed player MUST be a new named version. The previous version MUST stay available so earlier results can be reproduced, and every result MUST name the version used (Constitution II, IV). An offered move or item that the player still does not model MUST be flagged (FR-013).
- **FR-017**: The feature MUST be built in two steps (user, 2026-10-14).
  1. **Reference (no time limit).** First, every offered candidate is judged by the strong player, with no pre-filter and no run-time limit. Its results on the benchmark (SC-002) are recorded as the reference.
  2. **Pre-filter.** Then a pre-filter is added that cuts which candidates reach the strong player. On the same benchmark requests and seeds, it MUST be compared with the reference, and it MUST NOT be worse by a statistically supported margin, in clear rate at the reported levels or in expected average final level. The target is a standard-budget run of about 2× today's time or less.
  - The reference mode MUST remain available after the pre-filter is added, so the pre-filter can be re-checked against it.
- **FR-018**: The availability ledger MUST model the three item sources found missing (user, 2026-10-14): the Route 221 house (Black Belt, Expert Belt, Focus Sash), the Pastoria City berry house and Amity Square.
  - Each source's items, copies and conditions (story gates, once-per-day limits, a required partner Pokémon, randomness) MUST be extracted from the decomp (Constitution I).
  - Each source is placed before or after the Champion by the ledger's existing rules. A condition the ledger can't decide MUST be resolved the conservative way and recorded.
  - Each source needs a positive-control test that ties it to its decomp script.
  - The validator MUST accept the items these sources give exactly when the ledger does.
- **FR-019**: Every approximation this feature introduces MUST be built reference-first (user, 2026-10-14; Constitution VI):
  - first an expensive, accurate version as the reference;
  - then cheaper versions, each compared with the reference on the same benchmark requests and seeds.

  This covers the candidate pre-filter (FR-017), any player-model shortcut (FR-016), item relevance filtering (FR-009) and any cap on candidates per member. A cheaper version is adopted only if it is not worse than the reference by a statistically supported margin. The comparison and its run times MUST be recorded. The aim is higher accuracy and shorter run times in the finished tool; extra development time and compute spent on references is expected and encouraged.

### Key Entities

- **Status-move category**: a grouping of status moves by decomp effect (recovery, inflict status, Leech Seed, self-boost, protection, screen, weather, other). Each category records whether the battle player models it.
- **Move-item pairing**: a status move together with the held item that strengthens it, offered as one candidate choice.
- **Candidate test record**: for one member, one offered moveset or item compared with its alternative. It holds the runs, clear rates, p-value, verdict and whether it was adopted.
- **Held-item candidate set**: per member and moveset, the items offered after the availability and relevance filters, each with its copy count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each in-scope category (FR-001), at least one test team exists where a member's candidates include a moveset from that category, and the result shows it was evaluated in battle (positive control per category).
- **SC-002**: Across a fixed benchmark of at least 5 teams, chosen in planning, at standard budget, no team's result gets worse than before by a statistically supported margin. That means clear rate at the reported levels, or expected average final level.
- **SC-003**: 100% of offered status moves and items appear in the result with a tested or not-tested state, and with the not-modelled flag where it applies.
- **SC-004**: 100% of optimizer outputs pass the independent validator, including required-HM checks, on the benchmark and in the existing test suite.
- **SC-005**: Re-running any benchmark request with the same seed gives an identical result.
- **SC-006**: The reference mode (FR-017 step 1) runs the benchmark to completion with no limit, and its run time is recorded. With the pre-filter, a standard-budget run takes about 2× today's time or less on the benchmark. Its results are not worse than the reference by a statistically supported margin.
- **SC-009**: Under default options, each of the three added sources (FR-018) shows up in the item catalog with its decomp source. The before or after the Champion verdict is shown with its reason. A count check on the ledger changes only by the items those sources add.
- **SC-007**: No offered move falls under FR-002 or FR-003. Positive control: a member that legally learns Screech and Seismic Toss is offered neither.
- **SC-008**: For each status-move category and held-item effect the player newly models, a positive-control battle position exists where the player chooses that move or benefits from that item. A matching position where it does not help shows the player does not choose it there.

## Assumptions

- The battle engine (Showdown, Gen 4 Platinum rules) already applies the real effect of every status move and held item. Only the optimizer's candidate generation and the screening path change.
- The strong player, expectimax2, is the player that judges status-move candidates (FR-007). It is extended in this feature (FR-016) as a new version, rather than replaced by a new player.
- The screening player (greedy-v1) is not required to understand status moves. FR-007 keeps it from eliminating them instead.
- The optimizer's objective is unchanged: meet the clear-rate threshold with the lowest expected average final level, and a final level gap of 10 or less.
- IVs are whatever the project's builds already use; planning will state the values and their source. Friendship is the maximum, 255 (FR-012).
- Weather planning stays per member plus its own moveset and item. Choosing teammates to suit the weather is left to the existing team-level screen and search.
- Legality options, copy limits and the 004/005/006 rules are unchanged. The ledger gains the FR-018 sources only.
- "Today's time" means a standard-budget run on `main` at `f88cdd0`, measured on this machine on the benchmark teams.
