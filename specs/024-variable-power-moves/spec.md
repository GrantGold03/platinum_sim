# Feature Specification: Variable-Power Moves Offered by the Optimizer

**Feature Branch**: `024-variable-power-moves`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Variable-power moves offered by the optimizer, reference-first: feature 024, redone from the decomp and main (the archived 007 to 010 branches are not trusted; nothing is cherry-picked, their findings are used only as hypotheses to test). Today `optimizer/candidates.py` excludes every move with data power 1 (`is_attack`, power > 1), the screening player greedy-v1 scores such moves 0 (`expectedDamage`, power <= 1), while the battle engine computes their power at use (Showdown basePowerCallback) and the strong player expectimax2 already models Return, Frustration, Low Kick, Grass Knot, Gyro Ball and Hidden Power (`variablePower`) and nothing else. Scope, the same four moves the 010 branch chose and the decomp formulas (`src/battle/battle_script.c`): Return (effect script 0121: friendship*10/25; the simulator assumes max friendship 255 as legality already does, so 102), Grass Knot and Low Kick (BtlCmd_CalcWeightBasedPower :6808-6826 with sWeightToPower {100:20, 250:40, 500:60, 1000:80, 2000:100, else 120}, the break at limit >= weight so a weight on a limit gets the lower tier; weights from res/pokemon/<sp>/data.json as sim/ai/calcdamage.mjs reads them), Gyro Ball (BtlCmd_CalcGyroBallPower :7123-7133: 1 + 25*defender speed/attacker speed, cap 150, speeds at the fight's levels). Not offered, stated with the reason: Hidden Power (IVs are a uniform 15 by assumption, user 2026-10-19), Frustration (1 at friendship 255), Magnitude, Wring Out, Crush Grip, Punishment, Flail, Reversal, Fling, Trump Card, Natural Gift, Present, Spit Up (no player computes them; section 6 follow-up), fixed-damage and counter moves; Eruption and Water Spout keep today's treatment (data power 150). Three stories. (1) The screening player values the four moves: greedy-v1's expected damage computes their power with the decomp formulas (the same values expectimax2 uses; a shared table or helper, one source of truth in sim/), with unit tests against the decomp tables (every weight tier and both boundary behaviours, Gyro Ball at the cap, Return at 255); every recorded result stays byte-identical (no fixture team carries these moves: the replay fixtures and the determinism tests prove it; if any does, the change goes behind a new policy name instead). The divergence ledger gains an entry for the weight-tier boundary: the game breaks at limit >= weight, Showdown at weight >= limit, so a weight exactly on a limit (Flint's Flareon, 250 hg: game 40, engine 60) differs; accepted, impact stated, the player's model follows the decomp. (2) The optimizer offers the four moves: `candidates.py` computes each variable move's power per League opponent with the same formulas (Return 102; weight tier of the opponent; Gyro Ball from the member's speed at the reference level and the opponent's at its level) and scores it in `move_value` like a fixed-power move; the candidate list is additive so no set the optimizer offers today is displaced (the hazard the 010 record measured: with K_MOVESETS 3 and the diversity rule a variable-power set took a slot and Infernape lost Close Combat, about 10 points): the fixed-power candidate sets are generated exactly as today, then up to K extra sets containing at least one variable-power move are appended, and the screen chooses; a unit test asserts, for the six B2 species, that today's candidate sets are all still present and in the same order. The job fingerprint changes for every job (new candidates), so pre-024 checkpoints do not resume (state_version or the code hash; stated in the plan). (3) Acceptance, reference-first (Principle VI), alone on the machine, Eastern times, under today's defaults (v4, adaptive 0.98, Shift): (a) B2 quick (`optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2 --workers 16`) on main-before and on the branch: winner, moves, items, levels, confirmation clear rate, wall; (b) the 010 equal-levels protocol: the two winners played by expectimax2-v4 at the new winner's levels, 2,000 paired gauntlets, same seeds, McNemar exact; pass: the new team is not worse by a statistically supported margin, and the expected average final level is equal or lower; fail: the branch does not merge until the cause is found (the candidate lists are inspected per member, the displacement test being the first suspect); (c) the reference team and the 014 b2-main team evaluated unchanged (no variable move on them): byte-identical result.json to the pre-feature code, proving the change touches only teams that carry the moves; (d) a count: how many of the six B2 members' chosen sets carry a variable-power move and which, in the table. Deliverables: the shared power helper and its tests, greedy-v1 scoring, candidates.py with the additive list and its tests, the ledger entry, the acceptance script under specs/024-*/scripts/, README (the rule, the offered and not-offered lists with reasons, the friendship assumption, the acceptance numbers), FUTURE-FEATURES sections 1 and 6 updated, validation log, evidence under runs/024-evidence/ with small copies under the feature's evidence/. Merge gate: the Node suite and the full pytest suite. Out of scope: Hidden Power, the moves listed as not offered, any change to expectimax2's model or search, the alternatives stage, item pairings, greedy-v2, and the archived branches' code."

