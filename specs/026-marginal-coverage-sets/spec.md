# Feature Specification: Candidate sets by marginal coverage

**Feature Branch**: `026-marginal-coverage-sets`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Candidate sets by marginal coverage: no dead fourth move. Today the optimizer's candidate generation (optimizer/candidates.py) values each attack per League opponent, keeps the ten highest standalone scores as a member's pool, ranks four-move sets by coverage (the sum over opponents of the best move's value) and breaks coverage ties by the sum of the moves' standalone scores, then offers three sets that differ pairwise by at least two moves. Standalone score rewards redundant STAB moves, so a pool holds several moves of the member's own types and a set's third or fourth slot is often a dead move: a move that is never the best choice against any League opponent given the set's other moves. Evidence (B2 at level 48 on main after feature 025): Infernape's second set is Fire Blast / Flamethrower / Close Combat / Fire Punch, where Flamethrower and Fire Punch are both dead, and its third set carries dead Flame Wheel and Focus Blast; Floatzel's sets carry dead Surf, Brine and Water Pulse; Weavile's dead Avalanche, Faint Attack and Ice Beam; a competent player never clicks Fire Punch beside Flamethrower, and the slot should carry a move that is the best answer to someone, such as Grass Knot against Whiscash or Brick Break on Floatzel. A tie-break alone does not fix this (checked: every leftover pool move of Infernape contributes zero, so the tie-break only reshuffles the redundancy); the pool must be built by marginal contribution. Two stories. (1) Marginal coverage. Definitions: a move's marginal contribution to a set is the set's coverage minus the coverage of the set without it; a move is dead in a set when that is zero; a move is live for a member when it is the best against at least one opponent given the member's two strongest moves. The pool is built greedily over every legal attack plus the member's offered variable-power moves (024): the first move by standalone score, each next move the one adding the most coverage to the pool so far, ties by standalone score, the pool size unchanged (10). Sets are ranked by coverage, then by the sum of their moves' marginal contributions, then by the standalone sum as today; the diversity rule is unchanged. No offered set may contain a dead move while a legal attack or offered variable move with positive marginal contribution given the set's other three moves exists; where none exists (Rotom today: nothing it learns is ever best beyond Thunderbolt and Shadow Ball) the set is offered as today and the member is listed with that reason in the candidate summary and the hand check. Among moves with positive marginal contribution against the same opponents, a move without a cost effect (the EFFECT_COSTS class of feature 025: charge turn, recharge, recoil, self stat drop) is preferred to one with it, so Grass Knot takes the Whiscash slot on Infernape rather than Solar Beam, whose charge turn the move value does not price. The item-conditioned extra sets (025) and the variable-power extras (024) use the same pool and ranking rule under their valuations. The pruned map and the dominance rule are unchanged. Unit tests: the Infernape, Floatzel and Weavile cases above as controls (no dead move in any offered set; Fire Punch not offered on Infernape at level 48), Rotom as the no-live-move control with its reason, the Solar Beam versus Grass Knot preference, Garchomp and Staraptor unchanged, and a synthetic member whose greedy pool differs from its score pool. (2) Acceptance, the 025 protocol, alone on the machine with Eastern times, under today's defaults: the pre-feature side on the branch before any code change (B2 quick with --seed 014-b2, the two identity evaluations, the candidate snapshot for the six B2 species and B1 to B5 at their recorded levels), then the branch side: B2 quick, the identity comparison with the volatile fields removed, the equal-levels paired check on 2,000 gauntlets by expectimax2-v4 with the FR-009 rule of 024 (no supported loss at alpha 0.05, the branch winner's expected average final level at most one level above today's), the screen overlap and extras by kind, and the attributed diff per snapshot member through the 025 helper extended with the cause marginal_pool (a move entering or leaving a pool or set by the marginal rule) and a per-member table of dead moves before and after (expected zero after, except the listed no-live-move members). Expected direction: the winner equal or better; Infernape's fourth slot a live coverage move. Known limitation to record, not to fix here: on the B2 team Garchomp holds the game's only Earthquake and Stone Edge TMs, so Infernape's first set cannot be built and the repair step gives it its second set; team-level TM allocation is a separate feature. Deliverables: candidates.py (pool and ranking by marginal contribution, the dead-move rule, the cost preference, the candidate summary field), the unit tests, the acceptance script and attribution helper adapted from 025 under the feature's scripts/, the hand-check printout with dead moves per set, README (the candidate description: pool by marginal coverage, the dead-move rule and its Rotom exception), FUTURE-FEATURES (the TM allocation limitation; the cross-category user-conditioned dominance idea recorded as not chosen), validation log, evidence under runs/<feature>-evidence/ with small copies under the feature's evidence/. Merge gate: the Node suite and the full pytest suite. Out of scope: any change to the player's model, the damage model, the dominance rule, held items, what qualifies, team-level TM allocation, and a defence-aware move value (the opponent's Defense and Special Defense stay out of the candidate score)."

