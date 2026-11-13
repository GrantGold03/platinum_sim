# Data Model: H4, Wide Lens and Razor Claw

## Item rules (`candidates.held_item_candidates`, appended list `items_extra`)

| Rule | Hold effect | Condition on the moveset | Copies | Where it lands |
|---|---|---|---|---|
| accuracy item | `HOLD_EFFECT_ACCURACY_UP` (Wide Lens, param 10) | any attack with 0 < accuracy < 100 | `_item_copies != 0` (unlimited) | `items_extra[moveset]` |
| crit item | `HOLD_EFFECT_CRITRATE_UP` (Razor Claw 2 copies; Scope Lens 0, never offered) | any attack | `_item_copies != 0` | `items_extra[moveset]` |

Order within `items_extra`: accuracy item, then crit item. The single-use filter applies. Today's `items[moveset]` lists are
unchanged.

## Move value (`candidates.move_value(const, move, level, item_effect=None)`)

| Factor | Today | This feature |
|---|---|---|
| accuracy | `1.0` if data 0 else `acc/100` | under `ACCURACY_UP`: `min(1.0, acc/100 × (100+param)/100)` |
| crit term | none | `1 + 1/CRIT_STAGE_RATES[stage]`, `stage = high_crit(move) + (1 if item_effect == CRITRATE_UP else 0)`, cap 4 |
| others | power, STAB, base stat, effect weight, type multiplier, opponent weight | unchanged |

`CRIT_STAGE_RATES = [16, 8, 4, 3, 2]` parsed from `battle_lib.c` `sCriticalStageRates` (`:7097-7103`), pinned by test.
`HIGH_CRIT_EFFECTS`: decomp effects containing `HIGH_CRITICAL`.

## MemberCandidates (changed)

| Field | Notes |
|---|---|
| movesets | today's sets, then the 024 variable-power extras, then lens-conditioned extras, then claw-conditioned extras |
| items | per set: today's list (base sets) or `[conditioning item] + usual list` (item-conditioned extras) or the first-item list (024 extras) |
| items_extra | per base set: the appended items (accuracy, crit) |
| item_extras | `{moveset: item_const}` for the item-conditioned extra sets |
| extras | count of appended sets of every kind; `summary()` reports `extras_by_kind: {variable_power, accuracy_item, crit_item}` and `items_extra` |
| pruned | reasons now `dominated by X (same type/category; at least as good on power, accuracy, priority, PP, effect; better: <axes>)` |

## Appended screen options (`run._member_extra_options`), fixed order per member

1. 024 variable-power extra sets × their first item
2. item-conditioned extra sets × their conditioning item
3. base sets × each `items_extra` item (by slot, then set order, then item order)

Screen stage record: `extras_screened: {variable_power, accuracy_item, crit_item, item_deviations}`.

## Dominance (`candidates.dominates`)

Axes: type and category equal; power, accuracy (0 → 101), priority, PP at least as good; effect by class (`EFFECT_COSTS`
table: cost; plain; secondary) with equal effects compared by `effect_chance`; strictly better on at least one axis. Controls:
Earthquake > Dig, Waterfall > Dive, Rock Climb > Take Down (dropped); Fire Blast vs Flamethrower, Close Combat vs Brick Break,
Thunderbolt vs Discharge (kept); a constructed equal-power plain move > a self-dropping one (dropped).

## Provenance block (`provenance.member_defaults`)

```json
{"nature": "Hardy", "ivs": 15, "evs": 85, "friendship": 255,
 "reason": "the average Pokemon a player has, not a bred or trained one (constitution v1.5.0)",
 "fixed_by_game": ["SPECIES_..."]}
```

Written by `evaluate_team` and merged into the optimizer's provenance; absent in pre-feature files (no default on read); shown
by the xlsx provenance sheet's generic loop.

## Acceptance table

Both B2 quick winners (species, moves, items, levels, clear rate, n, wall, code hashes); members holding Wide Lens or Razor
Claw; screen overlap (of the main run's 81 teams, how many the branch screened; `extras_screened` by kind); identity rows
(identical after removing the volatile fields and `provenance.member_defaults`); the equal-levels row (n, rates, discordant,
p, verdict, levels); the attributed diff per B1 to B5 member (removed moves → dominated; added sets/items → appended; residual
reorderings → crit term; unexplained → defect).
