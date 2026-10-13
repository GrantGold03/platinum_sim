---
description: "Task list for 004 Breeding and Fossils Respect One-Time Choices"
---

# Tasks: Breeding and Fossils Respect One-Time Choices

**Input**: the design documents in `specs/004-breeding-source-limits/`: plan.md, spec.md,
research.md (R1–R9), data-model.md (rules B1–B3), contracts/team-rules.md and quickstart.md
(V1–V6).

**Tests**: included. Spec FR-010 lists the regression tests. The constitution requires positive
controls (Principle V).

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task can run in parallel, because it
touches different files and has no unfinished dependency.

## Ground rules for every task

- **Branch**: work on `004-breeding-source-limits`. Commit on it when done. Don't merge into
  `main` until the user has tested it and says so.
- **Scope**:
  - Don't edit `sim/`.
  - Don't modify existing files under `runs/`.
  - Don't add a user option (spec Assumptions).
- **Decomp is ground truth**: the starter choice, fossil parity, Day-Care rules and gift genders
  are parsed or cited from `pokeplatinum/` (research R3–R5). No hand-typed tables.
- **Generated data**: after any change to `availability/` output, run `uv run platsim extract` and
  then `uv run platsim extract --check`. `data/generated/` is git-ignored and rebuilt locally.
- **Recording results**: paste the real test output for each checkpoint into
  `specs/004-breeding-source-limits/validation-log.md` (created in T001).
- **Temp files** go in the session scratchpad, never `/tmp` or the repo. Run probe scripts with
  `python -u`.
- **Fixtures**: new tests use the session `ledger` and `catalog` fixtures from
  `tests/conftest.py`. Building a ledger takes about 35 s.
- **Starter-gift quantity**: two members that both declare the starter gift must still fail
  (`tests/unit/test_validator.py::test_starter_choice_is_exclusive`).

---

## Phase 1: Setup

- [X] T001 Create `specs/004-breeding-source-limits/validation-log.md` and record the baseline:
  - `git rev-parse HEAD`;
  - the output of `uv run pytest -q tests/unit/test_validator.py tests/unit/test_source_preference.py tests/unit/test_source_text.py tests/unit/test_legality_options.py`;
  - `sha256sum allowed_pokemon.md tests/fixtures/web_final_defaults/*`;
  - the sorted list of available species keys under default options (from the `catalog` fixture
    or `build_catalog()`), which SC-003 compares against later.
- [X] T002 Confirm that every `runs/*/state.json` is finished before the first `src/platsim` edit.
  A run is finished when its `state.json` has `stages.report`. Edits change `platsim_code_hash`,
  which blocks resuming an unfinished run. Paste the per-run list into `validation-log.md`.

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: the generic (group, choice) mechanism. With only starter gifts grouped, nothing
changes in behaviour yet, except that mixed-line checks become possible.

- [X] T003 Add `group_choice: str | None` to `Entry` in `src/platsim/availability/sources.py`.
  - Starter gifts (`sources.py:~690`) set it to the species constant.
  - Every other entry sets `None`.
  - Carry it through `ledger.py` wherever an `Entry` is rebuilt or serialised (`ledger.py:270`,
    `:424`).
- [X] T004 Add `group_choice` to `SourceOption` in `src/platsim/legality/movesources.py`:
  - copy it from the Entry in `_options` (around `:497`);
  - keep it on evolution options (around `:542`), as is done for `exclusive_group`.
- [X] T005 Add `team_group_conflicts(consts, led) -> dict[str, str]` to
  `src/platsim/legality/movesources.py`.
  - It returns submitted species → message for the members that cannot share one choice per
    group, and `{}` when the team is fine.
  - Use a small backtracking search over each member's `source_options`. Honour:
    - per-option quantity;
    - one choice per `exclusive_group`;
    - limited `consumes` item copies.
  - Messages follow `contracts/team-rules.md`.
- [X] T006 Change the group rule in `src/platsim/legality/validator.py` (`:326-374`):
  - Collect `(member, option id, group_choice)` per group.
  - Raise `SOURCE_EXHAUSTED` only when there is more than one distinct `group_choice`.
  - Stop skipping the quantity check for grouped options (`:365`).
  - Message and `src` refs per `contracts/team-rules.md`.
- [X] T007 In `src/platsim/optimizer/resources.py` `realize` (`:199-248`), change `groups` from
  a set to `dict[group → choice]`. Skip an option only when its group is held with a different
  choice. Apply the quantity check to grouped options too.
- [X] T008 Run `uv run platsim extract` and then `uv run platsim extract --check`. Run the T001
  test set again. Expect it green, with `test_starter_choice_is_exclusive` still failing the
  team, now through the quantity check. Record the output in `validation-log.md`.

