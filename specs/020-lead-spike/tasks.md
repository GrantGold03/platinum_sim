# Tasks: Lead Spike

**Input**: Design documents from `/specs/020-lead-spike/`

**Prerequisites**: plan.md, spec.md, research.md (R1-R8), data-model.md, contracts/scripts.md, quickstart.md

**Tests**: requested by the spec (FR-008, SC-002): fast-mode unit tests of the analysis's pure functions with a
positive and a negative control, written before the analysis CLI. No `battle_sim` test is added; the recordings are
tasks, not tests.

**Organization**: by user story. US1 (the six-lead tables) holds the only new battles; US2 (the split-sample test)
and US3 (screening and the record) are analysis over US1's recordings.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3
- The three recordings (T008, T009, T010) never run in parallel with anything: machine idle, Eastern start and end
  times in the validation log, raw output under `runs/020-evidence/` (local, gitignored), no commit or suite while
  one runs.

## Path Conventions

- Scripts: `specs/020-lead-spike/scripts/` (never `src/` or `sim/`; FR-001); 019 helpers imported by path (R7)
- Tests: `tests/unit/test_lead_spike.py` (fast mode, imports the script by path; 018/019 precedent)
- Evidence: `runs/020-evidence/` (local) and `specs/020-lead-spike/evidence/` (small files); log:
  `specs/020-lead-spike/validation-log.md`

---

## Phase 1: Setup

- [X] T001 Create `specs/020-lead-spike/scripts/`, `specs/020-lead-spike/evidence/` and `runs/020-evidence/`, and start `specs/020-lead-spike/validation-log.md` with the branch point (`main` ade9f9d), the Eastern start time and the before-hashes from `uv run python -c "from platsim import version; print(version.sim_code_hash(), version.platsim_code_hash())"` (FR-001, SC-006)

---

## Phase 2: Foundational

- [X] T002 Write the pure functions of `specs/020-lead-spike/scripts/lead_analysis.py` (contracts/scripts.md): `rotate(team, i)` (R1: `[team[i]] + [m for j, m in enumerate(team) if j != i]`), `load_recording(path)` (header + runs; validates 2,000 lines in index order), `check_paired(rec_a, rec_b)` (raise unless the seed lists are identical), `lead_row(rec, start_levels, order)` (clear count and rate, `platsim.stats.wilson_ci`, per-trainer battles and rate, Cynthia conditional rate, expected final levels per member mapped back to the original order through `order`, lead gain = lead's mean final level minus its start level), `choose_best(recs, n)` (R2: highest clear count over runs 0..n-1, ties to the lowest index, returns `(index, tied)`), `held_out(chosen, first, lo=1000, hi=2000)` and `naive(chosen, first)` (both `platsim.stats.mcnemar_exact(a=chosen cleared slice, b=first cleared slice, alpha=0.05)`; supported gain = verdict `A`), `control(first)` (first vs itself: discordant 0), `screening(recs)` (R5: choices at 200, 400, 1000 and agreement), `level_gains(rows, chosen)` (R6: chosen lead's gain minus the mean gain of the other five)
- [X] T003 Write `tests/unit/test_lead_spike.py` (load the script by path and register it in `sys.modules`, as `test_e4_estimator.py` does): rotation keeps relative order and lead 0 is the identity; `check_paired` raises on differing seed lists; `lead_row` reconciles with a hand-built recording (clear rate, per-trainer rates, final-level mapping through `order`, lead gain); `choose_best` picks the highest and breaks ties to the lowest index with the tie flag; the **positive control**: six synthetic recordings of 2,000 runs from seeded independent Bernoulli draws where lead 3 clears at 0.85 and the others at 0.75 (a 10-point advantage, chosen so the held-out test is significant for any seed) must give held-out verdict `A` for the chosen lead (choose on 0..999, test on 1000..1999), and a second, informational case at 0.80 that only prints its p-value and asserts nothing; the **negative control**: six identical recordings must give `indistinguishable` with 0 discordant pairs and `first_listed_already_best`; `screening` agreement logic; `level_gains` arithmetic; run `uv run pytest -q tests/unit/test_lead_spike.py` and record the output

