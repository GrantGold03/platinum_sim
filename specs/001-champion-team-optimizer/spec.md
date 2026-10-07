# Feature Specification: Champion Team Optimizer

**Feature Branch**: `001-champion-team-optimizer` (no git repository yet; directory name only)

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "optimize a 6-species team against the Elite Four and Champion, with an
emphasis on the Champion since she is the most difficult battle in the main game by far. The optimal
team will be one with the lowest average level after beating Cynthia, with a maximum gap of 10 levels
between the highest and lowest level members. Because we are optimizing for the champion, post-game
moves/pokemon/items are not allowed. TMs are single use. Item use aside from held items during
battles are not allowed. Pokemon has a huge amount of variance, so prefer a higher number of
simulations when in doubt. Internally consistent code doesn't mean anything unless it is consistent
with the decomp"

## Clarifications

### Session 2026-10-07

- Q: Are trade evolutions or Pokemon from other games allowed? → A: No. One cartridge only.
- Q: How strong is the player's in-battle policy? → A: Strong look-ahead player approximating a
  skilled human.
- Q: What clear rate counts as "beats Cynthia"? → A: User-set threshold, default 75% for the
  full gauntlet.
- Q: What IVs, EVs, and nature does each member have? → A: IVs 15 in every stat; EVs 85 in
  every stat (510 total, maxed); neutral nature.
- Q: What about gift Pokemon with stats fixed in the game code? → A: Use the game code's fixed
  values where they exist; the defaults fill anything the game code leaves unset.
- Q: When a species is available both from an NPC trade and from the wild, which copy is used?
  → A: The optimizer may choose either copy and MUST report which one it used.
- Q: How is the ability chosen for species with two abilities? → A: Test both and keep the better
  one; do not spend extra simulations when the difference is negligible or an ability only matters
  outside battle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find the lowest-level team that beats the League (Priority: P1)

A player enters six species. The tool searches over each member's starting level, moveset, ability, and
held item (IVs, EVs, and nature are fixed by FR-008), all restricted to what is obtainable
before beating the Champion.
It returns the build whose average team level after defeating Cynthia is lowest, while clearing the
Elite Four and Champion reliably and keeping the level gap within 10.

**Why this priority**: This is the product. Every other story supports or explains this result.

**Independent Test**: Give six species. The tool returns one fully specified team, its expected
final average level, its gauntlet clear rate with a confidence interval, and the provenance record.
Re-running with the same seed reproduces the same result.

**Acceptance Scenarios**:

1. **Given** six valid species, **When** the user runs the optimizer, **Then** the output contains
   a starting level, four moves, ability, nature, held item, IVs and EVs for each member, plus
   expected final average level, clear rate with confidence interval, simulation count, and the
   source versions used.
2. **Given** the returned team, **When** it is checked by the legality validator, **Then** every
   member passes and the final level gap (highest minus lowest) is at most 10.
3. **Given** two candidate teams where the lower-level one does not reach the required clear rate,
   **When** the optimizer ranks them, **Then** the lower-level team is rejected, not ranked first.
4. **Given** the same species, constraints, and seed, **When** the run is repeated, **Then** the
   output is identical.

---

### User Story 2 - Battle-test a user-specified team (Priority: P2)

A player who already has a team (levels, moves, items) asks the tool to evaluate it, without
optimizing. The tool checks legality and runs the full Elite Four plus Champion gauntlet many times.

**Why this priority**: The optimizer depends on this evaluator. It is also independently useful
for checking a real save-file team, and it is the easiest way to sanity-check the simulation.

**Independent Test**: Supply a fully specified team. The tool reports per-battle and full-gauntlet
clear rates with confidence intervals, expected final levels per member, and which Champion
Pokemon most often cause losses.

**Acceptance Scenarios**:

1. **Given** a legal fully specified team, **When** evaluated, **Then** the report shows the clear
   rate for each of the five battles and for the whole gauntlet, each with a confidence interval.
