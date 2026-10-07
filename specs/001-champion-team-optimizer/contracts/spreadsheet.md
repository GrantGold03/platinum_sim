# Contract: Result spreadsheet (`result.xlsx`, `result.csv`)

## Sheet "Team" (also `result.csv`)
One row per member. Example values are illustrative only, not checked against game data.

| Column | Example |
|---|---|
| Slot | 1 |
| Species | Garchomp |
| Obtained from | Wild – Wayward Cave (Gible) |
| Start level | 48 |
| Final level (expected) | 51.3 |
| Ability | Sand Veil |
| Ability choice | tested_better / tie_default / other_no_battle_effect / single_ability / fixed_by_trade |
| Held item | item name |
| Held item source | where the copy comes from, e.g. "Item ball – <map>" or "Shop – <map> (unlimited)" |
| Nature | Hardy |
| IVs | 15/15/15/15/15/15 |
| EVs | 85/85/85/85/85/85 |
| Move 1 … Move 4 | Earthquake |
| Move 1 … Move 4 source | TM26 – Victory Road item ball (1 copy) · Level-up Lv 48 · Route 212 tutor (2R/4B/2Y/0G) · Egg move · Pre-evolution level-up (Gabite Lv 40) |

## Sheet "Evaluation"
- clear rate with 95% CI;
- clear rate per trainer;
- expected average final level and level gap;
- runs;
- threshold;
- qualified/borderline;
- top loss causes.

## Sheet "Resources"
For each single-copy TM and limited item: who uses it, copies used, and copies available.

## Sheet "Provenance"
- decomp commit;
- Showdown commit;
- divergence ledger version;
- player and opponent policy;
- master seed;
- budget preset.

## Sheet "Divergences"
Every ledger entry that applies to this run, with its resolution and impact.
