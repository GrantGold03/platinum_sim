# Feature Specification: H4, resist berries

**Feature Branch**: `029-h4-resist-berries`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "H4, resist berries: the third held-item group (after 025 Wide Lens and Razor Claw, 028 Shell Bell): the 16 type-resist berries (decomp HOLD_EFFECT_WEAKEN_SE_<TYPE>) and Chilan (HOLD_EFFECT_WEAKEN_NORMAL); every one has unlimited pre-Champion copies. Game: after a hit's final damage is known, the battle script halves the HP loss (integer division by 2) when the defender holds the berry of the move's type and the hit is super-effective, or for Chilan when the move is Normal-type at any effectiveness, then removes the berry. Showdown applies a 0.5 damage modifier on such hits and consumes the berry, but skips a hit on a substitute. No League trainer holds one; the trainer AI already reacts. Three stories: (1) the player models resist berries (engine-vs-game checked; replay green; a reference-arm knob); (2) the optimizer appends the top N berries per member by the super-effective damage the League's moves would deal (N defaults to 2); (3) acceptance: a reference-first player check under Shift, then the 028 protocol on both codes. Out of scope: Lum Berry, King's Rock/Razor Fang, Metronome, Choice items, the damage formula, the trainer AI port, the 026/027 rules, what qualifies." (full text in the conversation of 2026-11-23)

## Overview

A resist berry halves the first super-effective hit of its type its holder takes, then is used up; Chilan Berry does the same
for any Normal-type hit. The game provides every one of the 17 berries before the Champion in unlimited supply, so each member of
a team could carry one, for example a Shuca Berry against Cynthia's Garchomp's Earthquake. The optimizer never offers them, and the
battle player does not know they halve damage, so it misjudges how hard its member will be hit. This feature teaches the player the
berries, checks the battle engine against the game, and offers each member the berries that block the most damage the League can
deal it. It follows Shell Bell's path (feature 028): the player change is measured on its own first.

| Source | When it triggers | Effect |
|---|---|---|
| Game (decomp) | after a hit's final damage, holder's berry matches the move's type and the hit is super-effective (Chilan: any Normal hit) | HP loss halved (integer division), berry removed |
| Battle engine (Showdown) | the same type and effectiveness test inside its damage modifiers; not when the hit lands on a substitute | 0.5 damage multiplier (its own rounding), berry eaten |
| Our player today | never | not modelled |
| League trainers | hold none | the trainer AI already reacts to a held resist berry (the game's AI script lists them) |

## Clarifications

### Session 2026-11-23

- Q: How many resist berries should the optimizer offer each member: only the single best one, the top two, or every berry that blocks a super-effective threat from the League? → A: B, the top two berries per member.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The battle player knows resist berries halve a hit (Priority: P1)

When a member holds a resist berry, the simulated player expects the first matching super-effective hit to be halved and the berry
then gone, as a competent player would, so its choices account for it.

**Why this priority**: an item the player misjudges cannot be measured fairly.

**Independent Test**: unit tests on constructed battle states; the replay test unchanged; the engine-versus-game comparison recorded.

**Acceptance Scenarios**:

1. **Given** a holder of the berry for the move's type and a super-effective hit, **When** the player computes the outcome, **Then**
   the damage is halved (rounded down) and the berry is consumed.
2. **Given** a neutral or resisted hit of that type, **When** the outcome is computed, **Then** the damage is not halved and the berry stays.
3. **Given** a second super-effective hit after the berry was consumed, **When** the outcome is computed, **Then** it is not halved.
4. **Given** a Chilan holder and a Normal-type hit at neutral effectiveness, **When** the outcome is computed, **Then** it is halved
   and the berry consumed.
5. **Given** any replay team (none holds a resist berry), **When** the replay test runs, **Then** every decision is byte-identical.
6. **Given** each difference between the battle engine and the game (rounding, a hit on a substitute, a multi-hit move, Chilan on an
   immune or resisted Normal hit, the Normalize ability), **When** checked against the decomp, **Then** it is confirmed equal or
   recorded as a divergence ledger entry with its impact.

---

### User Story 2 - The optimizer offers the right berries (Priority: P2)

Each member can be recommended the resist berries that block the most damage the League can deal it.

**Why this priority**: the point of the group; it depends on story 1 for a fair measurement.

**Independent Test**: candidate item lists for the B2 species and the 36 benchmark members: the top-ranked berries appended after the
existing items; members with no super-effective threat get none; every other list unchanged.

**Acceptance Scenarios**:

1. **Given** a member that League moves hit super-effectively, **When** its item candidates are built, **Then** up to two berries
   appear after the existing candidates, ordered by the damage they would block.
2. **Given** a member no League move hits super-effectively and no League Normal move threatens, **When** its candidates are built,
   **Then** no resist berry is offered.
4. **Given** a member with high Defense and low Special Defense facing an equally strong physical and special super-effective threat
   of two types, **When** its berries are ranked, **Then** the berry for the special threat ranks first (and the reverse for a
   specially bulky member).
3. **Given** any member, **When** its candidates are built, **Then** its base sets, extra sets and existing items equal today's.

---

### User Story 3 - Measured on both codes (Priority: P3)

The owner reads a player check (with and without the berry model on a team holding a berry) and the acceptance table on both codes.

**Why this priority**: the player change alters the measurement, and a berry may well be chosen.

**Independent Test**: the player check and the acceptance table complete; the merge rule passes or the merge is blocked with the cause.

**Acceptance Scenarios**:

1. **Given** the B2 team with a resist berry on the member facing the largest super-effective threat, **When** 2,000 paired gauntlets
   are played with and without the model under today's battle style, with a conditions control on a known team, **Then** the model
   is not worse (no supported loss at alpha 0.05) and the difference and its exact McNemar p are reported.
2. **Given** the acceptance protocol, **When** both sides run, **Then** the table shows both winners, which members took which berry,
   the extras screened, the equal-levels verdict, the identity rows and the attributed diff.

---

### Edge Cases

- **Two super-effective hits in one turn or a multi-hit move**: only the first hit is halved; the berry is gone after it.
- **A hit that would knock the holder out even halved**: halved, the holder faints, the berry is consumed.
- **Focus Sash**: one held item per member, so a berry holder has no Sash; on the opponent side neither applies (they hold none).
- **A hit on a substitute**: the engine does not consume the berry; the game's behaviour is checked and any difference recorded.
- **Normalize** (all moves Normal-type): Chilan's trigger in the game follows the move's resulting type; checked and recorded.
- **Doubly super-effective hits (4x)**: halved once, like any super-effective hit.
- **A member threatened in many types**: only the top two berries by blocked damage are offered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The battle player MUST, in its model of a damaging hit, halve the damage (rounding down) and consume the defender's
  berry when the defender holds the resist berry of the move's type and the hit is super-effective, or holds Chilan Berry and the
  move is Normal-type; on both sides.
- **FR-002**: A consumed berry MUST stay consumed in the player's model for the rest of that battle.
- **FR-003**: The battle player's decisions MUST be byte-identical to today's for the replay test's teams and the identity evaluation
  teams (none holds a resist berry); in general the halving applies only when the defender holds the berry.
- **FR-004**: Each difference between the battle engine's resist berries and the game's MUST be checked against the decomp and either
  confirmed equal or recorded as a divergence ledger entry with its impact.
- **FR-005**: The screening player MUST be confirmed to need no change (it scores its own moves), with the check recorded.
- **FR-006**: The optimizer MUST rank, per member, the resist berries by the expected damage they would block over the League's
  parties (each League move hitting the member super-effectively, or Normal moves for Chilan, weighted like the candidate move values:
  Elite Four 1, Cynthia 2). The damage estimate MUST account for the member's own defences: a physical move is weighed against the
  member's Defense and a special move against its Special Defense, so a member with high Defense and low Special Defense ranks a
  special threat above an equally strong physical one (owner's emphasis, 2026-11-23). The top two berries (owner's decision
  2026-11-23; fewer when fewer berries block a threat) are appended after the existing item candidates of every moveset with an attack
  (the append rule of feature 025); berries pass the
  single-use filter as feature 013 decided; copy limits hold.
- **FR-007**: Resist berries MUST NOT create item-conditioned extra sets; base sets, extra sets and existing item candidates MUST be
  unchanged.
- **FR-008**: A reference-first player check MUST run before the optimizer change: 2,000 paired gauntlets under today's battle style,
  with and without the model, on the B2 team with a berry on the member facing the largest threat, plus a conditions control on a known
  team; a supported loss (alpha 0.05) blocks the feature; a gain is reported, not required.
- **FR-009**: Acceptance MUST follow feature 028's protocol on both codes (pre-feature side before the optimizer change, B2 quick, the
  identity evaluations, the equal-levels paired check on 2,000 gauntlets, which members took which berry, the attributed diff with base
  sets, extras and existing items unchanged), alone on the machine with Eastern times.
