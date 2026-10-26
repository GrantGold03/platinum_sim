# Tasks: Held-Item Sources (held items, slice H1)

**Input**: Design documents from `specs/011-held-item-sources/` (spec.md, plan.md, research.md,
contracts/explain-text.md, quickstart.md)

**Tests**: The ledger and validator tests come over with commit `a8b529b`. One new test is required by the
spec (FR-007): the explain-text check, written to fail first on the archived text.

## Conventions

- Temp files go in the session scratchpad; evidence worth keeping goes in `runs/011-evidence/` (git-ignored).
- Never `git commit -a`: the user's uncommitted deletion of `.claude/scheduled_tasks.lock` stays out.
- `data/generated/` is shared between branches: rebuild with `uv run platsim extract` before any check.
- Record every result with real output in `specs/011-held-item-sources/validation-log.md`.
- Benchmark teams B1-B5: `tests/fixtures/bench_007.json` on branch `007-status-moves-items`
  (`git show 007-status-moves-items:tests/fixtures/bench_007.json`); copy into the scratchpad, not into the repo.
- Push every commit that touches `src/` or `tests/` (memory `push-code-commits`). Do not merge.

## Phase 1: Setup (baseline, code = `main`)

Must finish before any code change: these capture the "before" on `main`'s code.

- [ ] T001 Create `specs/011-held-item-sources/validation-log.md`: branch, base `73af068`, `git diff --stat f88cdd0 HEAD -- src tests sim` (must be empty) and the R1 `git apply --check` output
- [ ] T002 Rebuild with `uv run platsim extract` (record wall time); save per-item availability for every held item to `runs/011-evidence/availability-main.json` and record the counts (expected 66/37/55, research R2)
- [ ] T003 [P] Save `uv run platsim explain item:<key>` to `runs/011-evidence/explain-main.txt` for the 11 items of research R2 (`black_belt`, `expert_belt`, `focus_sash`, `charti_berry`, `chilan_berry`, `coba_berry`, `kebia_berry`, `occa_berry`, `passho_berry`, `payapa_berry`, `tanga_berry`), the Amity berry `belue_berry`, and the negative controls `liechi_berry` and `choice_band`
- [ ] T004 [P] For every member of B1-B5, compute `held_item_candidates` with a scratchpad script and save to `runs/011-evidence/candidates-main.json`
- [ ] T005 Quick optimization of B2 (garchomp, infernape, staraptor, rotom, floatzel, weavile), seed `011-sc006`, out `runs/011-evidence/sc006-main`; record wall time and the `result.json` sha256 (about 23 min). Must finish before T006: worker processes may re-import code or re-read generated data mid-run

## Phase 2: Foundational (bring over the archived code)

- [ ] T006 `git cherry-pick -n a8b529b`; restore the 007 spec files it touches (`git restore --staged --worktree specs/007-status-moves-items`) so only `src/platsim/availability/sources.py`, `tests/integration/test_availability_controls.py` and `tests/unit/test_validator.py` change; record any adaptation (FR-009)
- [ ] T007 Commit those three files alone as "feat(011): bring over item sources from a8b529b (unchanged)"; push
- [ ] T008 Rebuild with `uv run platsim extract` and `uv run platsim extract --check`; record wall time and the new counts (expected 74/40/44)

## Phase 3: User Story 1 - New item sources appear in the item catalog (P1)

**Goal**: the three sources are in the ledger and `explain` shows them in plain language.
**Independent test**: `explain` for Focus Sash, Expert Belt, Black Belt, Occa Berry and Belue Berry shows the source, ref, copies and verdict, with no internal labels.

