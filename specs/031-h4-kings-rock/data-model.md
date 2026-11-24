# Data Model: H4, King's Rock / Razor Fang

- **Equivalent items group**: `kings_rock -> (kings_rock, razor_fang)`; the candidates name the first; realize assigns the first
  affordable member of the group; at most the group's total copies on a team (2, less Gliscor's evolution use).
- **Extra kind** `flinch_item`: a member's best base set with its best affected multi-hit move swapped in, paired with `kings_rock`;
  recorded in `item_extras` and `extra_kind` like 025's kinds; counted in `extras_by_kind`.
- **Appended item**: `kings_rock` last in `items_extra` for sets with an affected move.
