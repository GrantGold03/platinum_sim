# Feature Specification: Candidate sets by marginal coverage

**Feature Branch**: `026-marginal-coverage-sets`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Candidate sets by marginal coverage: no dead fourth move. Today the optimizer's candidate generation (optimizer/candidates.py) values each attack per League opponent, keeps the ten highest standalone scores as a member's pool, ranks four-move sets by coverage (the sum over opponents of the best move's value) and breaks coverage ties by the sum of the moves' standalone scores, then offers three sets that differ pairwise by at least two moves. Standalone score rewards redundant STAB moves, so a pool holds several moves of the member's own types and a set's third or fourth slot is often a dead move: a move that is never the best choice against any League opponent given the set's other moves. Evidence (B2 at level 48 on main after feature 025): Infernape's second set is Fire Blast / Flamethrower / Close Combat / Fire Punch, where Flamethrower and Fire Punch are both dead, and its third set carries dead Flame Wheel and Focus Blast; Floatzel's sets carry dead Surf, Brine and Water Pulse; Weavile's dead Avalanche, Faint Attack and Ice Beam; a competent player never clicks Fire Punch beside Flamethrower, and the slot should carry a move that is the best answer to someone, such as Grass Knot against Whiscash or Brick Break on Floatzel. A tie-break alone does not fix this (checked: every leftover pool move of Infernape contributes zero, so the tie-break only reshuffles the redundancy); the pool must be built by marginal contribution. Two stories. (1) Marginal coverage. Definitions: a move's marginal contribution to a set is the set's coverage minus the coverage of the set without it; a move is dead in a set when that is zero; a move is live for a member when it is the best against at least one opponent given the member's two strongest moves. The pool is built greedily over every legal attack plus the member's offered variable-power moves (024): the first move by standalone score, each next move the one adding the most coverage to the pool so far, ties by standalone score, the pool size unchanged (10). Sets are ranked by coverage, then by the sum of their moves' marginal contributions, then by the standalone sum as today; the diversity rule is unchanged. No offered set may contain a dead move while a legal attack or offered variable move with positive marginal contribution given the set's other three moves exists; where none exists (Rotom today: nothing it learns is ever best beyond Thunderbolt and Shadow Ball) the set is offered as today and the member is listed with that reason in the candidate summary and the hand check. Among moves with positive marginal contribution against the same opponents, a move without a cost effect (the EFFECT_COSTS class of feature 025: charge turn, recharge, recoil, self stat drop) is preferred to one with it, so Grass Knot takes the Whiscash slot on Infernape rather than Solar Beam, whose charge turn the move value does not price. The item-conditioned extra sets (025) and the variable-power extras (024) use the same pool and ranking rule under their valuations. The pruned map and the dominance rule are unchanged. Unit tests: the Infernape, Floatzel and Weavile cases above as controls (no dead move in any offered set; Fire Punch not offered on Infernape at level 48), Rotom as the no-live-move control with its reason, the Solar Beam versus Grass Knot preference, Garchomp and Staraptor unchanged, and a synthetic member whose greedy pool differs from its score pool. (2) Acceptance, the 025 protocol, alone on the machine with Eastern times, under today's defaults: the pre-feature side on the branch before any code change (B2 quick with --seed 014-b2, the two identity evaluations, the candidate snapshot for the six B2 species and B1 to B5 at their recorded levels), then the branch side: B2 quick, the identity comparison with the volatile fields removed, the equal-levels paired check on 2,000 gauntlets by expectimax2-v4 with the FR-009 rule of 024 (no supported loss at alpha 0.05, the branch winner's expected average final level at most one level above today's), the screen overlap and extras by kind, and the attributed diff per snapshot member through the 025 helper extended with the cause marginal_pool (a move entering or leaving a pool or set by the marginal rule) and a per-member table of dead moves before and after (expected zero after, except the listed no-live-move members). Expected direction: the winner equal or better; Infernape's fourth slot a live coverage move. Known limitation to record, not to fix here: on the B2 team Garchomp holds the game's only Earthquake and Stone Edge TMs, so Infernape's first set cannot be built and the repair step gives it its second set; team-level TM allocation is a separate feature. Deliverables: candidates.py (pool and ranking by marginal contribution, the dead-move rule, the cost preference, the candidate summary field), the unit tests, the acceptance script and attribution helper adapted from 025 under the feature's scripts/, the hand-check printout with dead moves per set, README (the candidate description: pool by marginal coverage, the dead-move rule and its Rotom exception), FUTURE-FEATURES (the TM allocation limitation; the cross-category user-conditioned dominance idea recorded as not chosen), validation log, evidence under runs/<feature>-evidence/ with small copies under the feature's evidence/. Merge gate: the Node suite and the full pytest suite. Out of scope: any change to the player's model, the damage model, the dominance rule, held items, what qualifies, team-level TM allocation, and a defence-aware move value (the opponent's Defense and Special Defense stay out of the candidate score)."

