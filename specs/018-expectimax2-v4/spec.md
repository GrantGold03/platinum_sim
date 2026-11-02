# Feature Specification: expectimax2-v4, a Cheaper Battle Player, Reference-First

**Feature Branch**: `018-expectimax2-v4`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "expectimax2-v4: a cheaper battle player, reference-first (Constitution Principle VI). Profile and sizing evidence: runs/017-evidence/scratchpad/prof4/REPORT4.md (appendix). Today expectimax2-v2 samples the trainer AI 8 times for the opponent's reply at the root and 2 times at every hypothetical second-ply state, searches the 2 best switch targets at the root, and expands every first-ply branch however unlikely; the trainer AI runs 44.7 times per decision and the root samples all agree only 52% of the time, the second-ply samples 71%. Add a NEW player policy expectimax2-v4 (never -v3, the archived 007 name) that keeps v2's model, leaf and horizon and changes only the search budget: second-ply samples 2 -> 1, switch beam 2 -> 1, root samples 8 -> 4, and a branch-probability floor under which a first-ply branch (opponent action probability x branch probability) is valued by the leaf instead of the second-ply search (measured: branches below 0.02 are 9.3% of the second-ply subtrees but 0.48% of the probability mass; below 0.05, 20.7% and 2.2%). Sized in memory on the fixed set (same 40 gauntlets as the 015-017 benchmarks, same seeds): second-ply 1 gives 1.25x, beam 1 1.22x, root 4 1.08x, floor 0.02 1.07x, floor 0.05 1.20x; second-ply 1 + beam 1 1.49x; all four with floor 0.02 1.75x (2.24 gauntlets/s, 4.9 ms/decision, 16.6 AI calls/decision). v1 and v2 stay unchanged: the 015 replay fixture is not re-recorded for them; v4 gets its own fixture entry once its parameters are final. Reference-first acceptance: v2 is the reference. Each knob is tried on its own first (speed and paired outcomes), then the combination; v4's final parameters are the fastest combination that is NOT worse than v2 by paired comparison: the same seeds and opponents for both policies (Principle IV), on the benchmark fixture team, the reference fixture team and the two 014 B2 final teams at fixed levels, 2,000 paired full gauntlets each, McNemar exact alpha 0.05 with no statistically supported drop in clear rate on any team, plus a pairing control (v2 against itself: 0 discordant). End to end: optimize B2 (quick budget, same seed) with v4 as the player and compare the result with the v2 result at equal levels (the 010 rule, as feature 014 did): no statistically supported drop, no higher expected average final level; optimizer wall time on both sides reported with the ratio. If the full combination fails, the best passing subset becomes v4 and the failing knobs are recorded with their numbers (Principle V: a negative result with the evidence). Only if v4 passes does it become the default player (optimizer level search, setup check, confirmation, evaluate, bench, web) with every report naming it; v2 remains available by name for comparisons and as the reference for later changes. Tests: determinism (same seed, same log) for v4; the policy-strength paired test covers v4 (not worse than greedy, and a short in-suite v4-vs-v2 pairing that must not show a significant drop); the AI golden tests and the live opponent are untouched. Speed: at least 1.5x v2 single process on the fixed set and faster on the 16-worker pool, measured with the committed benchmark tool; the default-player switch, if it happens, is measured on one optimizer run (B2 quick) end to end. Out of scope: the exact items D, F, E and H (FUTURE-FEATURES section 7), any change to the model, leaf, horizon or the trainer-AI port, and re-running the README headline optimization (the provenance names the policy; a re-run is a separate decision). Any sim/ edit changes sim_code_hash."

## Context

The battle player `expectimax2-v2` decides each turn by sampling the game's trainer AI to predict the opponent and
searching its own replies two plies deep. Three exact speedups (features 015 to 017) made that search 3.2x faster
without changing a single decision. What remains is mostly the search budget itself: how many times the trainer AI is
sampled, how many switch targets are searched, and how many unlikely branches are expanded. The 2026-11-02 profile and
sizing runs (`runs/017-evidence/scratchpad/prof4/REPORT4.md`, appendix) measured each budget knob on the fixed
40-gauntlet set by changing the parameters in memory:

