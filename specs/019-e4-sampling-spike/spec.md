# Feature Specification: Elite Four Sampling Spike

**Feature Branch**: `019-e4-sampling-spike`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Elite Four sampling spike: a measurement-only feature that decides whether adaptive Elite Four sampling (assessment e4-scope, verdict go, .specify/assessments/e4-scope/decision.md) is built. No behaviour change: nothing under sim/ or src/platsim changes (sim_code_hash and platsim_code_hash unchanged, replay fixtures untouched); the feature commits scripts under specs/019-*/scripts/, evidence under runs/019-evidence/, a validation log, and a go / no-go record in FUTURE-FEATURES section 8 for the follow-on. Background: the four Elite Four battles are 70% of player decision time on 60 gauntlets (e4-scope research), Aaron, Bertha and Flint are won at 0.996 or better in every stored run, Lucian decides 7 to 46% of losses on teams at 0.77 to 0.81 clear rate (bench-010 B3: Lucian 0.8945, gauntlet 0.7715, Cynthia conditional 0.8625). The proposed method runs full gauntlets until each Elite Four member's pass rate is proven (Wilson lower bound at or above a floor), banks the real post-Lucian states as the Cynthia top-up does, serves the remaining runs as Cynthia-only battles from banked states, and estimates the gauntlet clear rate as Elite Four pass rate times Cynthia's conditional rate with a conservative combined interval. Three questions, each with a pass or kill criterion recorded with its numbers (Principle V): (1) Estimator on stored evidence, no new battles. For each of the ten stored evaluations with at least 2,000 runs (runs/t076/v7-w16, runs/final-defaults, runs/bench-007-baseline/B5, runs/bench-010/B1 to B5, runs/t076/v8, runs/job-20261008T235244Z-2d8f18), compute from result.json the composite estimate (Cynthia battles over n_runs, times Cynthia's conditional rate, both the full-run-only rate and the top-up-inclusive champion_rate) and a conservative interval for the product of two proportions (a documented, simple method; no new statistics), and compare with the stored clear_rate, clear_ci95 and the qualified / borderline verdict at threshold 0.75 under the preset's rules. Pass: the stored clear rate lies inside the composite interval and the verdict agrees on all ten, including B3; the interval's half-width is reported against the stored one. Positive control: a synthetic case where the verdicts must differ (an Elite Four pass rate below the threshold) is shown to differ. (2) Sequential replay with recorded per-run outcomes, two fresh runs. Record per-run, per-battle outcomes for 2,000 full gauntlets, stop_on_loss on, expectimax2-v4, the standard seed scheme, on the reference fixture team at its levels (strong: Lucian 1.000) and on bench-010 B3 at its recorded levels (Lucian-heavy), 16 workers, with the state_before of each Cynthia battle kept (log mode summary; this is the existing worker output, no code change). Apply the adaptive rule offline for floors 0.98, 0.99 and 0.995 over 200 random run orders: how many full runs until every Elite Four member clears the floor, how many of the 2,000 would have been Cynthia-only, and the composite estimate and interval against the full result, with the verdict. Pass: on the reference team at least half of the runs become Cynthia-only at some floor with the verdict unchanged and the full clear rate inside the interval in at least 95% of orders; on B3 the rule never proves Lucian at any floor and the estimate equals the full gauntlet's. Also report, from the same recordings, how many banked post-Lucian states the Cynthia-only phase would draw from, and the Cynthia-only battle's cost relative to a full gauntlet (turns and decisions per battle from the per-battle records). (3) In-stage time share, one measurement. The Elite Four share of wall time in a level-search-like setting: stop_on_loss on, batches of 50, 100 and 200, the same two teams plus the 018 v2 B2 team, expectimax2-v4, the real 16-worker pool, timed per battle through an in-memory harness (the prof3/prof4 precedent: hooks patch at module load, committed under the feature's scripts, never in sim/), with the harness checked against a plain run (same digests). Pass: the share is reported per team and batch size; kill criterion for the follow-on if it is below 40% on the strong team (far below the 70% measured single process). Then a projection: from (2) and (3), the expected wall time of evaluate on the reference team (baseline 769 s, 2,000 runs standard, 16 workers) and of optimize B2 quick (baseline 350 s with v4) under the method, as a range, against the problem's bar (about 1.5x material, under 1.2x not worth the change of method). Deliverables: scripts (estimator and interval as pure functions with fast-mode unit tests; the replay and the timing harness), evidence, validation log with Eastern start and end times, and FUTURE-FEATURES section 8 updated with go or no-go for feature 021 (adaptive sampling in evaluate) and the fallback order from the concept note (cheaper player for Aaron, Bertha and Flint only if its per-trainer rates are measured first; otherwise nothing). Measurements run alone on the machine, same seeds and opponents throughout (Principle IV). Out of scope: the adaptive sampling itself (021), the lead spike (020), any change to evaluate, the optimizer, the gauntlet, the player policies or the trainer-AI port, and any change to what qualifies (the gauntlet clear rate stays the statistic)."

