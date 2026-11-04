# Feature Specification: Adaptive Sampling in the Optimizer's Confirmation Stage

**Feature Branch**: `022-confirm-adaptive-sampling`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Adaptive Elite Four sampling in the optimizer's confirmation stage: feature 022, the follow-on feature 021 recorded (specs/021-adaptive-e4-sampling/validation-log.md; evaluate defaults to adaptive at floor 0.98 since the user's decision of 2026-11-03). Scope: `platsim optimize`'s confirmation stage only, which today evaluates the winner with full gauntlets at the preset's confirm count (2,000 standard, 500 quick), extends while the clear-rate interval straddles the threshold up to the borderline cap (4,000 standard), and compares the winner with the runner-up on paired full runs (FR-019 of feature 001: McNemar exact, "indistinguishable" warning). The level search and the setup check keep full gauntlets (their paired batches are at most 800 runs per level vector, at or below the switch point measured in 021; a later feature if a measurement earns it). The change: the confirmation of the winner uses `evaluate_team` with adaptive sampling (full gauntlets until every Elite Four member is proven at the floor, then Cynthia-only runs from banked states; the composite clear rate with the delta-method interval; the 021 extension rule), driven by two new optimize request fields, `sampling` (full | adaptive) and `floor` (default 0.98), exposed as `optimize --sampling` and `--floor`, recorded in the job fingerprint only when they differ from the defaults (the feature-006 precedent) and in provenance as `sampling_per_stage` beside `policy_per_stage`; the borderline extension applies the 021 extension rule to the composite interval up to the same caps; `_confirm_ok` and the confirm bumps read the same report fields as today. The runner-up comparison stays paired: run indices are paired only on runs of the same kind (full against full below both switch points, Cynthia-only against Cynthia-only above both, since both derive the same request seed for the same index), indices where the two teams' run kinds differ are excluded and their count reported with the pair count and the p-value; the runner-up, when it is better, is confirmed the way the winner was. state.json's confirm attempts record the run mix (full runs, Cynthia-only runs, switch run, banked states) and the winner's result.json carries the 021 fields as evaluate's does; a checkpoint resumed inside or after the confirmation stage gives the same result as an uninterrupted run (the fingerprint and the resume test cover it); checkpoints from before this feature do not resume (platsim_code_hash changes, as in 018). Default: the feature ships with `full` as the optimizer's default and adaptive behind the flag; after the acceptance table the owner decides whether the default flips, in a final commit on their go, as feature 021 did. Reference-first acceptance (Principle VI, same seeds and opponents, alone on the machine): (1) B2 quick end to end (the six species of the 014 B2 request, quick budget, the 018 seed) with `--sampling full` and with `--sampling adaptive`, 16 workers: the same winner, moves, items and levels (the level search is unchanged), the confirmation's verdict and clear-rate interval containing each other's estimate, the expected average final level at equal levels per the 010 rule, the runner-up pair count and p-value on both sides, and the wall time of the confirmation stage and of the whole run with their ratios; (2) the confirmation stage alone at the standard count on two stored winners (the 014 b2-main team and bench-010 B3 at their recorded levels: a strong team and a Lucian-heavy one that never switches), full against adaptive, reporting containment, verdict agreement, the run mix and the wall ratio (expected about 1.7x on b2-main at floor 0.98, about 1.0x on B3); (3) the resume control: a quick optimize interrupted during the confirmation stage and resumed produces result.json identical to the uninterrupted run; (4) the runner-up pairing control: on one team the paired set under adaptive, restricted to indices where both runs are full, reproduces the full method's McNemar counts on those indices exactly. Tests: fast-mode unit tests for the pairing rule (same-kind pairing, exclusion counts, a positive and a negative control) and for the request fields and fingerprint rule; the existing optimize integration test (two quick optimizations) passes unchanged under the default; a battle_sim test of the confirmation stage with adaptive sampling at a small count and a low floor on the reference team (fields present, determinism across worker counts); the optimizer resume test extended for the new fields. Docs: README (the optimize command row, a feature-022 block with the acceptance numbers, the current default), FUTURE-FEATURES section 8, RUN-STATE. Out of scope: the level search and the setup check on adaptive sampling; any change to the player policies, the gauntlet, the trainer-AI port or `sim/` (sim_code_hash unchanged); the web UI beyond showing the run mix in the optimize result view; the lead-reporting follow-on; Shift; the README headline re-run. Merge gate: the full pytest suite and the Node suite."

## Overview