## Clarifications

### Session 2026-11-13

- Q: When the diversity rule (sets at least two moves apart) and the dead-move rule conflict because a member has too few live moves, which gives way? → A: B, the dead-move rule: diversity relaxes to one move between sets whose two-apart alternative would carry a dead move.

## Overview

The optimizer offers each member three four-move sets drawn from a pool of ten attacks. The pool is the ten highest standalone
scores, and a standalone score rewards the member's own-type moves, so the pool fills with redundant Fire or Water moves and a
set's third or fourth slot often carries a **dead move**: one that is never the best choice against any League opponent once
the set's other moves are there. On the B2 team after feature 025, Infernape is offered Fire Blast / Flamethrower / Close
Combat / Fire Punch, where Flamethrower and Fire Punch are both dead; a competent player (constitution Principle VII) never
clicks Fire Punch beside Flamethrower and would carry a move that answers someone instead, such as Grass Knot against Whiscash.

The fix is to build the pool and rank the sets by **marginal contribution**: each move must add coverage the set does not already
have. A tie-break alone was checked and does nothing here (every leftover pool move of Infernape adds zero), so the pool itself
must be built that way, over every legal attack and the offered variable-power moves. Where a member has nothing live beyond its
two strongest moves (Rotom), its sets are offered as today and the member is listed with that reason. Acceptance is the 025
protocol on both codes, with every list difference attributed and a per-member table of dead moves before and after.