2. **Given** a team with an illegal element (e.g., a post-game move, a second copy of a one-time
   TM, a post-game held item), **When** evaluated, **Then** the tool refuses and names each
   violation and why it is illegal according to the game data.

---

### User Story 3 - Trace every rule and number back to the game (Priority: P3)

A player or developer asks why a move, item, or species is allowed or forbidden, or why an
opponent's team or behaviour looks the way it does. The tool answers with the game-source location
it relied on.

**Why this priority**: The user stated that internal consistency is worthless unless it matches the
game. This story makes that checkable.

**Independent Test**: Query any legality decision or opponent detail; the answer cites the game
source location and pinned version. Query a known Showdown-vs-game difference; it appears in the
divergence ledger with its resolution.

**Acceptance Scenarios**:

1. **Given** a TM, **When** queried, **Then** the tool reports how many copies are obtainable before
   the Champion, from where, and whether it is purchasable, with source references.
2. **Given** Cynthia's team, **When** displayed, **Then** species, levels, moves, held items, and AI
   behaviour match the game data, with source references.

---

### Edge Cases

- A species that is only obtainable post-game (e.g., needs the National Pokedex): rejected with the
  reason.
- A species whose final form requires trading to evolve: rejected (FR-005), naming the trade
  requirement.
- Six species that cannot clear the gauntlet at any level within the search bounds: report "no
  qualifying team found", the best clear rate reached, and at which levels, rather than a team that
  fails the threshold.
- Two members want the same one-time item or the same single-copy TM: only one may receive it.
- A member levels up during the gauntlet and would learn a move or evolve: it always keeps its
  current moves and declines evolution (fixed rule, not configurable), and new levels count toward
  final level.
- Level gain from Elite Four battles pushes the level gap above 10 by the end: the team is invalid.
- A battle ends in a draw or hits a turn limit: counted as a loss.
- A member's moveset relies on a move with no remaining PP late in the gauntlet: PP carries over
  between battles (see Assumptions), so this is simulated, not ignored.

## Requirements *(mandatory)*

### Functional Requirements

**Input and output**

- **FR-001**: The tool MUST accept exactly six species as input, plus optional settings: minimum
  clear rate (FR-015), simulation budget preset (FR-018), and random seed. IVs, EVs, and nature are
  not settable (FR-008).
- **FR-002**: The tool MUST output the optimized team in a standard team-export text format and as a
  machine-readable report containing the full provenance required by the constitution (simulation
  count, clear rates with confidence intervals, opponent policy, player policy, seeds, game-data
  version, simulator version).
- **FR-002a**: The tool MUST provide a simple local web page where the user searches species by
  name, adds six to a team, starts an optimization, sees its progress, and views the result.
- **FR-002b**: The result MUST be downloadable as a spreadsheet listing, per member: species, how
  it is obtained, start and expected final level, ability (and how it was chosen), held item and
  its source, nature, IVs, EVs, and four moves each with its source (level-up with level, TM/HM
  with where the copy comes from, tutor with location and cost, egg, or pre-evolution level-up).

**Legality (all derived from the game data, never hand-entered)**

- **FR-003**: The tool MUST exclude anything obtainable only after defeating the Champion for the
  first time: species, evolutions, moves, move tutors, TMs, held items, and areas. "Post-game" MUST
  be determined from the game's own story-progress gates, not from a hand-written list.
- **FR-004**: TMs MUST be treated as single-use. The number of copies of each TM available to the
  team MUST equal the number obtainable before the Champion according to the game data; TMs sold in
  shops (including for Game Corner coins) MUST be treated as purchasable in any quantity.
- **FR-005**: Species and evolutions requiring trades with another game or cartridge MUST be
  forbidden. Only what one Platinum cartridge can obtain alone, before the Champion, is allowed.