Feature 021 gave `platsim evaluate` adaptive Elite Four sampling and made it the default at floor 0.98: on strong
teams most of a 2,000-run evaluation becomes Cynthia-only battles from banked states, with the same verdict as the
full gauntlet, 1.7 to 2.1x faster; on Lucian-heavy teams the floor is never reached and nothing changes. The
optimizer still runs full gauntlets everywhere. Its confirmation stage is the one place where it spends thousands of
runs on one team: the winner at the preset's confirm count (2,000 standard, 500 quick), more while the interval
straddles the threshold (up to 4,000 standard), plus the paired runner-up comparison.

This feature applies the 021 method to that stage only, behind `optimize --sampling adaptive` with `full` as the
default until the owner's go. The level search and the setup check keep full gauntlets: their paired batches are at
most 800 runs per level vector, around the switch point, and are a later measurement. The one new statistical piece
is how the runner-up comparison stays paired when each team switches at a different run.

## Clarifications

### Session 2026-11-04

- Q: In the B2 quick acceptance, if the adaptive confirmation's verdict differs from the full one only at the margin (a borderline flip that triggers a level bump) while each estimate still lies inside the other's interval, does that count as a failure of the "same levels" check? → A: Containment decides: such a level difference is recorded with both intervals and counts as a pass; a difference with containment broken fails.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The confirmation stage on adaptive sampling (Priority: P1)

The owner runs `platsim optimize ... --sampling adaptive` and the confirmation stage evaluates the winner with the 021
method: full gauntlets until every Elite Four member is proven at the floor, then Cynthia-only runs from banked
states, the composite clear rate with its delta interval, the same qualification checks, and the borderline
extension following the 021 extension rule up to the same caps. The level search and the setup check are untouched.
state.json's confirm attempts and the winner's result.json record the run mix; provenance names the sampling per
stage; the request's `sampling` and `floor` enter the job fingerprint only when they differ from the defaults.

**Why this priority**: it is the saving the feature exists for, and the other stories measure or guard it.

**Independent Test**: a quick optimize on the reference-team species with `--sampling adaptive --floor 0.9` finishes
with a confirmation whose state.json attempt shows a switch run and Cynthia-only runs, the winner's result.json
carries the 021 fields, and the same request with another worker count gives byte-identical result.json.

**Acceptance Scenarios**:

1. **Given** `--sampling adaptive`, **When** the confirmation stage runs, **Then** the winner is evaluated with
   adaptive sampling at the request's floor, the confirm checks read the composite estimate and interval, and the
   confirm bumps (raising levels after a failed confirm) behave as today on those fields.
2. **Given** the confirmation's interval straddles the threshold, **When** the borderline extension runs, **Then** it
   adds runs by the 021 extension rule (Cynthia-only while they can close the composite interval, full gauntlets
   otherwise) up to the preset's borderline cap, and the attempt records the mix.