**Checkpoint**: the analysis is tested before any recording exists.

---

## Phase 3: User Story 1 - The six-lead table on optimizer-built teams (Priority: P1) 🎯 MVP

**Goal**: eighteen recordings (three teams × six leads, 2,000 runs each, identical seeds per team) and the six-row
table per team with the spread against the 8 to 15 points seen at n 100.

**Independent Test**: `lead_runs.py --team b2main` writes six files of 2,001 lines whose seed lists are identical;
`lead_analysis.py` prints the six-row table with the spread.

- [X] T004 [US1] Write `specs/020-lead-spike/scripts/lead_runs.py` (contracts/scripts.md, R7, R8): `sys.path.insert` of `specs/019-e4-sampling-spike/scripts` and import `common.assert_idle`, `eastern_now`, `code_hashes`; teams `b2main` (`runs/014-evidence/b2-main/result.json` team.builds), `b2branch` (`runs/014-evidence/b2-branch/result.json`), `b2v2` (`runs/018-evidence/b2-expectimax2-v2/result.json`); `--team`, `--leads 0,1,2,3,4,5`, `--runs 2000`, `--workers 16`, `--out-dir runs/020-evidence`; per lead: rotate, `platsim.evaluate.run_full_gauntlets(pool, team, master=f"020-lead-{team}", min_runs=runs, max_runs=runs, target=None, player_policy=DEFAULT_PLAYER_POLICY, log="summary")`, write `<team>-lead<i>.jsonl` (header: team, lead_index, lead_species, order, master, runs, workers, policies, both code hashes, pool sim hash, start, end, wall_s, gauntlets_per_s; run lines: run, seed, cleared, battles [trainer, won, end, turns, log_hash], final_levels), print one summary line per lead
- [X] T005 [P] [US1] Add the table part of the CLI to `specs/020-lead-spike/scripts/lead_analysis.py`: `--evidence-dir`, `--teams`, `--out`; per team load the six recordings, `check_paired` each against lead 0, build the six `LeadRow`s, print the table (lead, species, cleared/2000, clear rate [ci], per-trainer rates, Cynthia conditional, expected final levels, lead gain) and the spread line (best, worst, points, "vs 12 / 8 / 15 at n 100")
- [X] T006 [US1] Smoke the recorder alone: `uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2main --leads 0,1 --runs 20 --out-dir runs/020-evidence/smoke` then `lead_analysis.py --evidence-dir runs/020-evidence/smoke --teams b2main` on those two files (the analysis must accept a partial lead set for the table and skip the split-sample block when fewer than six leads exist); log the output; delete the smoke directory afterwards
- [X] T007 [US1] Commit 1: `feat(020): lead recorder and analysis with tests` (scripts, test, log); push
- [X] T008 [US1] Record `b2main`, alone (about 17 min): `uv run python specs/020-lead-spike/scripts/lead_runs.py --team b2main`; log Eastern start/end, the six summary lines, wall and gauntlets/s
- [X] T009 [US1] Record `b2branch`, alone: same command with `--team b2branch`; log as T008
- [X] T010 [US1] Record `b2v2`, alone: same command with `--team b2v2`; log as T008
- [X] T011 [US1] Run `uv run python specs/020-lead-spike/scripts/lead_analysis.py --out runs/020-evidence/lead_analysis.json > runs/020-evidence/lead_analysis.txt`; copy the three tables into the validation log with the spreads (SC-001); copy `lead_analysis.json`, `lead_analysis.txt` and the eighteen header lines into `specs/020-lead-spike/evidence/`

**Checkpoint**: question (1) answered with three tables.

---

## Phase 4: User Story 2 - Best lead versus first-listed, selection bias handled (Priority: P2)

**Goal**: per team, the chosen lead on the first half, the held-out McNemar, the naive McNemar labelled
selection-biased, the pairing control, and the chosen lead's gain versus the others.

**Independent Test**: the split-sample block prints for every team with control discordant 0; on the real
recordings the verdicts decide the go / no-go.

