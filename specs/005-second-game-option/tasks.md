---
description: "Task list for 005 Second-Game Option"
---

# Tasks: Second-Game Option Lifts the One-Choice Rules

**Input**: the design documents in `specs/005-second-game-option/`: plan.md, spec.md,
research.md (R1–R6), data-model.md (G1–G3), contracts/second-game-option.md and quickstart.md
(V1–V4).

**Tests**: included. Spec FR-008 lists the regression tests. The constitution requires positive
controls (Principle V).

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task can run in parallel, because it
touches different files and has no unfinished dependency.

## Ground rules for every task

- **Branch**: work on `005-second-game-option`. Commit on it when done. Don't merge into `main`
  until the user has tested it and says so.
- **Scope**:
  - Don't change the option key, flag, checkbox id or query name (FR-006).
  - Don't change one-copy limits (FR-007).
  - Don't edit `sim/` or anything under `runs/`.
- **Generated data**: none is regenerated. `uv run platsim extract --check` must stay green.
- **Recording results**: paste the real test output for each checkpoint into
  `specs/005-second-game-option/validation-log.md` (created in T001).
- **Temp files** go in the session scratchpad. Run probe scripts with `python -u`.
- **Helpers**: reuse the session `ledger` and `catalog` fixtures (`tests/conftest.py`). Reuse the
  004 helpers in `tests/unit/test_validator.py` (`_member`, `_with`, `_codes`, `_group_violations`)
  and in `tests/unit/test_team_groups.py` (`_count_teams`).

---

## Phase 1: Setup

- [X] T001 Create `specs/005-second-game-option/validation-log.md` and record the baseline:
  - `git rev-parse HEAD`;
  - `uv run platsim extract --check`;
  - the output of `uv run pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py tests/unit/test_reports.py tests/integration/test_web.py`;
  - `grep -rn "unobtainable in Platinum" src/platsim/web src/platsim/cli.py`, the V3 positive
    control (2 hits expected, `index.html:51` and `app.js:94`).
- [X] T002 Confirm that every `runs/*/state.json` is finished before the first `src/platsim` edit,
  as in 004 T002. The known exception is the cancelled `job-20261009T193750Z-a1822a`. Record the
  list.

---

## Phase 2: Foundational

- [X] T003 Add `groups_enforced(led)`, `second_game_members(opts)` and `SECOND_GAME_NOTE` to
  `src/platsim/legality/movesources.py`, next to the 004 group helpers (`STARTER_GROUP`,
  `choice_label`), following research R1/R2 and data-model. Nothing calls them yet, so behaviour
  is unchanged.

**Checkpoint**: the helpers exist; T001's test set is still green.

---

## Phase 3: User Story 1 — Mixed starters and fossils with the option on (P1) 🎯 MVP

**Goal**: with the option on, mixed starter or fossil lines are accepted everywhere, and the later
members are labelled. With it off, everything is as in 004.

**Independent test**: quickstart V1 and V2.

### Tests (write first and see them fail)

- [X] T004 [P] [US1] Add option-on validator tests to `tests/unit/test_validator.py`. Use
  `validate(team, led, options=LegalityOptions(allow_unobtainable_pokemon=True))`, or a view from
  `led.with_options(...)`, and the 004 `_member`/`_with` helpers.
  - Torterra (bred) + Infernape (gift): no violations with the option on; `SOURCE_EXHAUSTED` with
    it off.
  - Rampardos + Bastiodon: the same pair of results.
  - All three final starters: no violations with the option on.
  - Positive control: two Giratina still give `SOURCE_EXHAUSTED` with the option on. Build them
    with `_member("SPECIES_GIRATINA", <its static id>, led)`, taking the id from
    `MS.source_options`.
- [X] T005 [P] [US1] Add option-on tests to `tests/unit/test_team_groups.py`:
  - `team_group_conflicts([TORTERRA, INFERNAPE], on_view) == {}`, and both still conflict on the
    default view;
  - `C.resolve_species(["torterra", "infernape", *OTHERS], on_view)` returns six constants;
  - `MS.groups_enforced(ledger) is True` and `MS.groups_enforced(on_view) is False`.
- [X] T006 [P] [US1] Add label tests to `tests/unit/test_reports.py` using
  `report.sources.team_sources`. Build the team with `optimizer.resources.realize` on the
  option-on view, or validate a TeamCandidate built from the 004 test helpers.
  - Torterra + Infernape: exactly one obtained-from string ends with
    `MS.SECOND_GAME_NOTE`, and it belongs to the later member.
  - Swapped order: the label moves to the other member.
  - Infernape + Monferno: no label.
  - Option off: `team_sources` on a one-line team has no label.
