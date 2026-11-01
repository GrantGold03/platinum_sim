# Data Model: Exact Damage-Path Speedups (round two)

All structures are in-memory and transient except the counters. Nothing is persisted; the feature-015 replay
fixture is read-only here.

## Type-chart plan (`sim/damage.mjs`)

```text
Plan {
  struggle: boolean          // MOVE_STRUGGLE: replay returns the input damage, mask unchanged
  steps: Step[]              // in game order
  mask: number               // final MOVE_STATUS bits (given the incoming moveStatusMask seed)
  totalMul: number           // product of 2 per super-effective row (as today)
}
Step = { op: 'stab15' }                     // damage = idiv(damage * 15, 10)
     | { op: 'x2' }                         // damage = s32(damage * 2)   (Adaptability STAB, Tinted Lens)
     | { op: 'mul', mul: number }           // if (damage) damage = battleDivide(damage * mul, 10)
     | { op: 'div34' }                      // damage = battleDivide(damage * 3, 4)  (Filter / Solid Rock)
     | { op: 'pct', pct: number }           // damage = idiv(damage * pct, 100)      (Expert Belt, pct = 100 + param)
```

Identity: a pure function of `(attacker, defender, move, field, ignoreTypeChecks, moveStatusMask)`. Validation:
`replayTypeChart(plan, d)` equals `applyTypeChartDirect(input, d, opts)` for every `d` (FR-004).

## Pre-variance entry (`sim/ai/adapter.mjs`)

```text
PreVariance { damage: number, moveStatusMask: number }   // TAI:3081-3103 result before the variance step
```

Key within one decision: `attacker struct -> defender struct -> "${moveNum}|${power}|${type}|${ignore}|${fixedDamage}"`.
`ignore` is `fixedDamage !== 0` for `preVariance`; for `typeChartPlan` it is the caller's `ignoreTypeChecks` and
`fixedDamage` is absent. Lifecycle: created on first use in a decision, shared by every sample, dropped by
`beginDecision()`. Frozen under `PLATSIM_AI_FREEZE=1`. Under `PLATSIM_AI_CHECK=1` every hit is recomputed and
compared; a difference throws.

## Decision cache (feature 015, extended)

```text
DecisionCache {
  battlers: Map<ShowdownPokemon, BattlerStruct>      // 015
  fields:   Map<ShowdownSide, FieldStruct>           // 015
  plans:    Map<BattlerStruct, Map<BattlerStruct, Map<string, Plan>>>          // 016
  pre:      Map<BattlerStruct, Map<BattlerStruct, Map<string, PreVariance>>>   // 016
}
cacheStats { builds, hits, decisions,                 // 015
             plans, planHits, preVariance, preVarianceHits, checks }   // 016 (checks counts CHECK-mode comparisons)
```

## Shared mappers (`sim/ai/adapter.mjs`, module level)

```text
MapperSet {
  T: DecompTables                       // identity check: a different T for the same dex replaces the set
  move: Map<string, number>             // Showdown move id -> decomp move number
  ability: Map<string, number>
  item: Map<string, number>
  species: Map<string, number>          // Showdown species id -> decomp species number
  type: Map<string, number>             // 'Fire' -> TYPE_FIRE value; '???' -> TYPE_MYSTERY
  api: { move(id), ability(id), item(id), species(sp), type(name) }   // the five functions adapters use
}
MAPPERS: WeakMap<Dex, MapperSet>
```

Identity: a pure function of `(dex, T)`. Validation: equals a freshly built, unshared set over every engine
identifier the decomp knows; unknown identifiers throw the same message (FR-008).

## Counters (`sim/damage.mjs`)

```text
DAMAGE_STATS { plans: number, replays: number, direct: number }
```

Diagnostics only (like the policy's `STATS`); the US1 scenario-4 test reads them around one `calcDamage` call:
`plans` +1, `replays` +16, `direct` +0.

## Relationships

- `Plan` is built from a `damageInput` struct set (015) and consumed by `calcDamage` (policy path, not cached)
  and by `ai.typeChartPlan` / `ai.preVariance` (AI path, cached per decision).
- `PreVariance` depends on `Plan` (same key minus `fixedDamage`) and on `calcBaseDamage` of the same input.
- `MapperSet` is independent of battles and decisions; adapters hold a reference to the shared `api`.
- The replay fixture (015) is unchanged and validates every change above end to end.
