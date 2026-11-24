# Feature Specification: H4, King's Rock / Razor Fang

**Feature Branch**: `031-h4-kings-rock`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "H4, King's Rock / Razor Fang: the fourth held-item group (after 025, 028, 029), built on feature 030's flinch work. Both items: HOLD_EFFECT_SOMETIMES_FLINCH (param 10), one pre-Champion copy each; Gligar's evolution uses the Razor Fang; identical items are ONE option with a copy count of 2. Game: 10% after a damaging hit of a flagged move (202 moves), rolled after every hit of a multi-hit move; blocked by a substitute, Inner Focus, Shield Dust, a target that has moved. No League trainer holds either item, so the battle player needs no change. Owner's goal: King's Rock chosen when it is the best option, especially with multi-hit moves. Three stories: (1) engine against game; (2) the optimizer offers the flinch item, appended, one option with 2 copies, plus item-conditioned extra sets for flagged multi-hit moves; (3) acceptance on both codes, plus a measurement that the item helps a multi-hit user. Out of scope: the player valuing its own flinch odds, Lum Berry, Metronome, Choice items, the damage formula, the AI port, the 026/027 rules, what qualifies." (full text in the conversation of 2026-11-24)

## Overview

King's Rock and Razor Fang are the same item twice: held by an attacker, each damaging hit of most moves has a 10% chance to make a
slower target lose its turn. On a multi-hit move the chance applies to every hit, so a five-hit Bullet Seed or Rock Blast flinches
about 41% of the time. One copy of each is available before the Champion. The optimizer does not offer them today. This feature
checks the battle engine against the game, offers the item where it can help, and measures that it does help a multi-hit user.
The battle player does not count its own flinch chances (feature 030 and the assessment `player-own-flinch-value`), but every
simulated battle applies the item's flinches, so a team holding it is measured with them.

| Source | Rule |
|---|---|
| Game (decomp) | after each damaging hit of a move marked as affected (202 moves, including moves that already flinch, whose own chance is separate), 10% to flinch a target that took damage, still has HP and has not moved this turn; not through a substitute, Inner Focus or Shield Dust; every hit of a multi-hit move rolls |
| Battle engine | a 10% flinch added to the same 202 moves, applied on each hit (to be checked case by case) |
| Copies | King's Rock 1 (Celestic Town), Razor Fang 1 (Route 214); a team with Gliscor has used its Razor Fang |
| League | no trainer holds either item |
| Affected multi-hit moves | Arm Thrust, Barrage, Bone Rush, Bonemerang, Bullet Seed, Comet Punch, Double Hit, Double Kick, Double Slap, Fury Attack, Fury Swipes, Icicle Spear, Pin Missile, Rock Blast, Spike Cannon (Triple Kick is not affected) |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The battle engine flinches as the game does (Priority: P1)

The simulated battles apply the item exactly as the cartridge does, so a team holding it is measured fairly.

**Why this priority**: the measurement is the only way the item's value reaches the optimizer; a wrong rule mis-measures every
team that holds it.

**Independent Test**: constructed battles comparing the engine with the game's rule for each condition.

**Acceptance Scenarios**:

1. **Given** a faster holder using an affected single-hit move, **When** it hits over many seeds, **Then** the slower target loses
   its move on about 10% of them.
2. **Given** a multi-hit affected move, **When** it hits several times, **Then** each hit has its own chance; once the target has
   flinched, further hits change nothing.
3. **Given** a move with its own flinch chance (Air Slash), **When** the holder uses it, **Then** the item's chance is added
   separately.
4. **Given** a target behind a substitute, with Inner Focus or Shield Dust, or that has already moved, **When** hit, **Then** the item
   never flinches it.
5. **Given** any difference between the engine and the game, **When** found, **Then** it is recorded in the divergence ledger with its
   effect on the League.

---

### User Story 2 - The optimizer offers the flinch item (Priority: P2)

The optimizer offers King's Rock / Razor Fang as one option with two copies, after each moveset's existing item candidates, for every
set with an affected move; and it builds extra sets for members that learn an affected multi-hit move, holding the item.

**Why this priority**: the owner's goal is the item chosen when it is best, especially with multi-hit moves; a multi-hit move that
never reaches a candidate set can never show the item's value.

**Independent Test**: the candidate lists of known members, before and after.

**Acceptance Scenarios**:

1. **Given** a set with at least one affected move, **When** its item candidates are built, **Then** the flinch item is offered, last,
   after the existing candidates (after the resist berries).
2. **Given** a set with no affected move, **When** built, **Then** the flinch item is not offered.
3. **Given** a team with two holders, **When** it is checked for legality, **Then** one holds King's Rock and the other Razor Fang; a
   third holder is refused; with Gliscor on the team only one holder fits.
4. **Given** a member that learns an affected multi-hit move, **When** its candidates are built, **Then** an extra set appears with that
   move swapped into its best set and the flinch item held, as feature 025 does for Razor Claw.
