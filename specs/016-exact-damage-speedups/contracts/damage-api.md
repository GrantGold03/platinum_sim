# Contract: damage port additions (`sim/damage.mjs`)

Existing exports keep their names, signatures and results. Four additions and one internal change.

## `typeChartPlan(input, { ignoreTypeChecks = false, moveStatusMask = 0 } = {})`

`input` = `{ attacker, defender, move, field }` in the port's shape (the same object `applyTypeChart` takes).
Returns a `Plan` (data-model.md): `{ struggle, steps, mask, totalMul }`. Pure; reads the same fields
`applyTypeChart` reads today; never reads a damage value. Throws exactly where `prepare()` throws today (unknown
move or item data).

## `replayTypeChart(plan, damage)`

Returns `{ damage, moveStatusMask, totalMul }`: `damage` after applying `plan.steps` in order with the game's
integer helpers (`idiv`, `s32`, `battleDivide`), the `mul` steps skipped when the running damage is 0;
`moveStatusMask = plan.mask`; `totalMul = plan.totalMul`. For `plan.struggle` returns the input damage and the seed
mask. Pure; allocates one result object.

## `applyTypeChart(input, damage, opts)` (unchanged signature)

Equivalent to `replayTypeChart(typeChartPlan(input, opts), damage)`. Result deep-equal to
`applyTypeChartDirect(input, damage, opts)` for every input (FR-004; tested over >= 10,000 synthetic and >= 1,000
real-data matchups x 16 rolls, with a positive control).

## `applyTypeChartDirect(input, damage, opts)`

The per-roll implementation as of `main` 19519ed, kept verbatim and exported as the reference (Constitution
Principle VI). Not called by product code; the equivalence test and the Showdown cross-check may call it.

## `calcDamage(input)` (unchanged signature and result)

Builds `prepare()` once and the plan once per call and replays it for the 16 rolls. `DAMAGE_STATS.plans` grows by
1 and `DAMAGE_STATS.replays` by 16 per call. Result deep-equal to the current implementation (replay fixture,
equivalence subset, `damage.test.mjs` Showdown cross-check).

## `DAMAGE_STATS`

`{ plans, replays, direct }`, diagnostics, never reset by the module. Tests read deltas.

## Unchanged

`calcBaseDamage`, `applyScriptMultipliers`, `applyVariance`, `critMultiplier`, `critChance`, `critBlocked`,
`battlerFromShowdown`, `fromShowdown`, `moveData`, `itemData`, `TYPE_CHART`, `MOVE_STATUS`, `ENUMS`, `battleDivide`:
same exports, same results. Internally the first three accept a precomputed `prepare()` result through private
helpers so `calcDamage` prepares once; the exported entry points still prepare for themselves.