**Checkpoint**: (group, choice) is plumbed through, and existing behaviour is unchanged.

---

## Phase 3: User Story 1 — Mixed-starter teams are rejected (P1) 🎯 MVP

**Goal**: no accepted team mixes starter lines. Several members of the chosen line are allowed.

**Independent test**: quickstart V1 and V2.

### Tests (write first and see them fail)

- [X] T009 [P] [US1] In `tests/unit/test_validator.py`, add validator tests built from
  `legal_team.json` (slot 0 is gift Chimchar → Infernape):
  - Torterra declared `breed:SPECIES_TURTWIG@MAP_HEADER_POKEMON_DAY_CARE` → `SOURCE_EXHAUSTED`,
    and the message names both members;
  - Monferno declared `breed:SPECIES_CHIMCHAR@...` → accepted;
  - three Infernape (one gift, two bred) → accepted;
  - two bred Infernape plus a gift Torterra → `SOURCE_EXHAUSTED`.
- [X] T010 [P] [US1] Create `tests/unit/test_team_groups.py` with tests of `team_group_conflicts`
  on species lists:
  - Torterra + Infernape → conflict, keys for both;
  - Torterra + Infernape + Empoleon → conflict, all three;
  - Infernape + Monferno → `{}`;
  - Empoleon alone → `{}`.
- [X] T011a [P] [US1] In `tests/unit/test_team_groups.py`, test the optimizer entry point.
  `candidates.resolve_species(["torterra", "infernape", <four others>], ledger)` raises
  `InvalidRequest`, and `e.reasons` has exactly the keys `torterra` and `infernape`. The same
  call with Infernape + Monferno returns six constants. This covers FR-004 and quickstart V1.
- [X] T011 [P] [US1] Add tests to `tests/integration/test_web.py`:
  - `POST /api/jobs` with Torterra, Infernape and four others → 422. `reasons` has exactly the
    keys `torterra` and `infernape`, and no job is created.
  - The same request with Infernape + Monferno → accepted.

### Implementation

- [X] T012 [US1] Implement rule B1 in `_breed_options` / `breed_mothers` in
  `src/platsim/legality/movesources.py`.
  - A breed option gets `(exclusive_group, group_choice)` when every qualifying mother's non-breed
    pre-Champion sources share one group and one choice. Otherwise it gets `(None, None)`.
  - Key the results by the options view, as the existing cache does (`test_legality_options.py:283-302`).
- [X] T013 [US1] In `resolve_species` in `src/platsim/optimizer/candidates.py`, call
  `team_group_conflicts` after the per-name loop. On a conflict, raise
  `InvalidRequest("invalid species: <message>", reasons)`.
- [X] T014 [US1] In `SpeciesCatalog.resolve_team` in `src/platsim/web/species_catalog.py`, call
  `team_group_conflicts` after the per-species check (around `:171`). On a conflict, raise
  `InvalidRequest("some Pokémon cannot be used together: <message>", reasons)`.
- [X] T015 [US1] Run `extract` and `extract --check`, then T009–T011. Record the output.
  Also check that the default-option catalog still lists the T001 species set: there is no
  per-species change (FR-008).

**Checkpoint**: US1 is done. It is the MVP and can be shown on its own.

---

## Phase 4: User Story 4 — Fossil lines follow the Trainer ID (P2)

**Goal**: Cranidos and Shieldon lines are one-or-the-other. Revivals are unlimited when the
fossil can be dug again and again.

**Independent test**: quickstart V3.

### Tests

- [X] T016 [P] [US4] Add validator tests to `tests/unit/test_validator.py`:
  - Rampardos + Bastiodon → `SOURCE_EXHAUSTED`, with the Trainer ID message;
  - two Rampardos (both declaring the revival) → accepted.
- [X] T017 [P] [US4] Add a parity test to `tests/unit/test_team_groups.py`.
  - The fossil revival options have group `trainer_id_parity`: Skull Fossil gives `odd` and Armor
    Fossil gives `even`.
  - Positive control: every other mining item has no group. Check this against the parsed mining
    table: 85 rows, with only Armor and Skull split.
  - Each revival entry's `src` contains a `src/underground/mining.c:` reference.

### Implementation

- [X] T018 [US4] Parse the pre-National-Dex `oddTIDWeight`/`evenTIDWeight` per item from
  `pokeplatinum/src/underground/mining.c`. Reuse the existing underground parser in
  `src/platsim/availability/sources.py` if it already reads these weights; it produces the
  "(odd TID)" detail.
  - On the fossil revival entries (`sources.py:~693`), set `exclusive_group="trainer_id_parity"`
    and `group_choice` to the one non-zero parity.
  - Append the source reference `pokeplatinum/src/underground/mining.c:<line of that item's
    weight row>` to each revival entry's `src` list. Constitution I requires every extracted value
    to be traceable.
  - If both parities are non-zero, set no group.
