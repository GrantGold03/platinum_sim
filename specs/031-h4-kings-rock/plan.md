# Implementation Plan: H4, King's Rock / Razor Fang

**Branch**: `031-h4-kings-rock` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/031-h4-kings-rock/spec.md`

## Summary

No player change (no League holder; the player's own flinch odds stay unvalued, 030). Engine checks (Node, 030's pattern) compare
the vendored engine's King's Rock with the game's rule. The optimizer offers the flinch item in three places: (1) appended last in
`extra_item_candidates` for every set with an affected move (after the resist berries); (2) a new item-conditioned extra set kind
`flinch_item` for members whose candidate moves include an affected multi-hit move: the member's best such move swapped into its
best base set in place of that set's lowest-scoring move, held with the flinch item (025's `item_sets` path; 027's dead-move rule
applies); (3) "one option, two copies": the candidates name `kings_rock`; when a team is realized and King's Rock's copy is already
taken (or a later holder needs one), the holder is given `razor_fang` instead, and the realized team and report name the item each
member actually holds; Gliscor's evolution still uses the Razor Fang (team-gated copies). Acceptance is 029's protocol; the
attribution allows the appended flinch item and the new `flinch_item` extras. The report-only measurement (FR-007) plays B3's quick
winner on the branch with its multi-hit member (Lucario with Bone Rush, if it is on the winner; else the snapshot's best multi-hit
user) holding the flinch item against the same set with its usual item.

## Technical Context

**Language/Version**: Node (engine tests, `sim/`), Python 3.12 (`uv`, optimizer and scripts)

**Primary Dependencies**: `src/platsim/optimizer/candidates.py` (`extra_item_candidates`, `_item_for_effect`, the 025 `item_sets`
path, `dead_moves`), `src/platsim/optimizer/resources.py` (`realize`, `_member_option`'s item copy check, `copies`, team-gated items),
`src/platsim/availability/ledger.py` (`TEAM_GATED_ITEMS`, `team_item_copies`), the decomp (`battle_controller_player.c`
`CheckExtraFlinch` :4630, `MULTI_HIT_EXTRA_FLINCH`; `subscript_flinch_mon.s`), the vendored engine (`data/mods/gen4/items.ts`
kingsrock), 029's scripts (acceptance, attribution, equal levels, paired script with `--battle-style` and 030's `--master-suffix`)

**Storage**: `runs/031-evidence/` (local), copies under `specs/031-h4-kings-rock/evidence/`

**Testing**: Node (`sim/test/kings_rock.test.mjs` new), pytest (`tests/unit/test_kings_rock.py` new; 025/028/029 pins that compare
whole appended-item lists updated)

**Target Platform**: this machine, 16 workers, measurements alone

**Project Type**: CLI/library (optimizer)

**Performance Goals**: team build within 10 s (SC-006); the screen gains the item deviations and the `flinch_item` extras

**Constraints**: engine and player untouched; `sim_code_hash` unchanged unless an engine-check test file counts (tests only);
deterministic choices (ties by key)

**Scale/Scope**: three stories, one layer (the optimizer) plus engine tests, about 15 tasks

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Decomp data | Pass | rule from the decomp; copies, hold effects and the affected-move flag from game data |
| II. Showdown engine | Pass | untouched; differences ledgered |
| III. Legality | Pass | copies enforced at realize; the substitution never exceeds the two copies; Gliscor's evolution counted |
| IV. Reproducible | Pass | deterministic offers and substitution |
| V. Positive controls | Pass | engine cases per condition; a third holder refused; the measurement's pairing control |
| VI. Reference-first | Pass | no player change; the measurement is report only (clarified) |
| VII. Competent player | Pass | README states that the battles credit the item's flinches while the player does not steer toward them |

Post-design re-check: unchanged (Pass on all seven).

## Project Structure

```text
specs/031-h4-kings-rock/  plan.md research.md data-model.md quickstart.md contracts/ scripts/ evidence/ tasks.md
src/platsim/optimizer/candidates.py   flinch item appended; `flinch_item` extras for affected multi-hit moves; equivalence group
src/platsim/optimizer/resources.py    realize: an equivalent item when King's Rock's copy is taken
sim/test/kings_rock.test.mjs          engine against game (tests only)
tests/unit/test_kings_rock.py         offers, extras, copies, substitution, attribution
```

**Structure Decision**: optimizer plus engine tests; the player, engine and AI port untouched.

## Complexity Tracking

None.
