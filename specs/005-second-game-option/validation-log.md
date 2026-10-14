# Validation log: 005

## T001 Baseline (2026-10-13)

- HEAD: `dccb3a44e7dbaf4533241a4fcd9270d5563886d1`, branch `005-second-game-option`. No source
  edits yet.
- `uv run platsim extract --check` → "data/generated is up to date (11 files)", exit 0.
- `pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py tests/unit/test_reports.py tests/integration/test_web.py`
  → `87 passed, 1 warning in 93.83s`.
- `grep -rn "unobtainable in Platinum" src/platsim/web src/platsim/cli.py` gives 2 hits (the V3
  positive control):
  - `app.js:94` "Pokémon unobtainable in Platinum";
  - `index.html:51` "Allow Pokémon unobtainable in Platinum".

## T002 Runs

All `runs/*/state.json` are finished except `job-20261009T193750Z-a1822a`, the cancelled
6× Garchomp throwaway recorded in RUN-STATE.md.

## T003–T012 US1 (2026-10-13)

- **T003**: `groups_enforced`, `second_game_members` and `SECOND_GAME_NOTE` added to
  `movesources.py`.
- **Tests written first** (T004–T007), run with
  `-k "second_game or mixed_starters"` before T008–T011: `7 failed, 6 passed`.
  - The 7 failures are the expected ones: the validator gives `SOURCE_EXHAUSTED` with the option
    on, `team_group_conflicts` is non-empty, nothing is labelled, and the web returns 422.
  - The 6 passes: the Giratina one-copy control, the order helper, and the 004 option-off tests.
- **After T008–T011**, `pytest -q tests/unit/test_validator.py tests/unit/test_team_groups.py
  tests/unit/test_reports.py tests/integration/test_web.py` gave `1 failed, 95 passed`.
  - The failure was the 004 test `test_options_and_groups`, which asserted that this option keeps
    the starter conflict. Spec 005 deliberately supersedes that, so the assertion now expects `{}`.
    Its other checks are unchanged.
  - Then `tests/unit/test_team_groups.py` → `17 passed`.

## T013–T016 US2 wording (2026-10-13)

- The tests were written first. Before T015 they gave `2 failed`: the help text and the
  page/app.js wording.
- **T015** changed `index.html:51`, `app.js:94`, `cli.py` `_LEGALITY_HELP` and the README option
  paragraph (FR-005).
- `pytest -q tests/unit/test_legality_options.py tests/integration/test_web.py` → `39 passed`.
- `grep -rn "unobtainable in Platinum" src/platsim/web src/platsim/cli.py` gives no hits (exit 1).
  At T001 the same grep found 2 hits (positive control).

## T017 Counts (2026-10-13)

- `_count_teams(led, groups=None)` asks the engine (`MS.groups_enforced`).
- `pytest -q tests/unit/test_team_groups.py` → `18 passed`:
  - `test_species_team_count`, default options: 55,192,424,630, unchanged.
  - `test_species_team_count_second_game`: 310 species; the engine gives C(310,6) =
    1,174,080,931,485. Positive control: the groups forced on give 1,163,212,171,902.

## T018 Full suite (2026-10-13/14)

Started 22:09 and ended about 00:36 local time. Local CPU only, nothing paid. Browser tests
included. The 006 worktree was being worked on at the same time, at `nice` priority.

`uv run pytest -q`:
```
490 passed, 4 xfailed, 1 warning in 8843.23s (2:27:23)
exit=0
```
SC-001 holds: the 004 tests, `test_allowed_final_forms` and `test_species_team_count` are
unchanged and passing.
