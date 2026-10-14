# Implementation Plan: Second-Game Option Lifts the One-Choice Rules

**Branch**: `005-second-game-option` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-second-game-option/spec.md`. This amends the
004 behaviour (merged into `main` at `efbb110`/`dccb3a4`).

## Summary

The existing option `allow_unobtainable_pokemon` gets a new name: "Allow Pokémon unobtainable in
one Platinum game". When it is on, the 004 starter and fossil one-choice rules are lifted.

**Approach**:
- One predicate, `groups_enforced(led)`. It is false when the ledger view's option is on. Three
  places consult it:
  - the conflict check used by the optimizer and the web;
  - the validator's group check;
  - `resources.realize`.
- Members that need a second game are found by team order (`second_game_members`).
  `report/sources.team_sources` labels them "(from a second Platinum game, allowed by rule)".
  That function feeds every report format.
- Four wording changes: the checkbox, the summary label, the command-line help and the README.

**Result**: with the option on, the team count goes from 1,163,212,171,902 to 1,174,080,931,485
= C(310, 6). With it off, nothing changes.

## Technical Context

**Language/Version**: Python 3.14, and browser JavaScript (`static/app.js`, no build step).

**Primary Dependencies**: existing only. No new dependency.

**Storage**: none changed. No data regeneration and no schema change. Old reports are not
rewritten.

**Testing**: pytest. 004's `tests/unit/test_team_groups.py`, `test_validator.py`,
`test_reports.py` and `tests/integration/test_web.py` gain option-on cases. The full suite runs
before merge (about 2.5 h).

**Target Platform**: Linux, local, offline.

**Project Type**: a Python CLI package with a local web UI.

**Performance Goals**: no change. The predicate reads one boolean.

**Constraints**:
- The key, flag, checkbox id and query name are unchanged (FR-006).
- One-copy limits are unchanged (FR-007).
- `sim/` is untouched.

**Scale/Scope**: about 6 source or static files, 4 test files and the README.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | PASS | No game data changes. The starter and fossil groups still come from the decomp (004). |
| II. Showdown is the battle engine | PASS | `sim/` and Showdown are untouched. |
| III. In-game legality (v1.2.0) | PASS | The option widens output beyond one cartridge. It is off by default; the validator applies it per options view; each affected source is labelled (R2, FR-004); and `provenance.legality_options` records it. A labelled team says "second Platinum game", so it is never described as single-cartridge. |
| IV. Reproducible, statistically honest | PASS | Seeds are unchanged. Default-option results are byte-identical: the label can't appear when the option is off (data-model G3). |
| V. Verified claims, positive controls | PASS | Each check has a counterpart: the option-off control for each option-on acceptance; the groups forced on for the count (1,163,212,171,902); two Giratina still refused; a grep for the old wording, with 2 hits before the change. |
| Technical constraints | PASS | Offline. No data regeneration. |
| Workflow gates | PASS | Spec Kit flow, feature branch, merge only after the user tests, and RUN-STATE updated. |

**Post-design re-check (after Phase 1)**: still PASS. No complexity entries.

## Project Structure

### Documentation (this feature)

```text
specs/005-second-game-option/
├── spec.md
├── plan.md               # this file
├── research.md           # R1–R6
├── data-model.md         # derived values, rules G1–G3
├── quickstart.md         # V1–V4
├── contracts/second-game-option.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
src/platsim/
├── legality/
│   ├── movesources.py     # groups_enforced(), second_game_members(), SECOND_GAME_NOTE;
│   │                      #   team_group_conflicts returns {} when not enforced
│   └── validator.py       # group check only when groups_enforced(led)
├── optimizer/resources.py # realize: group skip only when enforced; first choice still recorded
├── report/sources.py      # team_sources appends SECOND_GAME_NOTE to second-game members
├── cli.py                 # --allow-unobtainable-pokemon help text
└── web/static/
    ├── index.html         # checkbox label
    └── app.js             # results summary rule label
README.md                  # Legality section: option name + second-game sentence

tests/
├── unit/test_team_groups.py      # option-on conflicts {}, count C(310,6) + control; _count_teams
│                                 #   groups=None asks the engine
├── unit/test_validator.py        # option-on acceptance (starters, fossils, all three), Giratina control
├── unit/test_reports.py          # team_sources label: exactly the later member; none for one line
└── integration/test_web.py       # 201 with the option, 422 without; wording on page and in app.js
```

**Structure Decision**: no new module. The predicate and the label helper live next to the 004
group code in `movesources.py`.

## Delivery order

1. **US1 rule and label** (P1): the predicate, its three uses, `second_game_members` and the
   `team_sources` label, with their tests (V1, V2).
2. **US2 wording** (P2): the four texts and the wording test (V3).
3. **Counts and suite**: the option-on count test (V4), the full suite, RUN-STATE, commit on the
   branch. No merge until the user has tested.
