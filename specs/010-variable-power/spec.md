# Feature Specification: Variable-Power Attacks Without Regression

**Feature Branch**: `010-variable-power`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Slice 3 of re-slicing feature 007 onto main (user 2026-10-19: 'merge and start 3'). Variable-power attacks (Return, Hidden Power, Grass Knot, Low Kick, Gyro Ball, Magnitude, Wring Out, Punishment) are scored by their decomp power when movesets are built. In 007 this caused a regression: on benchmark team B2 the chosen team clears 8-10 points less than before under the same player and levels, because four of six moveset changes added a variable-power attack and dropped coverage (Ice Beam, Close Combat). Find the cause, fix it, and land the feature only if no benchmark team gets worse."

## Context

Third slice of landing 007 on `main` (`FUTURE-FEATURES.md` item 1). Slices 1 (ledger item sources) and 2 (move and item classification) are merged; neither changed optimizer results. This slice is the first that is meant to change results, and the one where 007's regression appeared.

**What is known (007 validation log, 2026-10-19):**
- User's B2 run with all of 007: average final level 55.27 vs 53.49 before. A paired check (2,000 runs, same seeds and levels) showed the battle player is not the cause; the chosen team is worse under either player (−8 to −10 points, p < 1e-10).
- The team's moveset changes: Infernape −Close Combat −Flame Wheel +Grass Knot +Stone Edge; Rotom −Charge Beam +Hidden Power (now out of scope, user 2026-10-19); Floatzel −Ice Beam −Water Pulse +Brine +Return; Weavile −X-Scissor +Return; Staraptor −Take Down +Secret Power.
- The team screen plays with the simple greedy player, which scores every variable-power attack as 0 (documented in its header). The strong player computes their power correctly.
- 007 built this on top of other 007 changes, so it does not apply to `main` unchanged.

## Clarifications

### Carried over from 007 (user answers, 2026-10-14)

- Q: What friendship is assumed for Return? → A: Maximum (255): Return power 102, Frustration power 0 and never offered.

### Session 2026-10-19

- Q: Is Hidden Power offered? → A: No (user): "hidden power relies on the ivs of a pokemon which we use 15 across the board to simulate the average stats. Hidden power should not be used in this simulator." Its type and power would be an artifact of the IV assumption. Never offered, including for NPC-trade Pokémon with fixed IVs.
- Q (after the cause was found, research R3-R4): How is the regression fixed? → A: Both (user, 2026-10-19): (A) the team screen gets a player that values variable-power attacks at their real power, as a new screen policy `greedy-v2`, with `greedy-v1` kept byte-identical for its pinned test; (B) variable-power attacks may only add to a member's move pool, never push out an attack that `main` would consider. The B1-B5 acceptance runs then decide (FR-005).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Variable-power attacks are considered at their real power (Priority: P1)

A player's Pokémon can learn Return, Grass Knot or another variable-power attack. The optimizer considers it with the power the game would give it in the League (Return 102 at maximum friendship; Grass Knot and Low Kick from each League foe's weight; Gyro Ball from the speed ratio), instead of ignoring it.

**Why this priority**: Strong moves such as Return are currently never considered, which can leave levels on the table.

**Independent Test**: The power of each variable-power attack matches the game's formula on hand-checked cases (Return 102; Low Kick 120 against Hippowdon and 40 against Roserade); Return enters the candidate pool of a member that learns it; Hidden Power, Frustration, Seismic Toss and other fixed-damage moves stay out.

**Acceptance Scenarios**:

1. **Given** a member that learns Return, **When** its candidates are built, **Then** Return is scored at power 102 and can appear in its movesets.
2. **Given** a member that learns Hidden Power (any variant, including an NPC trade with fixed IVs), **When** its candidates are built, **Then** Hidden Power is not offered.
3. **Given** Frustration or a fixed-damage move, **When** candidates are built, **Then** it is not offered.

---

### User Story 2 - No benchmark team gets worse (Priority: P1)

Adding these moves must not make the optimizer choose weaker teams. On the five benchmark teams, the new results are compared with the existing baseline using the same player and seeds.

**Why this priority**: This is what went wrong in 007. A slice that makes results worse is not shipped.

**Independent Test**: Standard optimizations of B1-B5 with the change; each final team is compared with the baseline final team (paired, same player and seeds, each at its own start levels). No team is significantly worse.

**Acceptance Scenarios**:

1. **Given** B2, **When** it is optimized with this feature, **Then** its final team is not significantly worse than the baseline final team (unlike 007).
2. **Given** each of B1-B5, **When** compared with its baseline, **Then** neither its clear rate is significantly lower nor its expected average final level higher by more than the two confirm intervals' combined half-width.