## Overview

The optimizer builds a team's movesets from attacks whose power is a fixed number in the game data. Moves whose power
is computed when they are used (Return from friendship, Grass Knot and Low Kick from the target's weight, Gyro Ball
from the speed ratio) carry a data power of 1 and are excluded from every candidate set, and the screening player
scores them zero. The battle engine already computes them correctly, and the strong player's lookahead already values
the four moves. So a team the tool outputs can never carry Return, Grass Knot, Low Kick or Gyro Ball, even where one
of them is the member's best attack against the Elite Four.

This feature offers those four moves, reference-first and from the decomp: one source of truth for their power in the
battle code, used by the screening player and mirrored by the optimizer's candidate scoring; a candidate list that
appends variable-power sets after today's sets instead of displacing them (the hazard the archived 010 record measured
on the B2 team, where a displaced set cost Infernape its Close Combat and about ten points of clear rate); and an
acceptance that compares the new B2 winner with today's at equal levels on paired runs and refuses to merge a loss.
The archived branches are a source of hypotheses only; nothing is copied from them.

## Clarifications

### Session 2026-11-09

- Q: How should the extra candidate sets that carry a variable-power move be chosen and ordered after today's sets? → A: Rank every four-move set drawn from today's pool plus the member's variable-power moves by today's coverage score; keep, in rank order, up to K sets containing at least one variable-power move that differ from each other by at least two moves (diversity among the extra sets only); today's sets stay first and unchanged.
- Q: If the branch's B2 quick winner settles one level higher than today's winner while the equal-levels paired test shows no supported loss, does the acceptance pass or fail? → A: Pass if the paired test shows no supported loss and the level difference is at most one level on average (the quick search's known noise, 022); fail on two or more levels or on a supported loss; the difference is recorded either way.

### Session 2026-11-09 (after the first acceptance)

- Q: The first acceptance failed FR-009 (branch winner 0.778 vs today's 0.823 at equal levels, p 2e-4) with today's candidate sets intact; the measured cause was the screen's random fill changing under its 81-team cap once options were appended (43 of 81 teams shared; today's winner never screened). How should the screen handle the extra sets? → A: Screen superset: the screen's baseline, single-slot deviations and random fill draw from today's options only, so its first 81 teams are exactly today's; then one single-slot deviation per extra set (with that set's top held item) is appended beyond the cap (up to 18 more teams at quick).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The screening player values the four moves (Priority: P1)

The screening player (greedy-v1) scores Return, Grass Knot, Low Kick and Gyro Ball by the game's formulas, using the
same values the strong player's lookahead already uses, from one shared place in the battle code. Every recorded
result stays byte-identical, because no fixture team carries these moves. The ledger records the one place where the
engine and the game disagree about these formulas: the weight-tier boundary.

**Why this priority**: the optimizer's screen cannot choose a move it scores zero; everything else builds on this.

