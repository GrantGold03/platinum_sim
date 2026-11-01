# Feature Specification: Exact Damage-Path Speedups for expectimax2 (round two)

**Feature Branch**: `016-exact-damage-speedups`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Exact speedups for the expectimax2 player policies, round two (the three items ranked 1-3 from the 2026-11-01 re-profile on main 19519ed; profile in runs/015-evidence/scratchpad/prof2/REPORT2.md). On the fixed set (20 gauntlets x 2 fixture teams, seeds prof-a-*, all five trainers, stop_on_loss false) expectimax2-v2 runs at 0.779 gauntlets/s, 18.3 ms/decision, and the profile shows: (1) applyTypeChart in sim/damage.mjs is 12.9% of all time plus prepare at 4.8%: the policy's damage table walks the type chart 16 times per calcDamage call (once per variance roll, twice with the crit table), and the trainer AI's calcDamage repeats the same walk for every one of the K samples, although the walk, the status mask and every branch depend only on attacker, defender, move and field and on whether damage is zero, never on its value; (2) the AI's pre-variance damage (calcBaseDamage plus the chart result) is recomputed for each sample on identical cached inputs; (3) the adapter's Showdown-id-to-decomp-id mappers (move, ability, item, species, type) are rebuilt cold for each of the ~55,000 shadow adapters per 40 gauntlets and keyed by template strings (memo 3.8% self time). Three changes, all exact: (1) compute the type-chart plan once per input and replay it per roll, and memoise the plan per cached damage input on the AI side; (2) memoise the AI's pre-variance damage per cached damage input within a decision (the 015 beginDecision() boundary), shared by all K samples; (3) share the id mappers across adapters for the same dex and look them up by per-kind Map instead of string keys. Expected about 20-25% of time together (roughly 1.25-1.35x single process); report the measured figure. Both expectimax2-v1 and -v2 must produce byte-identical gauntlet results for identical seeds and the live decomp-ai opponent must be unchanged: the existing replay test (sim/test/replay.test.mjs) must pass against the unchanged fixture sim/test/replay_prof_a.json (v2 digest db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3, v1 digest 1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178, every player choice, the trainer-AI draw count inside every decision); the fixture is not re-recorded. Add a randomized equivalence test for the type-chart plan against the current applyTypeChart over many generated inputs (both rolls and status masks, including immunities, Levitate, Wonder Guard, Filter, Expert Belt and ignoreTypeChecks), a memo-versus-recompute control for the pre-variance memo, and the frozen-cache run (PLATSIM_AI_FREEZE=1) for anything new that is cached. Existing determinism and AI golden tests pass; Node suite, fast mode, full suite before merge. Report gauntlets/s and ms/decision before and after on the same seeds with node sim/bench.mjs and platsim bench --workers 16 (single process and pool, digests agreeing). No new policy name; v1 and v2 are replaced in place (Constitution Principle VI). Any sim/ edit changes sim_code_hash so earlier checkpoints will not resume. Keep it to the three items; the matchupScore/damageOutcomes memo, the interpreter argument index and the K() hoisting stay in FUTURE-FEATURES section 7, and the expectimax2-v4 approximations are the following feature."

## Context

Feature 015 (merged 2026-11-01) made the battle player `expectimax2-v2` 2.02x faster as a single process with
byte-identical decisions, by building the damage-formula inputs once per state and resolving game constants
once. The re-profile taken right after the merge, on the same fixed set and with the same harness (evidence in
`runs/015-evidence/scratchpad/prof2/REPORT2.md`; the hooked run reproduces the `main` digest, so the
measurement changes nothing), shows the next three waste items:

| Measure (main 19519ed, single process, 20 gauntlets x 2 fixture teams, seeds `prof-a-*`) | Value |
|---|---|
| Throughput, expectimax2-v2 | 0.779 gauntlets/s, 18.3 ms per decision |
| Throughput, greedy-v1, same seeds | 9.07 gauntlets/s |
| Trainer-AI calls per decision | 44.7 (root 16.6%, second ply 83.4%; unchanged by 015) |
| Share of time running the trainer AI on hypothetical states | 50.7% (was 72% before 015) |
| Working out a move's type effectiveness | 12.9% of all time, plus 4.8% preparing the same facts |
| ... how often, in the player's damage table | 32 identical chart walks per table entry (16 damage rolls, normal and critical) |
| ... how often, in the trainer AI's damage check | once per move per sample, identical for all samples on one state |
| Trainer-AI base damage (before the damage roll) | recomputed per sample on identical inputs |
| Rebuilding the game-identifier translation for each hypothetical-state view | 3.8% of all time; about 55,000 views per 40 gauntlets, each starting cold |

