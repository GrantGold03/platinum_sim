# Implementation Plan: No Single-Use Held Items (held items, slice H2)

**Branch**: `013-no-single-use-items` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-no-single-use-items/spec.md`. User input at `/speckit-plan`: "running on one team is sufficient. Running all 5 is not needed" (recorded in the spec's Clarifications; FR-007, SC-005).

## Summary

Add a decomp reader, `platsim.decomp.item_use`, that marks each held item single-use when its own hold effect, on
triggering, reaches the battle-script command `RemoveItem` on the holder (research R1, R2), and marks it a berry from
its item pocket (R3). `held_item_candidates` drops any item that is single-use and not a berry, as one final filter
(R5). The filter removes nothing today, so B1-B5 candidates and a same-seed B2 run must match `main` (R6).

## Technical Context

**Language/Version**: Python 3.14 (uv); Node 22 only for the unchanged Node suite

**Primary Dependencies**: none new; existing readers `platsim.decomp.items`, `platsim.decomp._util`
(`ref`, `line_of`), comment stripping as in `platsim.optimizer.abilities.strip_comments`

**Storage**: none; `data/generated/` unchanged (R3)

**Testing**: pytest: new `tests/unit/test_item_use.py`; additions to `tests/unit/test_optimizer_candidates.py`; then
fast mode (`-m "not battle_sim"`) and the Node suite

**Target Platform**: this Linux machine, offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: the reader is cached per process and reads the 624 battle script files and one C file once.
Target: under 1 s. Measured and logged

**Constraints**: decomp is ground truth; no hand-typed item or hold-effect list; generated data unchanged; battle
player, ledger, validator and `explain` unchanged (FR-008)

**Scale/Scope**: 1 new module (about 150-250 lines), 3-line filter in `candidates.py`, 2 test files. 2 user
stories, small task count

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Single-use comes from `RemoveItem` sites and their triggers in `res/battle/scripts/` and `src/battle/battle_lib.c`; berry from `fieldPocket`; every classification carries `file:line` evidence (FR-005) | PASS |
| II. Showdown is the battle engine | No battle change. Showdown's `consumable` flag is at most a cross-check | N/A |
| III. In-game legality | Narrows candidates only; validator unchanged; every output stays legal | PASS |
| IV. Reproducible, honest evaluation | B1-B5 candidates and one same-seed B2 run compared with `main` captured fresh (R6); objective unchanged | PASS (planned) |
| V. Verified claims, positive controls | Focus Sash single-use, Sitrus allowed berry; the reader raises on an unattributed `RemoveItem` or an empty result; guard test shows an injected `focus_sash` is filtered and would otherwise appear | PASS (planned) |
| VI. Reference-first speed | No approximation introduced | N/A |

Workflow: Spec Kit stages run by the user; tasks via `/speckit-implement`; branch merged after the user's test.

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/013-no-single-use-items/
├── spec.md
├── plan.md                 # this file
├── research.md             # R1 removal sites; R2 reader rules; R3 berry; R4 expected sets; R5 filter; R6 comparison
├── data-model.md           # ItemUse, RemoveSite
├── contracts/item-use.md   # item_uses(), is_excluded_single_use()
├── quickstart.md           # validation run guide
├── checklists/requirements.md
└── tasks.md                # /speckit-tasks
```

### Source Code (repository root)

```text
src/platsim/decomp/item_use.py            # new: RemoveItem sites, C trigger switches, script guards, berry pocket
src/platsim/optimizer/candidates.py       # held_item_candidates: final filter via is_excluded_single_use
tests/unit/test_item_use.py               # new: positive/negative controls, completeness gate, evidence refs
tests/unit/test_optimizer_candidates.py   # guard test (injected focus_sash filtered; filter-off control)
```

**Structure Decision**: The reader sits with the other decomp readers in `src/platsim/decomp/`. The optimizer only
imports `is_excluded_single_use`. No change to `sim/`, `web/`, the ledger or the validator.

## Complexity Tracking

None. If a reader rule in R2 is replaced by a pinned line assertion (R2 fallback), it is listed here with the reason.
