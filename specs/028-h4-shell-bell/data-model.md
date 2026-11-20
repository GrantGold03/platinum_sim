# Data model: H4, Shell Bell

- **Heal**: `max(1, floor(dmg / 8))` where `dmg` is the HP the target lost to the holder's move; applied when the holder is below
  max HP and above 0 after the move's own self-effects; capped at max HP.
- **Policy option**: `shellBell` (default true); knob `expectimax2-v4?shellBell=0` for the reference arm only.
- **items_extra**: per moveset with an attack, the existing appended items then `shell_bell` when a copy exists.
- **Ledger entries**: one per confirmed engine-vs-game difference (id, decomp and engine citations, impact).