## Overview

Every evaluation and optimizer stage simulates all five League battles per run, yet the four Elite Four battles take
about 70% of the simulation time while deciding only 1 to 4% of lost runs on strong teams (up to 46% on Lucian-heavy
teams near the threshold). The e4-scope assessment (`.specify/assessments/e4-scope/`, verdict go) proposes adaptive
Elite Four sampling: run full gauntlets until each Elite Four member's pass rate is proven, bank the real post-Lucian
states, serve the remaining runs as Cynthia-only battles from banked states, and estimate the gauntlet clear rate as
the Elite Four pass rate times Cynthia's conditional win rate with a conservative combined interval.

This feature is the **spike** that decides whether that method is built. It changes no behaviour: the simulator, the
evaluation, the optimizer and what qualifies are untouched. It answers three questions with pass-or-kill criteria and
records the verdict and its numbers for the follow-on (feature 021, adaptive sampling in `evaluate`).

## Clarifications

### Session 2026-11-03

- Q: When the projection clears the 1.5x bar on the strong-team evaluation but not on the B2 quick optimization (or the reverse), what is the go rule for feature 021? → A: Go if the reference-team evaluation projection is at or above 1.5x; the B2 quick projection is reported but does not decide.
- Q: Which Cynthia rate should the composite estimate use when it is checked against the stored verdicts? → A: The pass criterion applies to the top-up-inclusive composite; the full-run-only composite is reported as an input consistency check.
- Q: Which test run is the merge gate for a feature that changes no code under sim/ or src/platsim? → A: Fast-mode pytest and the Node suite, with the code-hash check recorded as the reason the full suite is skipped.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The composite estimate reproduces the stored verdicts (Priority: P1)

The project owner wants to know, before anything is built, whether "Elite Four pass rate times Cynthia's conditional
rate, with a combined interval" gives the same answer as the full gauntlet on the evaluations already on disk. They
run the estimator over the ten stored evaluations with at least 2,000 runs and read one table: for each team, the
stored clear rate and interval, the composite estimate and interval, and whether the qualified / borderline verdict at
threshold 0.75 agrees. No new battles are simulated.

**Why this priority**: it is the cheapest check and the one that can kill the whole idea. If the composite statistic
disagrees with the full gauntlet's verdict on any stored team (B3 above all, where Lucian decides 46% of losses), the
method cannot replace the gauntlet statistic and nothing else in the feature matters.

**Independent Test**: can be fully tested by running the estimator over the ten stored `result.json` files and
checking the table against the stored fields; the estimator's pure functions have fast-mode unit tests, including a
positive control that must produce a differing verdict.

**Acceptance Scenarios**:

1. **Given** the ten stored evaluations with at least 2,000 runs, **When** the composite estimate and interval are
   computed from each result's per-trainer battle counts and Cynthia rate, **Then** the stored clear rate lies inside
   the composite interval and the qualified / borderline verdict at threshold 0.75 agrees for all ten, and the table
   reports each composite half-width against the stored half-width.
2. **Given** the same ten evaluations, **When** the composite is computed with the full-run-only Cynthia rate and with
   the top-up-inclusive rate, **Then** both estimates are reported side by side, the full-run-only point estimate
   equals the stored clear rate (a consistency check of the inputs), and the pass criterion is applied to the
   top-up-inclusive estimate, which is the one the method would use.
3. **Given** a synthetic evaluation whose Elite Four pass rate alone is below the threshold while Cynthia's
   conditional rate is above it, **When** the estimator runs, **Then** its verdict is "not qualified" (positive
   control: the check can fail).
4. **Given** a stored evaluation with no Cynthia top-up or no run reaching Cynthia, **When** the estimator runs,
   **Then** it reports the case as not estimable rather than inventing a rate.

---

### User Story 2 - The adaptive rule, replayed on recorded runs, saves work where it should and not where it should not (Priority: P2)

