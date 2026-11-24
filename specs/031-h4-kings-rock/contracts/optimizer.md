# Contract: the flinch item in the optimizer

- `extra_item_candidates(member, moveset, led)`: ends with `kings_rock` when the moveset has an affected move.
- `member_candidates(...)`: may add one extra set of kind `flinch_item` per variant (see data model).
- `realize(team, levels, led)`: a second `kings_rock` holder holds `razor_fang`; a third is refused; the realized team names the
  actual item.
- Reports: `held_item` is the actual item; the acceptance script lists flinch-item holders.