All three are pure waste. The type-effectiveness evaluation reads only the attacker, the defender, the move and
the field, plus whether the damage is zero; it never reads the damage value, so one evaluation serves every
damage roll. The trainer AI's base damage on a given state is the same for every sample taken on that state;
only the sample's own damage roll differs. The translation from the battle engine's identifiers to the game's
numbers is a fixed table of the game data, the same for every view and every battle.

This feature removes that waste and nothing else. It is an exact speedup under Constitution Principle VI:
`expectimax2-v1` and `expectimax2-v2` stay the references and are improved in place, with the existing replay
test (feature 015) proving their decisions did not change. The remaining exact items from the re-profile
(the replacement heuristic's memo, the interpreter's argument lookup, hoisting the constant lookups) and the
approximations that change decisions (`expectimax2-v4`) are later features.

## Clarifications

### Session 2026-11-01

- Q: How should the randomized equivalence test for the type-effectiveness evaluation generate its matchups: from
  synthetic inputs built to hit every rule, from real game Pokemon and moves, or both? → A: Both: synthetic inputs
  over the damage port's own input shape for guaranteed coverage of every rule and the positive control, plus a
  real-data layer of at least 1,000 matchups drawn from the game's species, moves and items.
- Q: Where should the memo-versus-recompute control for the shared base damage run: in the default Node suite on
  the full fixed set, in the default suite on a short subset with the full set as a recorded opt-in gate, or only
  as an opt-in run? → A: The default suite runs a short control (one battle per policy); the full 40-gauntlet
  control is an opt-in run switched on by an environment variable (the feature-015 freeze-guard pattern),
  required and recorded for the merge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Type effectiveness is worked out once per matchup (Priority: P1)

A user runs an optimization or a gauntlet with `expectimax2-v2` (or `-v1`). Wherever the player or the trainer
AI computes damage for one attacker, defender, move and field, the type-effectiveness evaluation (the chart
walk, the resulting status flags such as immune, super effective, not very effective, and the ability and item
adjustments that follow from them) is worked out once and then replayed for each damage roll, instead of
repeated per roll. Every roll's damage and every status flag is identical to what the repeated evaluation
produced.

**Why this priority**: Largest item in the re-profile (17.7% of all time including the preparation it repeats),
exact by construction: the evaluation does not read the damage value.

**Independent Test**: Replay the fixed seed set with only this change applied and compare every result and
every player choice with the unchanged fixture. Separately, generate many random matchups covering every
branch of the evaluation and check that the single evaluation replayed per roll gives the same damage and the
same status flags as the per-roll evaluation, for every roll; a deliberately altered replay must be detected.

**Acceptance Scenarios**:

1. **Given** the replay fixture (result digests `db6d20cf…` for v2 and `1273b694…` for v1, every player choice
   and the trainer-AI draw count inside every decision for the 40 gauntlets), **When** the same 40 gauntlets run
   with this change, **Then** the digests, every choice and every draw count match.
2. **Given** at least 10,000 synthetic matchups (random attacker, defender, move and field facts in the damage
   port's input shape, with the real type chart and move data) that between them exercise immunities, Levitate
   and Magnet Rise, Wonder Guard, Filter and Solid Rock, the super-effective boosting item, Tinted Lens,
   same-type bonus with and without Adaptability, Foresight and Scrappy, Normalize, a type override, the
   "ignore type checks" mode, zero damage and the Struggle early exit, plus at least 1,000 real-data matchups
   (random game species, moves, items and stages), **When** each matchup is evaluated both ways for all 16
   damage rolls, with and without a critical hit, **Then** 0 mismatches in damage or status flags.
3. **Given** the same generated matchups, **When** one step of the replayed evaluation is deliberately altered
   (positive control), **Then** the comparison reports mismatches.
4. **Given** one entry of the player's damage table, **When** the type-effectiveness evaluations are counted,
   **Then** the count is a small constant independent of the number of damage rolls (today 32).

---

### User Story 2 - The trainer AI's base damage is computed once per matchup per decision (Priority: P1)

A user runs the same optimization. When the player samples the trainer AI several times on one hypothetical
state, the AI's base damage for a given attacker, defender and move (everything before the sample's own damage
roll is applied) is computed once for that state and shared by every sample; each sample then applies its own
roll. The live opponent AI gets the same treatment within one of its decisions, and forgets it when the decision
is made, exactly as the inputs it was given in feature 015.

