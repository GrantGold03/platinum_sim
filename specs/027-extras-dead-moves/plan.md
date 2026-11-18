# Implementation Plan: Dead moves in the extra candidate sets

**Branch**: `027-extras-dead-moves` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-extras-dead-moves/spec.md`

## Summary

`candidates.member_candidates` builds the 024 variable-power extras (combinations of the marginal pool plus the offered variable
moves, at least one variable move each, two apart among themselves) and the 025 item-conditioned extras (an item-valued
marginal pool, ranked, two apart, not already offered) without 026's dead-move repair. This feature routes both through 026's
`choose_sets` machinery under each kind's own valuation, with two new optional arguments that leave the base-set call
unchanged: `exclude` (sets already offered, so a repaired duplicate is skipped) and `require` (the kind's defining check: a live
offered variable move for a variable-power extra; for an item extra, a move whose value the item changes). Extras that fail
are not offered and are recorded with the reason (owner's decision at clarify). Fillers in extras carry 026's reason per set.
Acceptance is 026's protocol with the attribution helper treating any base-set difference as a defect.

## Technical Context

**Language/Version**: Python 3.12 (`uv`); the Node battle worker untouched (`sim/` must not change)

**Primary Dependencies**: `platsim.optimizer.candidates` (`choose_sets`, `_repaired`, `pool_by_marginal`, `rank_sets`,
`dead_moves`, `cost_tier`, `move_value(item_effect=)`), `platsim.optimizer.run` (`_member_notes`, the screen's extra kinds,
unchanged), feature 026's scripts (`acceptance.py`, `attribution.py`, `equal_levels.py`, `hand_check.py`)

**Storage**: `runs/027-evidence/` (local) with small copies under `specs/027-extras-dead-moves/evidence/`

**Testing**: pytest (`tests/unit/test_extras_dead_moves.py` new; `test_marginal_coverage.py`, `test_h4_items.py`,
`test_variable_power.py`, `test_optimizer_candidates.py` kept green)

**Target Platform**: this Linux machine, 16 workers, measurements alone

**Project Type**: CLI/library (optimizer)

**Performance Goals**: candidate generation for the six B2 species with the allocation within 10 s (SC-006; 4.8 s today); the
extras add one repair walk per kind, the same order of work as the base sets'

**Constraints**: base sets, their items and the setup set byte-identical to main (SC-003, enforced by the attribution helper and
a unit test); deterministic (ties by score then name); `sim/` unchanged; the screen's extra kinds and order unchanged

**Scale/Scope**: two stories, one layer (candidates), about 16 tasks

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Game data from the decomp | Pass | no new game data |
| II. Showdown engine | Pass | `sim/` untouched; hash gate |
| III. Legality independent | Pass | only which candidate sets are offered changes; `realize`, repair and the validator check every team |
| IV. Reproducible | Pass | deterministic ties; seeds unchanged; identity evaluations |
| V. Positive controls | Pass | Infernape's Fire Punch, Garchomp's Return set, a synthetic duplicate, a synthetic filler extra, base sets byte-identical; attributed diff with base differences as defects |
| VI. Reference-first | Pass | 026's protocol on both codes; a supported loss blocks the merge |
| VII. Competent player | Pass | the feature's purpose: every set the tool can recommend earns its moves |

Post-design re-check: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/027-extras-dead-moves/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/candidates-extras.md
├── scripts/            (from 026: acceptance.py, attribution.py, equal_levels.py, hand_check.py)
├── evidence/pre/       (the recount probe and its output)
└── tasks.md            (/speckit-tasks)
```

### Source Code (repository root)

```text
src/platsim/optimizer/candidates.py   choose_sets(exclude=, require=); extras built through it; MemberCandidates.filler_reasons,
                                      dropped_extras; dead_moves covers extras under their own valuation
src/platsim/optimizer/run.py          _member_notes reads the per-set filler reason
tests/unit/test_extras_dead_moves.py  NEW
```

## Phase 0: Research

[research.md](research.md): R1 reuse of `choose_sets` with base sets unchanged, R2 the defining checks, R3 per-set filler reasons
and the report note, R4 the attribution change, R5 expected effect and size.

## Phase 1: Design

[data-model.md](data-model.md), [contracts/candidates-extras.md](contracts/candidates-extras.md), [quickstart.md](quickstart.md).

## Complexity Tracking

None: one layer, the 026 machinery reused.
