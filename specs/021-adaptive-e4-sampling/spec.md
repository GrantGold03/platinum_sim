# Feature Specification: Adaptive Elite Four Sampling in evaluate

**Feature Branch**: `021-adaptive-e4-sampling`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Adaptive Elite Four sampling in evaluate: feature 021, the follow-on that feature 019's spike cleared (specs/019-e4-sampling-spike/validation-log.md T022 and the user decision of 2026-11-03: the method's interval is the delta method). Scope: `platsim evaluate` only; the optimizer's level search, setup check and confirmation keep full gauntlets (a later feature). The method: full gauntlets run in request-seed index order until every Elite Four member's pass rate is proven (Wilson 95% lower bound at or above a floor, default 0.99, with 0.98 as the alternative measured in the spike: 81% and 91% of a 2,000-run evaluation Cynthia-only on the reference team); every full run that reaches Cynthia banks her state_before; the remaining runs are Cynthia-only battles from banked states, drawn deterministically as the Cynthia top-up does (its seed scheme, a reserved battle index, independent of batching and worker count); when the floor is never reached (Lucian-heavy teams such as bench-010 B3) every run is a full gauntlet and the result equals today's. The clear rate becomes the Elite Four pass rate (Cynthia battles reached over full runs) times Cynthia's conditional win rate over all her battles (full and Cynthia-only), with a 95% interval by the log-scale delta method; the threshold, half-width and borderline rules apply to that interval exactly as today; the run count rule (at least --runs, more while the half-width is above the preset's target, up to --max-runs) counts both kinds of runs and adds Cynthia-only runs while the floor is met. Reports: result.json, xlsx, csv and the web result view name the method and carry full_runs, cynthia_only_runs, the floor, the switch run index, the banked-state count, the Elite Four pass rate with its interval and the composite interval; per-trainer rates and loss causes come from the full fraction plus Cynthia-only losses (a Cynthia-only battle replays like any gauntlet request with a start state); provenance records the method so results from different methods are told apart; result.json stays a pure function of its inputs (independent of worker count and batch size, determinism test). The full gauntlet stays available as `--sampling full` and remains the reference (Principle VI); `--sampling adaptive` becomes evaluate's default only if acceptance passes, otherwise it ships behind the flag. Reference-first acceptance, paired on the same seeds and opponents (Principle IV): adaptive against full at 2,000 runs on the two policy fixture teams, the two feature-014 B2 teams, the 018 v2 B2 team and bench-010 B3 at its recorded levels (the Lucian-heavy team, never expected to switch), standard budget, 16 workers: the adaptive estimate lies inside the full run's 95% interval and the qualified / borderline / not-qualified verdict agrees on every team; the composite half-width is reported against the full run's; wall time of both reported with the ratio (expected 1.9 to 2.9x on strong teams, about 1.0 on B3); a pairing control where adaptive with an unreachable floor (1.0) produces result.json identical to the full method byte for byte (Principle V); and a small-count control that Cynthia-only battles from banked states reproduce the top-up's own results on the reference team. Tests: fast-mode unit tests for the switch rule, the run accounting, the composite estimate and the delta interval (positive control: an Elite Four pass rate below the threshold yields not qualified); a battle_sim integration test of evaluate with adaptive sampling at a small count on the reference team (determinism across worker counts, the fields present, the control with floor 1.0 equal to full); the existing evaluate tests unchanged under `--sampling full`. Docs: README (the method, the flag, the new fields, the numbers), the divergence ledger untouched (no game rule changes: exp, PP and items still carry between battles in the full fraction, and the banked states carry them into Cynthia-only battles). Out of scope: the optimizer stages (a later feature), any change to the player policies, the trainer-AI port or the gauntlet rules, the lead-reporting follow-on, the Shift style, and the README headline re-run. Any src/platsim change changes platsim_code_hash; sim/ is expected to stay untouched (the Cynthia-only request already exists), so sim_code_hash should be unchanged and the replay fixtures untouched."

## Overview

Every `platsim evaluate` run simulates all five League battles for every one of its runs, yet the four Elite Four
battles take about 72 to 75% of the battle time (feature 019, measured on the pool) and, on strong teams, decide
almost none of the losses. Feature 019 replayed an adaptive rule on real recordings: run full gauntlets until each
Elite Four member's pass rate is proven, then play only Cynthia from the real post-Lucian states already seen. On
the reference team 81 to 91% of a 2,000-run evaluation became Cynthia-only with the verdict unchanged; on the
Lucian-heavy B3 team the rule never switched and nothing changed. The owner decided the method's interval is the
delta method (the spike's conservative product interval had turned four threshold teams borderline).

This feature builds that method into `evaluate` only, behind `--sampling adaptive`, keeps the full gauntlet as `--sampling full` and as the reference (and as the default), runs a paired acceptance against the full gauntlet on six teams including B3, and flips the default to adaptive in a final commit only on the owner's explicit decision after seeing the acceptance table. The optimizer's stages are a later feature.

## Clarifications

### Session 2026-11-03

- Q: When the paired acceptance passes on all six teams, should adaptive sampling become evaluate's default automatically, or only after the owner's explicit go? → A: The owner's go: the feature ships adaptive behind the flag with `full` as the default, presents the acceptance table, and the default flips in a final commit only on the owner's explicit decision.
- Q: When more runs are needed to meet the half-width target and the Cynthia factor is already tight, should the extension add full gauntlets or keep adding Cynthia-only runs? → A: Mixed: Cynthia-only runs while they can still bring the composite half-width under the target; when the Cynthia part is no longer the limiting term, full gauntlets until the target is met or the cap is reached.


## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate a team faster with the same answer (Priority: P1)

The owner runs `platsim evaluate TEAM --sampling adaptive` and gets the same reports as today, with the same
meaning of the clear rate and the same qualification rule, in a fraction of the time on strong teams. Full
gauntlets run in request-seed order until every Elite Four member's pass rate is proven; after that the remaining
runs are Cynthia-only battles from the banked post-Lucian states. The reports say how many runs were full and how
many Cynthia-only, where the switch happened, how many states were banked, and show the Elite Four pass rate and the
composite interval. On a Lucian-heavy team the floor is never reached and the result is today's.

**Why this priority**: it is the whole value of the feature, and every other story measures or documents it.

**Independent Test**: a small-count evaluation of the reference team with `--sampling adaptive` produces
result.json with the new fields, identical across worker counts, with a switch before the end and Cynthia-only
runs after it; the same command with floor 1.0 produces result.json byte-identical to `--sampling full`.

**Acceptance Scenarios**:

1. **Given** a strong team and `--sampling adaptive` at the default floor, **When** the evaluation runs, **Then** full
   runs stop at the first run index after which every Elite Four member's Wilson 95% lower bound is at or above the
   floor, every later run is a Cynthia-only battle from a banked state drawn deterministically, and result.json
   reports full_runs, cynthia_only_runs, floor, switch_run, banked_states, the Elite Four pass rate with its interval,
   the composite estimate with its delta-method interval, and the method in provenance.
2. **Given** a Lucian-heavy team (B3 at its recorded levels), **When** the evaluation runs with adaptive sampling,
   **Then** the floor is never reached, every run is a full gauntlet, and the clear rate, interval and verdict equal
   those of `--sampling full` on the same seeds.
3. **Given** `--sampling adaptive` with floor 1.0, **When** the evaluation runs, **Then** result.json is identical to
   `--sampling full` for the same inputs once the four sampling-specific keys are removed (the pairing control).
4. **Given** the same team, seed and run count, **When** the evaluation runs with 16 workers and again with 3,
   **Then** result.json is byte-identical (the switch point and the Cynthia-only draws depend only on run order).
5. **Given** a Cynthia-only battle that is lost, **When** loss causes are collected, **Then** it is replayed from its
   banked state like any lost battle and counted in the loss causes.
6. **Given** the run-count rule (at least `--runs`, more while the half-width is above the preset's target, up to `--max-runs`), **When** the floor has been met and Cynthia-only runs can still bring the half-width under the target, **Then** the added runs are Cynthia-only; **When** they cannot (the Elite Four part is the limiting term), **Then** the added runs are full gauntlets; **When** the floor has not been met, **Then** they are full gauntlets.

---

### User Story 2 - Reference-first acceptance on six teams (Priority: P2)

The owner wants proof that the method gives the same answer as the full gauntlet before it becomes the default.
Adaptive and full evaluations run paired on the same seeds and opponents at 2,000 runs, standard budget, on six
teams: the two policy fixture teams, the two feature-014 B2 teams, the 018 v2 B2 team and bench-010 B3. For each
team the adaptive estimate must lie inside the full run's 95% interval and the verdict must agree; the half-widths
and the wall times are reported with their ratio. Two controls: the floor-1.0 run equals the full run byte for
byte, and Cynthia-only battles from banked states reproduce the top-up's own results on the reference team at a
small count.

**Why this priority**: Principle VI; the default switch (US3) depends on it.

**Independent Test**: a committed script runs the twelve evaluations and prints one table (team, full estimate and
interval, adaptive estimate and interval, containment, verdicts, half-width ratio, Cynthia-only share, wall times
and ratio) plus the two controls.

**Acceptance Scenarios**:

1. **Given** the six teams, **When** adaptive and full run paired at 2,000 runs, **Then** on every team the adaptive
   estimate lies inside the full run's 95% interval and the qualified / borderline / not-qualified verdict agrees.
2. **Given** the same runs, **When** the table is printed, **Then** it reports per team the half-width ratio, the
   Cynthia-only share, and wall time for both with the ratio (expected 1.9 to 2.9x on strong teams, about 1.0 on B3).
3. **Given** the reference team at a small count, **When** adaptive runs with floor 1.0, **Then** result.json equals
   the full run's byte for byte once the four sampling-specific keys are removed.
4. **Given** the reference team at a small count, **When** the Cynthia-only phase draws from banked states, **Then**
   its Cynthia win rate agrees with the existing top-up's on the same states within sampling noise, and the top-up
   itself is still run only when its own rules are not already met by the Cynthia-only battles.

---

### User Story 3 - The default and the documentation (Priority: P3)

The feature ships with `full` as the default and adaptive behind the flag. After US2, the owner sees the acceptance table and decides; on their go the default flips to adaptive in a final commit, otherwise it stays `full` with the acceptance (pass or fail) recorded. The
README explains the method, the flag, the new fields and the acceptance numbers; the web result view shows the new
fields; the divergence ledger is untouched because no game rule changes.

**Why this priority**: it is the user-facing outcome of US2 and must not run ahead of it.

**Independent Test**: `platsim evaluate` without the flag uses the recorded default (`full` until the owner's go, adaptive after it), the help text and README say so, and the existing evaluate tests pass unchanged under `--sampling full`.

**Acceptance Scenarios**:

1. **Given** the acceptance table has been presented and the owner has given the go, **When** `evaluate` runs without `--sampling`, **Then** it uses adaptive and reports say so; **Given** no go (or a failed team), **Then** it uses full and the README records the acceptance result.
2. **Given** any evaluation, **When** the reports are written, **Then** result.json, xlsx, csv and the web result view
   name the sampling method and carry the new fields, and the existing fields keep their meaning.
3. **Given** the existing evaluate tests, **When** run with `--sampling full`, **Then** they pass unchanged.

---

### Edge Cases

- The floor is reached only at the last requested run: no Cynthia-only runs; the result equals full.
- No full run reaches Cynthia before the floor is met (impossible by construction, since the floor requires Lucian to
  be proven, which requires reaching Cynthia; guarded anyway): no banked state, no switch, full gauntlets throughout.
- The quick budget (no half-width target, never qualifies): adaptive still applies with the fixed run count; the
  quick warning stays.
- `--max-runs` reached while the half-width is still above target: the warning stays, and the run mix is reported.
- The Cynthia part of the interval is already tight after the switch but the Elite Four part is not: the extension adds full
  gauntlets, which also add banked states and Cynthia battles; the report shows how many of each kind were added.
- A Cynthia-only battle's replay for loss causes must reproduce its log hash like any replay; a mismatch is an error
  as today.
- The top-up: Cynthia-only battles already raise her count above every other trainer's; the top-up adds battles only
  when its half-width rule is still unmet, and its battles are counted in her conditional rate as today.
- A request with `--sampling` and an unknown value: usage error, exit 2.
- A checkpoint or stored result from before this feature has no sampling fields: reports read them as `full`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `platsim evaluate` MUST accept `--sampling {full,adaptive}` and a `--floor` (0.9 to 1.0, default 0.99)
  that applies to adaptive; `full` MUST behave exactly as today and remain the reference.
- **FR-002**: Under adaptive sampling the evaluation MUST run full gauntlets in request-seed index order and switch
  to Cynthia-only runs at the first run index after which every Elite Four member's Wilson 95% lower bound (battles
  faced and won in the full runs so far) is at or above the floor; a member never faced counts as unproven.
- **FR-003**: Every full run that reaches Cynthia MUST bank her starting state; Cynthia-only runs MUST draw a banked
  state deterministically from the run index and master seed (the top-up's scheme with a reserved battle index
  distinct from the top-up's), so the result is independent of batching and worker count.
- **FR-004**: The clear-rate estimate under adaptive sampling MUST be the Elite Four pass rate (full runs that reached
  Cynthia over full runs) times Cynthia's conditional win rate over all her battles (full-run, Cynthia-only and
  top-up), with a 95% interval by the log-scale delta method; the threshold, half-width and borderline rules MUST
  apply to that interval exactly as today's rules apply to the binomial one.
- **FR-005**: The run-count rule MUST count both kinds of runs toward `--runs` and `--max-runs`. Before the floor is met, added runs are full gauntlets. After it, runs added to reach the half-width target MUST be Cynthia-only while Cynthia-only runs can still bring the composite half-width under the target (the Cynthia part is the limiting term); once they cannot, the added runs MUST be full gauntlets (which narrow both parts) until the target is met or the cap is reached, and the report MUST show the mix.
- **FR-006**: When the floor is never reached, every run MUST be a full gauntlet and the report's statistics MUST be
  computed by the full method (the binomial Wilson interval and today's rules), so the clear rate, interval and verdict
  equal those of `--sampling full` on the same inputs; the composite and the delta interval apply only once a switch has
  happened.
- **FR-007**: result.json MUST carry the method, full_runs, cynthia_only_runs, floor, switch_run (or none),
  banked_states, the Elite Four pass rate with its interval, and the composite estimate with its interval, and
  provenance MUST record the method; xlsx, csv and the web result view MUST show them.
- **FR-008**: Per-trainer rates MUST come from the full runs; loss causes MUST include Cynthia-only losses, replayed
  from their banked state with the log-hash check as for every replay.
- **FR-009**: result.json MUST remain a pure function of its inputs: byte-identical across worker counts and batch
  sizes.
- **FR-010**: With floor 1.0, adaptive sampling MUST produce result.json identical to `--sampling full` in every field except
  the four sampling-specific ones (`sampling`, `sampling_detail`, `provenance.sampling`, `seeds.cynthia_only_seed`); the
  control compares the two files with those keys removed, byte for byte.
- **FR-011**: The Cynthia top-up MUST still run only when its own rules are not already met by the Cynthia battles
  on hand, and its battles MUST be counted in Cynthia's conditional rate as today.
- **FR-012**: A committed acceptance script MUST run adaptive against full, paired on the same seeds and opponents, at
  2,000 runs with the standard budget on the six named teams, and print per team: both estimates and intervals,
  containment of the adaptive estimate in the full interval, both verdicts and their agreement, the half-width ratio,
  the Cynthia-only share, both wall times and the ratio; plus the floor-1.0 control and the top-up control.
- **FR-013**: The feature MUST ship with `full` as the default and present the acceptance table (FR-012) to the owner; the default MUST flip to adaptive only in a final commit on the owner's explicit go, which presupposes containment and verdict agreement on all six teams; otherwise `full` stays the default and the acceptance result is recorded in the README.
- **FR-014**: Fast-mode unit tests MUST cover the switch rule, the run accounting, the composite estimate and the delta
  interval, with a positive control (an Elite Four pass rate below the threshold yields not qualified); a `battle_sim`
  integration test MUST run adaptive sampling at a small count on the reference team and check determinism across
  worker counts, the new fields, and the floor-1.0 equality; the existing evaluate tests MUST pass unchanged under
  `--sampling full`.
- **FR-015**: No file under `sim/` changes (the Cynthia-only request already exists), so `sim_code_hash` and the replay
  fixtures stay unchanged; the divergence ledger is untouched.
- **FR-016**: Every measurement MUST be recorded in the validation log with Eastern times and the code hashes; the
  acceptance runs alone on the machine.

### Key Entities

- **Sampling method**: `full` (today) or `adaptive` with a floor; recorded in provenance.
- **Run mix**: full_runs, cynthia_only_runs, switch_run, banked_states, top-up battles.
- **Elite Four pass rate**: full runs that reached Cynthia over full runs, with a Wilson interval.
- **Composite clear rate**: pass rate times Cynthia's conditional rate, with the delta-method interval; the statistic
  the qualification rule reads under adaptive sampling.
- **Banked state**: a Cynthia starting state from a full run, drawn by index for Cynthia-only runs.
- **Acceptance table**: per team the paired figures and controls (FR-012).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On all six acceptance teams at 2,000 runs, the adaptive estimate lies inside the full run's 95%
  interval and the verdict agrees.
- **SC-002**: Wall-time ratio full over adaptive reported per team with the switch run; on the reference fixture team at
  least 1.5x; on B3 about 1.0 (no switch); on any team whose floor-0.99 switch run is above 1,000 or absent, the
  acceptance also reports floor 0.98 as the alternative for the record.
- **SC-003**: The floor-1.0 control produces result.json identical to the full run with the four sampling-specific keys
  removed; the top-up control agrees within sampling noise.
- **SC-004**: result.json is byte-identical across worker counts (16 and 3) and batch sizes for an adaptive run.
- **SC-005**: The existing evaluate tests pass unchanged under `--sampling full`; the new unit and integration tests
  pass; the Node suite and the replay fixtures are unchanged, `sim_code_hash` identical.
- **SC-006**: Every report (result.json, xlsx, csv, web) names the method and shows the run mix and the two
  intervals; a stored result from before the feature reads as `full`.
- **SC-007**: The default is `full` until the owner's explicit go after the acceptance table; the README states the current default and the acceptance result.

## Assumptions

- The default floor is 0.99 (81% Cynthia-only on the reference team in the spike, switch after about 381 full
  runs); 0.98 is reported in the acceptance as the alternative but not shipped as default.
- The delta-method interval is the log-scale one from feature 019's estimator (variance of log p approximated by
  (1 − p1)/(n1 p1) + (1 − p2)/(n2 p2)), clamped to [0, 1].
- Cynthia-only runs use a reserved battle index distinct from the top-up's (the top-up keeps index 99), so the two
  never share seeds; the banked state for Cynthia-only run k is chosen as the top-up chooses (a hash of master, k and
  the reserved index, modulo the banked count).
- "The run-count rule counts both kinds" means `--runs` is the total of full and Cynthia-only runs; the half-width
  target is evaluated on the composite interval.
- Expected final levels and the final-level gap come from cleared full runs only (Cynthia-only runs carry a banked
  state's levels, which are already counted).
- The six acceptance teams: `tests/fixtures/policy_benchmark_team.json`, `tests/fixtures/reference_team.json`,
  `runs/014-evidence/b2-main` and `b2-branch` team.builds, `runs/018-evidence/b2-expectimax2-v2` team.builds,
  `runs/bench-010/B3` team.builds at their recorded levels; default player expectimax2-v4 against decomp-ai.
- The acceptance costs about twelve 2,000-run evaluations (six full at about 3 minutes each with v4, six adaptive at
  about 1 to 3 minutes), plus loss-cause replays and top-ups: under an hour alone on the machine.
- The merge gate is the full pytest suite and the Node suite, as for every behaviour change (this feature changes
  `src/platsim`).
