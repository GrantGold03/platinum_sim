# Research: H4, resist berries

## R1. The game's rule

- **Finding**: `subscript_update_hp.s:10` calls `BATTLE_SUBSCRIPT_TYPE_RESIST_BERRY` before the HP bar update. The subscript reads the
  defender's hold effect: 35 (Chilan) triggers when the move's type is Normal (after Normalize: `_000`-`_033`, the type is Normal when
  the attacker has Normalize); 19 to 34 (the 16 type berries) trigger only with `MOVE_STATUS_SUPER_EFFECTIVE` and the matching type;
  then `DivideVarByValue BTLVAR_HP_CALC_TEMP, 2` (integer, the HP change) and `RemoveItem`. One-hit KO moves and type-check-ignoring
  moves skip it. The halving is on the final damage, before the HP clamp.
- **Decision**: the player's rule: `dmg = floor(dmg / 2)` before the clamp to the defender's HP, berry removed, when the defender's hold
  effect is `HOLD_EFFECT_WEAKEN_SE_<move type>` and the hit is super-effective, or `HOLD_EFFECT_WEAKEN_NORMAL` and the move is Normal
  (after Normalize).

## R2. Multi-hit moves

- **Finding**: the game runs the HP update per hit, so the berry halves the first hit and is gone for the rest. The player applies a
  multi-hit move's total in one `applyHit` call (its `HITS` table gives the hit counts).
- **Decision**: for a multi-hit outcome of `n` hits totalling `dmg`, the reduction is `floor(dmg / n) - floor(floor(dmg / n) / 2)`
  (the first hit's share halved); a single hit is the R1 rule. Recorded as the model's approximation (per-hit rolls are not modelled).

## R3. The super-effective flag in the player

- **Finding**: `damageOutcomes(X, S, u, t, rec)` builds the per-roll damage list from `sim/damage.mjs`, whose type-chart pass computes
  the move-status mask including super-effective.
- **Scope of the model**: only the hit's outcome sees the berry; the player's other judgements that read raw damage (switch-in
  choice, threat assessment) do not; stated in the README (spec FR-012).
- **Decision**: `damageOutcomes` adds `se: true|false` (and the hit count for multi-hit) to each outcome; `applyHit(X, S, side, rec, e,
  dmgIn, se, hits)` applies R1/R2; the knob `X.opts.resistBerries === false` turns it off. Both sides, for symmetry.

## R4. Engine checks (to run at implementation, Node tests against the vendored engine)

- Rounding (game integer halving of the final HP change vs the engine's 0.5 modifier with its rounding); a hit on a substitute (engine:
  no consumption); a multi-hit move (engine: first hit); Chilan on an immune Normal hit (no damage: no trigger) and on a resisted Normal
  hit (game: triggers; engine: `onSourceModifyDamage` for Chilan checks `move.type === 'Normal'` only?); Normalize. Each difference is
  ledgered with its impact (League movesets: who uses Normal moves against a Chilan holder, who has Normalize: none expected).

## R5. The berry ranking (FR-006)

- **Decision**: `resist_berry_ranking(const_member, level)`: for each League mon (weights as `league_opponents`: Elite Four 1, Cynthia
  2) and each of its stored damaging moves whose type hits the member super-effectively (or any Normal move, for Chilan), a threat value
  = power × accuracy × the opponent's STAB weight × the opponent's base attacking stat by category × the type multiplier against the
  member, divided by the member's base Defense (physical move) or base Special Defense (special move), so the ranking reflects how hard
  the hit lands on this member (owner's emphasis, analyze 2026-11-23); per mon and per type the largest; per type the weighted sum,
  halved (the damage the berry blocks). Berry types ranked by that
  value, ties by type name; the top two with a copy appended to every moveset's `items_extra` after Shell Bell. Members with no threat
  get none.
- **Alternative**: full damage formula per opponent (levels, the member's defences): rejected as unneeded for a ranking.

## R6. The player-check team

- **Decision**: the 029 pre-feature B2 winner with the top-ranked berry given to the member whose top berry blocks the most (by R5),
  replacing its item; the check uses 028's `paired_policies.py --battle-style shift` with `--a expectimax2-v4 --b
  'expectimax2-v4?resistBerries=0'`, a `--self` pairing control and a conditions control on the unmodified team.
