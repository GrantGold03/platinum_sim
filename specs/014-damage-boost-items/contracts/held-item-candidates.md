# Contract: `held_item_candidates` after H3

Signature unchanged: `held_item_candidates(const_member, moveset, led, team=None) -> list[str | None]`.

Output, in order:
1. Unchanged from `main`: best HP berry; type-boost item for the strongest attack's type; Leftovers when the team
   may hold it.
2. New, when the moveset has at least one attack:
   - each `HOLD_EFFECT_POWER_UP_SE` item with a pre-Champion copy (today `expert_belt`);
   - the strongest attack is physical → each `HOLD_EFFECT_POWER_UP_PHYS` item with a copy (today none);
     special → each `HOLD_EFFECT_POWER_UP_SPEC` item with a copy (today `wise_glasses`).
3. No duplicates; then the H2 filter (no single-use non-berry item); `[None]` if empty.

| Case (tests) | Result |
|---|---|
| Empoleon, `(MOVE_SURF,)` | `['sitrus_berry', 'splash_plate', 'expert_belt', 'wise_glasses']` |
| Garchomp, `(MOVE_EARTHQUAKE,)` | `['sitrus_berry', 'earth_plate', 'expert_belt']` |
| any member, no attacking move | no booster |
| Garchomp, `(MOVE_EARTHQUAKE,)`, ledger stub giving Muscle Band 1 copy | includes `muscle_band` (positive control) |
| Snorlax team, Body Slam | `['sitrus_berry', 'silk_scarf', 'leftovers', 'expert_belt']` |

The exact lists for Empoleon, Garchomp and Snorlax are checked against the real function at implement time (T-task)
before they are fixed in tests.
