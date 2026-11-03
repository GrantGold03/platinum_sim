# Feature Specification: Lead Spike

**Feature Branch**: `020-lead-spike`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Lead spike: a measurement-only feature that decides whether the optimizer gets a lead check (assessment lead-per-fight, verdict go, .specify/assessments/lead-per-fight/decision.md). No behaviour change: nothing under sim/ or src/platsim changes (sim_code_hash and platsim_code_hash unchanged, replay fixtures untouched); the feature commits scripts under specs/020-*/scripts/ (it may reuse the feature-019 scripts by path), small result files under specs/020-*/evidence/, raw evidence local under runs/020-evidence/ (gitignored, as for every feature), a validation log with Eastern times, and a go / no-go record in FUTURE-FEATURES section 8 for the two follow-ons (the lead named in every output; a paired six-lead check at the optimizer's confirmation stage). Background: today the lead is the first species listed in the optimize request and is never reported; the game lets the player reorder the party between League rooms (decomp-cited in the assessment); on three hand-built or 018 teams at 100 paired gauntlets the six fixed leads spanned 12, 8 and 15 points of clear rate, almost all at Cynthia, while best-lead-versus-first-listed was +6, +2 and 0 points, none significant, and the optimizer-built B2 team already had its best lead first by chance of listing order. A per-fight lead is closed (it adds under one point over the best fixed lead); this spike asks only whether choosing the lead is worth building into the optimizer. Three questions with pass or kill criteria recorded with their numbers (Principle V): (1) Six-lead spread on optimizer-built teams. For each of the two feature-014 B2 teams at their recorded levels (runs/014-evidence/b2-main/result.json and runs/014-evidence/b2-branch/result.json, team.builds), run 2,000 full gauntlets per lead for each of the six leads (the chosen member first, the others in their existing relative order), stop_on_loss on, log summary, expectimax2-v4 against decomp-ai, the same 2,000 seeds for every lead (the standard seed scheme on a master per team), 16 workers, alone on the machine (about 24,000 gauntlets, roughly 35 minutes at the rate 019 measured). Report per team and lead: clear rate with its Wilson interval, per-trainer rates, expected final levels per member over cleared runs and the lead's own level gain, and Cynthia's conditional rate. Pass for the question itself: the table exists with every row; the spread (best minus worst lead) is reported against the 8 to 15 points seen at n 100. (2) Best lead versus first-listed, with the selection bias handled. On each team, choose the best lead on the first 1,000 pairs only, then test that lead against the first-listed lead on the second 1,000 pairs by McNemar exact at alpha 0.05 (a split-sample test, so the choice and the test never use the same runs); also report the naive full-sample 2,000-pair McNemar for the same comparison, labelled as selection-biased, and the pairing control (the first-listed lead against itself on the same seeds: 0 discordant pairs). Pass (the bar for building the confirmation-stage check): a statistically supported gain for the chosen lead on at least one of the two teams on the held-out half. Kill: no supported gain on either; then only the reporting follow-on is built. (3) Screening-sized check. On each team, report which lead the first 400 pairs would have chosen and whether it is the lead the first 1,000 chose, and the same for 200 pairs; this sizes the confirmation-stage check (screening-sized versus full-sized) for the follow-on. Then the record: FUTURE-FEATURES section 8 under the lead bullet with the three answers and their numbers, the go / no-go for the confirmation-stage check (question 2's rule) and the standing go for the reporting follow-on, and a note of the lead's exp coupling (the chosen lead's level gain versus the others) for the equal-levels comparison the follow-on must make. Deliverables: scripts (the paired six-lead runner, the split-sample and naive McNemar analysis as pure functions with fast-mode unit tests including a positive control where the held-out test must find a gain and a negative where it must not), evidence, the validation log, the records. Measurements run alone on the machine, same seeds and opponents on both sides throughout (Principle IV). Merge gate as for 019: the fast-mode pytest suite and the Node suite green plus the code-hash check, the full suite skipped on that evidence and the reason logged. Out of scope: any change to evaluate, the optimizer, the gauntlet, the player policies or the trainer-AI port; naming the lead in outputs (the first follow-on); the confirmation-stage check itself (the second follow-on); a per-fight lead; Shift; the README headline re-run."

## Overview

The simulator sends the first-listed team member out first in every League battle, so the lead is fixed by the order
the owner typed the six species in, and nothing reports it. The lead-per-fight assessment (`.specify/assessments/
lead-per-fight/`, verdict go for "choose and report the lead") measured, on three teams at 100 paired gauntlets, that
the six fixed leads span 8 to 15 points of clear rate, almost all at Cynthia, while the best lead's gain over the
first-listed one (+6, +2, 0) was not significant at that count. A per-fight lead is closed.

