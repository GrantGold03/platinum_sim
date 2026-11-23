# Data model: H4, resist berries

- **Outcome** (player): `{p, dmg, se, hits}`; `se` true for a super-effective hit; `hits` the hit count (1 for single hits).
- **Berry rule**: defender hold effect `HOLD_EFFECT_WEAKEN_SE_<type>` with `se` and matching type, or `HOLD_EFFECT_WEAKEN_NORMAL` with a
  Normal move: `dmg -= floor(first-hit share / 2)` (single hit: `dmg = floor(dmg / 2)`), berry removed; before the HP clamp.
- **Ranking**: per member, `[(berry_key, blocked_value)]` sorted desc, ties by type; the top two appended to `items_extra`.
- **Policy option**: `resistBerries` (default true); knob `expectimax2-v4?resistBerries=0` for the reference arm.
