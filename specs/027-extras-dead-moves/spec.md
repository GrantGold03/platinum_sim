# Feature Specification: Dead moves in the extra candidate sets

**Feature Branch**: `027-extras-dead-moves`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Dead moves in the extra candidate sets. Feature 026 removed dead moves from each member's three offered base sets, but its FR-007 gave the appended extra sets only the new pool and ranking rule: the 024 variable-power extras and the 025 item-conditioned extras. A read-only recount on main 63d6329 over the 36 benchmark members judged each extra set under its own valuation: variable-power 108 sets, 71 dead moves, 46 sets with one; Wide Lens 108, 67, 46; Razor Claw 108, 70, 48; 29 of 36 members affected. Two stories: (1) the 026 rule applied to the extras (dead-move replacement under each set's own valuation with the 026 cost tiers, fillers only when nothing live is left, the extras' own diversity with the one-apart rule, repaired duplicates dropped, a variable-power extra must keep a live variable move and an item-conditioned extra must differ from the base sets under its item, else not offered by default); (2) acceptance by the 026 protocol on both codes with the base sets required unchanged and a table of dead moves in the extras before and after. Out of scope: the base sets, dominance, item rules, the team allocation, the player, the damage model, what qualifies, new item groups, a defence-aware value." (full text in the conversation of 2026-11-18)

## Overview

