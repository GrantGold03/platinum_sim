# Feature Specification: The battle player models flinch

**Feature Branch**: `030-player-flinch`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Player models flinch (prerequisite for the H4 King's Rock / Razor Fang group, owner's decision 2026-11-23: flinch first, then the items as feature 031). Today the battle player ignores flinch entirely, although 10 League Pokemon carry flinch moves [...]. Three stories: (1) the player models flinch on both sides [...]; (2) measurement: reference-first paired gauntlets under Shift on the reference team, the benchmark team and the B2 winner, 2,000 pairs each, model against flinch=0; a supported loss on any team stops the feature; (3) acceptance on both codes. Out of scope: King's Rock / Razor Fang (feature 031), Stench, confusion and infatuation, the damage formula, the trainer AI port, the optimizer." (full text in the conversation of 2026-11-23)

## Overview

A flinch costs a Pokemon its move for the turn. Some damaging moves (Air Slash, Iron Head, Dark Pulse, the three elemental Fangs,
Zen Headbutt, Extrasensory, Dragon Rush, Waterfall, Fake Out and others) can flinch the target, but only when the attacker moves
first in the turn. Ten League Pokemon carry such a move, including Cynthia's Togekiss (Air Slash) and Garchomp (Dragon Rush), and
many of the player's own Pokemon learn one. The simulated battle player does not know flinch exists: it never expects a faster
foe's Air Slash to cost it a turn, and it never values its own faster flinch move for the turn it can deny. A competent player
(constitution Principle VII) knows both. This feature teaches the player flinch, checks the battle engine against the game, and
measures what the change does to the levels the tool reports. It is the prerequisite for offering King's Rock and Razor Fang (a
held-item flinch chance), which follow as feature 031.

