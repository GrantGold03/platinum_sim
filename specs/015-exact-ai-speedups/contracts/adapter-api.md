# Contract: AI adapter additions (`sim/ai/adapter.mjs`)

The adapter stays read-only over the Battle. Three additions; everything else is unchanged.

## `ai.beginDecision()`

Drops the decision cache (`battlers`, `fields`) and increments `cacheStats.decisions`. Must be called by an
adapter owner that reuses the adapter across battle changes, at the start of every decision:

- `sim/ai/opponent.mjs` `decide(st, side)`: first statement.
- `sim/policy/expectimax2.mjs` `makeContext()`: after `mirrorFor`, on `mirror.ai`.

An adapter over a state that never changes (a shadow view) need not call it. Calling it more often than needed
is always safe (only speed is lost).

## `ai.damageInput(attackerPoke, defenderPoke, moveNum, { power, type, powerMul })`

Returns `{ attacker, defender, move: { id, power, type, powerMul }, field, crit: false }`, deep-equal to
`fromShowdown(ai.battle, attackerPoke, defenderPoke, moveNum, { power, type, powerMul })` for the same battle
state, with:

- `attacker`, `defender`: the cached battler structs of the two Pokemon objects (built on first use in the
  decision with `battlerFromShowdown`);
- `field`: the cached field struct for the defender's side, plus `attackerSideAbilities` /
  `defenderSideAbilities` derived from the two structs (built per call, two one-element arrays);
- `move`: built per call.

The returned `attacker`, `defender` and `field` objects are shared: callers MUST NOT write to them. Callers today:
`calcdamage.portInput` and the post-KO scorer in `switch.mjs`. Throws for a non-singles battle, as `fromShowdown`
does.

## `ai.cacheStats`

`{ builds, hits, decisions }`, diagnostics only. `builds` counts battler structs built, `hits` cache returns.
Used by the tests for FR-004 (one build per Pokemon per decision regardless of samples).

## Freeze guard

`PLATSIM_AI_FREEZE=1` in the environment at import time deep-freezes every struct when it is built (battler and
field). A write anywhere downstream then throws `TypeError` (ESM strict mode). Default off; the Node suite is run
once with it on (quickstart). `sim/ai/INTERFACE.md` documents the variable next to `PLATSIM_AI_DEBUG`.

## Constants (`sim/ai/constants.mjs`)

`Constants.get(name)` is unchanged in result and in error behaviour (unknown symbol, recursive definition). Its
memo hit path performs one `Map.get` and allocates nothing.

`effectSet(ai, table)` (exported from `sim/ai/calcdamage.mjs`): `Set<number>` of `table.names` resolved through
`ai.constants`, cached per `(table, constants instance)`. `effectIn(ai, table, x)` ≡ `effectSet(ai, table).has(x)`.
