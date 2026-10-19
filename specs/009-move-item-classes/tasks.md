# Tasks: Move and Item Classification

**Input**: `specs/009-move-item-classes/` (spec.md, plan.md, research.md, quickstart.md)

**Tests**: come with the 007 commit `9e1f065`. The "before" records (T002-T004) are taken while the
branch's code still equals `main`.

## Conventions

- Temp files in the session scratchpad; evidence in `runs/009-evidence/` (git-ignored).
- Never `git commit -a` (the user's `.claude/scheduled_tasks.lock` deletion stays out).
- `data/generated/` is shared between branches: `uv run platsim extract --check` before checks.
- Record results with real output in `specs/009-move-item-classes/validation-log.md`.

## Phase 1: Setup

- [X] T001 Create `specs/009-move-item-classes/validation-log.md`; record branch, base `de102fa`, R1 patch check, R2 and R3 findings; confirm `git diff --stat main -- src sim tests` is empty and `extract --check` is up to date

## Phase 2: Before (code = `main`)

- [X] T002 [P] Record B1-B5 candidate movesets and held items (all variants; Lv 45/55/65) with slice 1's script (`runs/008-evidence/` method; copy to `runs/009-evidence/candidates-main.json`)
- [X] T003 [P] Write a scratchpad script that, for every member/variant/level above, every ranked candidate moveset and every HM in `/api/hms` order, records which slot `resources.place_required_hms` replaces on a one-member team (or the refusal); save `runs/009-evidence/hm-main.json` (research R3)
- [X] T004 Quick optimization of B2 (garchomp, infernape, staraptor, rotom, floatzel, weavile), seed `009-sc004`, out `runs/009-evidence/sc004-main`; record wall time

## Phase 3: Apply

- [X] T005 `git cherry-pick -n 9e1f065`; drop the 007 spec file it touches; confirm the 8 src/test files are byte-identical to `9e1f065` (FR-008)

## Phase 4: User Stories 1 and 2 - classification (P1)

**Independent test**: the classification tests pass.

- [X] T006 [US1] [US2] Run `uv run pytest -q tests/unit/test_move_classes.py tests/unit/test_item_classes.py`; record counts and the positive controls (Screech foe drop, 6 fixed-damage effects, Magnitude variable, 17 resist berries, Amulet Coin no outcome, exp/EV items) (SC-001, SC-002)

## Phase 5: User Story 3 - nothing changes (P1)

**Independent test**: identical candidates, HM choices and quick-run result.

- [X] T007 [US3] Run `uv run pytest -q tests/unit/test_required_hms_adopted.py tests/unit/test_required_hms.py`; record (FR-006, FR-007)
- [X] T008 [US3] Re-run T002 and T003 on the branch; `cmp` with the `-main` files; record; explain any difference before going on (SC-003, FR-004, FR-005, FR-006)
- [X] T009 [US3] Re-run T004's request, out `runs/009-evidence/sc004-branch`; field-level diff of the two `result.json`; only `platsim_code_hash` may differ (SC-004)

## Phase 6: Polish

- [X] T010 Full suite `uv run pytest -q` and `node --test sim/test/*.test.mjs`; record against slice 1's run (509 passed, 4 xfailed; node 314) and explain every changed count (SC-005)
- [X] T011 Update `RUN-STATE.md` (slice 2 section) and `FUTURE-FEATURES.md` (slice 2 status); README only if it describes these rules
- [X] T012 Commit (src, tests, docs; not the lock deletion), push, hand over for the user's test; do not merge

## Dependencies

T001 → (T002, T003, T004) → T005 → (T006, T007, T008) → T009 → T010 → T011 → T012.
T002-T004 must finish before T005 (they need `main`'s code).

## Parallel opportunities

T002 and T003 together; T004 alone (uses all workers). T006-T008 together.
