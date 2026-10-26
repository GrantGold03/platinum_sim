# Feature Specification: Fast test mode without the battle simulations

**Feature Branch**: `012-fast-test-mode`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Fast test mode without the battle simulations. The full suite takes about 2.5 h (measured 2:27:20 for 522 pytest tests on 2026-10-26), almost all of it in integration tests that start the Node/Showdown battle worker or the optimizer. Add a pytest marker (e.g. battle_sim) on every such test and one documented command for the fast mode (e.g. `uv run pytest -m "not battle_sim"`) that runs everything else. Add a guard test so a new battle-simulation test cannot be left unmarked: positive control, a known battle test carries the marker; negative check, the fast set starts no Node worker. Record per-test times once with `--durations=0` on a full run to confirm the split and the fast mode's run time. The full suite plus `node --test sim/test/*.test.mjs` stays the gate before any merge; the fast mode is for iterating on features that don't touch the battle code. Test infrastructure only, no behaviour change. Keep it small: one story, well under 30 tasks. User note: take extra care that the split is correct."

## Clarifications

### Session 2026-10-26

- Q: What is the fast mode's run-time target? → A: At most 30 minutes, to allow for future growth (user).
- Q: Should a test that starts the battle simulation without the battle mark fail in every run, or only in the fast
  mode? → A: In every run, including the full suite before merge (user).