- [X] T012 [US2] Add the split-sample block to the CLI in `specs/020-lead-spike/scripts/lead_analysis.py`: per team `choose_best(recs, 1000)` (tie reported), `held_out`, `naive` (printed with the label "selection-biased"), `control`, `first_listed_already_best` handling (0 discordant, counts as no supported gain), `level_gains`; write all of it into the JSON (SplitSampleResult per data-model.md)
- [X] T013 [US2] Re-run the analysis on the eighteen recordings (seconds; no new battles); copy the three split-sample blocks into the validation log; state per team whether the held-out gain is supported (verdict `A`, p < 0.05) and the naive p beside it (SC-002, SC-003)
- [X] T014 [US2] Commit 2: `feat(020): split-sample lead test on three optimizer-built teams` (script, evidence, log); push

**Checkpoint**: question (2) answered; the go / no-go rule for the confirmation-stage check can be applied.

---

## Phase 5: User Story 3 - Screening-sized check and the record (Priority: P3)

**Goal**: the 200- and 400-pair choices per team against the 1,000-pair choice, and the recorded decision.

**Independent Test**: the screening block prints for every team; FUTURE-FEATURES section 8 carries the record with
every number.

- [X] T015 [US3] Add the screening block to the CLI in `specs/020-lead-spike/scripts/lead_analysis.py` (`screening(recs)`: choices at 200, 400, 1000 and agreement flags) and the closing summary (per team supported_gain; go / no-go for the confirmation-stage check = any team supported); re-run and copy the block into the log (SC-004)
- [X] T016 [US3] Write the record in `FUTURE-FEATURES.md` section 8 under the lead bullet: per team the spread, the chosen lead with held-out counts and p, the naive p (selection-biased), control 0, the 200/400-pair agreement, the chosen lead's gain versus the others; the go / no-go for the confirmation-stage check by question (2)'s rule and the standing go for the reporting follow-on; the same as the closing section of the validation log (FR-010, SC-005)
- [X] T017 [US3] Commit 3: `feat(020): screening check and the lead decision record` (script, evidence, FUTURE-FEATURES, log); push

---

## Phase 6: Polish, gates and merge

- [X] T018 [P] Record the feature in `README.md` (one paragraph after the 019 block: what was measured, the numbers, the decision; no behaviour change) and `RUN-STATE.md` START HERE
- [X] T019 Gates, in order, nothing else running: (a) the code hashes equal the T001 before-hashes; (b) `git diff --stat main -- sim src/platsim` empty; (c) `(cd sim && node --test test/*.test.mjs)` green; (d) `uv run pytest -q -m "not battle_sim"` green with the battle split clean; log each output with Eastern times and the sentence that the full suite is skipped because (a) and (b) hold (FR-012, SC-006)
- [X] T020 Commit 4: `docs(020): README, RUN-STATE, gates recorded`; push; report to the user with the decision and the numbers. Merge to `main` only on the user's go (`git checkout main && git merge --ff-only 020-lead-spike && git push`)

---

## Dependencies

- Setup → Foundational (T002, T003) → US1 → US2 → US3 → Polish. T004 and T005 are parallel (different parts of
  different files); T006 needs both; T007 before T008 (no commit during a recording); T008, T009, T010 strictly
  sequential and alone; T011 after T010. US2's T012 can be written while a recording runs (no commit, no suite); T013
  after T011. T015 after T013. T019 after everything; T020 after T019.

## Parallel execution examples

- Foundational: none (T003 tests T002's functions; write T002 then T003).
- US1: T004 (recorder) beside T005 (table CLI).
- During T008-T010: write T012 and T015's code, commit nothing, run no suite.
- Polish: T018 beside T016/T017 (different files).

## Implementation strategy

- **MVP = US1** (T001-T011): the recordings are the whole battle cost (three runs of about 17 minutes); the table is
  the first answer.
- **Increment 2 = US2**: analysis only; the verdicts decide the go / no-go.
- **Increment 3 = US3**: analysis only plus the record.
- Size: 20 tasks, three stories, four commits, about 50 minutes of measurement; within the project's size rule.