## Amendments at implementation (2026-11-13, recorded in validation-log.md; owner's review at the report)

- FR-003: the marginal-sum tie-break is dropped (it rewarded the weakest filler); sets rank by coverage, the standalone
  sum, name.
- FR-004, FR-004a: a set is never dropped for a lower-coverage all-live set; dead moves are replaced where a live legal move
  exists, a filler stays only when none is, and the one-apart all-live set replaces a two-apart set only when that set
  carries a dead move and the all-live set is at least as good as its live part (option B as chosen).
- FR-006: the cost class splits into turn costs (charge turn, recharge, lock-in, delayed hit, first-turn-only, sleep-only,
  fails-when-hit, the user faints: allowed only for an opponent no cost-free move hits) and damage costs (recoil, self stat
  drops, crash damage: compared with cost-free candidates only), so Close Combat stays offerable and Fly never displaces
  Aerial Ace; dominance keeps the single class.
- SC-002: Staraptor's sets change (Return, its same-type 102-power move, enters the pool once variable moves are eligible;
  Fly and Giga Impact stay out); Garchomp's and Rotom's are unchanged as stated.
- SC-006: candidate generation for the six B2 species is 1.2 s without the allocation and 4.8 s with it (0.9 s before), over
  "twice today's"; proposed bound: at most 10 s for six members (a few seconds of a seven-minute quick optimize).
- Edge case "too few live moves": the spec's premise that Infernape has five live moves was wrong; "live" is set-relative,
  and Infernape gets three all-live sets two apart.

## Clarifications

### Session 2026-11-13

- Q: When the diversity rule (sets at least two moves apart) and the dead-move rule conflict because a member has too few live moves, which gives way? → A: B, the dead-move rule: diversity relaxes to one move between sets whose two-apart alternative would carry a dead move.
- Q: When none of a member's offered sets can be built on the team because other members hold the single-copy TMs those sets need, should the repair fallback obey the dead-move rule, or should the sets be built with the team's copies in mind from the start? → A: C, resource-aware candidate generation: each member's offered sets are built knowing the team's copies, so a contested single-copy TM goes where it adds the most coverage and the other members' sets are built without it (a third story; team-level TM allocation moves into scope).
- Q: Should the player-facing report tell the user when an offered set's third or fourth move is filler (never the best choice against any League opponent because the member learns nothing better)? → A: A, yes: one line per affected member in the team text and the summary, naming the filler moves and why, so the user knows which slots are free for a move of their own.

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

A second cause of the same symptom is the team's TM copies: on the B2 team Garchomp holds the game's only Earthquake and Stone
Edge TMs, every all-live Infernape set needs one of them, and today's repair step silently falls back to the first buildable set
in the ranked list, dead moves and all. The owner chose to build each member's offered sets knowing the team's copies (a third
story): a contested single-copy resource goes to the member whose coverage gains the most from it and the others are built
without it, so the sets the screen sees are the sets a player can actually teach.

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
   check list Rotom with the reason that nothing it learns is ever the best choice beyond its two strongest moves; **and** when
   Rotom is in the final team, the team text and the summary carry one line naming its filler moves and that reason.
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