| Measure (fixed set, 40 gauntlets, same seeds) | v2 today | Change tried alone | Speed | Cleared (sanity only, noise about ±3) |
|---|---|---|---|---|
| Trainer-AI samples for the opponent's reply at the root | 8 | 4 | 1.08x | 34/40 (36/40 for v2) |
| Trainer-AI samples at each second-ply state | 2 | 1 | 1.25x | 36/40 |
| Switch targets searched at the root | 2 best | 1 best | 1.22x | 37/40 |
| First-ply branches expanded | all | those above probability 0.02 (the rest valued by the leaf) | 1.07x | 36/40 |
| Same floor at 0.05 | all | above 0.05 | 1.20x | 37/40 |
| Second-ply 1 and beam 1 together | | | 1.49x | 36/40 |
| All four together, floor 0.02 | | | 1.75x (2.24 gauntlets/s, 4.9 ms per decision) | 39/40 |

The trainer AI runs 44.7 times per decision today; the root samples all agree only 52% of the time and the second-ply
samples 71%, so fewer samples change decisions in a sizeable share of positions. Branches below probability 0.02 are
9.3% of the second-ply subtrees but carry 0.48% of the probability mass (below 0.05: 20.7% and 2.2%).

These changes are approximations: they alter decisions, so Constitution Principle VI applies. `expectimax2-v2` stays
unchanged as the reference; the cheaper player is a new policy, `expectimax2-v4` (never `-v3`, the name of an
archived feature-007 policy), adopted only if paired comparison on the same seeds and opponents shows it is not
worse. Speed is not the risk; accuracy is, and the paired comparison is how it is judged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new, cheaper player that can be chosen by name (Priority: P1)

A user runs an evaluation, a benchmark or an optimization and names `expectimax2-v4` as the player. The policy uses
the same battle model, leaf valuation and horizon as `expectimax2-v2` and a smaller search budget: one trainer-AI
sample per second-ply state, one switch target searched at the root, four root samples, and first-ply branches below
a probability floor valued by the leaf instead of searched. Every result names the policy that played. `expectimax2-v1`,
`expectimax2-v2`, `greedy-v1` and the live opponent are untouched.

**Why this priority**: Everything else (the comparison, the default switch) needs the policy to exist and be
selectable; on its own it already gives users a 1.5x to 1.75x faster player to try.

**Independent Test**: Run the benchmark tool and one gauntlet with `expectimax2-v4` and with `expectimax2-v2`; the v4
run is faster, its decisions are deterministic for a seed, and the v2 run reproduces the 015 replay fixture unchanged.

**Acceptance Scenarios**:

1. **Given** the fixed 40-gauntlet set, **When** played with `expectimax2-v2` and `expectimax2-v1`, **Then** the 015 replay
   fixture matches (digests `db6d20cf…` and `1273b694…`, every choice, every per-decision draw count): v1 and v2 are
   unchanged.
2. **Given** the same set played with `expectimax2-v4`, **When** timed with the benchmark tool, **Then** it is at least
   1.5x `expectimax2-v2`'s single-process throughput measured in the same session, and faster on the 16-worker pool,
   and the single-process and pool digests agree.
3. **Given** one seed, **When** a gauntlet is played twice with `expectimax2-v4`, **Then** the battle logs are identical
   (determinism), and the live opponent's draw counts equal those recorded for the same positions.
4. **Given** the final parameters, **When** the fixed set is recorded, **Then** the replay fixture gains an
   `expectimax2-v4` entry (digests, choices, draw counts) that the replay test checks from then on, beside the
   unchanged v1 and v2 entries.
5. **Given** any evaluation, optimization or benchmark report, **When** v4 played, **Then** the report's provenance
   names `expectimax2-v4` (Constitution Principle IV).

