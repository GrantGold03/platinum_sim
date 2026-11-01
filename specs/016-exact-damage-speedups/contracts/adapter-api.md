# Contract: AI adapter additions (`sim/ai/adapter.mjs`), round two

The adapter stays read-only over the Battle. Feature-015 contracts (`beginDecision`, `damageInput`, `cacheStats`,
freeze guard) are unchanged; this feature adds two memoised methods, counters, one environment variable and
module-level mapper sharing.

## `ai.typeChartPlan(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul }, { ignoreTypeChecks = false } = {})`

Returns `typeChartPlan(ai.damageInput(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul }),
{ ignoreTypeChecks, moveStatusMask: 0 })`, memoised for the current decision on `(attacker struct, defender struct,
move num, power, type, ignoreTypeChecks)`. The returned plan is shared and read-only (frozen under
`PLATSIM_AI_FREEZE=1`). Throws as `damageInput` does (non-singles, unknown move).

## `ai.preVariance(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul }, fixedDamage)`

Returns `{ damage, moveStatusMask }`, the trainer AI's damage before the variance step (TrainerAI_CalcDamage,
TAI:3081-3103):

- `fixedDamage === 0`: `damage = calcBaseDamage({ ...input, critMul: 1 })`, then `replayTypeChart(plan, damage)` with
  type checks on;
- otherwise: `replayTypeChart(plan, fixedDamage)` with `ignoreTypeChecks: true` (SYSCTL_IGNORE_TYPE_CHECKS, TAI:3093).

Memoised for the current decision on the plan key plus `fixedDamage`. Shared and read-only. The caller applies the
immune check and the sample's variance (`calcdamage.calcDamage`, TAI:3106-3109), per sample, unchanged.

## `ai.cacheStats` (extended)

`{ builds, hits, decisions, plans, planHits, preVariance, preVarianceHits, checks }`. `plans` / `preVariance` count
builds, `*Hits` cache returns, `checks` the comparisons made under `PLATSIM_AI_CHECK=1`. Diagnostics only; the tests
use deltas (one build per attacker-defender-move per decision regardless of K; hits grow with K).

## `beginDecision()` (unchanged contract, extended effect)

Also drops the plan and pre-variance memos.

## `PLATSIM_AI_CHECK=1` (control mode)

Read once at import time (like `PLATSIM_AI_FREEZE`). When on, every memo hit in `typeChartPlan` and `preVariance`
recomputes the value from the current inputs and compares it with the memoised one (plan: `struggle`, `steps`,
`mask`, `totalMul`; pre-variance: `damage`, `moveStatusMask`); a difference throws
`Error('adapter: CHECK mismatch <kind> <key>: memo=<json> fresh=<json>')`. `cacheStats.checks` counts the
comparisons. Default off: one boolean test per hit. Documented in `sim/ai/INTERFACE.md` next to
`PLATSIM_AI_FREEZE` and `PLATSIM_AI_DEBUG`.

Required runs: the default Node suite runs one Aaron battle per policy (`expectimax2-v2`, `expectimax2-v1`) in a
child process with the variable on and asserts exit 0 and `checks > 0`; a second child corrupts a memo entry and
must fail with the message above (positive control). Before the merge, `PLATSIM_AI_CHECK=1 node sim/bench.mjs
--policy expectimax2-v2` and `-v1` run the full fixed set with digests unchanged, recorded in the validation log.

## Shared mappers

`makeMappers(dex, T)` (exported for tests) builds an unshared mapper set. `createAdapter` uses the module-level
`mappersFor(dex, T)`: one set per `dex` (a `WeakMap`), replaced if `T` differs. The five functions `move(id)`,
`ability(id)`, `item(id)`, `species(sp)`, `type(name)` return the same numbers and throw the same messages as
before (`adapter: no decomp move for Showdown move <id>`, etc.). Two adapters created on the same dex and tables
share one set (`ai.mappers === other.mappers`, exposed read-only for the test).

## Call-site changes (`sim/ai/calcdamage.mjs`)

- `calcDamage(env, ...)`: after the move switch, `const r = env.ai.preVariance(attacker, defender, move, { power:
  power & 0xffff, type: typeName(type), powerMul: 10 }, damage)`, then the immune check and the variance step as
  today. `portInput` is no longer called from `calcDamage`.
- `applyTypeChart(env, { move, type, attacker, defender, damage })`: `replayTypeChart(env.ai.typeChartPlan(attacker,
  defender, move, { power: 0, type: typeName(type), powerMul: 10 }), damage)`, returning `{ damage, moveStatusMask }`
  as today.
- Battler ids are resolved to Pokemon objects through `ai.pokemon(b)` as `portInput` does; the empty-battler error
  message is kept.