Probe on main after 025 (B2 at level 48; dead moves in today's three sets, and what a greedy marginal pool changes):

| Member | Dead moves in today's sets | Greedy marginal pool |
|---|---|---|
| Garchomp | none | sets unchanged |
| Infernape | Flamethrower, Fire Punch; Flame Wheel, Focus Blast | a Whiscash answer enters (Solar Beam by value; Grass Knot preferred, no charge turn) |
| Staraptor | none | sets unchanged |
| Rotom | two per set (Thunder, Ominous Wind, Shock Wave, Dark Pulse, Charge Beam, Thunder Shock) | nothing live beyond Thunderbolt and Shadow Ball; unchanged, listed |
| Floatzel | Surf; Brine; Brine, Water Pulse | Brick Break enters |
| Weavile | Avalanche; Faint Attack, Ice Beam | Brick Break enters |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every offered slot earns its place (Priority: P1)

A player asks the tool for their six's movesets. Each offered set carries moves that are each the best answer to at least one
League opponent given the set's other moves, or, where the member learns nothing that is, the tool says so. Infernape is no
longer offered Fire Punch beside Flamethrower; its fourth slot is a coverage move such as Grass Knot.

**Why this priority**: the output is advice to a competent player; a dead move is advice the player would ignore and a screened
option wasted on a set no one would run.

**Independent Test**: the candidate lists of the six B2 species at level 48, before and after: no dead move in any offered set
except for members listed as having no live move; the named controls (Infernape, Floatzel, Weavile changed; Garchomp, Staraptor
unchanged; Rotom unchanged with its reason); the Solar Beam versus Grass Knot preference; a synthetic member whose marginal pool
differs from its score pool.

**Acceptance Scenarios**:

1. **Given** Infernape at level 48 on the B2 team, **When** its candidate sets are built, **Then** no offered set contains Fire
   Punch, no offered set contains a dead move while a live replacement exists, the slot that answers Whiscash carries Grass
   Knot, not Solar Beam, and the three sets are all live, differing by one move where two apart was impossible (FR-004a), with
   the summary saying so.
2. **Given** Floatzel and Weavile at level 48, **When** their sets are built, **Then** Brick Break (the best answer to opponents
   their own types do not cover) is in the pool and in an offered set, and no offered set carries a dead move while a live
   replacement exists.
3. **Given** Rotom at level 48, **When** its sets are built, **Then** its sets are today's and the candidate summary and the hand
   check list Rotom with the reason that nothing it learns is ever the best choice beyond its two strongest moves.
4. **Given** Garchomp and Staraptor at level 48, **When** their sets are built, **Then** the sets equal today's.
5. **Given** a synthetic member whose ten highest standalone scores are all one type while a weaker move of another type is the
   best answer to some opponent, **When** its pool is built, **Then** that move is in the pool and its score-only pool is not the
   result.
6. **Given** the item-conditioned extra sets of 025 and the variable-power extras of 024, **When** they are built, **Then** they
   follow the same pool and ranking rule under their own valuations.

---

### User Story 2 - Not worse on B2, measured on both codes (Priority: P2)

The owner runs the 025 acceptance protocol: the pre-feature side on the branch before any code change, then the branch side,
and reads one table: the two winners, the screen overlap and extras by kind, the equal-levels verdict, the identity rows, the
attributed diff with every change explained, and the dead moves per member before and after.

**Why this priority**: today's sets change for members that had dead moves, so the screen's baseline changes; the owner needs the
measurement that the new sets are not worse, and the list of what changed and why.

**Independent Test**: the acceptance script's table is complete; the attributed diff has no unexplained line; the identity rows
are identical once the volatile fields are removed; the equal-levels row passes the merge rule or the cause is recorded and the
merge blocked.

**Acceptance Scenarios**:

1. **Given** the branch before any code change, **When** the pre-feature side runs (B2 quick with the 014 seed, the two identity
   evaluations, the candidate snapshot of the six B2 species and every B1 to B5 member at its recorded level), **Then** the
   results are stored for the comparison.
2. **Given** the branch after the change, **When** the branch side runs, **Then** the table shows both winners, the screen
   overlap and extras by kind, the equal-levels verdict on 2,000 paired gauntlets, the identity rows, and per snapshot member the
   attributed diff (causes: dominated, crit_term, appended, marginal_pool; no defect) and the dead moves before and after.
3. **Given** the equal-levels row, **When** the branch winner loses to today's at equal levels with support at alpha 0.05, or its
   expected average final level is more than one level above today's, **Then** the merge is blocked and the cause recorded.
4. **Given** the two unaffected teams (the reference team and 014's b2-main team), **When** evaluated on both codes, **Then** the
   reports are identical once the volatile fields are removed.

---

### Edge Cases

- **Too few live moves for three distinct sets.** With five live moves (Infernape: Fire Blast, Close Combat, Earthquake, Stone
  Edge, Grass Knot), no three four-move sets can differ pairwise by two moves. The dead-move rule wins: the diversity threshold
  drops to one move between sets whose only two-apart alternative would carry a dead move (owner's decision, 2026-11-13), so
  Infernape is offered three all-live sets that differ in which of Earthquake, Stone Edge and Grass Knot they carry.
- **A member with no live move beyond its two strongest** (Rotom): the sets are today's; the member is listed with the reason.
- **A cost move and a cost-free move answering the same opponents** (Solar Beam and Grass Knot against Whiscash): the cost-free
  one is taken even if its value is lower; a cost move enters only for opponents no cost-free move answers.
- **A variable-power move in a base set**: Grass Knot may now be in today's sets, not only in the 024 extras; the extras rule
  still appends sets for the variable moves not chosen.
- **Ties on marginal contribution**: broken by standalone score, then by move name, so the lists are deterministic.
- **A move dead by value but more accurate** (Flamethrower beside Fire Blast): dead by this feature's definition; accuracy is
  already in the value, and the lens-conditioned sets of 025 cover the accuracy preference.
- **Members with fewer than four legal attacks**: unchanged (sets of the available size, no dead-move rule applies).
- **The setup set** (three attacks plus a setup move): built from the same pool; the dead-move rule applies to its attacks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The candidate generation MUST define, for a member at a level: a move's **marginal contribution** to a set as the
  set's coverage minus the coverage of the set without that move; a move **dead in a set** when its marginal contribution is
  zero; a move **live for the member** when it is the best choice against at least one League opponent given the member's two
  strongest moves by standalone score.
- **FR-002**: The pool MUST be built greedily over every legal attack plus the member's offered variable-power moves: the first
  move by standalone score, each next move the one adding the most coverage to the pool so far, ties by standalone score then by
  name; the pool size is unchanged (10).
- **FR-003**: Sets MUST be ranked by coverage, then by the sum of their moves' marginal contributions, then by the standalone
  sum, then by name; the three offered sets keep today's pairwise diversity rule (at least two moves apart) while an all-live
  set two apart exists, and otherwise accept a set one move apart rather than a set with a dead move (FR-004a).
- **FR-004**: No offered set MAY contain a dead move while a legal attack or offered variable move with positive marginal
  contribution given the set's other three moves exists; the replacement is the one with the highest marginal contribution
  (ties as FR-002), and the resulting set MUST still satisfy the diversity rule against the sets offered before it.
- **FR-004a**: When no set at least two moves apart from the sets already offered is free of dead moves while a set one move
  apart is, the one-apart set MUST be offered; a dead move is accepted only when no live replacement exists at either distance
  (FR-005). The candidate summary MUST state which offered sets were taken at one move apart.
- **FR-005**: Where a member has no live move beyond its two strongest, its sets MUST be offered as today and the member MUST be
  listed with that reason in the candidate summary and the hand check.
- **FR-006**: Among moves with positive marginal contribution against the same opponents, a move without a cost effect (the
  025 cost class: charge turn, recharge, recoil, self stat drop and the rest of that table) MUST be preferred to one with it; a
  cost move MAY enter only for opponents no cost-free move answers.
- **FR-007**: The item-conditioned extra sets (025) and the variable-power extras (024) MUST use the same pool and ranking rule
  under their own valuations.
- **FR-008**: The pruned map, the dominance rule, the held-item rules, the player's model, the damage model and what qualifies
  MUST be unchanged.
- **FR-009**: The candidate summary MUST state, per member, the dead moves in each offered set (expected none) and the
  no-live-move reason where it applies; the hand-check printout MUST show them.
- **FR-010**: Acceptance MUST follow the 025 protocol: the pre-feature side on the branch before any code change (B2 quick with
  `--seed 014-b2`, the two identity evaluations, the candidate snapshot of the six B2 species and every B1 to B5 member), then
  the branch side (B2 quick, the identity comparison with the volatile fields removed, the equal-levels paired check on 2,000
  gauntlets by expectimax2-v4, the screen overlap and extras by kind), alone on the machine with Eastern times.
- **FR-011**: The attributed diff MUST explain every difference between the pre-feature snapshot and the branch's lists with a
  cause among dominated, crit_term, appended and **marginal_pool** (a move entering or leaving a pool or set by the marginal
  rule), and MUST show a per-member table of dead moves before and after; an unexplained difference blocks the merge.
- **FR-012**: The merge rule is 024's FR-009: a supported loss at equal levels (alpha 0.05) or an expected average final level
  more than one level above today's blocks the merge, with the cause recorded.
- **FR-013**: The README's candidate description MUST state the pool by marginal coverage, the dead-move rule and its
  no-live-move exception; FUTURE-FEATURES MUST record the team-level TM allocation limitation (on the B2 team Garchomp holds the
  only Earthquake and Stone Edge TMs, so Infernape's first set cannot be built and the repair step gives it its second set) and
  the cross-category user-conditioned dominance idea as considered and not chosen.

### Key Entities

- **Marginal contribution**: a move's share of a set's coverage; zero means the set is as good without it.
- **Live move**: a move that is the best choice against at least one opponent given the member's two strongest moves.
- **Dead move**: a move with zero marginal contribution in its set.
- **Pool**: the ten moves the sets are drawn from, built greedily by marginal contribution.
- **No-live-move member**: a member whose legal attacks hold nothing live beyond its two strongest; listed with the reason.
- **Attributed diff cause `marginal_pool`**: a move entering or leaving a pool or set by the marginal rule.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the six B2 species at level 48, no offered set contains a dead move, except for members listed as having no
  live move; Infernape's sets contain no Fire Punch and one contains Grass Knot.
- **SC-002**: Garchomp's and Staraptor's offered sets are identical to today's; Rotom's are identical and Rotom is listed with
  its reason.
- **SC-003**: Over the 36 snapshot members (B2 at level 48 and B1 to B5), every list difference is attributed; 0 unexplained
  lines; the table of dead moves after the change shows 0 for every member not listed as no-live-move.
- **SC-004**: The branch's B2 quick winner is not worse than today's at equal levels (no supported loss at alpha 0.05) and its
  expected average final level is at most one level above today's.
- **SC-005**: The two unaffected teams evaluate identically on both codes once the volatile fields are removed.
- **SC-006**: Candidate generation for the six B2 species takes at most twice today's time (the greedy pool scans every legal
  attack ten times).
- **SC-007**: The Node suite and the full pytest suite pass on the final code.

## Assumptions

- "Dead" and "live" are judged on the candidate value (power, accuracy, STAB, the user's attacking stat, type effectiveness,
  the crit term) against the League's stored parties; the opponent's defences stay out of the value (out of scope), so a move
  can be dead here and still the better click in a real battle; the screen and the battles decide between offered sets.
- Variable-power moves become eligible for today's base sets (the user's Grass Knot example); 024's extras still append sets for
  variable moves not chosen.
- The pre-feature prefix guarantee of 024 does not hold (today's sets change where dead moves are replaced); every change is
  attributed instead, as in 025.
- The pool size and the number of offered sets (3) are unchanged; the diversity threshold (2 moves) relaxes to 1 only where
  the two-apart alternative would carry a dead move (FR-004a).
- Checkpoints from before this feature do not resume (the candidate code's hash changes), as for every candidate change.
- Evidence lives under `runs/026-evidence/` (local) with small copies under `specs/026-marginal-coverage-sets/evidence/`.
