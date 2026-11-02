# Feature Specification: Exact Dispatch, Damage-Input and Speed Speedups for expectimax2 (round three)

**Feature Branch**: `017-exact-dispatch-speedups`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Exact expectimax2 speedups, round three (post-016 profile, runs/016-evidence/scratchpad/prof3/REPORT3.md). The player policy expectimax2-v2 (and v1) must make byte-identical decisions: the replay test sim/test/replay.test.mjs against the unchanged fixture (digest db6d20cf... for v2, 1273b694... for v1, every p1 choice, every per-decision draw count) stays green after every commit, plus the determinism and AI golden tests; no change under pokemon-showdown/. Three user stories, each an independent commit with its own attribution measurement on the fixed set (node sim/bench.mjs --policy expectimax2-v2, then uv run platsim bench --workers 16): US1 Interpreter effect dispatch. The trainer-AI interpreter executes 143 M instructions per bench run, 128 M of them IfCurrentMoveEffectEqualTo, in two contiguous runs of 178 and 152 instructions in script.s (no jump lands inside a run; one effect value repeats within a run, first match wins). At parse time, fuse each run into one lookup (current move's effect -> the first matching jump target, else the instruction after the run) and pre-resolve the by-name argument lookup (ctx.arg's linear find) into per-instruction fields. Exact: the fused instructions read only the current move's effect and have no side effects; the live opponent AI uses the same interpreter and must produce the same choices and draw counts (replay fixture records them). US2 Policy damage inputs memoised per decision. damageTable builds the damage-formula inputs with fromShowdown on the live battle for every table miss (141 k calls, 677 k battlerFromShowdown builds, each running Showdown's Type / Ability / Item events on a live mon); the live battle does not change during a decision, so cache the battler and field structs per live mon per decision (the 016 adapter's damageInput memo already does this for the AI) and copy before the policy's fix() mutates them. 55% of the misses come from matchupScore. US3 One speed comparison per view. The AI's speedValuesNow runs compareBattlerSpeed once per sample (127 k) and the policy's speedInfo once per resolveTurn (247 k calls, 79% view hits, each paying a signature string), while the result depends only on the view (54,779 views). Compute the speed pair once per view and share it (battlerSpeed(b) is order-independent, both callers pass rand () => 0), and call speedInfo once per state instead of inside the (action, opponent action) loops. Success: single-process gauntlets/s on the fixed set at least 1.15x the same-session main measurement (main today: 1.019 gauntlets/s, 12.4 ms/decision), 16-worker pool faster, digests and draw counts identical; Node suite, fast mode, then the full suite before the merge (merge rule). Out of scope (next feature): Constants.get hoisting (~320 sites, 6.3%), damageOutcomes memo (66% repeats of 2.8%), skipping the merge signature for single-branch turns (21% of calls, 0.5%); killed: matchupScore memo (0 repeated keys in 12,269 calls)."

## Context

Features 015 and 016 (merged 2026-11-01) made the battle player `expectimax2-v2` about 2.7x faster as a single
process on the fixed set with byte-identical decisions. The re-profile taken on `main` f67ff1e on 2026-11-02, on
the same fixed set and with the same harness (`runs/016-evidence/scratchpad/prof3/REPORT3.md`; the hooked run
reproduces the `main` digest, so the measurement changes nothing), shows the next three waste items:

| Measure (main f67ff1e, single process, 20 gauntlets x 2 fixture teams, seeds `prof-a-*`) | Value |
|---|---|
| Throughput, expectimax2-v2 (benchmark tool, alone) | 1.019 gauntlets/s, 12.4 ms per decision |
| Trainer-AI calls per decision | 44.7 (unchanged since the first profile) |
| Share of time running the trainer AI on hypothetical states | 45.8% |
| Trainer-AI script interpretation | 10.7% of all time; 143 million script instructions per run, 1,124 per AI call |
| ... of which one instruction kind, "is the current move's effect X?" | 128 million (89.7%), in two contiguous lists of 178 and 152 checks in the game's script, plus eleven short ones |
| Building the player's damage-formula inputs from the live battle | 5.8% of all time; 141 thousand builds, 677 thousand live-Pokemon conversions, each firing the engine's type, ability and item events |
| ... distinct inputs actually needed | at most one per live Pokemon per decision: about 34 thousand |
| Working out which battler moves first | 7.2% + 2.4% of all time; 127 thousand times for the trainer AI (once per sample) and 247 thousand times for the player (once per hypothetical turn), for 54,779 distinct hypothetical states |

All three are pure waste. The game's script checks the current move's effect against a long list, one check
per step, and the checks have no side effects: the list can be answered in one step. The live battle does not
change while the player is deciding, so one conversion per live Pokemon serves the whole decision. Which
battler moves first depends only on the hypothetical state, not on which sample or which pair of actions is
being examined.

This feature removes that waste and nothing else. It is an exact speedup under Constitution Principle VI:
`expectimax2-v1` and `expectimax2-v2` stay the references and are improved in place, with the replay test
(feature 015) proving their decisions did not change. The remaining exact items from the re-profile (hoisting
the constant lookups, a memo for the damage-outcome buckets, skipping the merge signature for single-branch
turns) and the approximations that change decisions (`expectimax2-v4`) are later features.

## Clarifications

### Session 2026-11-02

- Q: Should the trainer AI's in-script speed comparison (the one that draws a random number on ties) also reuse
  the shared per-state speed values, keeping only the tie draw per sample, or stay fully per sample? → A: Share
  the speed values with the in-script comparison too; its tie draw stays per sample, and the equivalence test
  covers all three users of the values.
- Q: Should the interpreter step count that SC-004 relies on be reported by the committed benchmark tool, or
  only measured by the profiling harness in the scratchpad? → A: The committed benchmark tool reports the
  interpreter step count per run; SC-004 is checked from that output (a plain per-step counter, measured at
  under 1% of run time even at today's 143 million steps).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The trainer AI answers a list of effect checks in one step (Priority: P1)

A user runs an optimization or a gauntlet with `expectimax2-v2` (or `-v1`), or any battle against the live
`decomp-ai` opponent. Wherever the game's trainer-AI script compares the current move's effect against a list
of effects one by one, jumping to a different place for each match, the interpreter finds the answer in one
step: the first matching entry's destination, or the instruction after the list when nothing matches. Every
decision, every score and every random draw the trainer AI makes is identical to the step-by-step version.

**Why this priority**: Largest item in the re-profile (about 10% of all time) and shared by the live opponent
AI; exact by construction, since the checks read only the current move's effect and change nothing.

**Independent Test**: Replay the fixed seed set with only this change applied and compare every result, every
player choice and every per-decision draw count with the unchanged fixture. Separately, for every list in the
script and every possible effect value, check that the one-step answer equals the step-by-step answer; a
deliberately altered entry must be detected.

**Acceptance Scenarios**:

1. **Given** the replay fixture (result digests `db6d20cf…` for v2 and `1273b694…` for v1, every player choice
   and the trainer-AI draw count inside every decision, for the player's predictions and for the live
   opponent), **When** the same 40 gauntlets run with this change, **Then** the digests, every choice and every
   draw count match.
2. **Given** every list of consecutive effect checks in the game's script (today 13 lists: 178, 152, 5, 5, 5, 5,
   4, 3, 2, 2, 1, 1 checks long) and every effect value the game defines (277 values) plus a value that matches
   nothing, **When** each is answered in one step and by stepping through the list, **Then** the destinations
   are equal for every pair, including the one list in which an effect value appears twice (the first entry
   wins).
3. **Given** the same lists, **When** one entry's destination is deliberately altered (positive control), **Then**
   the comparison reports a mismatch.
4. **Given** a script in which a jump lands inside a list (not at its first check), **When** the lists are
   prepared, **Then** that list is not answered in one step from that entry point: it is either left to
   step-by-step evaluation or split at the landing point, and a test with such a script proves it. (Today's
   script has no such jump; the preparation checks this rather than assumes it.)
5. **Given** the existing trainer-AI golden fixtures (score additions with their script lines, choices and
   draws), **When** they run, **Then** they pass unchanged.
6. **Given** one bench run of the fixed set, **When** the benchmark tool reports the interpreter's step count,
   **Then** fewer than 20 million (today 143 million), with the per-decision count independent of the length of
   the lists.

---

### User Story 2 - The player converts each live Pokemon once per decision (Priority: P1)

A user runs the same optimization. When the player builds the damage-formula inputs for a hypothetical state,
the facts it takes from the live battle for a given Pokemon (species, level, stats, types, ability, item and
the rest) are converted once per decision and reused for every hypothetical state and every damage table that
needs them; the per-state facts (HP, status, stat stages, item, whether the Pokemon is freshly switched in) are
applied on a copy, never on the shared conversion. The live opponent AI already works this way (feature 016);
the player's own damage tables now do too.

**Why this priority**: Second item (5.8% of all time, 677 thousand conversions for about 34 thousand distinct
ones); exact because the live battle does not change during a decision, and the player overrides the
state-dependent facts itself.

**Independent Test**: Replay the fixed seed set with only this change applied; the fixture matches. A control
mode compares every reused conversion with a fresh one on every use and reports any difference; the
frozen-cache run proves nothing writes into a reused conversion; the count of live conversions per decision is
at most one per live Pokemon plus one per side.

**Acceptance Scenarios**:

1. **Given** the replay fixture, **When** the 40 gauntlets run with this change, **Then** the digests, every
   choice and every draw count match.
2. **Given** the control mode switched on for the fixed set (opt-in run, recorded in the validation log before
   the merge), **When** every reused conversion is compared with a fresh one, **Then** 0 differences; and the
   default Node suite runs the same control on one battle per policy on every run.
3. **Given** every reused conversion frozen (the feature-015 freeze guard), **When** the replay and the AI tests
   run, **Then** they pass: the player's per-state adjustments land on copies.
4. **Given** one decision of the player on the fixed set, **When** live-Pokemon conversions are counted, **Then**
   at most one per live Pokemon and one field conversion per side, however many hypothetical states and damage
   tables the decision examines (today up to several hundred).
5. **Given** a battle in which a Pokemon's live types, ability or item change between two of the player's
   decisions, **When** the player decides, **Then** it uses the current facts (the conversions are discarded at
   the end of every decision).

---

### User Story 3 - Who moves first is worked out once per hypothetical state (Priority: P2)

A user runs the same optimization. For each hypothetical state the player examines, the two battlers' speeds
and who moves first are worked out once and shared by everything that needs them on that state: the player's
turn resolution for every pair of actions it tries, every trainer-AI sample taken on that state, and the trainer
AI's own in-script speed comparison, which keeps only its tie-breaking random draw per sample. Today the
trainer-AI samples each compute it again, and the player computes it again for every pair of actions.

**Why this priority**: Third item (about 7% of all time plus 2.4% of state lookups caused by it); exact because
the speed values depend only on the state, and the only random draw (the in-script tie break) happens after the
values are known and stays per sample.

**Independent Test**: Replay the fixed seed set with only this change applied; the fixture matches. For many
hypothetical states, the shared speed values equal the values each of the three users computed on its own
before this change, including states where an active Pokemon has fainted; the count of speed computations per
state is at most one.

**Acceptance Scenarios**:

1. **Given** the replay fixture, **When** the 40 gauntlets run with this change, **Then** the digests, every
   choice and every draw count match.
2. **Given** at least 1,000 hypothetical states drawn from real battles on the fixed set (including states with
   stat stages, paralysis, speed-changing items and abilities, weather, and a fainted active on either side),
   **When** the speeds and the first mover are computed the shared way and the three original ways (the player's
   turn resolution, the trainer AI's speed memory, the trainer AI's in-script comparison), **Then** the values are
   equal in every case, and the in-script comparison's result and its tie-break draws are unchanged.
3. **Given** one hypothetical state and K trainer-AI samples plus every pair of actions the player tries on it,
   **When** speed computations are counted, **Then** at most one on that state; the trainer AI's in-script speed
   comparison reuses the values and keeps only its tie-breaking random draw per sample.
4. **Given** the trainer-AI draw counts recorded in the fixture, **When** the gauntlets run, **Then** every
   per-decision count is equal (no draw is added or removed by sharing).

---

### User Story 4 - The speedup is measured and recorded (Priority: P2)

A user can read how much faster the player is on the same seeds, before and after, as a single process and on
the 16-worker pool the optimizer uses, using the benchmark tool shipped with feature 015, with each story's
contribution measured on its own commit.

**Why this priority**: Principle VI requires the run times of both versions in the validation log; the before
figures exist (today's `main` measurement) and the tool is in place.

**Independent Test**: Run the benchmark tool on `main` and on the branch under identical conditions and record
gauntlets/s and ms per decision (single process) and wall time and gauntlets/s (16-worker pool), with the
single-process and pool digests agreeing on both sides, and the single-process figure after each story's commit.

**Acceptance Scenarios**:

1. **Given** the 40-gauntlet set run as one process on `main` and on the branch, **When** timed, **Then**
   gauntlets/s and ms per decision for both are in the validation log, with the ratio, for v2 and v1, and the
   single-process v2 figure after each of the three story commits.
2. **Given** the same gauntlets run through the 16-worker pool on both sides, **When** timed, **Then** wall time
   and gauntlets/s for both are in the validation log, with the ratio, and the pool digest equals the
   single-process digest on each side.

---

### Edge Cases

- A list in which the same effect value appears twice: the first entry's destination is the answer (today one
  such repeat exists). An effect value absent from a list: evaluation continues at the instruction after the
  list. A list of one check: answered the same way or left as is, with the same result.
- A jump that lands inside a list (none in today's script): the one-step answer must not be used from that
  entry point (User Story 1, scenario 4). The preparation step checks the script, so a future script change
  cannot silently break this.
- The interpreter's step limit (a guard against a non-terminating script) counts the one-step answer as one
  step; the limit is a safety guard, not game behaviour, and no test depends on the exact count.
- Traces: the trainer-AI golden fixtures record score additions with their script lines and must be unchanged.
  The optional per-instruction trace may show one entry for a list instead of one per check; the plan records
  the choice and no committed fixture depends on it.
- The trainer AI has two copies of the interpreter loop (the plain one and the tracing one used by the golden
  tests); both must give the same answers and both must use the one-step dispatch, or the tracing copy must be
  shown to be used only by tests.
- Argument lookup: an instruction still fails loudly when asked for an argument it does not have (same error
  as today); the by-name lookup keeps working for every handler, including the ones that read a jump target.
- Live-Pokemon conversions are shared only within one decision of the player; a Pokemon whose live types
  (Roost), ability (Trace, Skill Swap) or item changed between decisions is converted afresh (User Story 2,
  scenario 5). Within one decision the live battle does not change; the freeze guard proves nothing writes into
  a shared conversion.
- A freshly switched-in hypothetical Pokemon (the player's "fresh" rule resets stages, volatile flags and
  types): applied on the copy, as today; the shared conversion keeps the live facts.
- The replacement heuristic's damage tables (55% of today's misses) use the same shared conversions; they
  remain their own table entries (different stages and freshness), only the live conversion is shared.
- Speed sharing: a state in which an active Pokemon has fainted gives the same values as today on each path
  (the player records a half-and-half order with zero speeds; the trainer AI is never asked to decide for a
  fainted active, since a replacement is chosen first). A speed tie keeps today's half-and-half order. The
  random speed value used by the Quick Claw rule is fixed per decision, so it is part of the state's facts.
- The player asks who moves first in the middle of resolving a turn for one move's power (Gyro Ball): that
  question is about the partially resolved state and must keep seeing that state's facts, as today. "Once per
  state" means once per distinct set of state facts, never a stale answer for a state that has since changed.
- Draw counts: the shared speed values contain no random draws; the trainer AI's in-script speed comparison
  reuses the values and still draws its tie break per sample, in the same order; the recorded per-decision draw
  counts are the proof.
- Any edit under `sim/` changes the sim code hash, so optimizer checkpoints written before the change will not
  resume (expected; stated in the plan). `data/generated/` needs no rebuild for this feature unless the
  extractor changes, which it does not.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every seed, `expectimax2-v1` and `expectimax2-v2` MUST produce byte-identical gauntlet results
  to `main` f6d845c: on the fixed set (20 gauntlets x `policy_benchmark_team` and `reference_team`, seeds
  `prof-a-<team>-<i>`, all five League trainers, stop_on_loss off) the full-result digests MUST equal
  `db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3` (v2) and
  `1273b69462bcce8c690e020e9c9699412e1a3f40809d4d7b1a77ecc23d3c3178` (v1), every player choice MUST equal the
  recorded one, and the trainer-AI draw count inside every decision (the player's predictions and the live
  opponent) MUST equal the recorded one.
- **FR-002**: The replay fixture from feature 015 MUST be used unchanged (not re-recorded); the existing replay
  test is the acceptance test for FR-001 and stays in the default Node suite.
- **FR-003**: The live opponent AI (`decomp-ai`) MUST be unchanged in behaviour: the existing opponent-AI
  fixture and golden tests (score additions with script lines, choices, draws) pass unchanged, and the recorded
  per-decision draw counts match (FR-001).
- **FR-004**: Every list of consecutive "current move's effect equals X" checks in the trainer-AI script MUST be
  answered in one step with the destination the step-by-step evaluation would reach: a test MUST compare the
  two for every list and every defined effect value plus one undefined value, with a positive control showing an
  altered entry is detected; the preparation MUST verify that no jump lands inside a list and MUST handle a
  script where one does (scenario 4) without changing its behaviour.
- **FR-005**: Instruction arguments MUST remain available by name to every handler with the same values and the
  same error for a missing name; the lookup MUST no longer scan the argument list on every use.
- **FR-006**: Within one decision of the player, the live facts of a Pokemon used by the damage-formula inputs
  MUST be converted at most once and shared by every hypothetical state and damage table of that decision, with
  at most one field conversion per side; the per-state adjustments MUST be applied to copies. A control mode,
  switched on by the feature-016 environment variable, MUST compare every reused conversion with a fresh one and
  report differences; the default Node suite MUST run that control on one battle per policy, and the full fixed
  set under the control is an opt-in run that MUST be recorded in the validation log before the merge.
- **FR-007**: Nothing MUST write into a shared conversion after it is created: the feature-015 freeze guard MUST
  cover the shared conversions, and the replay and AI tests MUST pass with it on. Shared conversions MUST be
  discarded at the end of every decision.
- **FR-008**: For one hypothetical state, the battlers' speeds and the first mover MUST be computed at most once
  for the player's turn resolution, the trainer AI's speed memory and the trainer AI's in-script speed comparison
  together, and the shared values MUST equal the values each computed on its own before this feature, including
  states with a fainted active; the in-script comparison's tie-breaking random draw MUST stay per sample, in the
  same order (clarification 2026-11-02). A test over at least 1,000 real states MUST show equality for all three
  users.
- **FR-009**: The player's search MUST be unchanged: same sample counts, same beam, same evaluation, same
  registered policy names; no new policy is added.
- **FR-010**: The vendored Showdown tree MUST NOT be edited.
- **FR-011**: Run time MUST be measured before and after on the same seeds with the committed benchmark tool and
  recorded in the validation log: gauntlets/s and ms per decision as a single process (v2 and v1), the
  single-process v2 figure after each story's commit, wall time and gauntlets/s through the 16-worker pool, and
  the single-process and pool digests, which MUST agree on each side. The benchmark tool MUST also report the
  number of trainer-AI script instructions executed in the run (clarification 2026-11-02), before and after.
- **FR-012**: The Node test suite, fast mode (`not battle_sim`) and, before merge, the full pytest suite MUST
  pass, with their output recorded.
- **FR-013**: Scope is the three items above. Hoisting the remaining constant lookups, the damage-outcome bucket
  memo and skipping the merge signature for single-branch turns MUST stay in FUTURE-FEATURES section 7; the
  decision-changing approximations (`expectimax2-v4`) are a later feature; the replacement heuristic memo is
  recorded there as killed (0 repeated keys).

### Key Entities

- **Effect-check list**: a maximal run of consecutive script instructions that each compare the current move's
  effect with one value and jump on a match; answered as a whole by the first matching entry's destination or
  the instruction after the run. A property of the parsed script, prepared once.
- **Live conversion**: the damage-formula facts of one live Pokemon (and the field facts of one side) as the
  battle engine reports them at the start of a decision; shared read-only within the decision, discarded after.
- **Per-state adjustment**: the hypothetical state's HP, status, stat stages, item, screens and freshness,
  applied on a copy of a live conversion to form one damage table's inputs.
- **State speed facts**: the two active battlers' effective speeds and the resulting first mover for one
  hypothetical state; shared by the player's turn resolution, the trainer AI's speed memory and the trainer AI's
  in-script speed comparison on that state (the latter adds its own tie-break draw per sample).
- **Decision**: one player or opponent choice; the unit after which shared live values are discarded
  (feature 015).
- **Replay fixture**: the recorded digests, player choices and per-decision draw counts of the fixed seed set
  (feature 015), unchanged by this feature.
- **Benchmark tool**: the project command from feature 015 that replays the fixed set with a named policy and
  reports throughput, ms per decision, the digests and, from this feature, the interpreter step count, as a
  single process and through the worker pool.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fixed 40-gauntlet set, 0 differences from the replay fixture for both `expectimax2-v1` and
  `expectimax2-v2`: digests equal, 0 of the roughly 2,850 (v2) and 3,300 (v1) player choices differ, and the
  trainer-AI draw count inside every decision is equal (the player's predictions draw 849,962 times for v2 and
  1,206,240 for v1 over the set; the live opponent 19,168 and 22,060).
- **SC-002**: The player is at least 1.15x faster as a single process on the same seeds (gauntlets/s on the
  fixed set, 1.019 for v2 on `main` today, re-measured in the same session as the after figure; the profile
  shares suggest about 1.2x). A smaller gain is reported, not hidden.
- **SC-003**: The 16-worker wall time on the same gauntlets is reported for both sides with the ratio, with
  single-process and pool digests agreeing on each side.
- **SC-004**: The effect-check equivalence test reports 0 mismatches over every list x every defined effect
  value (277) plus an undefined value, and its positive control detects an altered entry; the benchmark tool
  reports fewer than 20 million interpreter steps per bench run of the fixed set (today 143 million, measured
  with the profiling harness; the tool's own before figure is recorded first).
- **SC-005**: The control mode for shared live conversions reports 0 differences on the full fixed set (opt-in
  run, recorded) and on the one-battle-per-policy control in the default suite; the frozen run passes every
  replay and AI test; live conversions per decision are at most one per live Pokemon plus one per side.
- **SC-006**: The speed-sharing equivalence test reports 0 differences over at least 1,000 real states for all
  three users of the values, and speed computations are at most one per hypothetical state.
- **SC-007**: All existing tests pass: Node suite (334 tests today), fast mode (528 passed, 4 xfailed today)
  and, before merge, the full suite (556 passed, 4 xfailed today).

## Assumptions

- The re-profile on `main` f67ff1e is representative: two seed blocks agree to within 2 points on every
  category, and its counters equal the earlier profiles' where those existed, as an exact change requires.
- The effect checks read only the current move's effect and have no side effects. This was established by
  reading the handler and the game's source it cites; the exhaustive equivalence test (FR-004) is the proof,
  not the reading.
- The live battle does not change while the player decides (the feature-015 invariant that the trainer AI's
  per-decision memos already rely on, checked by its freeze guard); the player's shared conversions rely on the
  same invariant and are covered by the same guard (FR-007).
- The speeds of the two battlers do not depend on the order in which the two are compared, and neither user of
  the shared values draws a random number for them; the equivalence test (FR-008) is the proof.
- The feature-015 replay fixture is still the right reference: 015 and 016 were exact, so the digests recorded
  at the 015 instrumentation commit equal today's `main` digests, as the 2026-11-02 health check shows.
- The benchmark tool from feature 015 is the measurement; the only addition is the interpreter step count in
  its report (clarification 2026-11-02), a plain per-step counter whose cost was measured at under 1% of run
  time at today's step count.
- The expected gain (about 15 to 19% of time, roughly 1.2x) is an estimate from profile shares, not a
  measurement; SC-002 sets the bar below it.
- Numbering: this feature takes 017, so the decision-changing approximations (`expectimax2-v4`, called 017 in
  FUTURE-FEATURES section 7 until now) become 018 and the held-items work H4 follows them.
