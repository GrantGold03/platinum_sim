# Quickstart: validating 005

Each scenario says how to check one part of the feature. See the contract
([second-game-option](contracts/second-game-option.md)) and the entities
([data-model](data-model.md)).

## Prerequisites

- Branch `005-second-game-option` and `uv sync`.
- No data regeneration is needed. `uv run platsim extract --check` must still pass.

## Fast checks

```bash
uv run pytest -q tests/unit/test_team_groups.py tests/unit/test_validator.py tests/unit/test_reports.py \
  tests/unit/test_legality_options.py tests/integration/test_web.py
```

## V1. Mixed lines with the option on (US1)

- **Validator**: build Torterra + Infernape and Rampardos + Bastiodon teams (the 004 test helpers
  `_member` and `_with`). Validate them with `options=LegalityOptions(allow_unobtainable_pokemon=True)`.
  - **Expect**: no `SOURCE_EXHAUSTED`. The same teams with default options give `SOURCE_EXHAUSTED`.
- **Optimizer**: `resolve_species(["torterra", "infernape", …])` on the option-on view returns six
  constants, and on the default view raises `InvalidRequest`.
- **Web**: `POST /api/jobs` with `allow_unobtainable_pokemon: true` returns 201. Without it,
  the response is 422.
- **Positive control**: two Giratina is still refused with the option on.

## V2. Label (FR-004)

- `team_sources` on a Torterra + Infernape team (option-on view) labels exactly the second member.
- On Infernape + Monferno, no member is labelled.
- Order swapped, the label moves to the other member.

## V3. Wording (US2)

- The page HTML contains "Allow Pokémon unobtainable in one Platinum game".
- `app.js` contains "Pokémon unobtainable in one Platinum game".
- `platsim optimize --help` shows the new help text.
- Positive control: `grep -rn "unobtainable in Platinum" src/platsim/web src/platsim/cli.py`
  returns nothing. Before the change, the same grep finds 2 hits.

## V4. Counts (SC-001, SC-002)

- `test_species_team_count` (default) → `55192424630`.
- The new option-on count test → `1174080931485`. Its control, with the groups forced on →
  `1163212171902`.
- `test_allowed_final_forms` is unchanged (188 species, 98 final forms).

## Full suite before merge

The full suite (`uv run pytest -q`) must be green before merge. Record the output in
`validation-log.md`.
