# Implementation Plan: Held-Item Sources (held items, slice H1)

**Branch**: `011-held-item-sources` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-held-item-sources/spec.md`

## Summary

Bring the archived item-source code (commit `a8b529b`, `src/` and `tests/` only) onto this branch, then
change one thing: the text that `platsim explain` shows for the new sources is rewritten in plain
language, and the test sentinel that lived in that text moves out of it. The availability ledger then
models the Route 221 house, the Pastoria City berry house and Amity Square; the validator follows the
ledger. No optimizer, player or candidate change.

## Technical Context

**Language/Version**: Python 3.14 (uv); Node ≥ 22.18 only for the unchanged node test suite

**Primary Dependencies**: none new; the existing decomp readers (`platsim.decomp.scripts`)

**Storage**: generated JSON in `data/generated/` (git-ignored, rebuilt by `uv run platsim extract`)

**Testing**: pytest (`tests/integration/test_availability_controls.py`, `tests/unit/test_validator.py`,
a new explain-text test, then the full suite); node tests unchanged

**Target Platform**: this Linux machine, offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: `platsim extract` stays about 40 s (41.8 s measured on the same code in 008)

**Constraints**: decomp is ground truth; no hand-typed item lists; `data/generated/` rebuilt per branch

**Scale/Scope**: 3 files from one commit (+253 / −14 lines), plus the text change and one new test;
11 held items change availability (research R2)

## Constitution Check

`main` carries constitution v1.4.0 (Principles I-VI).

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Every new source is parsed from decomp scripts, with file:line refs; the Amity Gift Man list is parsed from `scrcmd_amity_square.c`; no hand-typed lists. The text rewrite keeps every file:line reference | PASS |
| II. Showdown is the battle engine | No battle change | N/A |
| III. In-game legality | Validator follows the ledger; tests for 1 vs 2 Focus Sash holders and Choice Band | PASS |
| IV. Reproducible, honest evaluation | SC-006: B1-B5 candidates identical, one same-seed quick optimization identical apart from provenance hashes | PASS (planned) |
| V. Verified claims, positive controls | Positive: Focus Sash/Expert Belt/Black Belt = 1 copy; `main`'s pinned 66/55 counts must move to 74/44. Negative: Liechi stays unobtainable, Choice Band unavailable. Jargon test has a positive control (it must fail on the archived text) | PASS |
| VI. Reference-first speed | No approximation is introduced | N/A |

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/011-held-item-sources/
├── spec.md
├── plan.md                      # this file
├── research.md                  # R1 patch applies; R2 counts; R3 optimizer impact; R4 jargon; R5 sentinel
├── contracts/explain-text.md    # the user-facing text for the new sources
├── quickstart.md                # validation run guide
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

No `data-model.md`: no new entity. The new sources reuse the ledger's existing source record
(kind, map, quantity, gates, refs, conditions, detail text).

### Source Code (repository root)

```text
src/platsim/availability/sources.py               # from a8b529b, then: plain-language detail text (contract),
                                                  # sentinel moved out of the text (research R5)
tests/integration/test_availability_controls.py   # from a8b529b: new-source tests, count pins 66/55 -> 74/44;
                                                  # sentinel test reads the helper, not the text
tests/unit/test_validator.py                      # from a8b529b: Focus Sash once / twice, Choice Band
tests/integration/test_explain_item_sources.py    # new: explain text for the new sources has no internal labels
```

**Structure Decision**: existing single-project layout; three changed files and one new test file.

## Approach

1. **Baseline first.** On this branch before any code change (code = `main`), rebuild `data/generated/`
   and save: per-item availability, B1-B5 held-item candidates, `explain` for the 11 items, and a
   same-seed quick optimization of one benchmark team. Evidence in `runs/011-evidence/` (git-ignored).
2. **Apply** `a8b529b` with `git cherry-pick -n`, keeping only `src/` and `tests/`. Commit as is, so the
   diff of step 3 reads alone.
3. **Text and sentinel.** Rewrite the new-source detail text per `contracts/explain-text.md`; move the
   sentinel out of the text (R5). Add the explain-text test; confirm it fails on the step-2 text first.
4. **Rebuild and verify.** `platsim extract` and `--check`; focused tests; per-item diff against the
   baseline (every changed item is one these sources give); B1-B5 candidates identical; same-seed quick
   optimization identical apart from provenance hashes.
5. **Full suite**, record in `validation-log.md`, commit, push, hand over for the user's test.

## Complexity Tracking

None. No principle violation, no new abstraction.
