# Feature Specification: H4, Shell Bell

**Feature Branch**: `028-h4-shell-bell`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "H4, Shell Bell: the second held-item group after 025 (Wide Lens, Razor Claw), the first that needs the battle player to learn the item. Shell Bell (decomp HOLD_EFFECT_HP_RESTORE_ON_DMG, param 8; one pre-Champion copy, the Hearthome City southeast house gift) heals its holder after a move that hits: the damage the holder dealt that move divided by 8, at least 1, only while the holder is below its maximum HP and still standing, never for damage to itself. Pokemon Showdown heals move.totalDamage / 8 truncated, at least 1, skipped when the holder has a forced switch pending. No League trainer holds Shell Bell. Today the strong player expectimax2-v4 does not model it. Three stories: (1) the player models Shell Bell (engine-vs-game differences checked and recorded; replay test byte-identical without Shell Bell; a unit test on constructed states); (2) the optimizer offers Shell Bell by hold effect with its one copy, appended after each moveset's items, no item-conditioned extras; (3) acceptance: a reference-first player check (2,000 paired gauntlets with and without the model, not worse), then the 025 protocol on both codes. Out of scope: the other item groups, the trainer AI port, the damage formula, the 026/027 candidate rules, what qualifies." (full text in the conversation of 2026-11-20)

## Overview

Shell Bell restores HP to its holder each time the holder's move damages a foe: an eighth of the damage dealt, at least 1 HP,
while the holder is hurt and still standing. The game gives one copy before the Champion. The optimizer never offers it, and the
battle player that plays the simulated runs does not know it heals, so a holder's HP after its own attack is misjudged by the
heal. This feature teaches the player the heal, checks the battle engine against the game for when and how much it heals, then
offers the item as an appended choice like Wide Lens and Razor Claw. It is the first item group that changes the player, so the
player change is measured on its own first (reference-first, constitution Principle VI).

| Source | Heal | When |
|---|---|---|
| Game (decomp) | damage the holder dealt that move / 8, at least 1 | after a move that hit; holder below max HP and above 0; U-turn heals on a separate path before the switch; damage to a substitute counts |
| Battle engine (Showdown) | the move's total damage / 8, truncated, at least 1 | after the move; skipped when a forced switch is pending (U-turn) |
| Our player today | none | not modelled |

## Clarifications

### Session 2026-11-20

- Q: For the battle player's Shell Bell model to be accepted, is it enough that the player does not get worse on a team holding Shell Bell, or must it show a measurable improvement? → A: A, not worse: no supported loss at alpha 0.05 over 2,000 pairs; the gain is reported, whatever it is.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The battle player knows Shell Bell heals (Priority: P1)

When a member holds Shell Bell, the simulated player anticipates the heal after each of the member's damaging moves, as a
competent player would, so its choices (stay in, switch, which move) account for it.

**Why this priority**: an item the player misjudges cannot be measured fairly; offering it first would bias the result.

**Independent Test**: a unit test on constructed battle states; the existing replay test unchanged for teams without Shell Bell;
the engine-versus-game comparison recorded.

**Acceptance Scenarios**:

1. **Given** a holder at half HP whose move deals 80 damage, **When** the player computes the outcome, **Then** the holder heals 10.
2. **Given** a holder at full HP, **When** its move deals damage, **Then** it heals nothing.
3. **Given** a move dealing 7 damage, **When** the holder is hurt, **Then** it heals 1.
4. **Given** a holder knocked out by its own recoil that turn, **When** the outcome is computed, **Then** it heals nothing.
5. **Given** any team without Shell Bell, **When** the replay test runs, **Then** every decision is byte-identical to today's.
6. **Given** each difference between the battle engine and the game (U-turn timing, damage to a substitute, rounding), **When**
   checked against the decomp, **Then** it is confirmed equal or recorded as a divergence ledger entry with its impact.

---

### User Story 2 - The optimizer offers Shell Bell (Priority: P2)

A player's member can be recommended Shell Bell when it helps, within the single copy the game provides.

**Why this priority**: the point of the item group; it depends on story 1 for a fair measurement.

**Independent Test**: candidate item lists for the B2 species and the 36 benchmark members: Shell Bell appended after the existing
items on every moveset with an attack; every other list unchanged; a second Shell Bell on a team refused.

**Acceptance Scenarios**:

1. **Given** a moveset with an attack, **When** its item candidates are built, **Then** Shell Bell appears after the existing
   candidates, which keep their order.
2. **Given** a team where two members would hold Shell Bell, **When** the team is built, **Then** the second is refused (one copy).
3. **Given** any member, **When** its candidates are built, **Then** its base sets, extra sets and other item candidates equal today's.

---

### User Story 3 - Measured on both codes (Priority: P3)

The owner reads a player check (the player with the Shell Bell model against without, on a team holding it) and the 025
acceptance table on both codes.

**Why this priority**: the player change alters the measurement; the merge needs evidence that the player is not worse and that
the optimizer's winner is not worse.