- [X] T019 [US4] Make fossil revivals item-limited in `src/platsim/legality/movesources.py`.
  - The revival option's quantity comes from `led.item_copies(fossil)` (unlimited before the
    Champion).
  - The option adds `(fossil item, 1)` to `consumes`.
  - Remove the fixed quantity of 1 at `sources.py:~694`, or override it here, whichever keeps
    `extract --check` honest.
- [X] T020a [US4] Add option-interaction tests to `tests/unit/test_team_groups.py` (spec Edge
  Cases, US4 scenario 4). Use `ledger.with_options(...)`.
  - **`allow_post_game_pokemon`**: if the view admits a non-group source for a starter line, that
    line's breed option is ungrouped (B1), and Torterra + Infernape passes
    `team_group_conflicts`.
    - If no post-game source exists for any starter, record that fact in `validation-log.md`.
      Then test B1 with a monkeypatched extra ungrouped source instead, as a positive control.
  - **`allow_post_game_pokemon`, fossils**: Rampardos + Bastiodon is still a conflict. The
    National Dex weights keep the parity split.
  - **`allow_unobtainable_pokemon`**: the starter-group rule is unchanged for starters that have
    an in-game source. Torterra + Infernape is still a conflict. Record the observed behaviour of
    the synthetic `outside_platinum` source for starters; today it applies only to species with no
    entry at all (`movesources.py` `_has_entry`).
- [X] T020 [US4] Run `extract` and `extract --check`, then T016–T017 and T020a. Record the output.

---

## Phase 5: User Story 2 — Breeding needs a real partner (P2)

**Goal**: a breed option exists only with a compatible father, or Ditto (research R4).

**Independent test**: quickstart V4, the partner part.

### Tests

- [X] T021 [P] [US2] Add partner tests to `tests/unit/test_team_groups.py`:
  - Under default options, list every breed option and check that each one has a father or
    Ditto.
  - Assert the count is 86, or record any change with a reason.
  - Positive control: monkeypatch `compatible_father` to find nothing for one line (for example
    Gible); its breed option disappears.

### Implementation

- [X] T022 [US2] Extract the species-level part of `find_father` (`movesources.py:808-815`) into
  `compatible_father(mothers, led)`. Then:
  - `find_father` calls it, and the egg-move behaviour is unchanged;
  - `breed_mothers` (`:594-615`) requires `compatible_father(...)` or an obtainable Ditto;
  - cite `daycare.c:817-875` in the docstring.
- [X] T023 [US2] Run T021 and the egg-move tests in `tests/unit/test_validator.py` (`:117-140`).
  Record the output.

---

## Phase 6: User Story 3 — One-time parents are traced (P2)

**Goal**: a one-time parent must be able to be female (rule B3), and the explanation names the
parent's source.

**Independent test**: quickstart V4, the one-time and explain parts.

### Tests

- [X] T024 [P] [US3] Add one-time parent tests to `tests/unit/test_team_groups.py`:
  - bred Lucario and bred Vaporeon exist;
  - Lucario from Riley's egg plus a bred Lucario → accepted by `team_group_conflicts` and by the
    validator.
  - Positive control: a test ledger or monkeypatch marks the Riolu egg as a fixed-male source, and
    the Riolu-line breed option disappears.
- [X] T025 [P] [US3] Add breed-text tests to `tests/unit/test_source_text.py`:
  - Infernape bred → `Day Care egg from your starter Chimchar`;
  - Rampardos bred → `Day Care egg from a revived Skull Fossil (odd Trainer ID)`;
  - fossil revival → `Fossil - Mining Museum (Skull Fossil, odd Trainer ID)`, matching the
    contract as revised during implementation;
  - Lucario bred → names Riley's egg (Iron Island);
  - an ungrouped line keeps `Day Care egg (mother: ...)`, without " or Ditto";
  - **all breed options (SC-005)**: under default options, every breed option's `detail` starts
    with `Day Care egg` and names either its group's parent source or at least one mother. Assert
    the count, 86 or the T021 figure.

### Implementation