This feature is the **spike** that decides whether the optimizer gets a lead check. It changes no behaviour. It
answers three questions on three optimizer-built teams (the two feature-014 B2 teams and the 018 v2 B2 team) at 2,000 paired gauntlets per lead, with a
split-sample test so that choosing the best of six leads and testing it never use the same runs, and records go or
no-go for the confirmation-stage check. The reporting follow-on (the lead named in every output) stands regardless.

## Clarifications

### Session 2026-11-03

- Q: Should the spike keep the two feature-014 B2 teams as its only teams, given that b2-main is strong and the lead effect was largest near the threshold band? → A: Keep both 014 teams and add the 018 v2 B2 team (Garchomp-first, optimizer-built, near-threshold) as a third team; the go rule stays "at least one team".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The six-lead table on optimizer-built teams (Priority: P1)

The owner wants to see, on teams the optimizer actually built, how much the choice of lead moves the clear rate.
For each of the three teams at their recorded levels, each of the six members is put first (the others keep
their relative order) and 2,000 full gauntlets are run with the same seeds for every lead. One table per team shows
clear rate and interval, per-trainer rates, Cynthia's conditional rate, expected final levels per member and the
lead's own level gain, and the spread between the best and worst lead.

**Why this priority**: it is the measurement every later answer is computed from, on the right teams; the earlier
spread figures came from hand-built fixtures and one 018 team at a tenth of the run count.

**Independent Test**: the six-lead runner on one team produces six rows with 2,000 runs each, identical seed lists
across rows, and the per-row figures reconcile with the raw recordings; the spread is printed against the 8 to 15
points seen at n 100.

**Acceptance Scenarios**:

1. **Given** a 014 B2 team at its recorded levels, **When** the six-lead runner finishes, **Then** there are six rows,
   each from 2,000 runs, with the same 2,000 request seeds in every row, and each row carries clear rate, Wilson 95%
   interval, per-trainer rates, Cynthia's conditional rate, expected final levels per member and the lead's own gain.
2. **Given** the six rows of a team, **When** the table is printed, **Then** it names the best and worst lead, the
   spread in points, and compares it with the 12, 8 and 15 points seen at n 100.
3. **Given** the first-listed member is Garchomp on all three teams, **When** the rotation puts another member first,
   **Then** Garchomp keeps its place in the remaining relative order (rotation changes only who leads).

---

### User Story 2 - Best lead versus first-listed, selection bias handled (Priority: P2)

The owner wants to know whether a chosen lead beats the first-listed one with statistical support, without the
optimism of picking the best of six on the same runs it is tested on. On each team the best lead is chosen on the
first 1,000 pairs only and tested against the first-listed lead on the second 1,000 pairs by McNemar exact at alpha
0.05. The naive 2,000-pair test is shown beside it, labelled selection-biased, and a pairing control (first-listed
against itself, 0 discordant) proves the pairing.

**Why this priority**: it is the go or no-go rule for building the confirmation-stage check.

**Independent Test**: the analysis functions, run on synthetic paired outcomes, find a gain on the held-out half in
a positive control and none in a negative control; run on the real recordings they print, per team, the chosen lead,
the held-out McNemar counts and p, the naive counts and p, and the control's 0 discordant pairs.

**Acceptance Scenarios**:

1. **Given** the six recordings of a team, **When** the best lead is chosen on pairs 1..1000 by clear rate (ties to
   the lowest member index) and tested against the first-listed lead on pairs 1001..2000, **Then** the output states
   the chosen lead, only-chosen and only-first-listed counts, the exact p, and whether the gain is supported at 0.05.
2. **Given** the same recordings, **When** the naive full-sample test is run, **Then** it is printed beside the
   held-out one and labelled "selection-biased".
3. **Given** the first-listed lead's recording, **When** it is paired against itself, **Then** 0 discordant pairs.
4. **Given** the first-listed lead is itself the best on the first half, **When** the test runs, **Then** it reports
   "first-listed already best" with 0 discordant pairs rather than claiming a gain.
5. **Given** a synthetic positive control (a lead that wins 5 points more on independent runs) and a negative control
   (six identical leads), **When** the analysis runs, **Then** the held-out test finds a supported gain in the first
   and none in the second.

---

