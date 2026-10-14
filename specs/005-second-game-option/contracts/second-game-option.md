# Contract: Second-Game Option (005)

This file lists only the changes from `specs/004-breeding-source-limits/contracts/team-rules.md`.

## Validator, optimizer and web

| | Option off (default) | Option on (`allow_unobtainable_pokemon`) |
|---|---|---|
| Two starter lines | `SOURCE_EXHAUSTED` "only one starter…" / `InvalidRequest` / 422 (as in 004) | accepted |
| Both fossil lines | `SOURCE_EXHAUSTED` Trainer ID / `InvalidRequest` / 422 (as in 004) | accepted |
| One starter gift used by two members | `SOURCE_EXHAUSTED` (quantity) | `SOURCE_EXHAUSTED` (quantity), unchanged |
| Two Giratina | refused (quantity) | refused (quantity), unchanged |

With the option on, `POST /api/jobs` with a mixed team returns 201 and creates the job.

## "Obtained from" (JSON report, CSV, spreadsheet, web results view)

- **Labelled members:** each member whose group choice differs from an earlier member's has
  `(from a second Platinum game, allowed by rule)` added to its normal text. For example:
  `Day Care egg from your starter Turtwig -> … (from a second Platinum game, allowed by rule)`.
- **No other member is labelled.** With the option off, the text never appears.
- **Old reports are not rewritten.** `report --rerender` recomputes the text from the report's
  own recorded options.

## Wording

| Place | Text |
|---|---|
| Setup checkbox | Allow Pokémon unobtainable in one Platinum game |
| Results summary rule label | Pokémon unobtainable in one Platinum game |
| `--allow-unobtainable-pokemon` help (validate, evaluate, optimize) | allow Pokémon unobtainable in one Platinum game (other cartridges, events, none, or a second starter / the other fossil) |

**Unchanged:** the key `allow_unobtainable_pokemon`, the flag `--allow-unobtainable-pokemon`,
the checkbox id `allow-unobtainable-pokemon` and the query name `unobtainable_pokemon`.