---

### User Story 3 - The cause of 007's regression is found and recorded (Priority: P1)

Before the fix, the cause is established by experiment, not assumed, and recorded.

**Why this priority**: Without the cause, a fix that passes on five teams could still fail on the next one.

**Independent Test**: The validation log states the cause with the experiment that shows it (for example: same candidates screened by a player that sees the moves' power vs one that does not; or each single moveset swap played on its own).

**Acceptance Scenarios**:

1. **Given** the B2 regression, **When** the experiments are run, **Then** the log names which step produced the weaker team (candidate ranking, the greedy screen, or something else) with paired evidence.

### Edge Cases

- **A variable-power attack is genuinely the best move.** It must still be chosen; the fix must not simply ban these moves.
- **Moves whose power depends on battle state** (Wring Out, Punishment, Magnitude) use a documented expected value; the assumption is recorded.
- **Required HMs.** Placing an HM must keep working with the new movesets.
- **Teams with no variable-power learner.** Results must be unchanged (same-seed run identical except fingerprints).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Variable-power attacks MUST be scored with the power the game computes, per member and per League foe where it depends on the foe, from decomp formulas (Constitution I); every member is assumed at friendship 255.
- **FR-002**: Fixed-damage and conditional attacks, Frustration, and Hidden Power MUST stay out of candidate movesets (Hidden Power: user 2026-10-19, IVs are a uniform 15 by assumption, so its type and power are not meaningful).
- **FR-003**: The cause of 007's B2 regression MUST be established by paired experiment and recorded before the fix is chosen.
- **FR-004**: Every stage that judges movesets MUST value a variable-power attack consistently with its real power, or the feature MUST otherwise prevent a stage's blind spot from choosing weaker teams; the chosen approach is recorded with its evidence.
- **FR-005**: On each of B1-B5 at the standard budget, the new final team MUST NOT be worse than the baseline final team ("worse" as defined in User Story 2, McNemar exact, alpha 0.05).
- **FR-006**: Standard-budget run time MUST stay within 2.0x the baseline per team (user's hard maximum).
- **FR-007**: Results for a team with no variable-power learner MUST be identical except fingerprints.
- **FR-009**: The team screen MUST value variable-power attacks at their real power (new screen player `greedy-v2`; `greedy-v1` unchanged and still selectable), and for a team without variable-power attacks it MUST choose exactly as `greedy-v1` does.
- **FR-010**: A member's move pool MUST contain every attack `main` would put in it; variable-power attacks are added on top.
- **FR-011**: Only variable-power attacks that the strong battle player computes MAY be offered: Return (friendship), Grass Knot and Low Kick (weight), Gyro Ball (speed). Magnitude, Wring Out, Crush Grip and Punishment MUST NOT be offered until a player models them (found 2026-10-19: neither `main`'s expectimax2-v2 nor 007's v3 computes their power, so they would deal no damage in the player's model; research R5).
- **FR-008**: The 007 implementation (commit `d3d53e7` and the parts of the battle player it relies on) MUST be reused where it applies; adaptations are recorded.

### Key Entities

- **Variable-power attack**: a damaging move whose power the game computes at use time; its computed type and power per member and foe.
- **Baseline team**: the B1-B5 final teams from `runs/bench-007-baseline/` (code equal to `main` in behaviour).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The hand-checked powers (Return 102, Low Kick 120/40, Gyro Ball cap 150) all match; Hidden Power, Magnitude, Wring Out, Crush Grip and Punishment are offered to 0 members.
- **SC-002**: 0 of the 5 benchmark teams is significantly worse than its baseline; the table with clear rates, average final levels, p-values and run times is recorded.
- **SC-003**: Each team's standard run takes at most 2.0x its baseline time.
- **SC-004**: The regression's cause is recorded with paired evidence (p-value and run counts).
- **SC-005**: The full test suite passes, with every changed count explained.

## Assumptions

- The baseline in `runs/bench-007-baseline/` (code `f88cdd0`) still represents `main`: slices 1 and 2 changed no optimizer result (verified in their validation logs).
- The acceptance runs (5 standard optimizations, about 8-10 h, plus paired evaluations) are local compute, within the one-time budget (about 110 h total, 32.2 h used in 007).
- The strong player on `main` (expectimax2-v2) already computes variable power in battle (`variablePower` in the player); only the greedy screen scores these moves as 0.
- The 007 B2 evidence was gathered with all of 007 applied; whether this slice alone reproduces it is part of User Story 3.