Each member is offered three **base** sets (feature 026 made those free of dead moves, a dead move being one that is never the
best choice against any League opponent given the set's other moves) and up to six **extra** sets appended after them: three
built to carry a variable-power move (feature 024: Return, Grass Knot, Low Kick, Gyro Ball) and up to three per conditioning
item, ranked as if the member held Wide Lens or Razor Claw and paired with that item (feature 025). The extras were left out of
026's dead-move rule. A recount on main (evidence `evidence/pre/extras_dead_probe.txt`), judging each extra under its own
valuation:

| Extra kind | Sets | Dead moves | Sets with a dead move |
|---|---|---|---|
| variable-power | 108 | 71 | 46 |
| Wide Lens | 108 | 67 | 46 |
| Razor Claw | 108 | 70 | 48 |

29 of the 36 benchmark members carry at least one. On B2, two of Infernape's item sets carry Fire Punch dead, the move that
started feature 026, and Garchomp's Return set carries Return itself dead. The extras are screened beyond the 81-team cap, so
each dead move wastes a screened option and, if such a set wins, reaches the player. Fixing the rule before the next item groups
lets each inherit it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extra sets earn their slots too (Priority: P1)

A player whose optimized team ends up using an extra set (a Return set, a Wide Lens set) gets four moves that each answer
someone, or a named filler where the member learns nothing better, exactly as for the base sets.

**Why this priority**: the advice standard (constitution Principle VII) applies to every set the tool can recommend, and the
screen spends runs on every extra.

**Independent Test**: the extra sets of the six B2 species at level 48 and of the 36 benchmark members, before and after.

**Acceptance Scenarios**:

1. **Given** Infernape at level 48 on the B2 team, **When** its extra sets are built, **Then** no extra set contains Fire Punch
   and no extra set contains a dead move (under its own valuation) while a live replacement exists.
2. **Given** Garchomp's variable-power extra whose Return is dead, **When** its extras are built, **Then** that set is either made
   to carry a live variable move or not offered, and the candidate summary says which.
3. **Given** an extra that after repair equals a base set or an earlier extra, **When** the extras are built, **Then** it is not
   offered twice.
4. **Given** a member whose extra keeps a dead move because nothing live is left, **When** the summary is read, **Then** the move is
   listed with the 026 reason.
5. **Given** any member, **When** its candidates are built, **Then** its base sets, items and setup set are identical to main's.

---

### User Story 2 - Not worse on B2, measured on both codes (Priority: P2)

The owner runs the 026 acceptance protocol and reads one table: both winners, the screen's extras by kind, the equal-levels
verdict, the identity rows, the attributed diff (base sets unchanged), and the dead moves in the extras before and after.

**Why this priority**: the screen's extra options change, so the winner can change; the merge needs the measurement.

**Independent Test**: the acceptance table complete; no unexplained difference; base sets unchanged; the merge rule passes or
the merge is blocked with the cause recorded.

**Acceptance Scenarios**:

1. **Given** the branch before any code change, **When** the pre-feature side runs, **Then** the B2 quick result, the two identity
   evaluations and the 36-member snapshot (with dead moves per extra set) are stored.
2. **Given** the branch after the change, **When** the branch side runs, **Then** the table shows both winners, extras screened by
   kind, the equal-levels verdict on 2,000 paired gauntlets, the identity rows, the attributed diff, and the dead-moves table.
3. **Given** a supported loss at equal levels or an expected average final level more than one level above today's, **When** the
   gate is read, **Then** the merge is blocked and the cause recorded.

---

### Edge Cases

- **A variable-power extra whose variable move is dead** (Garchomp's Return beside Earthquake, Dragon Claw, Stone Edge): if
  another offered variable move can be made live in the set, it takes the slot; otherwise the set is not offered (default; the
  owner may choose at clarify to keep it as a named filler set).
- **An item-conditioned extra whose item changes nothing** (its repaired set ranks the same under the item as without it, or it
  equals a base set): not offered (default, same owner choice).
- **A repaired extra equal to a base set or an earlier extra**: dropped; the next ranked extra of that kind is considered.
- **Too few live moves for extras two apart**: the 026 one-apart rule applies among the extras of one kind.
- **A member with nothing live beyond its two strongest** (Rotom): extras that keep dead moves are listed with the 026 reason, as
  its base sets are.
- **Fewer extras than today**: allowed; the screen screens what is offered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every extra set MUST be judged under its own valuation: an item-conditioned extra with its conditioning item, a
  variable-power extra without an item.
- **FR-002**: Every extra set MUST have its dead moves replaced by the legal attack or offered variable move adding the most
  coverage under that valuation, with feature 026's cost tiers, while one exists; a dead move stays only when none exists, and is
  recorded with feature 026's reason.
- **FR-003**: Extras of one kind MUST stay pairwise two moves apart, accepting a one-apart set only where the two-apart set would
  carry a dead move (026 FR-004a).
- **FR-004**: An extra equal after repair to a base set or to an extra already offered MUST NOT be offered again.
- **FR-005**: A variable-power extra MUST carry at least one offered variable move that is live in it; an item-conditioned extra
  MUST rank differently from the base sets under its item's valuation; an extra failing its check is not offered (default,
  subject to clarify).
- **FR-006**: The candidate summary's dead moves, filler reason and one-apart record MUST cover the extras; extras dropped under
  FR-004 or FR-005 MUST be listed with the reason.
- **FR-007**: The base sets, their items, the setup set, the extras' items and kinds, the screen's rule for screening extras
  beyond the cap, the dominance rule, the item rules, the team allocation, the player, the damage model and what qualifies MUST be
  unchanged.
- **FR-008**: Acceptance MUST follow feature 026's protocol: the pre-feature side on the branch before any code change, then the
  branch side (B2 quick with the 014 seed, the identity comparison with volatile fields removed, the equal-levels paired check on
  2,000 gauntlets by the default player, the screen's extras by kind), alone on the machine with Eastern times.
- **FR-009**: The attributed diff MUST treat any difference in a base set, its items or the setup set as a defect, and MUST show
  per member the dead moves in the extras before and after.
- **FR-010**: The merge rule is feature 024's: a supported loss at equal levels (alpha 0.05) or an expected average final level
  more than one level above today's blocks the merge, with the cause recorded.
- **FR-011**: The README MUST state that the dead-move rule covers the extra sets; FUTURE-FEATURES MUST close the open item.

### Key Entities

- **Extra set**: an appended candidate set of one kind (variable-power, Wide Lens, Razor Claw) with its own valuation and item.
- **Defining move or item**: the variable move or conditioning item that makes a set an extra of its kind.
- **Dropped extra**: an extra not offered because it duplicates another set or fails its defining check; listed with the reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Over the 36 benchmark members, dead moves in offered extra sets fall from 208 to 0, except members listed with a
  reason.
- **SC-002**: No extra set offered to Infernape on B2 at level 48 contains Fire Punch.
- **SC-003**: Every base set, base-set item list and setup set of the 36 members is identical to main's.
- **SC-004**: The branch's B2 quick winner is not worse at equal levels (no supported loss at alpha 0.05) and its expected average
  final level is at most one level above today's.
- **SC-005**: The two unaffected teams evaluate identically on both codes once volatile fields are removed.
- **SC-006**: Candidate generation for the six B2 species, with the team allocation, stays within 10 seconds.
- **SC-007**: The Node suite and the full pytest suite pass on the final code.

## Assumptions

- "Dead" uses feature 026's definition (tie-aware), judged under each set's own valuation.
- The number of extras may fall; the screen screens what is offered beyond the cap, so its extras count and wall time may drop.
- The team allocation of feature 026 rebuilds lists as today; the extras of a rebuilt member follow this rule too.
- Checkpoints from before this feature do not resume (the candidate code's hash changes).
- Evidence lives under `runs/027-evidence/` (local) with small copies under `specs/027-extras-dead-moves/evidence/`.
