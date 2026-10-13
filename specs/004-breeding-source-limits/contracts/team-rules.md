# Contract: Team-Level Choice Rules (004)

This file lists only the changes. Everything else is as in the 001–003 contracts.

## Validator (`platsim validate`, `legality.validator.validate`)

- **Code**: `SOURCE_EXHAUSTED`. No new code is added. It is now raised in three cases:
  1. **A group has more than one choice.** The messages are:
     - Starter: `only one starter can be chosen, but the team uses <N> lines: <Member> (<Line base>), ...`
     - Fossil: `Skull and Armor Fossils need different Trainer IDs (odd vs even), so the team cannot use both: <Member> (<choice>), ...`
  2. **A one-time option is used more times than it allows.** This now includes grouped options.
     For example, two members declaring `gift:SPECIES_CHIMCHAR@MAP_HEADER_ROUTE_201`. The
     message is unchanged.
  3. **Breed-option group from the declared source.** A member declaring
     `breed:SPECIES_CHIMCHAR@MAP_HEADER_POKEMON_DAY_CARE` counts in the starter group with choice
     Chimchar.
- **`src` refs** on the violation:
  - starter: `res/field/scripts/scripts_route_201.s`, the starter choice;
  - fossil: `src/underground/mining.c:647-648`;
  - breeding: `src/overlay005/daycare.c:817-875`;
  - spec: FR-002 or FR-011.
- **Accepted** (no violation):
  - one starter gift plus any number of bred members of the same line;
  - any number of bred members of one line;
  - any number of members of one fossil line.

## Optimizer (`platsim optimize` / `evaluate`, `candidates.resolve_species`)

- **Mixed groups.** Six species that cannot share one choice per group raise
  `InvalidRequest("invalid species: <message>", reasons)` before any battle runs. `reasons` maps
  each conflicting submitted name to the group message.
- **Exit code and stderr** are the same as for other invalid species.

## Web (`POST /api/jobs`)

- **Mixed groups** return 422, `{"detail": "some Pokémon cannot be used together: <message>",
  "reasons": {<key>: <message>, ...}}`. The `reasons` keys are only the conflicting members.
- **No job is created.**
- **`GET /api/species` is unchanged.** The 188 species stay `available: true` under default
  options (spec FR-008). Conflicts exist only at team level.

## Source text ("Obtained from", CSV, JSON report, `platsim explain`)

- **Breed options name the parent's source:**
  - `Day Care egg from your starter <Line base>`
  - `Day Care egg from a revived <Skull|Armor> Fossil (<odd|even> Trainer ID)`
  - `Day Care egg from a one-time parent: <the parent's source text>` when the mother line has a
    single one-time source. For example, `Gift egg - Iron Island B2F Left Room (Riolu)` or
    `Gift - Hearthome City Northwest House (Eevee)`.
  - `Day Care egg (mother: <names>)` for other lines. This text is unchanged; " or Ditto" appears
    only when Ditto is obtainable.
- **Fossil revivals** read `Fossil - Mining Museum (<Fossil>, <odd|even> Trainer ID)`. This keeps
  the 003 prefix and adds the parity. (Revised 2026-10-13 during implementation.)
- **Old report files are not rewritten** (003 practice).