**Independent Test**: the player check and the acceptance table complete; the merge rule passes or the merge is blocked with the
cause recorded.

**Acceptance Scenarios**:

1. **Given** a fixed team in which one member holds Shell Bell, **When** 2,000 paired gauntlets are played with and without the
   model, **Then** the player with the model is not worse (no supported loss at alpha 0.05) and the difference and its exact
   McNemar p are reported.
2. **Given** the 025 protocol, **When** both sides run, **Then** the table shows both winners, which member if any took Shell Bell,
   the extras screened, the equal-levels verdict, the identity rows and the attributed diff.

---

### Edge Cases

- **Holder at full HP**: no heal.
- **Holder fainted by recoil, Life Orb or the target's counter-effects before the heal**: no heal.
- **A multi-hit move**: the heal uses the total damage of the move (game and engine agree on the total; confirmed or recorded).
- **Damage absorbed by a substitute**: the game counts it; whether the engine does is checked and recorded.
- **U-turn**: the game heals before the switch; the engine skips the heal; recorded as a divergence with its impact if confirmed.
- **Opponent holding Shell Bell**: none in the League; the model applies symmetrically anyway.
- **Shell Bell and another single-copy item on the same member**: one held item per member, as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The battle player MUST, after its own model of a damaging move, heal a Shell Bell holder by max(1, floor(damage the
  target lost / 8)) when the holder is below its maximum HP and above 0, on either side.
- **FR-002**: The battle player's decisions for teams without Shell Bell MUST be byte-identical to today's (the replay test).
- **FR-003**: Each difference between the battle engine's Shell Bell and the game's (U-turn timing, substitute damage, rounding)
  MUST be checked against the decomp and either confirmed equal or recorded as a divergence ledger entry with its impact.
- **FR-004**: The screening player MUST be confirmed to need no change (it scores moves, not HP), with the check recorded.
- **FR-005**: The optimizer MUST offer Shell Bell by its hold effect with its pre-Champion copy count, appended after every
  moveset's existing item candidates for movesets with an attack; the single-use filter applies; copy limits hold.
- **FR-006**: Shell Bell MUST NOT create item-conditioned extra sets (its heal is proportional to damage, so it does not change how
  moves rank); base sets, extra sets and other item candidates MUST be unchanged.
- **FR-007**: The screen MUST screen Shell Bell on a moveset as an item deviation beyond the cap, as feature 025 does for its items.
- **FR-008**: A reference-first player check MUST run before the optimizer change: 2,000 paired gauntlets on a fixed team in which
  one member holds Shell Bell, played with and without the model, by the default player; a supported loss (alpha 0.05) blocks
  the feature; a gain is reported but not required (owner's decision 2026-11-20).
- **FR-009**: Acceptance MUST follow feature 025's protocol on both codes (the pre-feature side on the branch before the optimizer
  change; B2 quick with the 014 seed; the identity evaluations; the equal-levels paired check on 2,000 gauntlets; which member took
  Shell Bell; the attributed diff with base sets and extras unchanged), alone on the machine with Eastern times.
- **FR-010**: The merge rule is feature 024's: a supported loss at equal levels (alpha 0.05) or an expected average final level more
  than one level above today's blocks the merge.
- **FR-011**: The README MUST state that Shell Bell is offered and modelled, with the remaining item groups and why they wait;
  FUTURE-FEATURES section 0 MUST record the group as done.

### Key Entities

- **Shell Bell**: a held item whose hold effect restores HP from damage dealt; one pre-Champion copy.
- **Heal**: max(1, floor(damage dealt / 8)) to a hurt, standing holder after its damaging move.
- **Player check**: paired gauntlets of one fixed team with and without the player's Shell Bell model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The heal matches the four constructed cases exactly (10, 0, 1, 0).
- **SC-002**: Teams without Shell Bell get byte-identical player decisions (the replay test green).
- **SC-003**: With the model, the player clears the fixed Shell Bell team at least as often as without (no supported loss over
  2,000 paired gauntlets).
- **SC-004**: Every one of the 36 benchmark members' base sets, extra sets and existing item candidates is unchanged; Shell Bell is
  appended for every moveset with an attack where a copy exists.
- **SC-005**: The branch's B2 quick winner is not worse at equal levels and its expected average final level is at most one level
  above today's.
- **SC-006**: The Node suite and the full pytest suite pass on the final code.

## Assumptions

- The Hearthome City gift is the only pre-Champion copy (one copy), as the item ledger records today.
- The player check's fixed team is a benchmark team with Shell Bell given to its member that attacks most often, chosen in the plan.
- Shell Bell is likely offered and not chosen on B2 (one copy; Sitrus Berry and type boosters compete); that is a valid outcome.
- The identity evaluation teams hold no Shell Bell, so their results are identical on both codes once volatile fields are removed.
- Checkpoints from before this feature do not resume (the player's and the candidate code's hashes change).
- Evidence lives under `runs/028-evidence/` (local) with small copies under `specs/028-h4-shell-bell/evidence/`.
