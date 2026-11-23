# Implementation Plan: H4, resist berries

**Branch**: `029-h4-resist-berries` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-h4-resist-berries/spec.md`

## Summary

The player (`sim/policy/expectimax2.mjs`) gains the resist-berry rule where a hit's damage is applied (`applyHit`, which already
handles Focus Sash): when the defender holds the berry of the move's type and the hit is super-effective (Chilan: a Normal move), the
damage is halved (integer) and the berry removed from the model state. `damageOutcomes` passes the hit's super-effective flag (the
damage calculation already computes it) with each outcome; multi-hit moves halve only the first hit's share (R2). A `resistBerries=0`
knob on the v4 candidate syntax (028's pattern) gives the reference arm. Engine checks follow 028's test pattern; differences go to the
ledger. The optimizer ranks berries per member by the damage they would block from the League's stored parties and appends the top two
through 025's `extra_item_candidates`, after Shell Bell; the screen's item-deviation kind screens them unchanged. Acceptance is 028's
protocol with 028's paired script under Shift and a conditions control.

## Technical Context

**Language/Version**: Node (player, `sim/`), Python 3.12 (`uv`, optimizer and scripts)

**Primary Dependencies**: `sim/policy/expectimax2.mjs` (`applyHit`, `damageOutcomes`, `moveInfo`, `holdEffect`), `sim/gauntlet.mjs`
(v4 knobs), the decomp (`res/battle/scripts/subscripts/subscript_type_resist_berry.s`, `subscript_update_hp.s:10`), the vendored engine
(`data/items.ts` resist berries), `data/generated/trainers.json` (League parties and moves), `candidates.extra_item_candidates`,
`candidates.league_opponents`, feature 028's scripts (`acceptance.py`, `attribution.py`, `paired_policies.py --battle-style`, `make_check_team.py`)

**Storage**: `runs/029-evidence/` (local) with copies under `specs/029-h4-resist-berries/evidence/`

**Testing**: Node (`sim/test/resist_berries.test.mjs` new; replay green), pytest (`tests/unit/test_resist_berries.py` new; 025/028
item-list pins updated where they pin whole lists)

**Target Platform**: this machine, 16 workers, measurements alone

**Project Type**: CLI/library (worker + optimizer)

**Performance Goals**: player speed unchanged within noise; the screen gains up to two item deviations per member set with a threat

**Constraints**: replay byte-identical; engine untouched; `sim_code_hash` changes; the ledger version changes only with an entry;
deterministic berry ranking (ties by type name)

**Scale/Scope**: three stories, two layers, about 16 tasks

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Decomp data | Pass | the trigger and halving cited from the battle scripts; hold effects and copies from the item data |
| II. Showdown engine | Pass | untouched; differences ledgered |
| III. Legality independent | Pass | copies unlimited; `realize` and the validator unchanged |
| IV. Reproducible | Pass | deterministic rule and ranking; seeds unchanged |
| V. Positive controls | Pass | four constructed cases, the knob, engine checks, the conditions control and pairing control |
| VI. Reference-first | Pass | the player check before the optimizer change |
| VII. Competent player | Pass | README states the measurement change: none without a berry; the measured difference for a holder |

## Project Structure

```text
specs/029-h4-resist-berries/  plan.md research.md data-model.md quickstart.md contracts/ scripts/ evidence/ tasks.md
sim/policy/expectimax2.mjs           damageOutcomes carries the super-effective flag; applyHit halves and consumes
sim/gauntlet.mjs                     v4 knob resistBerries=0|1
sim/test/resist_berries.test.mjs     NEW: engine checks; the four model cases; the knob; multi-hit first-hit share
src/platsim/optimizer/candidates.py  resist_berry_ranking(const, level); extra_item_candidates appends the top two
tests/unit/test_resist_berries.py    NEW: ranking, appending, lists otherwise unchanged
```

## Phase 0: Research — [research.md](research.md) R1 to R6. Phase 1: [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

## Complexity Tracking

None.