---

### User Story 2 - v4 is proven not worse than v2 before it is trusted (Priority: P1)

Before anyone relies on the cheaper player, each budget change is tried on its own and then in combination, against
`expectimax2-v2` on the same seeds and opponents (paired evaluation), on four fixed teams: the benchmark fixture team,
the reference fixture team, and the two final teams the feature-014 B2 optimizations produced (the `main` side and
the branch side), each at its own fixed levels. `expectimax2-v4`'s final parameters are the fastest combination that
shows no statistically supported drop in clear rate on any of the four teams. The outcome, pass or fail, is recorded
with its numbers.

**Why this priority**: This is the Principle VI gate: an approximation is adopted only against a reference on paired
runs. Without it the speed is worthless.

**Independent Test**: For each candidate parameter set, 2,000 paired full gauntlets per team against `expectimax2-v2`
with the McNemar exact test at alpha 0.05, plus a pairing control (v2 against itself on the same seeds: 0 discordant
pairs). The validation log holds the table of candidates, teams, clear rates, discordant counts, p-values and the
verdicts.

**Acceptance Scenarios**:

1. **Given** v2 played against itself on the same 2,000 seeds of one team, **When** compared, **Then** 0 discordant
   pairs (the pairing control works).
2. **Given** one budget change alone (each of: second-ply samples 1, switch beam 1, root samples 4, the floor at 0.02
   and at 0.05), **When** played on the four teams, 2,000 paired runs each, **Then** its clear rate per team, the
   discordant counts, the p-value and the verdict (not worse / worse) are recorded, together with its speed on the
   fixed set.
3. **Given** the combinations in order of speed (all passing knobs together first, then smaller subsets), **When**
   played the same way, **Then** the fastest combination with "not worse" on all four teams is v4's final parameter
   set; if a knob is worse on any team, it is excluded and its numbers are kept in the log.
4. **Given** that no combination passes, **When** the ladder is exhausted, **Then** the feature records the negative
   result with its evidence and ships no default change (v4 may still exist by name, marked as not validated, or be
   withdrawn; the plan decides and the log says which).
5. **Given** the chosen parameters, **When** the fixed set is timed, **Then** the speed is at least 1.5x v2 (User
   Story 1, scenario 2); if the passing combination is slower than that, the smaller gain is reported, not hidden.

---

### User Story 3 - The optimizer end to end with v4 (Priority: P2)

A user optimizes the B2 benchmark input (six species) with `expectimax2-v4` as the player at the quick budget and the
same seed feature 014 used, and compares the result with the v2 result by the feature-010 equal-levels rule: both
final teams are played at the new team's start levels on the same seeds, 2,000 paired runs. The v4 result must not
clear significantly less and must not have a higher expected average final level; the optimizer's wall time on both
sides is reported with its ratio.

**Why this priority**: The paired gauntlets prove the player; this proves that the optimizer, which uses the player
for level search, setup checks and confirmation, still finds teams as good, and shows the user-facing time saving.

**Independent Test**: Two optimizer runs (v2 and v4) on B2 with the same budget and seed, the equal-levels replay,
the McNemar verdict and the mean final levels in the log, plus both wall times.

**Acceptance Scenarios**:

1. **Given** B2 optimized with v2 and with v4 (quick budget, same seed), **When** both final teams are played at the v4
   team's start levels on the same 2,000 seeds, **Then** the v4 team does not clear significantly less (McNemar exact,
   alpha 0.05) and its expected average final level is not higher.
2. **Given** the two optimizer runs, **When** timed, **Then** both wall times and the ratio are in the log.
3. **Given** the v4 result, **When** validated, **Then** it is legal (the validator passes it, as for every output).

---

### User Story 4 - v4 becomes the default player only after it passes (Priority: P2)

