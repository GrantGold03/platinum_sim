# Contract: items, item-conditioned valuation, extras, screen, dominance

## `candidates.py`

- `CRIT_STAGE_RATES: tuple[int, ...]` parsed from `pokeplatinum/src/battle/battle_lib.c` (`sCriticalStageRates`); `HIGH_CRIT_EFFECTS`.
- `EFFECT_COSTS: dict[str, str]` (effect constant → reason); `effect_class(effect) -> "cost" | "plain" | "secondary"`.
- `dominates(a, b) -> bool` per data-model.md; `prune(move_consts)` unchanged in shape, reasons name the winner and axes.
- `move_value(const_member, move_const, member_level=100, item_effect: str | None = None) -> list[float]`.
- `held_item_candidates(const_member, moveset, led, team=None, level=100) -> list[str | None]` unchanged (today's list);
  `extra_item_candidates(const_member, moveset, led) -> list[str]` (the two rules, filtered, in order).
- `member_candidates(...)`: `MemberCandidates` gains `items_extra`, `item_extras`, `extras_by_kind`; `movesets` order per data-model.md.

## `run.py`

- `_member_options(mcs)`: base sets × `items` (no appended items).
- `_member_extra_options(mcs) -> list[tuple[kind, (variant, moveset, item)]]` in the fixed order; the screen appends them beyond
  `N_CANDIDATES` as single-slot deviations and records `extras_screened` by kind.

## Tests

- `tests/unit/test_h4_items.py`: the crit table pin; `move_value` with and without `item_effect` on fixed moves (Fire Blast
  under the lens, Stone Edge under the claw); the item rules on fixed movesets (lens only with a missing move; claw with any
  attack; Scope Lens never); a third Razor Claw refused by `resources.repair`; item-conditioned extras exist where the ranking
  changes and carry the item; the dominance controls; the pruned reasons.
- `sim/test/switch_reset.test.mjs`: `_internal.doSwitch` on a cloned root with boosts set resets every stage of the outgoing
  and incoming member.