| Source | Rule |
|---|---|
| Game (decomp) | a flinch move hits and its effect chance succeeds (doubled by the attacker's Serene Grace); the target gets the flinch only if it has not moved yet this turn, is not behind a substitute and lacks Inner Focus; when it then tries to move, it loses that move; Steadfast raises its Speed by one stage |
| Battle engine | the same rule in the simulator's own code (to be checked case by case) |
| Our player today | never models flinch |
| League | 10 flinch movers: Aaron's Yanmega (Air Slash), Scizor (Iron Head), Drapion (Ice Fang); Bertha's Whiscash (Zen Headbutt), Gliscor (Ice, Fire, Thunder Fang); Flint's Houndoom (Dark Pulse); Cynthia's Spiritomb (Dark Pulse), Roserade (Extrasensory), Togekiss (Air Slash, ability Hustle), Garchomp (Dragon Rush). Gallade and Lucario have Steadfast. None has Inner Focus or Serene Grace |

## Clarifications

### Session 2026-11-23

- Q: If modelling flinch makes the battle player slower, how much slowdown is acceptable before the feature has to be redesigned or stopped? → A: B, at most 25% slower (fewer gauntlets per second); over that, prune or stop for the owner's decision. Owner's addition: when the Pokemon with the flinch move moves second, no flinch chance is considered at all, because the Pokemon that already moved cannot be flinched.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The battle player knows flinch (Priority: P1)

When a Pokemon that moves first in a turn uses a flinch move and it hits, the simulated player expects, with the move's flinch
chance, that the slower target loses its move that turn, on both sides of the battle, as a competent player would.

**Why this priority**: the League's flinch moves already cost the player turns in every measurement; a player that ignores them
plays below the competent standard and the item feature (031) cannot be built without it.

**Independent Test**: constructed positions where a faster foe has a flinch move, and where the player's faster member has one,
show the model's expected outcome includes the lost move with the game's chance; with the reference switch off, nothing changes.

**Acceptance Scenarios**:

1. **Given** a faster foe whose flinch move hits the player's member, **When** the player evaluates the turn, **Then** with the
   move's chance the member's move that turn does not happen.
2. **Given** a slower foe with a flinch move, **When** it hits after the member has moved, **Then** no flinch is expected and
   the player does not consider a flinch chance for that turn at all (owner's rule, 2026-11-23: a Pokemon that has already moved
   cannot be flinched); the same holds for the player's own slower member.
3. **Given** the player's faster member uses a flinch move on a foe, **When** it hits, **Then** with the move's chance the foe loses
   its move that turn.
4. **Given** the target is behind a substitute, has Inner Focus, or has already moved, **When** a flinch move hits, **Then** no
   flinch is expected.
5. **Given** an attacker with Serene Grace, **When** its flinch move hits, **Then** the expected chance is doubled.
6. **Given** a target with Steadfast flinches, **When** the outcome is applied, **Then** its Speed rises by one stage.
7. **Given** Fake Out, **When** it is used on the user's first turn out, **Then** the target flinches whenever it is slower and the
   other conditions hold; on a later turn Fake Out fails as the game rules.
8. **Given** the reference switch is off, **When** the player plays, **Then** its play is identical to today's.

---

### User Story 2 - The change is measured reference-first (Priority: P2)

Because flinch is in play for every team, the levels the tool reports may move. The change is measured before anything depends on
it: the player with flinch against the player without, on the same battles, for three standing teams.

**Why this priority**: a change to the player's strength is a change to the measurement (Principle VII); it must not make play worse.

**Independent Test**: paired gauntlets under the Shift battle style on the reference team, the benchmark team and the B2 winner,
2,000 pairs each, plus a pairing control (the same player against itself, zero differences) and a conditions control (a known
team's clear rate matches the optimizer's own measurement).

**Acceptance Scenarios**:

1. **Given** each of the three teams, **When** 2,000 paired gauntlets are played with and without flinch, **Then** the version with
   flinch shows no statistically supported loss (two-sided test at the 0.05 level); a supported loss on any team stops the feature.
2. **Given** the measurement is done, **When** the README is updated, **Then** it states the change in clear rate per team and the
   speed cost in plain terms.

---

### User Story 3 - Accepted on both codes (Priority: P3)

The usual acceptance runs compare the branch with `main`: the B2 quick search, equal-level pairs and the optimizer's candidate
snapshot.

**Why this priority**: confirms the measurement change did not break the search, and records what it changed.

**Independent Test**: the acceptance script's output on both codes.

**Acceptance Scenarios**:

1. **Given** the optimizer is not changed, **When** the candidate snapshot of 36 members is taken on both codes, **Then** it is identical.
2. **Given** the B2 quick search on both codes, **When** the winners are compared at equal levels over 2,000 pairs, **Then** the
   branch shows no supported loss and an expected average final level at most 1.0 above `main`'s; a winner that differs is reported
   with the reason.
3. **Given** the identity evaluations, **When** compared, **Then** they are expected to differ (flinch changes play) and each
   difference is reported, not treated as a defect.

### Edge Cases

- A flinch move that knocks the target out: no flinch matters.
- Speed ties: the move order is a coin flip; the flinch is expected with half the weight the order gives it.
- Priority moves (Quick Attack, Aqua Jet, Bullet Punch, Fake Out): order by priority first, then Speed.
- A multi-hit flinch move: the chance applies once per hit in the game (Stomp and Double Hit forms; to be confirmed); none in the League.
- A two-turn move (Sky Attack) can flinch only on its hitting turn.
- A switch that turn: the incoming Pokemon has moved (switching counts as its action) or not, as the game rules; to be checked.
- The foe's switching or item use happens before moves; a flinch can only cost a move.
- Shield Dust blocks the held-item flinch only (relevant to 031); for move flinch the ordinary secondary-effect rules apply.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The battle player MUST expect a flinch, with the move's effect chance (doubled by the attacker's Serene Grace), when
  a damaging flinch move hits a target that has not moved yet this turn, is not behind a substitute and lacks Inner Focus (unless
  the attacker has Mold Breaker, which the game lets through Inner Focus); the
  flinched Pokemon's move that turn MUST NOT happen in the model.