**Why this priority**: Second item in the re-profile (the trainer AI's damage check is 19.2% of all time, most of
it repeated per sample); exact because the samples differ only in their random draws, which are applied after
the shared part.

**Independent Test**: Replay the fixed seed set with only this change applied; the fixture matches. A control
mode recomputes the base damage on every use and compares it with the remembered value, reporting any
difference; the count of base-damage computations per decision must be independent of the number of samples.

**Acceptance Scenarios**:

1. **Given** the replay fixture, **When** the 40 gauntlets run with this change, **Then** the digests, every
   choice and every draw count match.
2. **Given** the control mode switched on for the fixed set (opt-in run, recorded in the validation log before
   the merge), **When** every remembered base damage is compared with a fresh computation, **Then** 0
   differences; and the default Node suite runs the same control on one battle per policy on every run.
3. **Given** one hypothetical state and K samples of the trainer AI on it, **When** base-damage computations are
   counted, **Then** each attacker-defender-move combination is computed once for that state, not once per sample.
4. **Given** a battle in which a Pokemon's stats, types, ability or item change between two of the opponent's
   decisions, **When** the live opponent AI decides, **Then** it uses the current facts (the existing opponent-AI
   fixture and golden tests pass unchanged).
5. **Given** every remembered value frozen (the feature-015 freeze guard extended to the new caches), **When**
   the replay and the AI tests run, **Then** they pass: nothing writes into a remembered value.

---

### User Story 3 - The identifier translation is built once and shared (Priority: P2)

A user runs the same optimization. The table that translates the battle engine's move, ability, item, species
and type identifiers into the game's numbers is built once for a given set of game data and shared by every
hypothetical-state view and every battle, instead of being rebuilt from scratch for each of the tens of
thousands of views a run creates.

**Why this priority**: Third item (3.8% of all time, plus the allocation it causes); trivially exact, since the
translation is a fixed property of the game data.

**Independent Test**: Replay the fixed seed set with only this change applied; the fixture matches. For every
identifier the engine knows, the shared table gives the same number as a freshly built one.

**Acceptance Scenarios**:

1. **Given** the replay fixture, **When** the 40 gauntlets run with this change, **Then** the digests, every
   choice and every draw count match.
2. **Given** every move, ability, item, species and type identifier the battle engine knows for the game's
   generation, **When** translated through the shared table and through a freshly built one, **Then** the
   numbers are equal, and an unknown identifier is rejected the same way in both.
3. **Given** two views created on the same game data, **When** they translate identifiers, **Then** they use the
   same table (no cold start for the second view).

---

### User Story 4 - The speedup is measured and recorded (Priority: P2)

A user can read how much faster the player is on the same seeds, before and after, as a single process and on
the 16-worker pool the optimizer uses, using the benchmark tool shipped with feature 015.

