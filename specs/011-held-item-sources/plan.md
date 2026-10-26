# Implementation Plan: Held-Item Sources (held items, slice H1)

**Branch**: `011-held-item-sources` | **Date**: 2026-10-26 (rewritten after Clarifications, Session 2026-10-26) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-held-item-sources/spec.md`

## Summary

Make the availability ledger's NPC-gift reader understand four script patterns it drops today (research R1): values
set inside called routines, a random offset added to an item constant, items copied from a saved variable, and items
chosen from a C table and given by `AddItem` with variables. This is a general improvement (FR-010), built from the
decomp and `main`; no archived code is used (FR-009). The Route 221 house gets its 1-copy rule, detected from the
script. New reasons are written in plain English. Everything the improvement changes is listed and checked; the
optimizer, battle player and candidate rule do not change.

## Technical Context

**Language/Version**: Python 3.14 (uv); Node ≥ 22.18 only for the unchanged node test suite

**Primary Dependencies**: none new; existing decomp readers (`platsim.decomp.scripts`, `platsim.decomp.items`)

**Storage**: generated JSON in `data/generated/` (git-ignored, rebuilt by `uv run platsim extract`)

**Testing**: pytest (`tests/integration/test_availability_controls.py`, `tests/unit/test_validator.py`, a new
`tests/integration/test_gift_reader.py`, then the full suite); node tests unchanged

**Target Platform**: this Linux machine, offline

**Project Type**: CLI + local web app (existing)

**Performance Goals**: `platsim extract` stays near its baseline (44.6 s, T002); more than 1.5× is investigated

**Constraints**: decomp is ground truth; no hand-typed item lists; rules keyed to script commands, never to map or
script names; `data/generated/` rebuilt per branch

**Scale/Scope**: one reader function and its helpers in `src/platsim/availability/sources.py`, one new test file,
updated count pins; the number of changed ledger entries is measured (research R3)

## Constitution Check

Constitution v1.4.0.

| Principle | Check | Status |
|---|---|---|
| I. Decomp is ground truth | Items come from reading the scripts, the decomp item list and the C table; every entry cites file:line; the Route 221 rule is detected from `GetDailyRandomLevel` in the script, not the map name | PASS |
| II. Showdown is the battle engine | No battle change | N/A |
| III. In-game legality | Validator follows the ledger (1 vs 2 Focus Sash holders; Choice Band) | PASS (planned) |
| IV. Reproducible, honest evaluation | B1-B5 candidates and a same-seed B2 run compared with the T004/T005 baseline; every changed entry listed (FR-010) | PASS (planned) |
| V. Verified claims, positive controls | Each of G1-G4 gets a test that fails on `main`'s reader (positive control: Route 221, Pastoria, Amity pickup, Gift Man) and a negative control (an unrelated give unchanged; accessories not counted; Choice Band still unavailable). `main`'s 66/55 count pins must move | PASS (planned) |
| VI. Reference-first speed | No approximation is introduced | N/A |

Post-design re-check: unchanged, PASS.

## Project Structure

### Documentation (this feature)

```text
specs/011-held-item-sources/
├── spec.md
├── plan.md                      # this file
├── research.md                  # R1 gaps G1-G4; R2 sources and copies; R3 reach; R4 text; R5 optimizer; R6 story rank
├── contracts/explain-text.md    # the user-facing reason text for the new sources
├── quickstart.md                # validation run guide
├── validation-log.md            # T001-T005 baseline done
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

No `data-model.md`: the ledger's `Entry` record is unchanged; new sources are ordinary `npc_item_gift` entries.

### Source Code (repository root)

```text
src/platsim/availability/sources.py      # gift reader: call stack (G1), random offset (G2), saved variables (G3),
                                         # C-table command and variable AddItem (G4); daily-random-level 1-copy rule;
                                         # plain-English reasons for these cases
tests/integration/test_gift_reader.py    # new: one positive and one negative control per gap; explain text check
tests/integration/test_availability_controls.py  # count pins updated to the measured values
tests/unit/test_validator.py             # Focus Sash once / twice; Choice Band
```

**Structure Decision**: existing single-project layout; one source file, one new test file, two updated test files.

## Approach

1. Baseline (done: T001-T005, `runs/011-evidence/`).
2. Tests first: write the gap tests (G1-G4) and the text check; confirm each fails on `main`'s reader.
3. Reader, one gap at a time (G1, G2, G3, G4), each with its test passing before the next; then the 1-copy rule and
   the reasons.
4. Rebuild; full before/after diff of ledger entries and held-item availability against the baseline; list every
   changed site (FR-010); report any held-item change outside the three sources to the user before going on.
5. Validator check, B1-B5 candidates, same-seed B2 run.
6. After the build only: compare with 008's recorded results; check each difference against the decomp (FR-009).
7. Full suite, docs, hand over for the user's test. No merge.

## Complexity Tracking

None. The reader gains four cases; no new module or abstraction.