The owner wants to see how the method would have behaved on real runs: on a strong team most runs should become
Cynthia-only with the verdict unchanged; on a Lucian-heavy team the rule must never prove Lucian and the estimate must
equal the full gauntlet's. Two fresh 2,000-run recordings with per-run, per-battle outcomes (the reference fixture
team and bench-010 B3 at its recorded levels) are made with the existing worker output, and the rule is replayed
offline for three floors over 200 random run orders.

**Why this priority**: it is the first measurement of the saving and of the self-correcting behaviour the concept
relies on; it needs only the two recordings (about 13 minutes each on the pool) and no code change.

**Independent Test**: can be tested by replaying the rule over the two recordings and reading, per team and floor,
the distribution of full runs needed, the Cynthia-only share, and the agreement of estimate, interval and verdict with
the full result.

**Acceptance Scenarios**:

1. **Given** the reference-team recording, **When** the rule is replayed at floors 0.98, 0.99 and 0.995 over 200
   random run orders, **Then** at least one floor makes at least half of the 2,000 runs Cynthia-only, with the
   verdict unchanged in every order and the full clear rate inside the composite interval in at least 95% of orders.
2. **Given** the B3 recording, **When** the rule is replayed at every floor, **Then** Lucian's pass rate never
   clears the floor in any order, no run becomes Cynthia-only, and the estimate equals the full gauntlet's clear rate.
3. **Given** either recording, **When** the replay reports, **Then** it also states how many distinct post-Lucian
   states would have been banked by the time the floor was reached, and the cost of a Cynthia-only battle relative to
   a full gauntlet (turns per battle from the per-battle records; decisions per battle from the US3 timing harness).
4. **Given** a run order in which the floor is reached only in the last few runs, **When** the replay reports,
   **Then** the Cynthia-only share for that order is reported as near zero rather than hidden by an average.

---

### User Story 3 - The in-stage time share and the projected saving decide go or no-go (Priority: P3)

The owner wants the Elite Four's share of wall time measured in the setting that matters (stop-on-loss on, the level
search's batch sizes, the real worker pool, threshold teams), and a projection of what the method would save on the
two baselines they care about: a 2,000-run evaluation of the reference team (769 s) and the B2 quick optimization
(350 s). They then record go or no-go for feature 021 in FUTURE-FEATURES section 8.

**Why this priority**: the 70% share was measured single process on 60 gauntlets with stop-on-loss off; the spike's
kill criterion for the follow-on depends on the share in a real stage, and the owner's bar (about 1.5x material,
under 1.2x not worth the change) needs a projection to be judged.

**Independent Test**: can be tested by running the timing harness on the three teams at three batch sizes, checking
the harness against a plain run (identical digests), and reading the share per team and batch size and the projected
range.

**Acceptance Scenarios**:

1. **Given** the timing harness, **When** it runs the same requests as a plain run, **Then** the gauntlet results are
   identical (same digests), proving the harness changes nothing but timing.
2. **Given** the reference team, B3 and the 018 v2 B2 team, **When** each is run with stop-on-loss on at batches of
   50, 100 and 200 on the 16-worker pool, **Then** the Elite Four share of wall time is reported per team and batch
   size, and the report states whether the strong team's share is below 40% (the kill criterion).
3. **Given** the replay results and the time shares, **When** the projection is made, **Then** the expected wall time
   of the reference-team evaluation and of the B2 quick optimization under the method is given as a range with its
   inputs, against the 769 s and 350 s baselines and the 1.5x / 1.2x bar.
4. **Given** all three answers, **When** the feature closes, **Then** FUTURE-FEATURES section 8 records go or no-go
   for feature 021 with the deciding numbers, and on no-go the fallback order from the concept note (a cheaper player
   for Aaron, Bertha and Flint only if its per-trainer rates are measured first; otherwise nothing).

---

### Edge Cases

- A stored evaluation that was extended beyond 2,000 runs (B1 at 2,150, B4 at 2,345, v8 at 2,796): the estimator
  uses the stored run count, not 2,000.
- The two known duplicate directories are outside the list; if a future run adds them, the table lists each distinct
  result once and names the duplicate.
- A stored result with Cynthia's top-up status `cap_hit` or `no_reach`: reported as not estimable for the
  top-up-inclusive estimate; the full-run-only estimate still applies.
- The replay at a floor that no order reaches before the last run: the Cynthia-only share is 0 for that order and the
  estimate is the full gauntlet's; the report shows the distribution, not only the mean.
- The timing harness disagreeing with the plain run on any digest: the measurement is invalid and must not be
  reported as a share.
