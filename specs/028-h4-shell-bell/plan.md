# Implementation Plan: H4, Shell Bell

**Branch**: `028-h4-shell-bell` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/028-h4-shell-bell/spec.md`

## Summary

The player (`sim/policy/expectimax2.mjs`, `applyHit`, which already applies recoil, drain heals and Life Orb after the damage)
gains the Shell Bell heal: a holder below maximum HP and above 0 heals max(1, floor(dmg / 8)) after its move hits, `dmg` being the
HP the target lost. A `shellBell=0` knob on the 018 v4 candidate syntax (`expectimax2-v4?shellBell=0`) gives the reference arm,
so 018's `paired_policies.py --teams file:<team>` runs the reference-first player check on the same seeds. The engine-versus-game
check is a Node test against the vendored engine plus decomp citations; differences go to the divergence ledger. The optimizer
appends Shell Bell through 025's `extra_item_candidates` (by hold effect `HOLD_EFFECT_HP_RESTORE_ON_DMG`, with a copy, for sets
with an attack), so the screen's item-deviation kind screens it with no screen change. Acceptance is the 025/027 protocol.

## Technical Context

**Language/Version**: Node (the worker and player, `sim/`), Python 3.12 (`uv`, the optimizer and scripts)

**Primary Dependencies**: `sim/policy/expectimax2.mjs` (`applyHit`, `holdEffect`), `sim/gauntlet.mjs` (v4 candidate knobs),
the vendored Showdown engine (`pokemon-showdown/data/items.ts` shellbell, `sim/battle.ts` heal), the decomp
(`battle_controller_player.c` AFTER_MOVE_HIT_STATE_SHELL_BELL, `battle_lib.c` pivot path and `BattleSystem_Divide`),
`platsim.optimizer.candidates.extra_item_candidates`, `specs/018-expectimax2-v4/scripts/paired_policies.py`, the 027 scripts

**Storage**: `runs/028-evidence/` (local) with copies under `specs/028-h4-shell-bell/evidence/`

**Testing**: Node (`sim/test/shell_bell.test.mjs` new; `replay.test.mjs` unchanged and green), pytest
(`tests/unit/test_shell_bell.py` new; the candidate and report tests kept green)

**Target Platform**: this machine, 16 workers, measurements alone

**Project Type**: CLI/library (worker + optimizer)

**Performance Goals**: the player's speed unchanged within noise (one item check per hit); the screen gains one item deviation
per moveset with an attack where Shell Bell has a copy

**Constraints**: replay test byte-identical (no replay team holds Shell Bell); the vendored engine untouched (`pokemon-showdown/`
diff empty); `sim_code_hash` changes (the player changes) and the ledger version changes only if an entry is added; deterministic

**Scale/Scope**: three stories, two layers (player, candidates), about 18 tasks

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Game data from the decomp | Pass | the heal rule is cited from the decomp; the hold effect and copy count from the item data |
| II. Showdown engine | Pass | engine untouched; its Shell Bell behaviour checked against the game, differences ledgered |
| III. Legality independent | Pass | the one copy enforced by `realize`; validator unchanged |
| IV. Reproducible | Pass | deterministic heal; seeds unchanged; replay test |
| V. Positive controls | Pass | four constructed heal cases; the reference arm via the knob; engine checks with expected values |
| VI. Reference-first | Pass | the player check (with vs without the model) before the optimizer change |
| VII. Competent player | Pass | a competent player counts the heal; the policy name stays `expectimax2-v4` with the change documented (R4) |

## Project Structure

```text
specs/028-h4-shell-bell/  plan.md, research.md, data-model.md, quickstart.md, contracts/, scripts/, evidence/, tasks.md
sim/policy/expectimax2.mjs           applyHit: the Shell Bell heal; the shellBell option (default on)
sim/gauntlet.mjs                     v4 candidate knob shellBell=0|1
sim/test/shell_bell.test.mjs         NEW: the four heal cases; the knob; engine checks (substitute, U-turn, multi-hit, rounding)
src/platsim/optimizer/candidates.py  extra_item_candidates: the HP_RESTORE_ON_DMG item for sets with an attack
tests/unit/test_shell_bell.py        NEW: appended after existing items; one copy (a second refused); lists otherwise unchanged
divergences ledger                   entries only for confirmed engine-vs-game differences
```

## Phase 0: Research — [research.md](research.md) (R1 to R6)

## Phase 1: Design — [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

## Complexity Tracking

None.
