# Quickstart: validating 004

Each scenario says how to check one part of the feature. See the contract
([team-rules](contracts/team-rules.md)) and the entities ([data-model](data-model.md)).

## Prerequisites

- Branch `004-breeding-source-limits` and `uv sync`.
- After the ledger change, run `uv run platsim extract`. Then `uv run platsim extract --check`
  must pass.

## Fast checks

```bash
uv run pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py \
  tests/unit/test_source_preference.py tests/unit/test_source_text.py tests/unit/test_legality_options.py
uv run pytest -q tests/integration/test_web*.py tests/integration/test_availability_controls.py
```

## V1. Mixed starters are rejected (spec US1, SC-001)

- **Validator**: the `legal_team.json` fixture has slot 0 as gift Chimchar → Infernape. Add a
  Torterra declared as `breed:SPECIES_TURTWIG@MAP_HEADER_POKEMON_DAY_CARE`.
  - **Expect**: `SOURCE_EXHAUSTED`, with a message naming both members and "only one starter".
- **Web**: `POST /api/jobs` with Torterra, Infernape and four other Pokémon.
  - **Expect**: 422. `reasons` has exactly the keys `torterra` and `infernape`, and no job is
    created.
- **Optimizer**: `uv run platsim optimize torterra infernape ...`.
  - **Expect**: a non-zero exit and an "invalid species" line on stderr before any battle.
- **Positive control**: the same three calls with Infernape, Monferno and four others succeed.
  So do three Infernape plus three others.

## V2. Two gifts are still one gift (regression)

- `test_starter_choice_is_exclusive` (two members both declaring the starter gift) still gives
  `SOURCE_EXHAUSTED`.

## V3. Fossils (spec US4)

- **Rampardos + Bastiodon** → `SOURCE_EXHAUSTED`, with the Trainer ID message.
- **Two Rampardos** → accepted.
- **`platsim explain species:rampardos`** shows the revival with "odd Trainer ID".

## V4. Breeding partner and one-time female (spec US2, US3)

- **Test**: list all breed options under default options and check that each one has a father,
  or Ditto, from `compatible_father`. Expect 86 options. Any drop must be listed and explained.
- **Positive controls (fixture ledgers)**:
  - Remove all compatible males of one line → its breed option disappears.
  - Mark a one-time parent as fixed male → its line's breed option disappears.
- **Explain text**: bred Lucario names Riley's egg (Iron Island), and bred Vaporeon names the
  Hearthome gift Eevee.

## V5. Nothing else moved (spec FR-008, SC-003)

- Regenerate `allowed_pokemon.md` with the 2026-10-13 script, or with the per-species catalog
  test.
  - **Expect**: the same 188 allowed species and the same 98 final forms. `git diff
    allowed_pokemon.md` is empty.

## V6. Team count (spec SC-002)

- **`tests/unit/test_team_groups.py::test_species_team_count`** recounts the teams of six distinct
  species from the engine.
  - **Expect**: `55192424630`.
  - **Positive control**: the same function with the group rule disabled returns `56574476596`.

## Full suite before merge

The full suite (`uv run pytest -q`) must be green before merge. Record its output in
`RUN-STATE.md`.