### User Story 3 - Screening-sized check and the record (Priority: P3)

The owner wants to know whether a cheaper check would pick the same lead, and to record the decision. On each team
the lead chosen by the first 400 pairs and by the first 200 pairs is compared with the lead chosen by the first
1,000. FUTURE-FEATURES section 8 then carries the three answers with their numbers, the go or no-go for the
confirmation-stage check, the standing go for the reporting follow-on, and the lead's exp coupling.

**Why this priority**: it sizes the follow-on's check and closes the feature; it needs no new runs.

**Independent Test**: the screening function on the real recordings prints, per team, the leads chosen at 200, 400
and 1,000 pairs and whether they agree; the record exists with every number.

**Acceptance Scenarios**:

1. **Given** the six recordings of a team, **When** the screening check runs, **Then** it prints the lead chosen at
   200, 400 and 1,000 pairs and whether the smaller samples agree with the 1,000-pair choice.
2. **Given** all three answers, **When** the feature closes, **Then** FUTURE-FEATURES section 8 records them with
   their numbers, the go / no-go for the confirmation-stage check by question (2)'s rule, the standing go for the
   reporting follow-on, and the chosen lead's level gain versus the other members on each team.

---

### Edge Cases

- A tie for best lead on the first half: the lowest member index wins and the tie is reported.
- The first-listed lead is the best on the first half: reported as such; the held-out test is lead against itself
  (0 discordant) and counts as no supported gain on that team.
- A team so strong that the spread is smaller than the interval width: reported; the held-out test decides.
- A lead whose rotation leaves the party order unchanged (member 0): it is the first-listed row itself; no duplicate
  run is made.
- Runs that end before Cynthia under one lead and reach her under another: per-trainer and Cynthia rates are
  conditional on reaching, as in every report; the clear rate is the paired statistic.
- The machine not idle (another Node or pytest process): the runner refuses to start.
- A recording whose seed list differs from the first-listed lead's: the analysis refuses to pair them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST leave the simulator, the evaluation, the optimizer and the replay fixtures unchanged:
  `sim_code_hash` and `platsim_code_hash` identical before and after, and no file under `sim/` or `src/platsim`
  changed.
- **FR-002**: The feature MUST record, for each of the three teams at their recorded levels (the two feature-014 B2 teams
  and the 018 v2 B2 team, `runs/018-evidence/b2-expectimax2-v2/result.json` team.builds) and for each of the six leads (the chosen member first, the others in their existing relative order), 2,000 full gauntlets with
  stop-on-loss on, summary log, the default player against the live trainer AI, the same 2,000 request seeds for every
  lead of a team (the standard seed scheme on one master per team), on the 16-worker pool, alone on the machine.
- **FR-003**: Each recording MUST keep per-run, per-battle outcomes (trainer, won, end, turns, log hash) and final
  levels, with a header carrying the team, the lead, the master seed, both code hashes, the policies and Eastern
  start and end times.
- **FR-004**: The feature MUST produce, per team, a six-row table with clear rate and Wilson 95% interval,
  per-trainer rates, Cynthia's conditional rate, expected final levels per member over cleared runs, the lead's own
  level gain, and the spread between the best and worst lead compared with the 8 to 15 points seen at n 100.
- **FR-005**: The feature MUST choose, per team, the best lead on pairs 1..1000 by clear rate (ties to the lowest
  member index, reported) and test it against the first-listed lead on pairs 1001..2000 by McNemar exact at alpha
  0.05, reporting the only-chosen and only-first-listed counts and the p-value.
- **FR-006**: The feature MUST report beside it the naive 2,000-pair McNemar for the same comparison, labelled
  selection-biased, and the pairing control (first-listed against itself: 0 discordant pairs).
- **FR-007**: The feature MUST report, per team, the lead chosen by the first 200 and the first 400 pairs and whether
  each agrees with the 1,000-pair choice.
- **FR-008**: The analysis MUST be pure functions with fast-mode unit tests, including a positive control (a lead with a 10-point advantage on seeded independent synthetic runs, 0.85 against 0.75,
  must show a supported gain on the held-out half; expected difference about 100 discordant pairs against a spread of
  about 19, so the control cannot pass or fail by seed choice) and a
  negative control (six identical leads must show none), and the pairing refusal when seed lists differ.
- **FR-009**: The feature MUST record every measurement in the validation log with Eastern start and end times, the
  commands, the code hashes and the idle check, keep raw recordings under `runs/020-evidence/` and copy the small
  result files to the feature's `evidence/` directory.