### User Story 3 - Offered sets the team can actually build (Priority: P3)

The player's six compete for single-copy TMs and items. Each member's offered sets are built knowing what the other members
take, so a contested resource goes where it adds the most coverage and the others' sets are built without it; no offered set is
silently swapped for a worse one at the repair step because a TM was already spent.

**Why this priority**: on the B2 team this, not the pool, is what put Fire Punch on Infernape; without it the fix is invisible
there. It is a separate layer (team resources) and can ship after stories 1 and 2 or as its own feature if the plan finds it
large.

**Independent Test**: the B2 team at the screen's levels: every offered set of every member is buildable together with the
other members' first sets; the candidate summary names each contested resource and who received it with the coverage gained;
Infernape's offered sets contain a live coverage move that it can learn on this team.

**Acceptance Scenarios**:

1. **Given** the B2 team where Garchomp and Infernape both want the single Earthquake and Stone Edge TMs, **When** the sets are
   built, **Then** each TM goes to the member whose coverage gains the most from it, the other member's sets are built from its
   remaining live moves, and the summary names the allocation.
2. **Given** a team with no contested resource, **When** the sets are built, **Then** they equal the sets built member by member.
3. **Given** a member whose remaining live moves after the allocation are fewer than four, **When** its sets are built, **Then**
   the dead-move and diversity rules apply as in story 1 (one-apart sets, then dead moves only where nothing live is left) and
   the summary says so.
4. **Given** any team, **When** the screen's baseline and every screened option are built, **Then** the repair step has nothing to
   replace (zero repair notes for the candidate sets), and the independent validator still checks every team.

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
- **A contested single-copy resource** (a TM, an evolution item, a held item with one copy): it goes to the member whose coverage
  gains the most from it, ties by slot order; the others are built without it and the summary says who got it and why.
- **HM requirements** (feature 006) never contest a resource: the game never consumes an HM, so an HM has unlimited copies;
  the allocation concerns TMs, evolution items and single-copy held items only.
- **The repair step** stays as the safety net for anything the allocation missed (levels, evolution paths), and its notes are
  expected empty for the offered sets.
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
  sum, then by name, the marginal-sum tie-break applying among all-live sets; sets accepted with dead moves (FR-005) keep
  today's key (coverage, then the standalone sum), so a no-live-move member's sets are unchanged. The three offered sets keep
  today's pairwise diversity rule (two moves apart) except as FR-004a states.