- **FR-002**: The rule MUST apply on both sides: foes flinching the player's members and the player's members flinching foes.
- **FR-012**: A flinch chance MUST be considered only when the flinch move's user moves before its target in that turn's order
  (priority first, then Speed; a Speed tie counts each order with its own weight). When the flinch move's user moves second, the
  player MUST NOT consider any flinch chance for that hit (owner's rule, 2026-11-23), so no extra outcome is evaluated.
- **FR-003**: Steadfast MUST raise the flinched Pokemon's Speed by one stage in the model.
- **FR-004**: Fake Out MUST follow the game: it flinches only on its user's first turn out and fails otherwise. The game's rule
  decides: if the engine differs, the difference is ledgered (FR-005) and the player models the game.
- **FR-005**: The battle engine's flinch handling MUST be checked against the game for each condition in FR-001 to FR-004; each
  difference MUST be recorded in the divergence ledger with its effect on the League.
- **FR-006**: The flinch model MUST be on only in the v4 player; the older v1 and v2 players MUST play exactly as today (their replay
  fixture entries stay byte-identical). The replay fixture also holds v4 (corrected at implementation: analyze finding C1 said v1 and
  v2 only, from the test file's header comment); its v4 entry is re-recorded, because flinch intentionally changes v4's decisions. The v4 player with the switch off MUST play exactly as `main`'s v4: a v4 bench
  digest recorded on `main` before any code change MUST equal the branch's digest with the switch off.
- **FR-007**: The greedy player MUST stay unchanged.
- **FR-008**: The change MUST be measured reference-first (Story 2) before acceptance; a statistically supported loss on any of the
  three teams MUST stop the feature.
- **FR-009**: The README MUST state what flinch modelling changes in the measurement (clear rate per team, speed cost) and what the
  player still does not model (Principle VII).
- **FR-010**: The optimizer and its candidate lists MUST NOT change.
- **FR-011**: Merge only if Story 2 shows no supported loss on any team, the player with flinch is at most 25% slower than
  without (SC-004), and Story 3's equal-level comparison passes.

### Key Entities

- **Flinch chance**: per move and attacker, the probability the hit flinches the target given the order and the target's state.
- **Reference switch**: the player option that turns the flinch model off, for the reference arm of every comparison.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In constructed positions, the player's expected outcome includes a lost move with exactly the game's chance (10%, 20%,
  30% or 100% for Fake Out, doubled for Serene Grace), and none when the target has moved, is behind a substitute or has Inner Focus.
- **SC-002**: The replay test's v1 and v2 entries and the 028/029 player tests pass unchanged (the v4 entry re-recorded); the v4 bench digest with the switch off equals
  `main`'s v4 digest.
- **SC-003**: On each of the three teams, 2,000 paired gauntlets show no supported loss for the flinch model; the per-team clear
  rates and their difference are reported.
- **SC-004**: The player with flinch plays at least 75% as many gauntlets per second as without (at most 25% slower), measured
  on the paired runs of Story 2 with the pool's start-up excluded; the README states the figure. Over the bound: the plan prunes the
  flinch outcomes or the feature stops for the owner's decision.
- **SC-005**: The candidate snapshot is identical on both codes; the B2 comparison passes the merge rule.
- **SC-006**: The Node and full Python suites pass.

## Assumptions

- The ten League flinch movers and the absence of Inner Focus and Serene Grace in the League are read from the stored parties
  (checked 2026-11-23).
- The game's rule is as read in the decomp on 2026-11-23: `subscript_flinch_mon.s` (moved this turn, substitute, Inner Focus;
  Shield Dust only for the held-item flinch), `battle_script.c` (Serene Grace doubles the effect chance), `battle_controller_player.c`
  (the flinch is checked when the Pokemon tries to move), `subscript_flinched.s` (Steadfast).
- Because play changes for every team, the identity evaluations and the replay of the default player are expected to change; the
  acceptance protocol reports those differences rather than requiring identity.
- The trainer AI's own reasoning about flinch is unchanged (out of scope).