If User Stories 2 and 3 pass, `expectimax2-v4` becomes the default player everywhere a player is chosen by default:
the optimizer's level search, setup check and confirmation runs, `evaluate`, `bench` and the web interface. Every
report names the policy that played. `expectimax2-v2` stays available by name as the reference for comparisons and
for later changes. If either story fails, the default stays `expectimax2-v2` and the feature says so.

**Why this priority**: The speed only reaches users through the default; the gate order (prove first, switch after)
is what Principle VI requires.

**Independent Test**: With the default switched, an evaluation, an optimization and a benchmark run without naming a
policy all report `expectimax2-v4`; naming `expectimax2-v2` still works and reports v2; the documentation states the
default and the date it changed.

**Acceptance Scenarios**:

1. **Given** the switch, **When** `evaluate`, `optimize`, `bench` and the web interface run without a policy name,
   **Then** their reports name `expectimax2-v4`.
2. **Given** the switch, **When** a user names `expectimax2-v2` or `expectimax2-v1`, **Then** that policy plays and is
   named in the report.
3. **Given** the existing policy-strength tests, **When** they run, **Then** v4 is not significantly worse than
   `greedy-v1` on the benchmark team (as v2 is checked today), and a short in-suite pairing of v4 against v2 shows no
   statistically supported drop (a regression guard, not the proof: the proof is User Story 2's 2,000-run comparison).
4. **Given** a failed gate, **When** the feature ends, **Then** no default changed, and the README and run state record
   the negative result and its numbers.

---

### Edge Cases

- A knob that passes alone but fails in combination: the ladder tries smaller combinations; the final set is the
  fastest passing combination, and the log says which knobs were dropped and why.
- A team on which v4 is better (more clears) and another on which it is worse: "not worse on every team" is the rule;
  one worse team fails the candidate.
- Ties and near-ties in the McNemar test (few discordant pairs): the verdict is "indistinguishable", which counts as
  not worse; the discordant counts are recorded so a reader can see how much evidence there was.
- The floor and a first-ply branch that is a knockout: today a branch in which an active member fainted is already
  valued by the leaf (the v2 horizon rule); the floor applies only to the remaining branches, so no knockout branch
  changes treatment.
- The floor and probability mass: the floor drops at most the measured mass (0.48% at 0.02, 2.2% at 0.05) from the
  second-ply search; it is valued by the leaf, never dropped from the expectation, so the sum of branch probabilities
  is unchanged.
- One root sample instead of several when the opponent is locked, charging or recharging: unchanged, the prediction
  is already deterministic there.
- The forced-switch request (our active fainted) does not use the root switch beam; the beam applies only to voluntary
  switches at the root, as today.
- The live opponent (`decomp-ai`) and its draw counts: untouched; the replay fixture's live-opponent draw counts for
  v1 and v2 must still match, and v4's own entry records its own.
- Seeds: v4's private trainer-AI sample streams are seeded by the policy name, as v1's and v2's are, so v4's samples
  are its own and reproducible per seed.
- The headline README result (average final level 58.23 with v2) is not re-run here; the provenance of every result
  names its policy, and a re-run with v4 is a separate decision.
- Any edit under `sim/` changes the sim code hash; optimizer checkpoints written before this feature will not
  resume (expected; stated in the plan).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new player policy named `expectimax2-v4` MUST be selectable wherever a player policy is named (evaluate,
  optimize, bench, the web interface and the battle worker), with the same battle model, leaf valuation and horizon
  as `expectimax2-v2` and only the search budget changed: trainer-AI samples per second-ply state, switch targets
  searched at the root, trainer-AI samples at the root, and a first-ply branch-probability floor below which a branch
  is valued by the leaf instead of searched.
- **FR-002**: `expectimax2-v1`, `expectimax2-v2`, `greedy-v1` and the live opponent MUST be unchanged: the 015 replay
  fixture entries for v1 and v2 MUST match (digests `db6d20cf…` and `1273b694…`, every choice, every per-decision draw
  count) and MUST NOT be re-recorded; the trainer-AI golden and fixture tests pass unchanged.
- **FR-003**: `expectimax2-v4` MUST be deterministic: the same seed gives the same battle log; its trainer-AI sample
  streams are private to the policy name.
- **FR-004**: Each budget change MUST be evaluated alone and then in combination against `expectimax2-v2` on the same
  seeds and opponents (paired), on four fixed teams (benchmark fixture team, reference fixture team, the feature-014
  B2 final teams from `main` and from the branch, each at its own fixed levels), 2,000 paired full gauntlets per team,
  McNemar exact at alpha 0.05, with a pairing control (v2 against itself: 0 discordant pairs); every candidate's clear
  rates, discordant counts, p-values, verdicts and fixed-set speed MUST be recorded in the validation log.
- **FR-005**: v4's final parameters MUST be the fastest evaluated combination that is not worse than v2 on every one
  of the four teams (no statistically supported drop in clear rate). A knob that is worse on any team MUST be
  excluded and its numbers kept. If no combination passes, the negative result MUST be recorded with its evidence and
  no default MUST change.
- **FR-006**: With the final parameters, `expectimax2-v4` MUST be at least 1.5x `expectimax2-v2`'s single-process
  throughput on the fixed 40-gauntlet set measured in the same session with the committed benchmark tool, and faster
  on the 16-worker pool, with single-process and pool digests agreeing; a smaller gain MUST be reported as such.
- **FR-007**: The optimizer MUST be run end to end on B2 with v4 and with v2 (quick budget, the feature-014 seed), and
  the two results compared by the feature-010 equal-levels rule (both final teams at the v4 team's start levels, 2,000
  paired runs): the v4 result MUST NOT clear significantly less and MUST NOT have a higher expected average final
  level; both wall times and the ratio MUST be reported. The v4 result MUST pass the legality validator.
- **FR-008**: Only if FR-005 and FR-007 pass MUST `expectimax2-v4` become the default player for the optimizer's level
  search, setup check and confirmation runs, `evaluate`, `bench` and the web interface; every report MUST name the
  policy that played; `expectimax2-v2` MUST remain selectable by name. If either fails, the default MUST stay
  `expectimax2-v2` and the documentation MUST say so with the numbers.
- **FR-009**: The replay fixture MUST gain an `expectimax2-v4` entry (digests, every choice, every per-decision draw
  count on the fixed set) recorded with the final parameters, checked by the replay test from then on.
- **FR-010**: The policy-strength tests MUST cover v4: not significantly worse than `greedy-v1` on the benchmark team,
  and a short in-suite paired v4-versus-v2 check that must not show a statistically supported drop (a regression
  guard; the proof is FR-004).
- **FR-011**: The vendored Showdown tree MUST NOT be edited; the trainer-AI port MUST NOT be changed.
- **FR-012**: The Node test suite, fast mode (`not battle_sim`) and, before merge, the full pytest suite MUST pass,
  with their output recorded.
- **FR-013**: Scope is the search budget of one new policy and its validation. The exact items D, F, E and H
  (FUTURE-FEATURES section 7), any change to the model, leaf, horizon or trainer-AI port, and a re-run of the README
  headline optimization are out of scope.

### Key Entities

- **Player policy**: a named decision procedure for the player's side; `expectimax2-v4` is a new one with v2's model
  and a smaller search budget; `expectimax2-v2` is the reference.
- **Search budget**: the four knobs: root samples, second-ply samples, root switch beam, first-ply branch-probability
  floor (valued by the leaf below it).
- **Candidate**: one assignment of the four knobs under evaluation; the ladder is the ordered list of candidates
  (each knob alone, then combinations fastest first).
- **Paired comparison**: both policies (or both teams) played on the same seeds and opponents; outcome per seed;
  McNemar exact on the discordant pairs; verdict not worse / worse / indistinguishable; the pairing control is a
  policy against itself.
- **Fixed teams**: the benchmark fixture team, the reference fixture team, the feature-014 B2 final teams (`main` and
  branch sides), each at fixed levels.
- **Equal-levels comparison** (feature 010 rule): two optimizer results played at the newer team's start levels on
  the same seeds; clear rate (McNemar) and expected average final level.
- **Replay fixture**: the recorded digests, choices and draw counts of the fixed set per policy (015); v1 and v2
  entries unchanged, a v4 entry added.
- **Default player**: the policy used when none is named; v2 today, v4 after a passing gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The 015 replay fixture matches for v1 and v2 (0 differences) after every commit; the golden trainer-AI
  tests pass unchanged.
- **SC-002**: Every candidate in the ladder has a recorded row: four teams x (clear rate v4, clear rate v2, discordant
  counts, p-value, verdict) and its fixed-set speed; the pairing control shows 0 discordant pairs.
- **SC-003**: v4's final parameters show no statistically supported drop on any of the four teams (McNemar exact,
  alpha 0.05, 2,000 paired runs each).
