# Tasks: Variable-Power Attacks Without Regression

**Input**: `specs/010-variable-power/` (spec.md, plan.md, research.md)

## Conventions

- Evidence in `runs/010-evidence/` (git-ignored); temp files in the scratchpad; record real output in
  `specs/010-variable-power/validation-log.md`. Never `git commit -a`. `extract --check` before checks.
- Times for the user in Eastern.

## Phase 1: Research (done)

- [X] T001 Cause of the 007 B2 regression established by paired swaps (research R3, R4)
- [X] T002 Adapt `d3d53e7` onto `main`; Hidden Power excluded; `test_variable_power.py` 11 passed (R1)
- [X] T003 Which variable-power attacks the strong player models (R5)

## Phase 2: User Story 1 - real power, safe pool (P1)

- [ ] T004 [US1] `candidates.py`: add the three unmodelled effects to `NOT_OFFERED_VARIABLE` with reasons; make the pool additive (main's top-`POOL` fixed-power attacks + offered variable-power attacks); keep all combos for repair
- [ ] T005 [US1] Tests: Magnitude/Wring Out/Crush Grip/Punishment not offered (with positive controls that the member learns them); for B1-B5 members every attack in `main`'s pool (`runs/009-evidence/candidates-branch.json` method, store pools) is in the new pool

## Phase 3: User Story 2 - the screen sees real teams (P1)

- [ ] T006 [US2] `sim/policy/greedy.mjs`: `greedy-v2` with variable power for Return, Grass Knot, Low Kick, Gyro Ball; greedy-v1 unchanged; register in `sim/gauntlet.mjs`
- [ ] T007 [US2] `sim/test/greedy_v2.test.mjs`: greedy-v2 gauntlet logs byte-identical to greedy-v1 for the policy benchmark team (no variable-power moves); positive control: a team with Return gives a different log; golden v1/v2 test still passes
- [ ] T008 [US2] `SCREEN_POLICY = "greedy-v2"` in `run.py`, `screen.py`, `abilities.py` (docstrings too); `STATE_VERSION` 3 → 4; update pinned fingerprint tests
- [ ] T009 Unit + node tests; quick B2 run as a smoke test (validator passes; Infernape keeps Close Combat or the screen's choice is recorded)

## Phase 4: User Story 3 / acceptance (P1)

- [ ] T010 Commit and push the code (acceptance runs on a committed hash)
- [ ] T011 Standard optimizations B1-B5, seed `bench-007`, out `runs/bench-010/<B>`; wall time per team vs baseline (SC-003)
- [ ] T012 Each final team vs its baseline final team (`runs/bench-007-baseline/<B>`): 2,000 paired runs, expectimax2-v2, each at its own start levels; McNemar; plus the average-final-level rule; table in the validation log (SC-002, FR-005)
- [ ] T013 If any team is worse: stop, record, explain, and ask the user before changing anything

## Phase 5: Polish

- [ ] T014 Full suite `uv run pytest -q` and node; explain changed counts (SC-005)
- [ ] T015 README (default screen player, variable-power moves offered and not offered), RUN-STATE, FUTURE-FEATURES
- [ ] T016 Commit, push, hand over for the user's test; do not merge

## Dependencies

T004-T005 ∥ T006-T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016.