- [X] T026 [US3] Implement rule B3 in `breed_mothers` in `src/platsim/legality/movesources.py`.
  - A mother counts only if one of its sources allows a female. Signals, in order:
    1. The species must be able to be female (`_can_be_female`, from `gender_ratio`).
    2. An `npc_trade` source has a fixed personality (`fixed_mon`). Compute its gender with the
       game rule: female when `gender_ratio > (personality & 0xFF)`, with male-only, female-only
       and genderless ratios handled first (`SpeciesData_GetGenderOf` in
       `pokeplatinum/src/pokemon.c`). It counts only if the result is female.
    3. Every other kind (`gift`, `egg`, `static`, `roamer`, `wild_slot`) has a random personality
       (research R3). It counts whenever signal 1 holds.
  - No current gift, egg or static entry fixes gender, so B3 changes no current result. T024's
    monkeypatch is the positive control.
  - Cite the `GivePokemon`/`GiveEgg`/`CreateWildMon` paths (research R3).
- [X] T027 [US3] Rewrite the breed and fossil `detail` text in
  `src/platsim/legality/movesources.py` (`_breed_options` `:627` and `acquire_text` `:312-342`)
  per `contracts/team-rules.md`. In `src/platsim/explain.py`, print the group and choice for each
  grouped option.
- [X] T028 [US3] Run T024–T025 and `tests/unit/test_source_text.py` in full. Check every failing
  fixture test against plan Risks before editing a fixture: only newly generated text may change.
  Record the output.

---

## Phase 7: Polish and cross-cutting

- [X] T029 [P] Add `test_species_team_count` to `tests/unit/test_team_groups.py`.
  - Recount the species-only teams of six distinct species from the engine (research R9 method).
  - Assert `55192424630`.
  - Positive control: the same function with the group rule disabled → `56574476596`.
- [X] T030 [P] Add `test_allowed_final_forms` to `tests/unit/test_team_groups.py` (SC-003). It
  needs no script from outside the repo.
  - The default-option catalog species set equals the T001 baseline (188 keys).
  - Rebuild the final forms from the `catalog` fixture plus `data/generated/species.json`
    evolutions. A final form is an allowed species with no allowed evolution target. Parse the
    names in the "Flat list of final forms" section of `allowed_pokemon.md` and assert the two sets
    are equal (98 names).
  - Positive control: dropping one species from the allowed set changes the rebuilt list.
  - `allowed_pokemon.md` is untracked today. Commit it with this task so the test has a fixed
    reference.
- [X] T031 Bump the version in `pyproject.toml` from 0.2.0 to 0.3.0, because the default legality
  changed.
  - The version is read with `importlib.metadata.version` in `_platsim_version()`
    (`src/platsim/web/app.py:86`) and stored per job as `platsim_version`. It is shown by
    `src/platsim/web/result_view.py:80`.
  - Run `uv sync` so the installed metadata updates.
  - Check that `uv run python -c "from platsim.web.app import _platsim_version as v; print(v())"`
    prints `0.3.0`.
- [X] T032 Update `README.md` ("Legality" ground rules, lines 30–62) with the starter-line rule,
  the fossil Trainer ID rule and the breeding-partner rule.
- [X] T033 Run the quickstart fast checks, then the full suite `uv run pytest -q` (about 2.5 h).
  Paste the real outputs into `validation-log.md`.
- [X] T034 Update `RUN-STATE.md` (004 section): done, commits, how to test, and what is not
  committed. Commit on `004-breeding-source-limits`. Don't merge.

---

## Dependencies

- **Setup** (T001–T002) → **Foundational** (T003–T008) → the story phases.
- **US1** (T009–T015, including T011a) depends only on Foundational. It is the MVP.
- **US4** (T016–T020, including T020a) depends on Foundational. T020a also needs T012. It is independent of US1, but its breed
  inheritance for fossil lines uses T012 (B1). Do it after US1, or accept that bred fossils stay
  ungrouped until T012 lands.
- **US2** (T021–T023) and **US3** (T024–T028) depend on Foundational.
  - Both edit `breed_mothers`: do T022 before T026.
  - T027's fossil text needs T018.
- **Polish**: T029 needs US1 and US4. T030–T034 come last.

## Parallel opportunities

- Within each story, the test tasks marked [P] touch different files and can be written together.
  Examples: T009, T010, T011 and T011a; T016 and T017; T024 and T025.
- T029 and T030 can run in parallel.
- Implementation tasks mostly touch `movesources.py`, so they are sequential.

## Implementation strategy

1. **MVP**: Setup, Foundational, then US1. Stop and show that Torterra + Infernape is refused in
   validate, optimize and the web UI.
2. Then US4 (fossils), US2 (partner) and US3 (tracing and text), each run with its checkpoint.
3. Polish: the count proof (SC-002), the unchanged list (SC-003), docs and the full suite. Then
   the user tests by hand before merging.