- **FR-006**: Held items MUST be limited to those obtainable pre-Champion, respecting the number of
  copies obtainable; single-copy items can be held by at most one member.
- **FR-007**: Each member's moves, ability, and evolution stage MUST be valid for its species and
  for its level at the moment it is used (e.g., level-up moves at or below the current level, or
  learned by a pre-evolution and carried forward, or via move relearner if pre-Champion).
- **FR-008**: Every member MUST have IVs of 15 in every stat, EVs of 85 in every stat (510 total,
  the game maximum), and a neutral nature. These are fixed, not optimized. Exception: a Pokemon
  received from an in-game NPC trade or gift MUST use whatever IVs, nature (from its fixed
  personality value), and other stats the game code fixes for it; values the game code does not
  fix fall back to the defaults above. Because EVs start at the 510 maximum, no EVs are gained
  during the gauntlet.
- **FR-008a**: In-game NPC trades are within one cartridge and are allowed (FR-005 forbids only
  trades with another game or cartridge). Their Pokemon MUST be treated as not originally the
  player's, so they receive the game's boosted experience during the gauntlet.
- **FR-008b**: When a species (or its pre-evolution) is obtainable both from an NPC trade and
  another pre-Champion source, the optimizer MUST treat the two as separate options, evaluate
  either, and report which source each member uses.
- **FR-008c**: For a species with two abilities, the optimizer MUST evaluate both and keep the one
  that gives the better result, except:
  - An ability the game's battle code never checks (effect outside battle only) MUST be treated as
    having no battle effect and MUST NOT be tested separately; the other ability is tested alone,
    and if neither affects battle, the first ability is used. "Outside battle only" MUST be
    determined from the game code, not a hand-written list.
  - If a short screening comparison (same opponents and seeds) shows no statistically supported
    difference, the abilities are treated as equal: the first ability is kept and no further
    simulations are spent separating them.
  - A Pokemon from an NPC trade has its ability fixed by its personality value in the game code
    (odd personality gives the second ability) and MUST NOT be changed.
  The report MUST state for each member which ability was used and whether it was chosen by test,
  by tie, or because the other had no battle effect.

**Battle rules**

- **FR-009**: The gauntlet MUST be the four Elite Four members in the in-game order followed by the
  Champion, with each opponent's team, levels, moves, held items, and AI taken from the game data.
- **FR-010**: Opponent decisions MUST follow the in-game trainer AI as defined in the game data for
  that trainer, including any in-battle item use the game data gives that trainer.
  Any part of this AI that cannot be reproduced MUST be recorded as a divergence with its expected
  impact.
- **FR-011**: The player MUST NOT use bag items during battles. Only held items have effect.
- **FR-012**: Between battles the team MUST be restored as the game allows using unlimited
  purchasable items outside battle (HP, status, fainted members); PP is NOT restored between
  battles except by resources the build explicitly accounts for.
- **FR-013**: The player's in-battle decisions MUST come from a named, fixed decision policy, and
  every result MUST state which policy was used. The policy MUST be a strong look-ahead player
  approximating a skilled human.
- **FR-014**: Experience and level-ups during the gauntlet MUST follow the game's formulas
  (trainer-battle bonus, participation split, held experience items, boosted experience for
  Pokemon from in-game trades) so that "level after beating
  Cynthia" is computed, not estimated. EVs stay at 85 per stat throughout (FR-008).

**Objective and evaluation**

- **FR-015**: A team qualifies only if its full-gauntlet clear rate meets the required threshold:
  a user-set minimum full-gauntlet clear rate, defaulting to 75%. Every result MUST state the
  threshold used.
- **FR-016**: Among qualifying teams, the optimal team MUST be the one with the lowest expected
  average level of the six members after the Champion is defeated, with the final level gap
  (highest minus lowest member) at most 10.
- **FR-017**: The Champion battle MUST receive the largest share of the simulation budget and be
  reported separately, since it dominates gauntlet failures.
