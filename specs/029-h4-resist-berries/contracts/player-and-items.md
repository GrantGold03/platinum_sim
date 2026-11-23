# Contract: resist berries in the player and the optimizer

- Player: a super-effective hit of the berry's type on a holder: halved, berry gone; neutral: unchanged, berry kept; second hit after
  consumption: unchanged; Chilan with a Normal neutral hit: halved; the knob off: unchanged; replay byte-identical.
- `expectimax2-v4?resistBerries=0` is a valid candidate; other values are `invalid_policy`.
- `extra_item_candidates` ends with up to two resist berries (by `resist_berry_ranking`) after Shell Bell for every moveset with an
  attack; members with no threat get none; existing entries keep their order.