- [ ] T009 [US1] In `src/platsim/availability/sources.py`, add a helper that returns the newly found give sites (research R5), computed by the same comparison that sets `new_site`; do not change any text yet. Change `test_dataflow_sentinel_only_expected_give_sites_change` in `tests/integration/test_availability_controls.py` to read the helper instead of searching the text for "007"; run it and record that it passes with the expected set (Route 221 house, Pastoria SW house, Amity Square, Route 208 house, Solaceon News Press, Flower Shop)
- [ ] T010 [US1] Write `tests/integration/test_explain_item_sources.py` per `contracts/explain-text.md`: for every item with an entry at a site the T009 helper returns, run the explain function and fail on any forbidden pattern (rule 2) or a lost file:line ref (rule 3). Positive control: three archived lines embedded as fixture strings (contract "Check") must be rejected. Run it and record that it fails on the T007 code
- [ ] T011 [US1] In `src/platsim/availability/sources.py`, stop appending the " (007 dataflow: ...)" tag to `Entry.detail` and rewrite the new-source reason text per the contract table: Route 221 (once a day, daily random level, 1 copy each), Pastoria (once a day, random berry, unlimited), Amity (can be received again; needs one of N partner species). Move flag, level-check and party-check file:lines out of the sentence into the entry's refs (contract rule 3)
- [ ] T012 [US1] Rebuild (`uv run platsim extract`), then run `uv run pytest -q tests/integration/test_explain_item_sources.py tests/integration/test_availability_controls.py tests/integration/test_extract.py tests/integration/test_explain.py`; record the output (SC-001, SC-004, SC-002 count pins 74/40/44). Also name the existing test that covers the spec's "post-Champion sources" edge case (a source reachable only after the Champion is reported as such), or record that none does
- [ ] T013 [US1] Save `explain` for the same items as T003 to `runs/011-evidence/explain-branch.txt`; diff against `explain-main.txt` and against `runs/008-evidence/explain.txt`; record that Liechi Berry and Choice Band are unchanged from `main` (FR-006) and quote the new Focus Sash, Occa Berry and Belue Berry lines in the log, plus one Amity Square Gift Man entry (find an item it gives from the ledger; FR-003)

## Phase 4: User Story 2 - The validator accepts teams that hold these items (P1)

**Goal**: validator and ledger agree.
**Independent test**: one Focus Sash holder passes; two fail on copies; Choice Band fails as unavailable.

- [ ] T014 [P] [US2] Run `uv run pytest -q tests/unit/test_validator.py`; record that one Focus Sash holder passes, two give ITEM_COPIES and Choice Band gives ITEM_UNAVAILABLE (SC-003, FR-005)

## Phase 5: User Story 3 - Nothing else changes (P2)

**Goal**: optimizer inputs and results unchanged.
**Independent test**: identical held-item candidates; same-seed quick run identical apart from provenance hashes.

- [ ] T015 [P] [US3] Diff per-item availability against `runs/011-evidence/availability-main.json`; list every changed item with old and new copies and its source; confirm every change comes from the Route 221 house, the Pastoria berry house or Amity Square (SC-002, FR-006)
- [ ] T016 [P] [US3] Recompute B1-B5 `held_item_candidates` to `runs/011-evidence/candidates-branch.json`; compare with T004; record identical or explain each difference (FR-008, SC-006)
- [ ] T017 [US3] Same quick optimization as T005, out `runs/011-evidence/sc006-branch`; field-level diff of the two `result.json` files; record that only provenance hashes differ (SC-006)

## Phase 6: Polish

- [ ] T018 Commit T009-T011 (src and tests only) as "feat(011): plain-language explain text for the new item sources"; push
- [ ] T019 Full suite in the background: `uv run pytest -q` (about 2.5 h) and `node --test sim/test/*.test.mjs`; record against 008's run (509 passed, 4 xfailed; node 314) and explain every changed count (SC-005)
- [ ] T020 Update `README.md` where it lists item sources or held-item counts; `FUTURE-FEATURES.md` (held-items slices H1 done pending test, H2 next); `RUN-STATE.md`; commit docs
- [ ] T021 Hand over for the user's hands-on test (quickstart section 4). Do not merge

## Dependencies

- T001 → T002 → (T003, T004 in parallel) → T005 → T006 → T007 → T008.
- T008 → T009 → T010 → T011 → T012 → T013.
- T014, T015, T016 after T012 (they need the final rebuilt data); T017 after T016.
- T018 after T013-T017; T019 after T018; T020 → T021.
- US2 (T014) and US3 (T015-T017) do not depend on US1's text change for their results, but run after it so
  every check sees the final code.

## Parallel opportunities

- T003 and T004 (different outputs, same data).
- T014, T015 and T016 (read-only checks on the same rebuilt data).
- T005 (23 min) can run alongside T003-T004 once T002 is done.

## Implementation strategy

One small increment. US1 is the user's test surface; US2 is the legality guard; US3 is the slice's
acceptance gate (no optimizer change). 21 tasks, 3 stories.
