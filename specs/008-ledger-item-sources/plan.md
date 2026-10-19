# Implementation Plan: Ledger Item Sources

**Branch**: `008-ledger-item-sources` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-ledger-item-sources/spec.md`

## Summary

Bring the 007 item-source work (commit `a8b529b` on `007-status-moves-items`) onto `main` unchanged, then
re-verify it on `main`: the availability ledger models the Route 221 house, the Pastoria City berry house
and Amity Square; the validator follows the ledger. No optimizer, player or candidate change. This is slice 1
of the 007 re-slice (`FUTURE-FEATURES.md`).

## Technical Context

**Language/Version**: Python 3.14 (uv); Node ≥ 22.18 only for the unchanged test suite

**Primary Dependencies**: none new; the existing decomp readers (`platsim.decomp.scripts.walk`)

**Storage**: generated JSON in `data/generated/` (git-ignored, rebuilt by `uv run platsim extract`)

**Testing**: pytest (`tests/integration/test_availability_controls.py`, `tests/unit/test_validator.py`,
`tests/integration/test_extract.py`, then the full suite); node tests unchanged

**Target Platform**: this Linux machine (16 threads), offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: `platsim extract` stays about 40 s (measured 41.8 s on `main`, 2026-10-19)

**Constraints**: decomp is ground truth; no hand-typed item lists; generated data must be rebuilt per branch

**Scale/Scope**: 3 files from one commit (+253 / −14 lines); 11 items change availability (see research R2)

## Constitution Check

`main` is on constitution v1.3.0 (Principles I-V). v1.4.0 (VI, reference-first) is only on the 007 branch;
this feature has no approximation, so VI does not apply here.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Every new source is parsed from decomp scripts with file:line references; no hand-typed lists (the Amity Gift Man list is parsed from `scrcmd_amity_square.c`) | PASS |
| II. Showdown is the battle engine | No battle change | N/A |
| III. In-game legality | Validator follows the ledger; tests for 1 vs 2 Focus Sash holders and Choice Band | PASS |
| IV. Reproducible, honest evaluation | SC-005: same-seed quick optimization before/after; every difference explained | PASS (planned) |
| V. Verified claims, positive controls | Positive: Focus Sash/Expert Belt/Black Belt = 1, main's pinned 66/55 counts must change. Negative: Liechi 0, Choice Band unavailable | PASS |

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/008-ledger-item-sources/
├── spec.md
├── plan.md          # this file
├── research.md      # R1 patch applies; R2 counts before/after; R3 optimizer impact
├── quickstart.md    # validation run guide
├── checklists/requirements.md
└── tasks.md         # /speckit-tasks
```

No `data-model.md` or `contracts/`: no new entities or interfaces. The new sources reuse the ledger's
existing source records (kind, detail, availability_ref, copies, conditions).

### Source Code (repository root)

```text
src/platsim/availability/sources.py               # from a8b529b: return-aware dataflow, GetRandom+AddVar
                                                  # ranges, save-var literals, Amity Gift Man table,
                                                  # daily-random-level rule (1 copy)
tests/integration/test_availability_controls.py   # from a8b529b: new source tests; count pins 66/55 -> 74/44
tests/unit/test_validator.py                      # from a8b529b: Focus Sash once / twice, Choice Band
```

**Structure Decision**: existing single-project layout; three files only.

## Approach

1. **Apply** the three files from `a8b529b` with `git cherry-pick -n a8b529b`, keeping only `src/` and
   `tests/` (the commit's 007 `tasks.md` / `validation-log.md` edits are dropped). Record any adaptation.
2. **Rebuild** `uv run platsim extract` and `--check` on this branch.
3. **Verify** the focused tests, then the before/after diff of per-item availability against the saved
   `main` snapshot (`runs/008-evidence/availability-main-f88cdd0.json`): every changed item must come from
   the three sources.
4. **Optimizer impact (SC-005)**: compute `held_item_candidates` for every member of B1-B5 on `main`'s and
   this branch's ledger; if identical, a same-seed quick optimization of one team must be byte-identical
   (one run is enough as a control). If any differs, explain it before going further.
5. **Full suite** (about 2.5 h), record, commit, push, hand over for the user's test.

## Complexity Tracking

None. No principle violation, no new abstraction.