- **SC-004**: v4 is at least 1.5x v2 single process on the fixed set (same session; today's v2 figure 1.244
  gauntlets/s, 9.8 ms per decision; the sizing runs suggest 1.5x to 1.75x) and faster on the 16-worker pool; digests
  agree on both sides; v4's own replay entry reproduces on the fixed set.
- **SC-005**: On B2 (quick budget, the 014 seed), the v4 optimizer result at equal levels does not clear significantly
  less than the v2 result and has no higher expected average final level; both wall times and the ratio are
  reported, with the v4 optimization expected to be markedly faster.
- **SC-006**: If adopted, evaluate, optimize, bench and the web interface report `expectimax2-v4` by default and v2 on
  request; if not adopted, the default is unchanged and the negative result is documented with its numbers.
- **SC-007**: All existing tests pass: Node suite (347 tests today), fast mode (528 passed, 4 xfailed today) and, before
  merge, the full suite (556 passed, 4 xfailed today), plus the new determinism, replay-entry and policy-strength
  tests for v4.

## Assumptions

- The sizing runs are representative of the final policy: they changed the same parameters in memory on the same
  code; the measured speeds are candidates' speeds, not v4's result, which depends on which knobs pass.
- The floor is tried at 0.02 and 0.05 (the two sized values); the plan may add one value between them if 0.05 fails
  and 0.02 passes. Branches below the floor are valued by the leaf, never dropped, so the expectation's probability
  mass is unchanged.