- [X] T007 [P] [US1] Add web tests to `tests/integration/test_web.py`:
  - `POST /api/jobs` with Torterra, Infernape and four others plus `"allow_unobtainable_pokemon": true`
    → 201;
  - the same without the option → 422. This 004 test already exists; keep it.

### Implementation

- [X] T008 [US1] In `team_group_conflicts` in `src/platsim/legality/movesources.py`, return `{}`
  when `not groups_enforced(led)` (R1.1).
- [X] T009 [US1] In `validate` in `src/platsim/legality/validator.py`, raise the group
  `SOURCE_EXHAUSTED` only when `MS.groups_enforced(led)`. The quantity check is unchanged (R1.2).
- [X] T010 [US1] In `realize` in `src/platsim/optimizer/resources.py`, skip an option for a
  held-with-another-choice group only when `MS.groups_enforced(led)`. Record each group's first
  choice with `setdefault` (R3). Update the module docstring line from 004.
- [X] T011 [US1] In `team_sources` in `src/platsim/report/sources.py`, compute
  `second = set(MS.second_game_members(opts))` and append `MS.SECOND_GAME_NOTE` to those members'
  `opt.detail` (R2).
- [X] T012 [US1] Run T004–T007. Record the output.

**Checkpoint**: US1 is the MVP.

---

## Phase 4: User Story 2 — The option says what it means (P2)

**Goal**: the new name everywhere (FR-005).

**Independent test**: quickstart V3.

- [X] T013 [P] [US2] Add a wording test to `tests/integration/test_web.py`.
  - The page contains "Allow Pokémon unobtainable in one Platinum game".
  - `/static/app.js` contains "Pokémon unobtainable in one Platinum game".
  - Neither contains "unobtainable in Platinum\"" nor "unobtainable in Platinum<", which are the
    old label endings.
- [X] T014 [P] [US2] In `tests/unit/test_legality_options.py`, assert that the
  `--allow-unobtainable-pokemon` help text in the `validate`/`evaluate`/`optimize` parsers contains
  "one Platinum game" and "second starter".
- [X] T015 [US2] Update the texts:
  - `src/platsim/web/static/index.html:51` (checkbox);
  - `src/platsim/web/static/app.js:94` (summary label);
  - `src/platsim/cli.py:19` (help);
  - `README.md:56`: the option name, plus one sentence on the second-game rule and the label.
- [X] T016 [US2] Run T013–T014, and the `grep` from T001 (expect 0 hits). Record the output.

---

## Phase 5: Polish and cross-cutting

- [X] T017 [P] In `tests/unit/test_team_groups.py`:
  - change `_count_teams(led, groups: bool = True)` to `groups: bool | None = None`, where `None`
    means `MS.groups_enforced(led)`;
  - keep `test_species_team_count`, whose figures are unchanged;
  - add `test_species_team_count_second_game`: on the option-on view the default gives
    `1_174_080_931_485 == comb(310, 6)`, and `groups=True` gives `1_163_212_171_902` (positive
    control).
- [X] T018 Run the quickstart fast checks, then the full suite `uv run pytest -q` (about 2.5 h,
  local only). Paste the outputs into `validation-log.md`. Confirm that `test_allowed_final_forms`
  and the 004 tests are unchanged (SC-001).
- [X] T019 Update the 005 section of `RUN-STATE.md` with what's done, the commit, how to test and
  what isn't committed. Commit on `005-second-game-option`. Don't merge.

---

## Dependencies

- **Setup** (T001–T002) → **Foundational** (T003) → US1 (T004–T012) → US2 (T013–T016) →
  Polish (T017–T019).
- **US2** depends only on Setup. It can be done before or alongside US1, since it touches
  different files.
- **T017** needs T003 (`groups_enforced`).

## Parallel opportunities

- **US1 tests:** T004, T005, T006 and T007 touch different files.
- **US2 tests:** T013 and T014.
- **US2 and US1 implementation:** T015 can be done alongside US1, since it touches only static,
  CLI and README files.

## Implementation strategy

1. **MVP**: Setup, Foundational and US1. Show a Torterra + Infernape team accepted and labelled
   with the option on, and refused with it off.
2. US2 wording.
3. Polish: counts, full suite, commit. Then the user tests it by hand before merging.