5. **Given** a member without such a move, **When** built, **Then** its candidate sets are unchanged apart from the appended item.

---

### User Story 3 - Accepted on both codes, and shown to help (Priority: P3)

The usual acceptance runs compare the branch with `main`, and a dedicated measurement shows the item helps a multi-hit user.

**Why this priority**: confirms nothing else changed, and gives the owner evidence that the item can be worth choosing.

**Independent Test**: the acceptance script's output; paired gauntlets of a multi-hit team with and without the item.

**Acceptance Scenarios**:

1. **Given** both codes, **When** the B2 quick search, identity evaluations and equal-level pairs run, **Then** they follow the 029
   rules; the report names which members took the flinch item.
2. **Given** the 36-member candidate snapshot, **When** compared, **Then** only the appended item and the new extra sets differ.
3. **Given** a team whose multi-hit member holds the flinch item, **When** played against the same team with that member's usual
   item, 2,000 paired gauntlets under Shift on fresh seeds, **Then** the clear rates and their difference are reported.

### Edge Cases

- A team with Gliscor (whose evolution used the Razor Fang): one copy left.
- A two-hit move that knocks the target out on the first hit: no further roll matters.
- The item on a slower holder: it can never flinch; offered anyway (the optimizer measures it), the player does not value it.
- A multi-hit member whose best multi-hit move is weaker than its set's moves: the extra set is still offered; the measurement decides.
- Trainers' Pokemon with Shield Dust or Inner Focus: none in the League (030's check covered Inner Focus).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The battle engine's handling of the flinch item MUST be checked against the game for: the 10% chance on single-hit
  affected moves, a roll after each hit of a multi-hit move, independence from a move's own flinch chance, and blocking by a
  substitute, Inner Focus, Shield Dust and a target that has moved; each difference MUST be ledgered with its League impact.
- **FR-002**: The optimizer MUST treat King's Rock and Razor Fang as one option with the combined number of copies (2, less any used by
  an evolution on the team); a team MUST NOT hold more flinch items than copies.
- **FR-003**: The flinch item MUST be appended after each moveset's existing item candidates for every set with at least one affected
  move, and MUST NOT be offered for a set with none.
- **FR-004**: For a member that learns an affected multi-hit move, the optimizer MUST offer an item-conditioned extra set: its best
  multi-hit move in its best set, held with the flinch item, following feature 025's pattern; the existing sets and their item lists
  MUST otherwise be unchanged.
- **FR-005**: The battle player MUST be unchanged (no League trainer holds the item; the player's own flinch odds stay unvalued).
- **FR-006**: Acceptance MUST follow the 029 protocol on both codes and report which members took the flinch item.
- **FR-007**: A measurement MUST compare a team whose multi-hit member holds the flinch item with the same team holding its usual
  item, 2,000 paired gauntlets under Shift on fresh seeds, reporting both clear rates.
- **FR-008**: The README MUST state the item rule, the copies, that the battles credit its flinches while the player does not steer
  toward them, and the measurement of FR-007.
- **FR-009**: Merge only if acceptance passes the 029 rules (no supported loss at equal levels, level difference at most 1.0, no
  attribution defect).

### Key Entities

- **Flinch item option**: King's Rock / Razor Fang as one candidate with a copy count; the concrete item is assigned per holder.
- **Multi-hit extra set**: a member's best set with its best affected multi-hit move swapped in, held with the flinch item.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The engine flinches at the game's rates in constructed battles (10% per hit within sampling error) and never through the
  four blockers; every difference found is ledgered.
- **SC-002**: Every set with an affected move offers the flinch item last; no set without one does; two holders get one of each item,
  a third is refused.
- **SC-003**: Every snapshot member that learns an affected multi-hit move gains exactly one multi-hit extra set; members without one
  change only by the appended item.
- **SC-004**: The B2 acceptance passes the 029 rules on both codes.
- **SC-005**: The multi-hit measurement reports both clear rates over 2,000 paired gauntlets with the paired test's verdict.
- **SC-006**: The Node and full Python suites pass; team build stays within 10 s.

## Assumptions

- Item copies, locations and hold effects are from the ledger and the decomp (King's Rock: Celestic Town; Razor Fang: Route 214).
- The game's rule is as read in the decomp: `CheckExtraFlinch` (`battle_controller_player.c:4630`), the per-hit `MULTI_HIT_EXTRA_FLINCH`
  step, and `subscript_flinch_mon.s` (moved this turn, substitute, Inner Focus, Shield Dust for the item flinch).
- The engine's Gen 4 list of affected moves equals the game's flag set (checked in feature 030; three spelling differences).
- The team used for the FR-007 measurement is chosen in the plan from members that learn an affected multi-hit move and are
  League-viable (for example a Rock Blast or Bullet Seed user).
