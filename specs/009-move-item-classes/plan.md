# Implementation Plan: Move and Item Classification

**Branch**: `009-move-item-classes` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-move-item-classes/spec.md`

## Summary

Bring 007 commit `9e1f065` onto `main` unchanged (src/tests only): `move_classes.py`, `item_classes.py`,
their tests, the adopted-move field and HM-placement tiers in `resources.py`, and small refactors in
`candidates.py` and `run.py`. Then prove nothing the optimizer does changes. Slice 2 of the 007 re-slice.

## Technical Context

**Language/Version**: Python 3.14 (uv)

**Primary Dependencies**: none new; decomp readers (`platsim.decomp.moves`, `platsim.decomp.items`)

**Storage**: none new; `MemberSpec.adopted` serialised only when non-empty

**Testing**: pytest (`test_move_classes.py`, `test_item_classes.py`, `test_required_hms_adopted.py`, `test_required_hms.py`, then the full suite)

**Target Platform**: this Linux machine, offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: no change in optimizer run time (the classification is cached)

**Constraints**: decomp is ground truth (rule table = decomp constants only); no behaviour change

**Scale/Scope**: one commit, 8 files (+666 / −26 in src/tests)

## Constitution Check

Constitution v1.4.0 (on `main` since slice 1).

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Categories derived from effect scripts; rule table holds ~20 decomp constants, never move names; test checks each constant exists | PASS |
| II. Showdown is the battle engine | No battle change | N/A |
| III. In-game legality | HM placement still places every required HM; validator unchanged | PASS (verified by tests + R3 check) |
| IV. Reproducible, honest evaluation | Same-seed quick run before/after (SC-004) | PASS (planned) |
| V. Verified claims, positive controls | Screech → foe drop, Magnitude → variable not fixed, 17 resist berries found numerically (a name-only search finds 0), Amulet Coin no outcome | PASS |
| VI. Reference-first | No approximation added | N/A |

Post-design re-check: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-move-item-classes/
├── spec.md, plan.md, research.md, quickstart.md, tasks.md, validation-log.md
└── checklists/requirements.md
```

No `data-model.md` / `contracts/`: no new interface; `MemberSpec.adopted` is documented in research R4.

### Source Code (repository root)

```text
src/platsim/optimizer/move_classes.py     # new: effect categories, rule table, exclusion reasons
src/platsim/optimizer/item_classes.py     # new: hold-effect references (name + number), no-outcome, exp/EV
src/platsim/optimizer/candidates.py       # EXCLUDED_ATTACK_EFFECTS and exp/EV list now from the new modules
src/platsim/optimizer/resources.py        # MemberSpec.adopted; _slot_cost tiers; repair keeps adopted
src/platsim/optimizer/run.py              # dataclasses.replace instead of positional MemberSpec(...)
tests/unit/test_move_classes.py, test_item_classes.py, test_required_hms_adopted.py   # new
```

**Structure Decision**: existing layout.

## Approach

1. **Before** (code = `main`): record held-item candidates and movesets for B1-B5 (slice 1's script), the
   HM-placement choice for every candidate moveset × HM (research R3), and a same-seed quick run.
2. **Apply** `git cherry-pick -n 9e1f065`, keep src/tests only; confirm byte-identical to the commit.
3. **Verify**: focused tests; candidates identical; HM choices identical; quick run identical except the
   code fingerprint; full suite.
4. Docs, commit, push, user test, merge.

## Complexity Tracking

None.
