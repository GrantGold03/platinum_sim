# Feature Specification: Exact AI-Prediction Speedups for expectimax2-v2

**Feature Branch**: `015-exact-ai-speedups`

**Created**: 2026-10-30

**Status**: Draft

**Input**: User description: "Exact speedups for the expectimax2-v2 player policy: make the trainer-AI prediction cheaper without changing any decision. Profiling on main c751fb2 (20 gauntlets x 2 fixture teams, seeds prof-a-*) shows 72% of policy time is running the decomp trainer AI on hypothetical states; inside it, 36% of all time is converting Showdown Pokemon objects into damage-port inputs (fromShowdown / battlerFromShowdown in sim/damage.mjs, called four times per calcDamage, per move, per sample, including Pokemon.getTypes through Showdown's event system on the live battle), and 14.6% is string-keyed constants.get lookups, mostly effectIn in sim/ai/calcdamage.mjs resolving effect-table names on every call. Two changes: (1) memoise the battler and field structs per Pokemon per battle state inside the AI adapter, shared by all K samples on one shadow view and cleared per decision for the live opponent AI; (2) resolve constant tables and hot constant lookups in sim/ai to numbers once per adapter instead of per call. Both must be exact: expectimax2-v1 and -v2 produce byte-identical gauntlet results for identical seeds, and the live decomp-ai opponent is unchanged. Acceptance: a new Node test replays the fixed seed set (prof-a-*, 20 gauntlets x policy_benchmark_team and reference_team, all five trainers, stop_on_loss false) and matches the result digest db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3 recorded on main plus every p1 choice; the existing determinism test and the AI golden/fixture tests pass; the AI RNG draw count per decision is unchanged. Report gauntlets/s and ms/decision before and after on the same seeds (single process and 16 workers). Note: any sim/ edit changes sim_code_hash so earlier checkpoints will not resume; data/generated must be rebuilt after switching branches. No new policy name; v2 is replaced in place (Constitution Principle VI). Keep it to the two items; second-level damage memoisation and cross-decision caches are later features."

## Context

The optimizer spends nearly all of its run time in the battle player `expectimax2-v2`, which looks two turns
ahead and, at every hypothetical state, asks the game's own trainer AI (the decomp port under `sim/ai/`) what
the opponent would do. A B2 quick optimization took 1198 s on feature 014. Measured on `main` c751fb2
(2026-10-30, single process, 20 gauntlets x 2 fixture teams, seeds `prof-a-*`; evidence in
`runs/015-evidence/scratchpad/prof/REPORT.md`):

| Measure | Value |
|---|---|
| Throughput, expectimax2-v2 | 0.386 gauntlets/s, 34.2 ms per decision |
| Throughput, greedy-v1, same seeds | 6.75 gauntlets/s |
| Trainer-AI calls per decision | 44.7 (root 16.6%, second ply 83.4%) |
| Share of time running the trainer AI on hypothetical states | 72% |
| ... of which: rebuilding the damage-formula inputs from the battle state | 36% of all time |
| ... of which: looking up game constants by name on every use | 15% of all time |
| Cloning hypothetical states | 0.7% |
| Prediction cache hit rate (same state asked twice in one decision) | 0.35% |

The two large items are pure waste. Within one decision the battle state the AI reads does not change, yet the
inputs to the damage formula are rebuilt four times per damage calculation, per move, per sample, and the
constant tables are re-resolved from their names on every check. Removing that waste changes no result: the
same inputs produce the same numbers, so the AI picks the same moves and the player makes the same decisions.

This feature does only that. It is an exact speedup under Constitution Principle VI: `expectimax2-v2` stays
the reference and is improved in place, with a test that proves its decisions did not change. Approximations
that change decisions (fewer samples, pruning) are a separate feature with a new policy name.

## Clarifications

### Session 2026-10-30

- Q: Which of the profile's candidates are in scope? → A: Only the two exact items: memoised damage-formula
  inputs and pre-resolved constants (user, 2026-10-30). Second-level damage memoisation, caches that persist
  across decisions, and every decision-changing change are later features.
- Q: Replace v2 in place or register a new policy? → A: In place. The results must be byte-identical, so the
  registered names `expectimax2-v1` and `expectimax2-v2` keep their meaning (Principle VI).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The damage-formula inputs are built once per state (Priority: P1)