- Q: Do tests that start a Node program other than the battle worker (the divergence check's data dump) count as
  battle tests? → A: No; only the battle worker counts. The divergence check stays in the fast set, its time is
  recorded, and the user decides if it is slow (user).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run every test except the battle simulations in minutes (Priority: P1)

While working on a feature that does not touch the battle code (the availability ledger, the validator, `explain`,
the web UI, the reports), the developer runs one documented command and gets the result of every test that does not
simulate a battle, in minutes instead of 2.5 hours. The split is trustworthy in both directions: no battle
simulation hides in the fast set, and nothing is left out of the fast set without a reason. Before any merge the
full suite still runs, as today.

**Why this priority**: It is the whole feature. Today every check of a ledger or UI change waits about 2.5 hours
(measured 2:27:20 on 2026-10-26), and the held-item slices H2, H3+ are mostly that kind of change.

**Independent Test**: Run the fast command on `main` plus this feature. It finishes in minutes, starts no battle
worker, and the fast and battle sets together are exactly the full collection.

**Acceptance Scenarios**:

1. **Given** the repository after this feature, **When** the developer runs the documented fast command, **Then**
   every test that does not simulate a battle runs, none that does, and the run finishes within the time in SC-001.
2. **Given** any run (fast or full), **When** a test without the battle mark starts the battle-simulation worker,
   **Then** that test fails with a message naming it and saying it must be marked as a battle test.
3. **Given** a new test that simulates a battle but carries no battle mark, **When** the fast command or the full suite
   runs, **Then** the run fails on that test (scenario 2), so the gap cannot reach `main`.
4. **Given** a full run (no selection), **When** it finishes, **Then** every test marked as a battle test has started
   the battle worker at least once, and a record lists any marked test that did not (expected: none).
5. **Given** the full suite, **When** it is run after this feature, **Then** the collected tests and their outcomes are
   the same as before the feature, apart from the tests this feature adds.

### Edge Cases

- **A test file mixes battle and non-battle tests** (e.g. `test_policy_strength.py` has a moves check that may not
  battle): the split is per test, not per file.
- **A test reaches the battle worker indirectly**: through the optimizer, `evaluate`, or a web job that runs the real
  optimizer or evaluator in a child process. It counts as a battle test; the detection must also see a worker started
  from a child process.
- **A test starts a Node program that is not the battle worker** (the divergence check runs a Node script that reads
  Showdown's data and simulates nothing): it is not a battle test and stays in the fast set (Clarifications). Its measured time is
  recorded; if it is large, the user decides.
- **A test is slow but simulates no battle** (e.g. the session-wide ledger build, about 35 s): it stays in the fast
  set; the fast mode excludes battles, not slowness. Its time shows in the recorded timings.
- **Browser tests** (system Chrome) stay in the fast set.
- **Expected failures**: the 4 tests marked as expected failures keep that status in whichever set they fall.
- **A marked test that fails, is skipped or is an expected failure** may stop before reaching the worker, so the
  over-marking check (FR-005) judges only marked tests that ran and passed.
- **Two fixtures with the same name** (e.g. `pool` in two battle files): the split tells fixtures apart by where they
  are defined, never by name alone.
- **A worker started outside any test** (e.g. while tests are being collected) fails the run.
- **The Node test suite** (`node --test sim/test/*.test.mjs`, about 4.5 min, 314 tests) is not part of either pytest
  set; it is unchanged and still part of the merge gate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every pytest test that starts the battle-simulation worker, directly or indirectly (optimizer,
  evaluator, web job with a real runner, worker pool), MUST carry one battle mark. No other test may carry it.
- **FR-002**: There MUST be one documented command for the fast mode that runs every test without the battle mark.
  It MUST be listed in the README next to the full-suite command, with the merge rule.
- **FR-003**: In every run (fast mode and full suite), a test without the battle mark that starts the battle worker
  MUST fail and name itself, whatever the path by which it started the worker (in-process or child process). A
  correctly marked test is never affected.
- **FR-004**: A guard test MUST check, with a positive control, that the run-time detection of FR-003 works: a known
  battle test carries the mark, and a deliberate worker start without the mark is caught.
- **FR-005**: The split MUST be verified in both directions on one full run, and the results recorded in the
  feature's validation log:
  - no unmarked test started the battle worker (the FR-003 detection fails any such test);
  - every marked test started it at least once (no over-marking).
- **FR-006**: Per-test run times MUST be recorded once from a full run, and the fast mode's own run time measured
  from a run of the fast command.
- **FR-007**: The merge gate MUST stay: the full pytest suite plus the Node test suite, before any merge. The fast
  mode MUST NOT be described as sufficient for a merge.
- **FR-008**: No change to the program's behaviour (`src/`, `sim/`): only tests, test configuration and docs change.
  The full suite's collected tests and outcomes MUST stay the same apart from the tests this feature adds.
- **FR-009**: The split MUST be by test, determined from what each test does, not by file name or by guess; each
  marked test's reason (the path by which it reaches the worker) MUST be recorded in the feature's docs.

### Key Entities

- **Battle test**: a pytest test that starts the battle-simulation worker at least once during its run.
- **Fast set**: every collected pytest test that is not a battle test.
- **Battle-worker start**: the moment the program launches the Node battle-simulation worker; the single event that
  the detection watches.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The fast command finishes in at most 30 minutes on this machine (measured; estimate today 10-12 min;
  the margin allows for future growth).
- **SC-002**: Fast set + battle set = the full collection, with no test in both (counts recorded; 522 on `main`
  before this feature, plus the tests it adds).
- **SC-003**: On the recorded full run, 0 unmarked tests start the battle worker and 0 marked tests fail to start it.
- **SC-004**: A deliberately unmarked battle test is caught by the fast mode (FR-004 positive control passes).
- **SC-005**: The full suite after the feature has the same outcomes as on 2026-10-26 (517 passed, 4 expected
  failures, plus the one test that failed only because of a commit made during that run, which must pass), plus the
  added tests passing; Node suite 314 of 314.

## Assumptions

- The battle-worker start is a single, observable event in the program (the worker pool launching `sim/worker.mjs`);
  the plan confirms this and finds every path to it.
- One extra full run (about 2.5 h, local machine only, no paid resources) is needed for FR-005 and FR-006; it can be
  the same run that serves as the merge gate.
- No parallel test runner is added; that is separate work.