- The four fixed teams are enough breadth for the paired comparison (two fixtures already used by the policy tests,
  and the two optimizer outputs from feature 014, which exercise held items and level choices the fixtures lack).
- "Not worse" is the feature-014 rule: no statistically supported drop at alpha 0.05; "indistinguishable" passes.
  With 2,000 paired runs the test resolves differences of a few percentage points in clear rate.
- The ladder order is: each knob alone, then all passing knobs together, then the next fastest subsets; the plan fixes
  the exact order and stops at the first passing combination.
- Compute is local only: each candidate costs 4 teams x 2,000 paired runs (v4 side only; the v2 side is played once per
  team and reused), about 8 to 10 minutes per team on the 16-worker pool; the B2 optimizations about 20 minutes (v2,
  already recorded in 014 but re-run on today's code for a fair wall time) and less for v4; the equal-levels replay
  about 22 minutes. The plan estimates the total and orders the runs so a failing knob is dropped early.
- The feature-014 B2 final teams (`runs/014-evidence/b2-main/result.json`, `b2-branch/result.json`) exist locally
  (git-ignored); if missing, they are regenerated with the 014 command and seed on today's code and that is recorded.
- The in-suite v4-versus-v2 pairing uses the policy-strength test's existing run count (hundreds of gauntlets), so it
  can only catch a large regression; FR-004 is the proof.
- Numbering: this feature takes 018; the exact round (D, F, E) and the adapter read memos (H) follow as 019 and
  later, as FUTURE-FEATURES section 7 says.
