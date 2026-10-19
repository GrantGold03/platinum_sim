# Tasks: Ledger Item Sources

**Input**: Design documents from `specs/008-ledger-item-sources/` (spec.md, plan.md, research.md, quickstart.md)

**Tests**: the tests already exist in the 007 commit `a8b529b`; they come over with the code. Before the
code is applied, `main`'s count pins (66/55) are the positive control that must change.

## Conventions

- Temp files go in the session scratchpad; evidence worth keeping goes in `runs/008-evidence/` (git-ignored).
- Never `git commit -a` (the user's uncommitted deletion of `.claude/scheduled_tasks.lock` stays out).
- Rebuild `data/generated/` with `uv run platsim extract` on this branch before any check; it is shared
  between branches.
- Record every result with real output in `specs/008-ledger-item-sources/validation-log.md`.

## Phase 1: Setup

- [X] T001 Create `specs/008-ledger-item-sources/validation-log.md`; record branch, base `f88cdd0`, the R1 patch check and the R2 `main` counts (66/37/55, snapshot `runs/008-evidence/availability-main-f88cdd0.json`)
- [X] T001b Before the code is applied (the branch's code still equals `main`, `git diff --stat main -- src sim tests` empty): quick optimization of B2 (Garchomp, Infernape, Staraptor, Rotom, Floatzel, Weavile), seed `008-sc005`, out `runs/008-evidence/sc005-main`; record wall time. This is SC-005's "before"

## Phase 2: Foundational

- [X] T002 Apply `a8b529b` to the working tree with `git cherry-pick -n a8b529b`; restore the 007 spec files it touches (`git restore --staged --worktree specs/007-status-moves-items`) so only `src/platsim/availability/sources.py`, `tests/integration/test_availability_controls.py` and `tests/unit/test_validator.py` change; record any adaptation per FR-008
- [X] T003 Rebuild with `uv run platsim extract` and `uv run platsim extract --check`; record the run time and the new counts

## Phase 3: User Story 1 - New item sources appear in the item catalog (P1)

**Goal**: the three sources are in the ledger with script references, copies and verdicts.
**Independent test**: `test_availability_controls.py` passes; catalog lookups show the sources.

- [X] T004 [US1] Run `uv run pytest -q tests/integration/test_availability_controls.py tests/integration/test_extract.py`; record the output (SC-002 counts 74/40/44)
- [X] T005 [US1] Diff per-item availability against `runs/008-evidence/availability-main-f88cdd0.json` with a scratchpad script; list every changed item with old and new copies and its source; confirm every change comes from the Route 221 house, the Pastoria berry house or Amity Square (SC-002, FR-006)
- [X] T006 [US1] Look up Focus Sash, Expert Belt, Black Belt, one Pastoria berry and one Amity Square item with `uv run platsim explain item:<key>`; record source, script reference, copies and verdict for each (SC-001, FR-004)

## Phase 4: User Story 2 - The validator accepts teams that hold these items (P1)

**Goal**: validator and ledger agree.
**Independent test**: the Route 221 validator test passes.

- [X] T007 [US2] Run `uv run pytest -q tests/unit/test_validator.py`; record that one Focus Sash holder passes, two give ITEM_COPIES and Choice Band gives ITEM_UNAVAILABLE (SC-003, FR-005)

## Phase 5: User Story 3 - Nothing else changes (P2)

**Goal**: optimizer inputs and results unchanged.
**Independent test**: identical held-item candidates; byte-identical same-seed quick run.

- [X] T008 [US3] For every member of B1-B5 (`tests/fixtures/bench_007.json` on the 007 branch; copy the team lists into the scratchpad script), compute `held_item_candidates` on `main`'s ledger snapshot and on this branch's ledger; record whether any differ and, if so, which item and why (FR-007, research R3)
- [X] T009 [US3] The same quick optimization as T001b with the code applied, out `runs/008-evidence/sc005-branch`; `cmp` the two `result.json` files; record (SC-005). If T008 found a candidate difference that touches B2, explain the difference instead

## Phase 6: Polish

- [X] T010 Full suite: `uv run pytest -q` and `node --test sim/test/*.test.mjs`; record the output against `main`'s last full run and explain every changed count (SC-004)
- [X] T011 Update `README.md` where it lists item sources or the held-item counts, and `RUN-STATE.md` (re-slice progress); move `FUTURE-FEATURES.md` from the 007 branch to this branch and mark slice 1 done, renumbering the old "008" items
- [X] T012 Commit (src, tests, docs; not the lock deletion), push, and hand over for the user's hands-on test. Do not merge

## Dependencies

- T001 → T001b → T002 → T003 → (T004, T005, T006, T007, T008 in any order) → T009 → T010 → T011 → T012.
- T001b must finish before T002 (it needs `main`'s code and ledger).

## Parallel opportunities

- T004-T008 read the same rebuilt data and do not write shared files; T005, T006 and T008 can run together.

## Implementation strategy

One increment: all three stories land together in this small slice; US3 is the acceptance gate for the
re-slice method (a slice must not move optimizer results unless explained).