- **FR-004**: No offered set MAY contain a dead move while a legal attack or offered variable move with positive marginal
  contribution given the set's other three moves exists; the replacement is the one with the highest marginal contribution
  (ties as FR-002); diversity against the sets offered before it follows FR-004a.
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
- **FR-009a**: The player-facing report (the team text and the summary) MUST carry one line per member whose chosen set holds a
  filler move, naming the moves and the reason ("no better option: the member's two strongest moves cover every League
  opponent"), so the user knows those slots are free for a move of their own; members without filler get no line.
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
  no-live-move exception, and the team-aware allocation of contested resources; FUTURE-FEATURES MUST record the cross-category
  user-conditioned dominance idea as considered and not chosen.
- **FR-014**: Each member's offered sets MUST be built knowing the team's copies of single-copy resources (TMs, evolution items,
  held items): a resource wanted by more members than it has copies goes to the members whose coverage gains the most from it
  (ties by slot order), the others' pools and sets are built without it (HMs are never consumed and never contested), and the
  candidate summary MUST name each contested resource, who received it and the coverage each contender would have gained.
- **FR-015**: Every offered set of every member (today's sets, the extras, the setup set) MUST be buildable together with the
  other members' first sets at the reference level the candidates are built at: after the first-set contention is resolved, a
  move whose resource the other members' first sets fully consume is unavailable to that member and its lists are rebuilt
  without it. The repair step MUST report no replacement for the baseline or for any single-slot deviation of it at the
  reference level; its notes stay as the safety net for the screen's randomly combined teams (two members' non-first sets may
  still compete for one copy) and for level differences between the reference and the screen's levels, and the acceptance
  reports those counts.

### Key Entities

- **Marginal contribution**: a move's share of a set's coverage; zero means the set is as good without it.
- **Live move**: a move that is the best choice against at least one opponent given the member's two strongest moves.
- **Dead move**: a move with zero marginal contribution in its set.
- **Filler move**: a dead move in a chosen set that has no live replacement, as the player-facing report names it (FR-009a).
- **Pool**: the ten moves the sets are drawn from, built greedily by marginal contribution.
- **No-live-move member**: a member whose legal attacks hold nothing live beyond its two strongest; listed with the reason in
  the candidate summary and, for the final team, in the player-facing report (filler moves named).
- **Contested resource**: a single-copy TM, evolution item or held item that more members want than there are copies; allocated
  by coverage gained, named in the candidate summary with the allocation.
- **Attributed diff cause `marginal_pool`**: a move entering or leaving a pool or set by the marginal rule.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the six B2 species at level 48, no offered set contains a dead move, except for members listed as having no
  live move; Infernape's sets contain no Fire Punch and one contains Grass Knot.
- **SC-002**: Garchomp's and Staraptor's offered sets are identical to today's; Rotom's are identical and Rotom is listed with
  its reason in the candidate summary and, in the final report, in the team text and the summary.
- **SC-003**: Over the 36 snapshot members (B2 at level 48 and B1 to B5), every list difference is attributed; 0 unexplained
  lines; the table of dead moves after the change shows 0 for every member not listed as no-live-move.
- **SC-004**: The branch's B2 quick winner is not worse than today's at equal levels (no supported loss at alpha 0.05) and its
  expected average final level is at most one level above today's.
- **SC-005**: The two unaffected teams evaluate identically on both codes once the volatile fields are removed.
- **SC-006**: Candidate generation for the six B2 species takes at most twice today's time, both measured in the acceptance
  (the pre-feature side on today's code, the branch side after; the greedy pool scans every legal attack ten times and the
  allocation adds a rebuild per member that loses a resource).
- **SC-007**: The Node suite and the full pytest suite pass on the final code.
- **SC-008**: On the B2 team, every offered set of every member is buildable together with the others' first sets at the
  reference level (zero repair notes for the baseline and its single-slot deviations), Infernape's offered sets contain a live
  coverage move it can learn on that team, and the summary names the Earthquake and Stone Edge allocation.

## Assumptions

- "Dead" and "live" are judged on the candidate value (power, accuracy, STAB, the user's attacking stat, type effectiveness,
  the crit term) against the League's stored parties; the opponent's defences stay out of the value (out of scope), so a move
  can be dead here and still the better click in a real battle; the screen and the battles decide between offered sets.
- Variable-power moves become eligible for today's base sets (the user's Grass Knot example); 024's extras still append sets for
  variable moves not chosen.
- Team-level resource allocation is in scope (story 3, the owner's decision); which member gets a contested TM is decided by
  coverage gained, not by slot order; HMs (the only requirement the tool takes, feature 006) are never consumed and never
  contested.
- The pre-feature prefix guarantee of 024 does not hold (today's sets change where dead moves are replaced); every change is
  attributed instead, as in 025.
- The pool size and the number of offered sets (3) are unchanged; the diversity threshold (2 moves) relaxes to 1 only where
  the two-apart alternative would carry a dead move (FR-004a).
- Checkpoints from before this feature do not resume (the candidate code's hash changes), as for every candidate change.
- Evidence lives under `runs/026-evidence/` (local) with small copies under `specs/026-marginal-coverage-sets/evidence/`.