- **FR-018**: Simulation counts MUST be chosen so that every reported rate meets a stated confidence
  interval width. When the tool is uncertain whether more simulations are needed, it MUST run more.
  It MUST NOT reduce simulation counts below the configured minimum to save time without the user
  explicitly asking.
- **FR-019**: Candidate comparisons MUST use identical opponents and random seeds, and a candidate
  MUST NOT be reported as better unless the difference is statistically supported.

**Fidelity to the game**

- **FR-020**: Every game fact the tool uses (species data, learnsets, TM/tutor/item availability,
  opponent teams and AI, experience and damage formulas) MUST come from the game's decompiled
  source at a pinned version, and MUST be testable against known values from that source.
- **FR-021**: Wherever the battle simulator's behaviour or data differs from the game, the game
  MUST win. Each difference MUST be listed in a divergence ledger as corrected or accepted with
  stated impact. Mid-battle level-ups (which change stats in the game) MUST be listed there if not
  reproduced.

### Key Entities

- **Species**: A Pokemon species with base stats, types, abilities, learnsets, evolution rules, and
  pre-Champion availability, all with game-source references.
- **Build**: One team member — species, source (wild/gift/NPC trade), level, moves, ability (and
  how it was chosen), held item; nature, IVs, and EVs fixed per FR-008.
- **Team Candidate**: Six builds plus the shared resources they consume (single-copy TMs and items).
- **Opponent Trainer**: An Elite Four member or the Champion — party, levels, moves, held items,
  in-battle items, AI behaviour, battle order.
- **Gauntlet Result**: Outcome of one simulated run — per-battle win/loss, final levels per member,
  seed.
- **Evaluation Report**: Aggregated results for a candidate — clear rates with confidence intervals,
  expected final average level, level gap, simulation count, policies, provenance.
- **Divergence Ledger Entry**: A known difference between the simulator and the game, with its
  source reference and resolution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any six pre-Champion-obtainable species, the tool returns either a qualifying team
  or an explicit "no qualifying team" result with the best clear rate found; never a team below the
  clear-rate threshold.
- **SC-002**: 100% of returned teams pass the independent legality check, including single-use TM
  counts, item copy counts, post-game exclusion, and the 10-level gap.
- **SC-003**: Every clear rate reported has a 95% confidence interval no wider than ±2 percentage
  points for the gauntlet and the Champion battle (configurable, never silently loosened).
- **SC-004**: Repeating a run with the same inputs and seed reproduces the identical team and
  numbers.
- **SC-005**: Every opponent detail (all five trainers' parties, levels, moves, held items) and a
  sampled set of at least 20 species' stats and learnsets match the game source exactly in tests.
- **SC-006**: For a known reference team, the tool's predicted final average level after Cynthia is
  within 1 level of a hand-computed value using the game's experience formula.

## Assumptions

- Game version is Platinum (USA) Rev 1, matching the vendored decomp's default build and the local
  ROM's hash.
- "Post-game" begins at the first Champion victory (the National Pokedex and post-game areas such as
  the Fight Area and Survival Area are excluded unless the game data shows earlier access).
- Starting levels are chosen by the optimizer. Players can train to any level before the League;
  rare candies are allowed outside battle, limited to pre-Champion availability.
- EV totals of 85 per stat are assumed reachable by training; how they were earned is not modeled.
- Money and time are unlimited for purchasable items.
- Level gap is measured on final levels after Cynthia. Members fainted at the end still count.
- PP carries over between League battles. Whether PP-restoring items can be bought before the
  Champion is unverified; if the game data shows they can, PP is restored like HP. Finite found PP
  items are out of scope for v1.
- During the gauntlet, level-up move prompts are always declined and evolution is always declined.
- A draw or turn-limit battle counts as a loss.
- The battle simulator's Platinum ruleset is the starting point for mechanics; the game's code wins
  wherever they disagree.