**Why this priority**: Principle VI requires the run times of both versions in the validation log; the before
figures already exist (015's after figures) and the tool is in place.

**Independent Test**: Run the benchmark tool on `main` and on the branch under identical conditions and record
gauntlets/s and ms per decision (single process) and wall time and gauntlets/s (16-worker pool), with the
single-process and pool digests agreeing on both sides.

**Acceptance Scenarios**:

1. **Given** the 40-gauntlet set run as one process on `main` and on the branch, **When** timed, **Then**
   gauntlets/s and ms per decision for both are in the validation log, with the ratio, for v2 and v1.
2. **Given** the same gauntlets run through the 16-worker pool on both sides, **When** timed, **Then** wall time
   and gauntlets/s for both are in the validation log, with the ratio, and the pool digest equals the
   single-process digest on each side.

---

### Edge Cases

- Zero damage entering the type-effectiveness evaluation: the multiplier steps are skipped for zero damage in
  the game, so the replayed evaluation must keep that rule per roll (a roll can be zero only when the base is
  zero, but the rule is kept, not assumed away).
- Struggle leaves the evaluation before any step; a replayed evaluation must return the input damage unchanged
  with no flags.
- "Ignore type checks" mode (fixed-damage moves in the trainer AI) skips the multipliers and clears the
  effectiveness flags at the end; the replayed evaluation does the same.
- Normalize and a type override change the move's type before the chart is consulted; both are inputs to the
  evaluation, so they select a different evaluation, never a shared one.
- Foresight or Scrappy stop the chart walk before the ghost immunities; a Pokemon with two identical types is
  checked once; Levitate suppressed by Gravity, Ingrain, Gastro Acid or Mold Breaker; the grounding item: all are
  inputs the evaluation already reads, so they are part of what identifies an evaluation.
- Critical hits: the base damage differs but the type-effectiveness evaluation is the same for the normal and
  the critical table of one matchup; sharing it between the two is exact.
- A remembered base damage must be shared only between samples on the same state within one decision; the live
  opponent AI's remembered values are discarded at each decision boundary (the feature-015 rule), so a change
  between turns is seen fresh.
- Two hypothetical states that differ in a fact the damage formula reads are different inputs and get their
  own values; sharing across states is out of scope.
- The trainer AI's random draws (damage-roll variance, speed ties, score randomization) must occur in the same
  order and number; the shared parts contain no draws, and the draw count per decision is checked.
- The identifier translation depends on the game data set in use (the decomp root and the engine's data); a
  different data set gets its own table. An identifier with no game counterpart is rejected the same way as
  before.
- Memory: the translation table is bounded by the number of identifiers in the game data; remembered base
  damages are released with the decision.
- Any edit under `sim/` changes the sim code hash, so optimizer checkpoints written before the change will not
  resume (expected; stated in the plan). `data/generated/` needs no rebuild for this feature unless the extractor
  changes, which it does not.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every seed, `expectimax2-v1` and `expectimax2-v2` MUST produce byte-identical gauntlet results
  to `main` 19519ed: on the fixed set (20 gauntlets x `policy_benchmark_team` and `reference_team`, seeds
  `prof-a-<team>-<i>`, all five League trainers, stop_on_loss off) the full-result digests MUST equal
  `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` (v2) and
  `1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178` (v1), every player choice MUST equal the
  recorded one, and the trainer-AI draw count inside every decision MUST equal the recorded one.
- **FR-002**: The replay fixture from feature 015 MUST be used unchanged (not re-recorded); the existing replay
  test is the acceptance test for FR-001 and stays in the default Node suite.
- **FR-003**: The live opponent AI (`decomp-ai`) MUST be unchanged in behaviour: the existing opponent-AI
  fixture and golden tests pass, and the recorded per-decision draw counts match (FR-001).
- **FR-004**: The type-effectiveness evaluation for one attacker, defender, move and field MUST be performed once
  and replayed for each damage roll, and the replayed result (damage and status flags) MUST equal the per-roll
  evaluation for every input: a randomized equivalence test over at least 10,000 synthetic matchups (the damage
  port's input shape, every flag and ability drawn independently, real type chart and move data) covering the
  conditions listed in User Story 1, plus at least 1,000 matchups drawn from real game species, moves, items and
  stages, with a positive control showing an altered replay is detected.
- **FR-005**: Within one decision, the trainer AI's base damage for one attacker, defender and move on one state
  MUST be computed at most once and shared by every sample on that state; a control mode, switched on by an
  environment variable like the feature-015 freeze guard, MUST compare every shared value with a fresh computation
  and report differences. The default Node suite MUST run that control on one battle per policy; the full fixed
  set under the control is an opt-in run that MUST be recorded in the validation log before the merge.
- **FR-006**: Anything remembered for the live opponent AI MUST be discarded at the end of each decision (the
  feature-015 rule extended to the new values).
- **FR-007**: Nothing MUST write into a remembered value after it is created: the feature-015 freeze guard MUST
  cover the new caches, and the replay and AI tests MUST pass with it on.
- **FR-008**: The translation from battle-engine identifiers to game numbers MUST be built once per set of game
  data and shared by every view and battle on that data; every identifier MUST translate to the same number as
  a freshly built translation, and unknown identifiers MUST be rejected as before.
- **FR-009**: The player's search MUST be unchanged: same sample counts, same beam, same evaluation, same
  registered policy names; no new policy is added.
- **FR-010**: The vendored Showdown tree MUST NOT be edited.
- **FR-011**: Run time MUST be measured before and after on the same seeds with the committed benchmark tool and
  recorded in the validation log: gauntlets/s and ms per decision as a single process (v2 and v1), wall time and
  gauntlets/s through the 16-worker pool, and the single-process and pool digests, which MUST agree on each side.
- **FR-012**: The Node test suite, fast mode (`not battle_sim`) and, before merge, the full pytest suite MUST
  pass, with their output recorded.
- **FR-013**: Scope is the three items above. The replacement heuristic's memo, the interpreter's argument lookup
  and the hoisting of the remaining constant lookups MUST stay in FUTURE-FEATURES section 7; the
  decision-changing approximations (`expectimax2-v4`) are the following feature.

### Key Entities

- **Type-effectiveness evaluation**: the outcome of consulting the type chart and the related ability and item
  rules for one attacker, defender, move and field: the ordered multiplier steps and the status flags. A pure
  function of those four inputs; applied to a damage value by replaying the steps.
- **Base damage**: the trainer AI's damage for one attacker, defender and move on one state before the sample's
  damage roll; a pure function of the state, shared by the samples on that state within one decision.
- **Identifier translation**: the mapping from the battle engine's move, ability, item, species and type
  identifiers to the game's numbers; a fixed property of one set of game data.
- **Decision**: one player or opponent choice; the unit after which remembered live-battle values are discarded
  (feature 015).
- **Replay fixture**: the recorded digests, player choices and per-decision draw counts of the fixed seed set
  (feature 015), unchanged by this feature.
- **Benchmark tool**: the project command from feature 015 that replays the fixed set with a named policy and
  reports throughput, ms per decision and the digests, as a single process and through the worker pool.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fixed 40-gauntlet set, 0 differences from the replay fixture for both `expectimax2-v1` and
  `expectimax2-v2`: digests equal, 0 of the roughly 2,850 (v2) and 3,300 (v1) player choices differ, and the
  trainer-AI draw count inside every decision is equal (the player's predictions draw 849,962 times for v2 and
  1,206,240 for v1 over the set; the live opponent 19,168 and 22,060).
- **SC-002**: The player is at least 1.2x faster as a single process on the same seeds (gauntlets/s on the
  fixed set, 0.779 for v2 on `main`; the profile shares suggest about 1.25x to 1.35x). A smaller gain is
  reported, not hidden.
- **SC-003**: The 16-worker wall time on the same gauntlets is reported for both sides with the ratio, with
  single-process and pool digests agreeing on each side.
- **SC-004**: The randomized equivalence test reports 0 mismatches over at least 10,000 synthetic matchups and
  at least 1,000 real-data matchups, each x 16 rolls x normal and critical, with each listed condition exercised
  at least 100 times in the synthetic layer, and its positive control detects an altered replay.
- **SC-005**: The control mode for the shared base damage reports 0 differences on the full fixed set (opt-in
  run, recorded) and on the one-battle-per-policy control in the default suite, and the frozen run passes every
  replay and AI test.
- **SC-006**: All existing tests pass: Node suite (326 tests today), fast mode (528 passed, 4 xfailed today) and,
  before merge, the full suite (556 passed, 4 xfailed today).

## Assumptions

- The re-profile on `main` 19519ed is representative: two seed blocks agree to within 0.3 points on every
  category, and its counters equal the pre-015 profile's, as an exact change requires.
- The type-effectiveness evaluation reads only the attacker, defender, move and field, plus whether the damage
  is zero. This was established by reading the port and the game's source it cites; the randomized equivalence
  test (FR-004) is the proof, not the reading.
- The inputs shared within a decision are immutable once built (the feature-015 invariant, checked by its
  freeze guard); the new shared values rely on the same invariant and are covered by the same guard (FR-007).
- The feature-015 replay fixture is still the right reference: 015 was exact, so the digests recorded at its
  instrumentation commit equal `main` 19519ed's, as the 015 validation log and the 2026-11-01 re-profile show.
- The benchmark tool from feature 015 is the measurement; no new tooling is needed. The "before" figures are
  015's "after" figures, re-measured on `main` at the time of the comparison for identical conditions.
- The expected gain (about 20 to 25% of time, roughly 1.25x to 1.35x) is an estimate from profile shares, not a
  measurement; SC-002 sets the bar below it.
- Numbering: this feature takes 016, so the decision-changing approximations (`expectimax2-v4`) become 017 and
  the held-items work H4 follows them (the user's 2026-10-30 numbering shifted by one).
