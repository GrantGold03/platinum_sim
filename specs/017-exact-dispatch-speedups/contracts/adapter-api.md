# Contract: AI adapter additions (`sim/ai/adapter.mjs`, `sim/ai/cmds/battler.mjs`), round three

The adapter stays read-only over the Battle. Feature-015 and 016 contracts (`beginDecision`, `damageInput`,
`typeChartPlan`, `preVariance`, `cacheStats`, freeze guard, `PLATSIM_AI_CHECK`) are unchanged in meaning; this
feature adds one memo slot, extends the control mode to the 015 structs, and splits the speed comparison into a
memoised part and a reference.

## `ai.speedPair(build)`

Returns the decision's speed pair: the stored one if present, else `build()` stored for the rest of the decision
(deep-frozen under `PLATSIM_AI_FREEZE=1`). `build` must be a pure function of the adapter's state (it is
`cmds/battler.mjs`'s pair builder). Counted in `cacheStats.speedPairs` (builds) and `speedPairHits`. Under
`PLATSIM_AI_CHECK=1` every hit calls `build()` again and compares (`checkSame('speedPair', 'pair', stored,
fresh)`); a difference throws `adapter: CHECK mismatch speedPair pair: memo=… fresh=…`. Dropped by
`beginDecision()`.

## `ai.damageInput(...)` (unchanged contract; control mode extended)

Under `PLATSIM_AI_CHECK=1`, a hit on the per-Pokemon battler struct recomputes `battlerFromShowdown(p)` and
compares (`'battler'`, key = the Pokemon's species id and party slot), and a hit on the per-side field struct
recomputes it and compares (`'field'`, key = side id). Comparisons are counted in `cacheStats.structChecks` and
`CHECK_STATS.checks`; a difference throws `adapter: CHECK mismatch battler <key>: …` / `… field <key>: …`.
`cacheStats.fieldBuilds` counts field builds. The returned structs stay shared and read-only; the policy copies
them before writing (contracts/policy-and-bench.md).

## `ai.cacheStats` (extended)

`{ builds, hits, decisions, plans, planHits, preVariance, preVarianceHits, checks, fieldBuilds, structChecks,
speedPairs, speedPairHits }`. Diagnostics only; tests use deltas (one pair build per adapter per decision however
many callers; `builds` <= Pokemon with hp > 0 per decision for the policy's root adapter).

## `beginDecision()` (unchanged contract, extended effect)

Also drops the speed pair.

## `compareBattlerSpeed(ctx, battler1, battler2)` (`cmds/battler.mjs`, unchanged signature and result)

1. The two fainted-battler early returns exactly as today (`curHP(b1) === 0 && curHP(b2)` -> 1; `curHP(b1) &&
   curHP(b2) === 0` -> 0), before any memo.
2. If `battler1` and `battler2` are 0 and 1 in either order: `pair = ctx.ai.speedPair(() => ({ b: [battlerSpeed(ctx,
   0, ncn), battlerSpeed(ctx, 1, ncn)] }))` with `ncn` = the Cloud Nine / Air Lock check as today; `b1 = pair.b[battler1]`,
   `b2 = pair.b[battler2]`. Any other battler ids (doubles slots, not reachable in singles) take the direct path.
3. `ctx.mem.monSpeedValues[battler1] = b1.speed`, `[battler2] = b2.speed`, then the comparison with `coin()` draws
   from `ctx.rand`, unchanged.

Result, `monSpeedValues` and draw count equal `compareBattlerSpeedDirect` for every input (FR-008; tested over >=
1,000 real views x three caller shapes with a positive control).

## `compareBattlerSpeedDirect(ctx, battler1, battler2)`

Today's body kept verbatim and exported as the reference (Constitution Principle VI). Not called by product code
(the doubles fallback above calls `battlerSpeed` directly, not this function).

## Call sites (unchanged code, changed cost)

`speedValuesNow(ai)` (`choose.mjs`), `speedInfo(X, S)` (`policy/expectimax2.mjs`) and `IfSpeedCompareEqualTo`
(`cmds/battler.mjs`) keep calling `compareBattlerSpeed`; the first call on a view builds the pair, the rest hit.

## `PLATSIM_AI_CHECK=1` runs

Default suite: the 016 child test (one Aaron battle per policy) now also asserts `structChecks > 0` and
`speedPairHits > 0` in the child's printed `cacheStats` aggregate; a new child mutates a returned battler struct
(`damageInput(...).attacker.hp = 1`, without FREEZE) and calls `damageInput` again, and must exit non-zero with
`CHECK mismatch battler`. Before the merge: `PLATSIM_AI_CHECK=1 node sim/bench.mjs --policy expectimax2-v2` and
`-v1` with digests unchanged, recorded in the validation log (the control now roughly doubles the struct and speed
work as well as the 016 memos).