**Independent Test**: unit tests of the shared power helper against the decomp tables (every weight tier, a weight
exactly on a limit under both rules, Gyro Ball below and at the cap, Return at friendship 255), the greedy player's
expected damage for each of the four moves equal to a fixed-power move of the computed power, and the replay and
determinism tests unchanged.

**Acceptance Scenarios**:

1. **Given** a member with Return and friendship 255, **When** the screening player scores its moves, **Then** Return
   scores as a 102-power Normal move.
2. **Given** a target of weight exactly 250 hg (Flint's Flareon), **When** the shared helper computes Low Kick's power,
   **Then** it returns 40 (the game's rule: a weight on a limit takes the lower tier).
3. **Given** a slow attacker and a fast target, **When** Gyro Ball's power is computed, **Then** it is 1 plus 25 times
   the speed ratio, capped at 150, from the two fighters' speeds at their levels.
4. **Given** the three recorded replay fixtures and the determinism tests, **When** they run, **Then** every digest,
   choice and draw count is unchanged.
5. **Given** the ledger, **When** it is regenerated, **Then** it carries an accepted entry for the weight-tier boundary
   with the Flareon case as its impact.

---

### User Story 2 - The optimizer offers the four moves without displacing today's sets (Priority: P2)

Candidate generation scores Return, Grass Knot, Low Kick and Gyro Ball per League opponent with the same formulas,
and offers them in extra candidate sets appended after today's sets, so every set the optimizer offers today is still
offered, in the same order, and the screen decides. Hidden Power, Frustration and the moves no player computes stay
out, each with its reason recorded. Checkpoints from before the feature do not resume.

**Why this priority**: it is the user-visible capability, and the additive list is the guard against the 010 loss.

**Independent Test**: for each of the six B2 species, the candidate sets produced before the change are a prefix of
the sets produced after it, in order; at least one appended set carries a variable-power move where one is legal;
the not-offered list never appears in any set.

**Acceptance Scenarios**:

1. **Given** the six B2 species at the reference level, **When** candidates are generated, **Then** today's sets
   appear first and unchanged, followed by up to K sets each containing at least one of the four moves.
2. **Given** a species that can learn Grass Knot, **When** its value against Bertha's Rhyperior and Flint's Flareon is
   scored, **Then** the power used is the opponent's weight tier (120 against Rhyperior, 40 against Flareon).
3. **Given** a species that learns Hidden Power, Frustration or Magnitude, **When** candidates are generated, **Then**
   none of those moves appears, and the README names the reason for each.
4. **Given** a checkpoint written before this feature, **When** an optimize is resumed from it, **Then** the resume is
   refused.

---

### User Story 3 - The B2 winner is not worse at equal levels (Priority: P3)

The owner sees, under today's defaults (v4 player, adaptive sampling, Shift), the B2 quick winner from today's code
beside the winner from this feature (moves, items, levels, confirmation clear rate, wall time, which members carry a
variable-power move), the two winners played at equal levels on 2,000 paired gauntlets with the exact paired test, and
two unaffected teams evaluated byte-identically. A supported loss blocks the merge.

**Why this priority**: it is the reference-first check that the archived branch failed; the feature is only worth
merging if it passes.

**Independent Test**: the acceptance script's table is complete; the equal-levels row shows no supported loss and the
branch winner's expected average final level is at most one level above today's winner's; the two unaffected teams'
result.json files equal the pre-feature code's once the code-version and ledger fields are removed.

**Acceptance Scenarios**:

1. **Given** the B2 quick request on the pre-feature code and on the branch, **When** both finish, **Then** the table
   lists each winner's species, moves, items, levels, confirmation clear rate and interval, wall time, and the members
   whose chosen set carries one of the four moves.
2. **Given** the two winners at the new winner's levels, **When** 2,000 paired gauntlets are played with the same seeds
   by expectimax2-v4, **Then** the exact paired test shows the new team not worse by a supported margin, and the new
   winner's expected average final level (from its own optimizer result) is at most one level above today's winner's
   (equal or lower expected); otherwise
   the feature does not merge until the cause is found, starting with the candidate lists per member.
3. **Given** the reference team and the 014 b2-main team (no variable-power move), **When** evaluated on the branch and
   on the pre-feature code with the same request, **Then** result.json is identical after removing the code-version and ledger fields (`sim_code_hash`, `platsim_code_hash`, `repo_commit`, `repo_dirty`, `divergence_ledger_version`, `divergence_ledger_file_version`, `provenance.worker.divergence_ledger_version`, `divergences`), which change with every feature; every statistic, level, seed and loss
   cause is the same.

---

### Edge Cases

- A weight exactly on a tier limit: the game gives the lower tier, the engine the higher; the player's model and the
  optimizer follow the game; the ledger records the engine's deviation (only Flint's Flareon among League Pokemon).
- Gyro Ball when the attacker is faster than the target: power 1 plus a fraction, i.e. 1; still offered, scored low.
- Gyro Ball's power depends on both levels: the optimizer scores it at the member's reference level against each
  opponent's recorded level; the battle computes it at the actual levels.
- Return at friendship below 255: not modelled; friendship is assumed at the maximum (reachable per the legality
  layer) and the README says so.
- A member that learns none of the four moves: no appended set; its candidates are exactly today's.
- Eruption and Water Spout: already pass the power filter at data power 150 and keep that treatment (their HP falloff
  is not modelled by any player; recorded, not changed).
- A variable-power move that is dominated by a fixed-power move of the same type under today's dominance rule: the
  rule compares data power, so it never removes a variable-power move; the computed power decides in scoring.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: One shared helper in the battle code MUST compute the power of Return (friendship*10/25, friendship 255),
  Grass Knot and Low Kick (the decomp weight table, break at limit >= weight, weights as the trainer-AI port reads
  them) and Gyro Ball (1 + 25*target speed/attacker speed, cap 150, speeds at the fighters' levels); the strong
  player's existing values MUST come from the same place or be shown equal to it by test.
- **FR-002**: The screening player greedy-v1 MUST score the four moves with that helper as if they were fixed-power
  moves of the computed power; all other moves with data power 1 MUST still score zero.
- **FR-003**: Every recorded replay fixture digest, choice list and draw count, and every determinism test, MUST be
  unchanged; if any fixture team carries one of the four moves, the scoring change MUST go behind a new policy name
  instead of changing greedy-v1.
- **FR-004**: The divergence ledger MUST gain an accepted mechanics entry for the weight-tier boundary (game: limit >=
  weight; engine: weight >= limit) with the Flareon case as its impact and both source references.
- **FR-005**: Candidate generation MUST compute each of the four moves' power per League opponent with the same formulas
  and score them in the move value like fixed-power moves; Hidden Power, Frustration, Magnitude, Wring Out, Crush
  Grip, Punishment, Flail, Reversal, Fling, Trump Card, Natural Gift, Present, Spit Up, fixed-damage and counter moves
  MUST NOT be offered, and the reason for each group MUST be stated in the code and the README.
- **FR-006**: The candidate list MUST be additive: the sets produced today MUST be produced first and unchanged (same
  sets, same order), followed by up to K extra sets each containing at least one of the four moves; a unit test on the
  six B2 species MUST pin this.
- **FR-006a**: The extra sets MUST be chosen by ranking every four-move set drawn from today's pool plus the member's
  variable-power moves with today's coverage score (ties broken as today), keeping in rank order up to K sets that
  contain at least one variable-power move and differ from each other by at least two moves; the diversity rule
  applies among the extra sets only, not against today's sets, so a one-move swap of today's best set is offered when it
  ranks.
- **FR-006b**: The optimizer's screen MUST build its capped candidate list (the baseline, the single-slot deviations and
  the random fill) from today's options only, so that list is identical to today's for the same request, and MUST then
  append one single-slot deviation of the baseline per extra set (with the set's first held-item candidate) beyond the
  cap; the acceptance MUST show the branch's first 81 screened teams equal to the pre-feature run's.
- **FR-007**: Checkpoints written before this feature MUST NOT resume (the plan states which fingerprint field
  changes).
- **FR-008**: Acceptance MUST run, alone on the machine with Eastern times, under today's defaults: the B2 quick
  request on the pre-feature code and on the branch (winner species, moves, items, levels, confirmation clear rate and
  interval, wall, members carrying a variable-power move); the two winners at the new winner's levels on 2,000 paired
  gauntlets with the same seeds by expectimax2-v4 with the exact paired test; and the reference team and the 014
  b2-main team evaluated on both codes with result.json identical after removing the code-version and ledger fields (`sim_code_hash`, `platsim_code_hash`, `repo_commit`, `repo_dirty`, `divergence_ledger_version`, `divergence_ledger_file_version`, `provenance.worker.divergence_ledger_version`, `divergences`), which change with every feature.
- **FR-009**: The feature MUST NOT merge if the equal-levels comparison shows the new team worse by a statistically
  supported margin (exact paired test at alpha 0.05), or if the new winner's expected average final level is higher
  than today's by more than one level on average (a difference of at most one level is within the quick level
  search's known noise, feature 022, and passes when the paired test shows no supported loss; the difference is
  recorded either way); the cause MUST be found first, starting with the candidate lists per member.
- **FR-010**: The README MUST state the rule, the offered and not-offered lists with reasons, the friendship assumption
  and the acceptance numbers; FUTURE-FEATURES sections 1 and 6 MUST be updated; evidence lives under
  `runs/024-evidence/` with small copies under the feature's `evidence/`.
- **FR-011**: Nothing from the archived 007 to 010 branches MUST be cherry-picked or copied; their findings are
  hypotheses tested here.

### Key Entities

- **Variable-power move**: one of Return, Grass Knot, Low Kick, Gyro Ball; data power 1; computed power per (attacker,
  target) from the shared helper.
- **Not-offered list**: Hidden Power (IVs assumed uniform 15), Frustration (1 at friendship 255), the moves no player
  computes, fixed-damage and counter moves; each with its reason.
- **Candidate list**: today's K sets (unchanged, first) plus up to K appended sets with at least one variable-power
  move, ranked by today's coverage score over today's pool plus the member's variable-power moves, diverse among
  themselves only.
- **Acceptance table**: per code (pre-feature, branch) the B2 quick winner's build, levels, confirmation statistics
  and wall; the equal-levels paired row; the two byte-identical unaffected evaluations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The shared helper reproduces every decomp weight tier, both boundary rules, the Gyro Ball cap and Return
  at 255 in unit tests; the strong player's values equal it.
- **SC-002**: The three replay fixtures and the determinism tests pass unchanged: zero digests, choices or draw counts
  differ.
- **SC-003**: For all six B2 species, today's candidate sets are a prefix of the new candidate list, in order.
- **SC-004**: The acceptance table is complete; the two unaffected teams' reports are identical across codes once the
  code-version and ledger fields are removed; the equal-levels row shows no supported loss and the branch winner's
  expected average final level is at most one level above today's winner's.
- **SC-005**: The ledger validates with the new entry; the README names the rule, both lists and the assumption.
- **SC-006**: The Node suite and the full pytest suite are green on the final code.

## Assumptions

- Friendship is at the maximum (255) for every player Pokemon, as the legality layer already assumes; Return is 102.
- The four offered moves are the ones the strong player already models; widening the set (Magnitude and the others
  in section 6) is a later feature once a player computes them.
- The additive candidate list is the chosen guard against displacement; K extra sets use the same K as today's list.
- Checkpoint refusal comes for free from the code fingerprint (the optimizer's Python changes), as in 018 and 023; the
  plan confirms it or bumps the state version.
- The acceptance's pre-feature side runs on this branch before any code change (the branch's code equals `main` at
  the branch point), with the code hashes and the repository commit recorded in each result as proof; both sides use
  today's defaults.
- Acceptance pool time about one hour: two B2 quick runs (about 7 min each), 2,000 paired gauntlets at equal levels
  (about 5 min), two reference evaluations on each code (about 2 min each).