- **FR-010**: The feature MUST close with a record in FUTURE-FEATURES section 8: the three answers with numbers, go
  or no-go for the confirmation-stage check (go when at least one of the three teams shows a supported held-out gain), the standing
  go for the reporting follow-on, and the chosen lead's level gain versus the other members on each team.
- **FR-011**: Every comparison MUST use the same seeds and opponents on both sides (Principle IV); every negative
  result MUST be recorded with its evidence (Principle V).
- **FR-012**: The merge gate is the fast-mode pytest suite and the Node suite green plus the code-hash check; the full
  suite is skipped on that evidence and the reason logged (as feature 019).

### Key Entities

- **Team**: one of the three stored results (014 b2-main, 014 b2-branch, 018 v2 B2), its six builds at recorded levels,
  first-listed member Garchomp.
- **Lead recording**: team, lead index and species, master seed, 2,000 runs with per-battle outcomes and final
  levels, header provenance.
- **Lead row**: the per-lead summary (clear rate and interval, per-trainer rates, Cynthia conditional rate, expected
  final levels, the lead's gain).
- **Split-sample result**: chosen lead on the first half (with tie note), held-out McNemar counts and p, naive
  counts and p, control discordant count, verdict (supported gain or not, or "first-listed already best").
- **Screening result**: leads chosen at 200, 400 and 1,000 pairs and their agreement.
- **Record**: the FUTURE-FEATURES section 8 entry and the validation log's closing section.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Eighteen recordings exist (three teams × six leads), 2,000 runs each, with identical seed lists across the
  six leads of a team, and all three tables are complete with the spread reported against 8 to 15 points.
- **SC-002**: The pairing control shows 0 discordant pairs on every team, and the unit tests' positive and negative
  controls pass in fast mode.
- **SC-003**: Per team, the held-out McNemar result (counts and p) and the naive result are both reported, with the
  verdict stated by the 0.05 rule; the go / no-go for the confirmation-stage check follows question (2)'s rule.
- **SC-004**: Per team, the 200- and 400-pair choices are reported with their agreement to the 1,000-pair choice.
- **SC-005**: FUTURE-FEATURES section 8 carries the record with every number, including the chosen lead's level gain
  on each team.
- **SC-006**: Code hashes unchanged, the replay fixture and determinism tests pass unchanged, no file under `sim/` or
  `src/platsim` modified; fast-mode pytest and the Node suite green, the full suite skipped with the reason logged.
- **SC-007**: New battles are limited to the eighteen 2,000-run recordings (about 36,000 gauntlets, roughly 50 minutes
  at 12 gauntlets per second) plus a 40-run recorder smoke, all alone on the machine.

## Assumptions

- The teams are the stored 014 B2 results (`b2-main`: Garchomp 52, Infernape 54, Staraptor 53, Rotom 55,
  Floatzel 55, Weavile 53, quick clear 0.918 under v2; `b2-branch`: Garchomp 51, Infernape 53, Staraptor 53, Rotom 53,
  Floatzel 53, Weavile 54, quick clear 0.838 under v2) and, per the clarification, the 018 v2 B2 team (`runs/018-evidence/
  b2-expectimax2-v2`: Garchomp 54, Infernape 52, Staraptor 54, Rotom 54, Floatzel 54, Weavile 55, quick clear 0.886 under v2 at
  500 runs; 0.83 under v4 at 100 paired in the assessment), all Garchomp-first; the spike runs them under the default player
  (expectimax2-v4), so their rates will differ from the stored v2 figures.
- "The same 2,000 seeds" means the request seeds `derive_seed(master, i, 0)` for i in 0..1999 with one master per
  team; the rotation changes the party, never the seeds.
- "Best lead on the first half" means the highest clear rate over pairs 1..1000; ties go to the lowest member index.
- The held-out test is `platsim.stats.mcnemar_exact` at alpha 0.05 on pairs 1001..2000; "supported gain" means
  p < 0.05 with the chosen lead winning more discordant pairs.
- Expected final levels are the per-member mean of final levels over cleared runs, as in every report; the lead's
  gain is its mean final level minus its start level.
- The reporting follow-on (the lead named in every output) is go regardless of this spike (lead-per-fight decision);
  this spike decides only the confirmation-stage check.
- The feature may import the 019 helper scripts by path (idle check, Eastern clock, code hashes, JSON-lines
  recording) rather than copying them.
- Measurements follow the project's rules: nothing else running, Eastern times, raw evidence kept locally.