A user runs an optimization or a gauntlet with `expectimax2-v2`. While the player predicts the opponent, the
game-state facts the damage formula needs (a Pokemon's types, ability, item, stats, stages, status, volatile
conditions; the field's weather, screens and abilities in play) are derived once for each Pokemon in each
hypothetical state and reused by every move, every damage check and every sample evaluated on that state. The
live opponent AI gets the same treatment: its inputs are derived once per decision and discarded when the
decision is made, so a change between turns (a berry eaten, a type changed by Roost or Conversion, an ability
swapped) is always seen fresh.

**Why this priority**: It is the largest single cost in the profile (36% of all time) and it is exact by
construction.

**Independent Test**: Replay the fixed seed set with only this change applied and compare every result and
every player choice with the fixture recorded on `main`. Count how many times the inputs are derived per
decision before and after; the count must drop to a small multiple of the number of Pokemon and hypothetical
states, independent of the number of samples.

**Acceptance Scenarios**:

1. **Given** the fixture recorded on `main` (result digest `db6d20cf…` and every player choice for the 40
   gauntlets), **When** the same 40 gauntlets run with this change, **Then** the digest and every choice match.
2. **Given** a battle in which a Pokemon's types, ability or item change between two of the opponent's
   decisions, **When** the live opponent AI decides, **Then** it uses the current facts (its result equals the
   result of the unchanged code on the same battle, and the existing opponent-AI tests pass).
3. **Given** one hypothetical state and K samples of the trainer AI on it, **When** the inputs are counted,
   **Then** each Pokemon's inputs were derived once for that state, not once per sample per move.
4. **Given** a decision, **When** the trainer AI's random-number draws are counted, **Then** the count equals the
   count on `main` for the same decision.

---

### User Story 2 - Game constants are resolved once (Priority: P1)

A user runs the same optimization. The trainer AI's checks that compare a move's effect against the decomp's
effect tables, and its other hot constant lookups, use values resolved once when the AI is set up rather than
re-resolving the constant names on every call.

**Why this priority**: Second-largest waste item (15% of all time), very low risk: the resolved values are the
same numbers the name lookups return.

**Independent Test**: Replay the fixed seed set with only this change applied; the digest and every player
choice match the `main` fixture. Count name-based constant lookups during one decision before and after; after,
the count is bounded by a constant that does not grow with the number of samples or moves evaluated.

**Acceptance Scenarios**:

1. **Given** the `main` fixture, **When** the 40 gauntlets run with this change, **Then** the digest and every
   choice match.
2. **Given** the trainer AI set up for a battle, **When** the number of name-based constant lookups during one
   decision is counted, **Then** it does not grow with the number of samples or moves evaluated.
3. **Given** the existing opponent-AI tests (the decomp-trace fixtures and golden decisions), **When** run,
   **Then** they pass unchanged.

---

### User Story 3 - The speedup is measured and recorded (Priority: P2)

A user can read how much faster the player is, on the same seeds, before and after, as a single process and on
the 16-worker pool the optimizer uses, so later features (and the B2 end-to-end reference of 1198 s) have a
baseline.

**Why this priority**: The feature exists to save run time; Principle VI requires the run times of both versions
to be recorded in the validation log.

**Independent Test**: Run the fixed seed set on `main` and on the branch under identical conditions and record
gauntlets/s and ms per decision; run the same gauntlets through the 16-worker pool on both sides and record wall
time.

**Acceptance Scenarios**:

1. **Given** the 40-gauntlet set run as one process on `main` and on the branch, **When** timed, **Then**
   gauntlets/s and ms per decision for both are in the validation log, with the ratio.
2. **Given** the same gauntlets run through the 16-worker pool on both sides, **When** timed, **Then** wall
   time and gauntlets/s for both are in the validation log, with the ratio.

---

### Edge Cases

- A Pokemon whose types differ from its stored types during a turn (Roost) or across turns (Conversion, Color
  Change, form change): inputs are per state, and the live AI's are discarded after each decision, so the
  value in use is always the one the unchanged code would read at that moment.
- An item consumed or an ability suppressed mid-battle (berry eaten, Gastro Acid, Embargo): same rule; a stale
  value can only exist within one decision, where the state does not change.
- Two hypothetical states that are identical except for a fact the damage formula ignores: they are different
  states and get their own inputs; sharing between states is out of scope.
- The trainer AI's random draws (damage-roll variance, speed ties, score randomization) must occur in the same
  order and number; the changes touch only deterministic reads, and the draw count per decision is checked.
- A constant whose definition refers to another constant (recursive definitions in the decomp): resolving it
  once gives the same value as resolving it on every use.
- Memory: anything remembered for a decision is released when the decision ends, so a long gauntlet (up to the
  1000-turn limit per battle) does not grow memory with the number of turns.
- Any edit under `sim/` changes the sim code hash, so checkpoints written before the change will not resume
  (expected; stated in the plan). `data/generated/` must be rebuilt after switching branches.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every seed, `expectimax2-v1` and `expectimax2-v2` MUST produce byte-identical gauntlet results
  to `main` c751fb2: on the fixed set (20 gauntlets x `policy_benchmark_team` and `reference_team`, seeds
  `prof-a-<team>-<i>`, all five League trainers, stop_on_loss off) the full-result digest MUST equal
  `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` and every player choice MUST equal the
  recorded one.
- **FR-002**: The fixture for FR-001 (digest and the sequence of player choices per gauntlet) MUST be recorded
  from `main` before any behaviour change and committed with the test that checks it.
- **FR-003**: The live opponent AI (`decomp-ai`) MUST be unchanged in behaviour: the existing opponent-AI
  fixture and golden tests pass, and for every decision the number of AI random-number draws equals `main`'s.
- **FR-004**: The facts the damage formula reads for a Pokemon (and for the field) MUST be derived at most once
  per Pokemon per battle state per decision, and reused by every move, damage check and sample on that state.
- **FR-005**: Anything remembered for the live opponent AI MUST be discarded at the end of each decision, so
  the next decision reads the current battle.
- **FR-006**: Constant tables used by the trainer AI's move checks, and the other constant lookups on its hot
  path, MUST be resolved to values once per AI set-up; the number of name-based lookups during one decision
  MUST NOT grow with the number of samples or moves evaluated.
- **FR-007**: The player's search MUST be unchanged: same sample counts, same beam, same evaluation, same
  registered policy names; no new policy is added.
- **FR-008**: The vendored Showdown tree MUST NOT be edited.
- **FR-009**: Run time MUST be measured before and after on the same seeds and recorded in the validation log:
  gauntlets/s and ms per decision as a single process, and wall time with gauntlets/s through the 16-worker
  pool.
- **FR-010**: The Node test suite, fast mode (`not battle_sim`) and, before merge, the full pytest suite MUST
  pass, with their output recorded.

### Key Entities

- **Battle-state inputs**: the facts the damage formula reads for one Pokemon (types, ability, item, stats,
  stages, status, relevant volatile conditions) and for the field (weather, screens, abilities in play). Pure
  function of one battle state.
- **Hypothetical state**: a predicted battle position the player evaluates; the trainer AI is sampled on it
  several times. Immutable once built.
- **Decision**: one player or opponent choice; the unit after which remembered live-battle inputs are discarded.
- **Replay fixture**: the recorded digest and player choices of the fixed seed set on `main`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fixed 40-gauntlet set, 0 differences from the `main` fixture: digest equal, 0 of the
  roughly 2,850 player choices differ, for both `expectimax2-v1` and `expectimax2-v2`.
- **SC-002**: The player is at least 1.5x faster as a single process on the same seeds (gauntlets/s on the
  fixed set, 0.386 on `main`; the profile bounds the gain at about 2x). A smaller gain is reported, not hidden.
- **SC-003**: The 16-worker wall time on the same gauntlets is reported for both sides with the ratio.
- **SC-004**: All existing tests pass: Node suite (314 tests today), fast mode, and the full suite before merge.
- **SC-005**: The trainer AI's random draw count per decision is identical to `main` on the fixed set.

## Assumptions

- The profile on `main` c751fb2 is representative: two fixture teams, all five League trainers, two seed
  blocks agreeing to within 0.2 points on every category.
- Within one decision nothing changes the battle state the trainer AI reads; hypothetical states are built
  once and never modified afterwards. The plan verifies this by reading the code and the test checks the
  consequence (FR-001, FR-003).
- The replay test runs in the Node suite using worker threads, as the determinism test does, so it adds on the
  order of 15 to 30 s rather than the 100 s a single process needs. If it proves slower it stays in the suite
  and the time is reported.
- The 16-worker measurement uses the existing worker pool on the same 40 gauntlets; it is a report, not a
  pass/fail gate, because pool contention is not part of this feature.
- Local compute only: the measurements take minutes; the full suite before merge takes about 2 h 10 min.
- Feature size: two code items, one test fixture, one measurement; expected 2 to 3 stories and well under 30
  tasks. If the plan grows past that, it is split.
