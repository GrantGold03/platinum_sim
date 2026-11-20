# Contract: Shell Bell in the player and the optimizer

- `applyHit` heals a Shell Bell holder by `max(1, floor(dmg / 8))` when `dmg > 0`, holder `0 < hp < maxhp`, option on; both sides.
- `expectimax2-v4?shellBell=0` is a valid v4 candidate with the heal off; any other value is an `invalid_policy` error.
- Replay test byte-identical; Node tests: holder 50% dealing 80 heals 10; full HP heals 0; 7 damage heals 1; fainted by recoil
  heals 0; the knob off heals 0.
- `extra_item_candidates(const, moveset, led)` ends with `shell_bell` for every moveset with an attack when a copy exists; existing
  entries keep their order; `resources.realize` refuses a second Shell Bell on a team.