- **FR-010**: The merge rule is feature 024's: a supported loss at equal levels or an expected average final level more than one level
  above today's blocks the merge.
- **FR-011**: The README MUST state the berries offered and modelled and, per constitution Principle VII, what the player change does to
  the measurement; FUTURE-FEATURES section 0 MUST record the group as done.

- **FR-012**: The player models the berry where a hit lands; its other judgements that read raw damage (which member to switch in,
  how threatening a foe is) do not see the berry. This partial model MUST be stated in the README block.

### Key Entities

- **Resist berry**: a held berry whose hold effect halves the first super-effective hit of one type (Chilan: any Normal hit), then is consumed.
- **Threat ranking**: per member, the damage each berry would block over the League's parties, weighted by battle, each threat
  weighed against the member's Defense (physical) or Special Defense (special).
- **Player check**: paired gauntlets of one fixed team with and without the player's berry model, under today's battle style.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The four constructed cases match exactly (halved and consumed; not halved and kept; second hit not halved; Chilan halved).
- **SC-002**: The replay test's teams and the identity evaluation teams get byte-identical decisions and results.
- **SC-003**: With the model, the player clears the berry-holding team at least as often as without (no supported loss over 2,000 pairs).
- **SC-004**: Over the 36 benchmark members, base sets, extra sets and existing item candidates are unchanged; every member with a
  super-effective League threat is offered at least one berry.
- **SC-005**: The branch's B2 quick winner is not worse at equal levels and its expected average final level is at most one level above today's.
- **SC-006**: The Node suite and the full pytest suite pass on the final code.

## Assumptions

- All 17 berries have unlimited pre-Champion copies, as the item ledger records today.
- The League's movesets are the stored parties (data the candidate scoring already uses); the threat ranking uses them as known moves.
- A berry may be chosen on B2 (unlimited copies), unlike Shell Bell; either outcome is valid.
- Lum Berry is a separate, later feature (a status trigger).
- Checkpoints from before this feature do not resume (the player's and the candidate code's hashes change).
- Evidence lives under `runs/029-evidence/` (local) with small copies under `specs/029-h4-resist-berries/evidence/`.