3. **Given** a request without `--sampling`, **When** the optimizer runs, **Then** the confirmation uses full gauntlets
   (the default until the owner's go) and the fingerprint is unchanged from before this feature's defaults.
4. **Given** the same request with 16 workers and with 3, **When** both finish, **Then** result.json is byte-identical.
5. **Given** a checkpoint written inside or after the confirmation stage, **When** the job is resumed, **Then** the
   result equals an uninterrupted run; **Given** a checkpoint from before this feature, **Then** it is not resumed.

---

### User Story 2 - The runner-up comparison stays paired (Priority: P2)

The owner still gets the FR-019 warning when the winner and the runner-up are indistinguishable. Under adaptive sampling the two teams may switch at different runs, so the comparison pairs only runs of the same
kind that share a seed: full runs by run index below both switch runs, Cynthia-only runs by their ordinal (the j-th
Cynthia-only run of each team is seeded alike); the surplus runs on either side are excluded and counted. The pair count, the
excluded count and the p-value are reported. A runner-up that is better is confirmed the way the winner was.

**Why this priority**: it is the only new statistical piece; a wrong pairing would silently weaken or bias FR-019.

**Independent Test**: unit tests on synthetic run lists (same-kind pairing, exclusion counts, a positive control
where one team clearly wins on the paired set and a negative control with identical outcomes); on real runs the
restriction to indices where both runs are full reproduces the full method's McNemar counts on those indices exactly.

**Acceptance Scenarios**:

1. **Given** two adaptive confirmations with switch runs k_a and k_b and c_a, c_b Cynthia-only runs, **When** the
   comparison pairs them, **Then** run indices below min(k_a, k_b) pair full against full, Cynthia-only ordinals below
   min(c_a, c_b) pair Cynthia-only against Cynthia-only (same seed on both sides), the |k_a − k_b| + |c_a − c_b| surplus
   runs are excluded, and the report carries pairs, full and Cynthia-only pair counts, excluded and the p-value.
2. **Given** the paired set restricted to full-against-full indices, **When** the McNemar counts are computed, **Then**
   they equal the full method's counts on the same indices (the pairing control).
3. **Given** the runner-up wins the comparison, **When** it is confirmed, **Then** it is evaluated with the same
   sampling and floor as the winner was and the same checks apply.

---

### User Story 3 - Acceptance, docs and the default (Priority: P3)

The owner sees a paired acceptance before deciding the default: B2 quick end to end both ways (same winner, moves,
items and levels; the confirmation's verdict and intervals containing each other's estimate; the 010 equal-levels
comparison; the runner-up pair counts and p-values; the wall time of the confirmation stage and of the whole run with
their ratios), the confirmation stage alone at the standard count on the 014 b2-main team and on bench-010 B3, the
resume control and the pairing control. README, FUTURE-FEATURES and RUN-STATE describe the stage, the flags and the
numbers; the default flips to adaptive only on the owner's go, in a final commit.

**Why this priority**: Principle VI and the project's default-switch practice (018, 021).

**Independent Test**: the acceptance script prints the four blocks with pass or fail per check; `optimize --help`
and the README state the current default; the existing optimize tests pass unchanged.

**Acceptance Scenarios**:

1. **Given** the B2 quick request with the 018 seed, **When** it runs with `--sampling full` and with `--sampling
   adaptive`, **Then** the winner, moves and items are identical (the level search is unchanged), each confirmation's
   estimate lies inside the other's interval, the expected average final level is compared at equal levels, and both
   wall times and their ratio are reported for the confirmation stage and the whole run; the final levels are expected
   to be identical, and a difference caused by a borderline flip with a level bump is recorded with both intervals and
   passes while containment holds.
2. **Given** the 014 b2-main team and bench-010 B3 at their recorded levels, **When** the confirmation stage alone runs
   at the standard count both ways, **Then** containment, verdict agreement, the run mix and the wall ratio are
   reported (about 1.7x on b2-main at floor 0.98, about 1.0x on B3).
3. **Given** a quick optimize interrupted during the confirmation and resumed, **When** it finishes, **Then** its
   result.json is identical to the uninterrupted run's.
4. **Given** the acceptance table, **When** the owner decides, **Then** the default flips to adaptive only on their
   go, as one final commit; otherwise `full` stays the default and the result is recorded.

---

### Edge Cases

- The floor is never reached during the confirmation (B3-like winners): every run is full, the full method's
  statistics apply (021 FR-006), and the comparison pairs full against full on every index.
- Only one of the two teams switches: its Cynthia-only runs have no partner and are excluded, as are the other team's
  full runs beyond the switch run; the excluded count shows it.
- A confirm bump raises the levels: the next attempt starts a fresh adaptive confirmation at the new levels with the
  same seed and floor; attempts are recorded separately. In the acceptance, a bump on one side only (a borderline flip
  at the margin) is a recorded difference, not a failure, while each estimate lies inside the other's interval.
- The borderline cap is reached while the composite interval still straddles: borderline, not qualified, as today.
- The quick preset (no half-width target): no extension; the run mix is still recorded.
- A pre-feature checkpoint: refused for resume because the code hash differs (as in 018).
- `--floor` given with `--sampling full`: accepted with a note that it applies to adaptive only (as evaluate does).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `OptimizeRequest` MUST gain `sampling` (full | adaptive, default full until the owner's go) and `floor`
  (0.9 to 1.0, default 0.98), exposed as `optimize --sampling` and `--floor`, and both MUST enter the job fingerprint
  only when they differ from the defaults.
- **FR-002**: Under adaptive sampling the confirmation stage MUST evaluate the winner with the 021 method at the
  request's floor, applying the confirm checks and bumps to the composite estimate and interval exactly as they apply
  to the full method's today.
- **FR-003**: The borderline extension MUST apply the 021 extension rule to the composite interval up to the preset's
  borderline cap, and the attempt MUST record the mix of added runs.
- **FR-004**: The runner-up comparison MUST pair runs only on runs of the same kind that share a seed: full runs by
  run index below both teams' switch runs (the same request seed on both sides), Cynthia-only runs by their ordinal
  (the j-th Cynthia-only run of each team shares `derive_seed(master, j, 98)`, each from its own banked state); every
  other run (the later-switching team's surplus full runs, the other team's surplus Cynthia-only runs) MUST be excluded
  and counted; the report MUST carry the pair count, the full and Cynthia-only pair counts, the excluded count and the
  McNemar exact p-value; a runner-up that is better MUST be confirmed with the same sampling and floor as the winner.
- **FR-005**: state.json's confirm attempts MUST record full runs, Cynthia-only runs, switch run and banked states, the
  winner's result.json MUST carry the 021 fields, and provenance MUST record `sampling_per_stage` (level search and
  setup check full, confirm as requested) beside `policy_per_stage`.
- **FR-006**: The optimizer's result MUST be a pure function of the request: byte-identical across worker counts, and
  a job resumed from a checkpoint inside or after the confirmation stage MUST equal an uninterrupted run; checkpoints
  from before this feature MUST not resume.
- **FR-007**: The level search and the setup check MUST keep full gauntlets.
- **FR-008**: A committed acceptance script MUST run the four acceptance blocks (B2 quick both ways with the 010
  equal-levels comparison and both wall times; the confirmation alone at the standard count on the 014 b2-main team
  and bench-010 B3; the resume control; the pairing control) and print pass or fail per check.
- **FR-009**: The default MUST stay `full` until the owner's explicit go after the acceptance table; the flip MUST be
  one final commit changing the request default, the CLI default, the README and the tests that depend on it.
- **FR-010**: Fast-mode unit tests MUST cover the pairing rule (same-kind pairing, exclusion counts, positive and
  negative controls) and the request fields and fingerprint rule; a `battle_sim` test MUST run the confirmation stage
  with adaptive sampling at a small count and a low floor on the reference-team species (fields present, determinism
  across worker counts); the existing optimize integration test MUST pass unchanged under the default; the resume
  test MUST cover the new fields.
- **FR-011**: No file under `sim/` changes (`sim_code_hash` unchanged); the player policies, the gauntlet and the
  trainer-AI port are untouched.
- **FR-012**: Every measurement MUST be logged with Eastern times and the code hashes; the acceptance runs alone on the
  machine; the merge gate is the full pytest suite and the Node suite.

### Key Entities

- **OptimizeRequest.sampling, .floor**: the confirmation's method and floor; in the fingerprint only when non-default.
- **Confirm attempt**: levels, runs (total), clear rate and interval, borderline, gap, expected average final level,
  passes_confirm_checks, plus the run mix (full, Cynthia-only, switch run, banked states).
- **Paired comparison**: pairs (full pairs by run index plus Cynthia-only pairs by ordinal), excluded (surplus runs on
  either side), only-winner, only-runner-up, p, verdict.
- **sampling_per_stage**: {"level_search": "full", "setup_check": "full", "confirm": "full" | "adaptive"} plus the floor.
- **Acceptance blocks**: the four checks of FR-008 with their numbers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: B2 quick both ways: identical winner, moves and items; each confirmation's estimate inside the other's
  interval (the deciding check); identical final levels expected, with a borderline-flip level difference recorded and
  passing while containment holds and failing otherwise; both wall times reported with ratios for the confirmation
  stage and the whole run.
- **SC-002**: Confirmation alone at the standard count: containment and verdict agreement on both stored winners;
  wall ratio about 1.7x on b2-main at floor 0.98 and about 1.0x on B3, with the run mix reported.
- **SC-003**: The resume control gives byte-identical result.json; result.json is byte-identical across worker counts.
- **SC-004**: The pairing control reproduces the full method's McNemar counts exactly on the full-against-full indices.
- **SC-005**: The existing optimize tests pass unchanged; the new unit and battle_sim tests pass; `sim_code_hash` is
  unchanged; the full pytest suite and the Node suite are green.
- **SC-006**: The default is `full` until the owner's go; the README and `optimize --help` state the current default and
  the acceptance numbers.

## Assumptions

- The B2 quick request is the six species of the 014 B2 request (`garchomp infernape staraptor rotom floatzel weavile`)
  with the seed the 018 run used (`014-b2`), quick budget, default options; its
  018 wall time with v4 was 350 s (level search plus confirmation), the baseline for the whole-run ratio.
- "The 014 b2-main team at its recorded levels" and "bench-010 B3 at its recorded levels" are the stored
  `team.builds` of those results, as in the 021 acceptance (the 018 v2 B2 team is the same as 014 b2-branch and is
  not used again).
- The 021 acceptance already measured the confirmation-sized evaluation on those teams (1.70x on b2-main at 0.98,
  1.0x on B3); block (2) repeats it through the optimizer's own confirmation path to show the integration, not to
  re-measure the method.
- Pairing by run index on Cynthia-only runs is legitimate for the same reason pairing full runs by seed is: both teams
  play the same RNG stream for that index from their own banked state; indices whose run kinds differ are excluded.
- The confirmation's `evaluate_team` call keeps `extend_borderline` semantics: under adaptive the straddle test uses the
  composite interval and the added runs follow the 021 extension rule.
- The acceptance costs: two B2 quick runs (about 6 minutes each), two standard confirmations on two teams (about 20
  minutes), the resume control (about 12 minutes), all alone on the machine; under an hour.
- The merge gate is the full pytest suite (about 1 hour) and the Node suite.
