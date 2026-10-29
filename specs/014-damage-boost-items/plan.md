# Implementation Plan: Damage-Boosting Held Items (held items, slice H3)

**Branch**: `014-damage-boost-items` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-damage-boost-items/spec.md`. User input at `/speckit-plan`: "use the quick budget for the B2 runs" (recorded in Clarifications).

## Summary

`held_item_candidates` adds Expert Belt (any moveset with an attack) and the physical/special booster that matches
the strongest attack's category, each only when the ledger has a copy. The group is chosen by hold effect from the
decomp (research R1, R2). The existing candidates, copy accounting, battle player and ledger are unchanged. Acceptance
compares B1-B5 candidates with `main`, and B2 at the quick budget by the 010 equal-levels rule. The run time is
measured on both sides (R4, R5).

## Technical Context

**Language/Version**: Python 3.14 (uv); Node 22 for the unchanged Node suite

**Primary Dependencies**: none new; `platsim.decomp.items`, `platsim.decomp.moves`, `platsim.decomp.item_use` (H2
filter), `platsim.evaluate` and `platsim.stats` for the comparison script

**Storage**: none; `data/generated/` unchanged

**Testing**: pytest additions to `tests/unit/test_optimizer_candidates.py`; then fast mode and the Node suite

**Target Platform**: this Linux machine, offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: none set. The B2 quick wall time is measured and the ratio reported (FR-010). Baseline
reference: 1123-1259 s (013)

**Constraints**: decomp is ground truth (items chosen by hold effect); no change to `sim/`, the ledger, the
validator or `explain`; existing candidates keep their order (FR-004)

**Scale/Scope**: about 15 lines in `candidates.py`, about 5 tests, one scratchpad comparison script. 3 stories

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Group chosen by `HOLD_EFFECT_POWER_UP_*` from item data; copies from the ledger | PASS |
| II. Showdown is the battle engine | No battle change. The Expert Belt divergences are already accepted in the ledger and stated in the spec | PASS |
| III. In-game legality | Copy accounting unchanged and tested for the 1-copy Expert Belt; validator runs on every output | PASS (planned) |
| IV. Reproducible, honest evaluation | B2 same seed and budget; equal-levels paired comparison, McNemar exact, 2,000 runs; objective unchanged | PASS (planned) |
| V. Verified claims, positive controls | Muscle Band appears when a copy is stubbed in (copy-check control); the copy test shows a second holder would be a violation; the candidate snapshot on `main` reproduces 013's | PASS (planned) |
| VI. Reference-first speed | No approximation added; more candidates only. Run-time change measured | N/A |

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/014-damage-boost-items/
├── spec.md
├── plan.md                              # this file
├── research.md                          # R1 group; R2 rule; R3 copies; R4 cost; R5 B2 comparison; R6 sources; R7 divergences
├── contracts/held-item-candidates.md    # output order and test cases
├── quickstart.md
├── checklists/requirements.md
└── tasks.md                             # /speckit-tasks
```

No `data-model.md`: no new data. The candidate list is a list of item keys, as before.

### Source Code (repository root)

```text
src/platsim/optimizer/candidates.py       # held_item_candidates: damage boosters after existing items, before the H2 filter
tests/unit/test_optimizer_candidates.py   # contract cases, Muscle Band copy control, Expert Belt single holder, report source
```

**Structure Decision**: One function changes. The comparison script lives in the session scratchpad (evidence, not
product code), as 011 and 013 did for their snapshot scripts.

## Complexity Tracking

None.
