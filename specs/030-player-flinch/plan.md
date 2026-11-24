# Implementation Plan: The battle player models flinch

**Branch**: `030-player-flinch` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/030-player-flinch/spec.md`

## Summary

The player (`sim/policy/expectimax2.mjs`) resolves a turn in `resolveTurn`: the two actions in order (priority, then Speed, a tie
split 0.5/0.5), each through `doMove` (pre-move status checks) and `execMove` (damage outcomes, `applyHit`). Flinch enters at two
points. In `execMove`, after a damaging flinch move lands, and **only when the target still has to move this turn** (`foeMovesLater`
is already passed in; owner's rule FR-012), each landing branch splits: with the move's effect chance (doubled for the user's Serene
Grace) the target is marked flinched, unless it fainted, is behind a substitute, or has Inner Focus (not ignored by Mold Breaker); the
rest of the branch is unchanged. In `doMove`, a flinched Pokemon loses its move (after the sleep and freeze checks, as the game orders
its status checks), Steadfast raises its Speed one stage, and the mark is cleared; `endOfTurn` clears any mark left. Fake Out fails
unless it is its user's first turn out. A `flinch=0` knob on the v4 candidate syntax (028's pattern) is the reference arm and keeps
today's play exactly. No branch is added when the flinch move's user moves second, so the cost is paid only where a flinch can happen.
Measurement: 028's paired script under Shift, on the reference team, the benchmark team and the B2 winner, 2,000 pairs each, plus a
pairing control and a conditions control; speed measured in both run orders (R5). Then acceptance on both codes.

## Technical Context

**Language/Version**: Node (player, `sim/`), Python 3.12 (`uv`, scripts)

**Primary Dependencies**: `sim/policy/expectimax2.mjs` (`resolveTurn`, `doMove`, `execMove`, `applyHit`, `endOfTurn`, `staticInfo`),
`sim/gauntlet.mjs` (v4 knobs), the decomp (`subscript_flinch_mon.s`, `subscript_flinched.s`, `battle_script.c` effect chance,
`battle_controller_player.c` status-check order), the vendored engine (`data/conditions.ts` flinch, `data/abilities.ts` Inner Focus and
Steadfast, `data/moves.ts` Fake Out and the flinch secondaries), feature 029's scripts (acceptance, paired script with `--battle-style`)

**Storage**: `runs/030-evidence/` (local) with copies under `specs/030-player-flinch/evidence/`

**Testing**: Node (`sim/test/flinch.test.mjs` new; the replay test with the knob off byte-identical; the default replay fixture
re-recorded only if it changes, with the difference stated), pytest unchanged (the optimizer is not touched)

**Target Platform**: this machine, 16 workers, measurements alone

**Project Type**: CLI/library (worker)

**Performance Goals**: the player with flinch at least 75% of the gauntlets per second without (SC-004)

**Constraints**: engine untouched; optimizer untouched; `sim_code_hash` changes; knob off = today's play

**Scale/Scope**: three stories, one layer (the player), about 14 tasks; the three 2,000-pair checks are the long part (about 45 min)

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Decomp data | Pass | the rule cited from the battle scripts; effect chances from the move data |
| II. Showdown engine | Pass | untouched; differences ledgered |
| III. Legality | Pass | no item or move offered changes |
| IV. Reproducible | Pass | deterministic model; seeds unchanged; paired runs on the same seeds |
| V. Positive controls | Pass | constructed cases (each condition), the knob, a pairing control, a conditions control |
| VI. Reference-first | Pass | the knob-off player is the reference; measured on three teams before acceptance |
| VII. Competent player | Pass | this feature raises the player to the competent standard on flinch; README states the per-team change and the speed cost |

Post-design re-check: unchanged (Pass on all seven).

## Project Structure

```text
specs/030-player-flinch/  plan.md research.md data-model.md quickstart.md contracts/ scripts/ evidence/ tasks.md
sim/policy/expectimax2.mjs   execMove: flinch branch when the target moves later; doMove: flinched loses its move, Steadfast;
                             endOfTurn clears; Fake Out first-turn rule; knob X.opts.flinch
sim/gauntlet.mjs             v4 knob flinch=0|1
sim/test/flinch.test.mjs     engine against game; the model's cases
```

**Structure Decision**: player only; the optimizer, the engine and the AI port are untouched.

**Amendment after the player check (2026-11-23)**: v4's default is `flinch: 'defend'` (the foe's flinches on the player only); the
both-sides model is `flinch=1`. Diagnosis knobs kept in the candidate syntax: `flinch=attack|defend`, `crn=1`, `flinchAtk`. Fix found by
the diagnosis: a flinched Pokemon's move-hit record is cleared, as the game's ClearFlags does.

## Complexity Tracking

None.