- The machine not idle during a measurement (another Node or pytest process present): the measurement is not started.
- A composite interval that is wider than the stored interval on every team: allowed, but the half-width ratio is
  reported so the follow-on can budget the extra runs it implies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST leave the simulator, the evaluation, the optimizer and the replay fixtures unchanged:
  `sim_code_hash` and `platsim_code_hash` are identical before and after, and no file under `sim/` or `src/platsim`
  changes.
- **FR-002**: The feature MUST provide a composite estimator that, from a stored evaluation's per-trainer battle
  counts, run count and Cynthia rate, computes the Elite Four pass rate, the composite clear-rate estimate (pass rate
  times Cynthia's conditional rate) and a conservative 95% interval for the product, using one documented, simple
  method, with no new statistical machinery (a second, delta-method interval may be reported for information and is
  used by no criterion).
- **FR-003**: The estimator MUST report both the full-run-only and the top-up-inclusive composite; the pass
  criterion (interval containment and verdict agreement) applies to the top-up-inclusive composite only, and the
  full-run-only composite serves as an input consistency check whose point estimate must equal the stored clear rate.
- **FR-004**: The estimator MUST apply the project's qualification rule (threshold 0.75, the preset's half-width
  target, the borderline rule) to the composite interval and compare both the **threshold verdict** (qualified /
  borderline / below, ignoring the half-width target) and the **full verdict** (with the half-width target) with the
  stored verdict. Agreement for the pass criterion means the threshold verdict agrees; a full-verdict difference that
  is half-width-only is reported with the run count at which the composite would meet the target, and that count
  feeds the projection as extra Cynthia-only runs.
- **FR-005**: The estimator MUST be exercised over the ten stored evaluations with at least 2,000 runs named in the
  description, listing each distinct result once and naming duplicates, and MUST produce one table with the stored
  and composite estimates, intervals, half-width ratio and verdict agreement per team.
- **FR-006**: The estimator's pure functions MUST have unit tests that run in fast mode, including a positive control
  in which the composite verdict must differ from a naive Cynthia-only verdict (Elite Four pass rate below the
  threshold), and a case with no run reaching Cynthia that must be reported as not estimable.
- **FR-007**: The feature MUST record per-run, per-battle outcomes for 2,000 full gauntlets on the reference fixture
  team at its levels and on bench-010 B3 at its recorded levels, with stop-on-loss on, the default player, the
  standard seed scheme and the existing worker output (summary log mode, so each Cynthia battle's starting state is
  kept), on the 16-worker pool, alone on the machine.
- **FR-008**: The feature MUST replay the adaptive rule offline on each recording for floors 0.98, 0.99 and 0.995 over
  200 random run orders, reporting per team and floor: the number of full runs until every Elite Four member clears
  the floor, the share of runs that would have been Cynthia-only, the composite estimate and interval against the
  full result, the verdict, the number of banked post-Lucian states at the switch, and the cost of a Cynthia-only
  battle relative to a full gauntlet in turns (decisions per battle come from the timing harness in US3), with
  distributions over orders rather than means alone.
- **FR-009**: The feature MUST measure the Elite Four share of wall time on the reference team, B3 and the 018 v2 B2
  team with stop-on-loss on at batch sizes 50, 100 and 200 on the 16-worker pool, through a timing harness that is
  checked against a plain run by identical gauntlet digests before any share is reported.
- **FR-010**: The timing harness MUST live under the feature's scripts and patch in memory only, never in committed
  simulator code.
- **FR-011**: The feature MUST produce a projection of the expected wall time of the reference-team 2,000-run
  evaluation and of the B2 quick optimization under the method, as a range with its inputs, against the 769 s and
  350 s baselines and the 1.5x / 1.2x bar.
- **FR-012**: The feature MUST record every measurement in the validation log with Eastern start and end times, the
  exact command, the code hashes and the machine-idle check, and keep raw outputs under `runs/019-evidence/`.
- **FR-013**: The feature MUST close with a go or no-go for feature 021 in FUTURE-FEATURES section 8, stating the
  deciding numbers for each of the three questions, and on no-go the fallback order from the concept note. The go
  rule is: go when questions (1) and (2) pass, the strong team's in-stage share is not below 40%, and the projected
  reference-team evaluation saving is at or above 1.5x; the B2 quick projection is reported beside it as the cost on
  threshold teams and does not decide.
- **FR-014**: Every comparison MUST use the same seeds and opponents on both sides (Principle IV), and every negative
  result MUST be recorded with its evidence (Principle V).

### Key Entities

- **Stored evaluation**: a result on disk with run count, per-trainer battle counts and clear rates, Cynthia's
  conditional rate and battle count (full-run-only and top-up-inclusive), clear rate and interval, verdict, budget
  preset and threshold.
- **Composite estimate**: Elite Four pass rate (Cynthia battles over runs), Cynthia conditional rate, their product,
  and a conservative 95% interval; carries which Cynthia rate it used and the verdict it implies.
- **Recording**: per-run, per-battle outcomes for 2,000 gauntlets of one team, with each Cynthia battle's starting
  state, turns and decision counts.
- **Replay result**: for one recording, floor and run order: full runs until the floor, Cynthia-only share, banked
  states, composite estimate and interval, verdict; aggregated as distributions over 200 orders.
- **Time-share measurement**: per team and batch size, wall time attributed to each trainer's battles and the Elite
  Four share, with the harness-versus-plain digest check.
- **Projection**: expected wall time range for the two baselines under the method, with inputs.
- **Go / no-go record**: the three answers, their numbers, the verdict for feature 021 and the fallback order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On all ten stored evaluations, the stored clear rate lies inside the composite interval and the
  threshold verdict agrees, with the half-width ratio reported per team and any half-width-only difference listed
  with its runs needed.
- **SC-002**: The estimator's positive control yields a differing verdict, and the not-estimable case is reported
  rather than guessed; the unit tests pass in fast mode.
- **SC-003**: On the reference-team recording, at least one floor makes at least 50% of runs Cynthia-only with the
  threshold verdict unchanged in 100% of the 200 orders and the full clear rate inside the interval in at least 95% of them.
- **SC-004**: On the B3 recording, Lucian never clears any floor in any order, the Cynthia-only share is 0, and the
  estimate equals the full gauntlet's clear rate.
- **SC-005**: The timing harness reproduces the plain run's digests exactly, and the Elite Four share of wall time is
  reported for three teams at three batch sizes.
- **SC-006**: The projection gives a range for both baselines, and the go / no-go record states which side of the
  1.5x / 1.2x bar the reference-team evaluation projection falls on (the deciding figure), reports the B2 quick
  projection beside it, and states whether the strong team's share is below the 40% kill criterion.
- **SC-007**: Code hashes are unchanged, the replay fixture test and the determinism tests pass unchanged, no file
  under `sim/` or `src/platsim` is modified, and the merge gate is the fast-mode pytest suite and the Node suite (the
  full suite is skipped on that evidence, with the reason logged).
- **SC-008**: The whole feature's new battles are limited to the two 2,000-run recordings, the harness smoke, and the
  timing runs (three teams at three batch sizes, each batch run twice: plain control and hooked), all alone on the
  machine.

## Assumptions

- The ten stored evaluations are those the e4-scope research listed with at least 2,000 runs; they are ten distinct
  results. The known duplicate directories (`runs/job-20261008T235244Z-c86e64`, `runs/t076/v8-rerendered`) are not in
  the list, and the duplicate check exists so that adding them later cannot count a result twice.
- Confirmed in clarification: the pass criterion for the stored-evidence check applies to the top-up-inclusive
  composite, because the method's Cynthia-only battles are top-up-like; the full-run-only composite is an input
  consistency check (its point estimate equals the stored clear rate by construction).
- A "conservative interval for the product of two proportions" means a documented, simple combination of the two
  per-factor 95% intervals (chosen in the plan), wider than an exact method rather than narrower; the half-width
  ratio tells the follow-on what the conservatism costs in runs.
- The adaptive rule for the replay is: full runs in order until every Elite Four member's Wilson 95% lower bound is at
  or above the floor, then Cynthia-only for the remainder; the floor set is 0.98, 0.99 and 0.995; 200 orders are
  uniformly random permutations of the 2,000 recorded runs with a fixed seed.
- "Lucian-heavy" means bench-010 B3 at the levels in its stored result; its stored Lucian rate is 0.8945.
- The B2 quick optimization baseline (350 s) and the reference evaluation baseline (769 s) are the figures in the 018
  validation log and the README; the projection does not re-run either.
- The Cynthia-only battle's relative cost is taken from turns and decisions per battle in the recordings; a per-battle
  wall time is taken from the timing harness where available.
- Measurements follow the project's rules: nothing else running, the default player (expectimax2-v4), the live
  trainer AI as opponent, Eastern times, raw evidence kept.
- Merge gate (clarified): the fast-mode pytest suite and the Node suite green, plus the feature's own fast-mode unit
  tests; the full pytest suite is skipped because the code hashes are proven unchanged (SC-007), and that reason is
  recorded in the validation log.
