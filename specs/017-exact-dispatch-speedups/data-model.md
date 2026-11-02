# Data Model: Exact Dispatch, Damage-Input and Speed Speedups (round three)

All structures are in-memory and transient except the counters. Nothing is persisted; the feature-015 replay
fixture is read-only here.

## Instruction fields (`sim/ai/parse.mjs`, set by the post-pass on every instruction)

```text
Instruction {                       // as today: index, op, name, args[], line, word, size
  a: { [argName]: number }          // NEW: argument value by name (null-prototype object); same `value` as args[]
  jt: { [argName]: number }         // NEW: jump target instruction index by name, for `jump` arguments only
  dispatch?: DispatchTable          // NEW: only on the first instruction of a fused effect-check run
}
DispatchTable {
  table: Map<number, number>        // int(battle_effect) -> jump targetInstr; first entry wins (never overwritten)
  after: number                     // index of the instruction following the run (the fall-through)
  length: number                    // instructions covered (>= 2); diagnostics and the structure test
}
```

Identity: a pure function of the parsed program. Validation: for every run head and every effect value, `table.get(e)
?? after` equals the destination of stepping through the covered instructions (FR-004). Entry points (every jump
target, every label, every `PushAndGoTo` return point) never fall strictly inside a run: the post-pass splits runs
there. `args[]` is unchanged.

## Interpreter counters (`sim/ai/interp.mjs`)

```text
INTERP_STATS { steps: number, dispatches: number }   // loop iterations; dispatch steps (each also counts as a step)
```

Diagnostics only, never reset by the module; `node sim/bench.mjs` reports deltas as `interp_steps`,
`interp_dispatches`. Expected on the fixed set: steps < 20 M (143 M today), dispatches about 0.8 M (one per run
entry, about 6 per AI call per section).

## Decision cache (feature 015/016, extended)

```text
DecisionCache {
  battlers: Map<ShowdownPokemon, BattlerStruct>      // 015; hits now CHECK-compared
  fields:   Map<ShowdownSide, FieldStruct>           // 015; hits now CHECK-compared
  plans, pre                                         // 016
  speedPair: SpeedPair | undefined                   // 017: one per adapter per decision
}
cacheStats { builds, hits, decisions, plans, planHits, preVariance, preVarianceHits, checks,   // 015/016
             fieldBuilds, structChecks, speedPairs, speedPairHits }                            // 017
```

`fieldBuilds` counts `fieldFor` builds (at most one per side per decision); `structChecks` the battler/field
comparisons made under `PLATSIM_AI_CHECK=1` (also added to `CHECK_STATS.checks`); `speedPairs` / `speedPairHits`
the pair builds and hits. `beginDecision()` clears `speedPair` with the rest.

## Speed pair (`sim/ai/cmds/battler.mjs`, stored in the decision cache)

```text
SpeedPair {
  b: [BattlerSpeed, BattlerSpeed]   // index = battler id (singles: 0 player, 1 AI)
}
BattlerSpeed { speed: number (u32), ability: number, quickClaw: 0|1, laggingTail: 0|1 }   // battlerSpeed() result, as today
```

Built only when both actives have hp > 0 (the early returns come first and build nothing). Identity: a pure
function of the adapter's battle state and `ai.speedRand(0..1)`. Frozen under `PLATSIM_AI_FREEZE=1`; recomputed
and compared on every hit under `PLATSIM_AI_CHECK=1`. Validation: `compareBattlerSpeed` with the pair equals
`compareBattlerSpeedDirect` in result, `mem.monSpeedValues` and RNG draws for every caller shape (FR-008).

## Policy damage inputs (`sim/policy/expectimax2.mjs`, `damageTable`)

```text
di   = X.rootView.ai.damageInput(u.ref, t.ref, moveNum, { power, type, powerMul: 10 })   // shared, read-only (015)
base = { attacker: { ...di.attacker }, defender: { ...di.defender }, move: di.move, field: { ...di.field }, crit: false }
```

`fix(base.attacker, u, sInfo)` / `fix(base.defender, t, tInfo)` and the field overrides write only into `base`'s
own objects (`stages` and, for a fresh switch-in, `types` are replaced by new objects; the other writes are scalar
fields of the copies). The damage-table entry `{ fixed } | { rolls, crolls, critP }` and its key are unchanged.

## Policy counters (`sim/policy/expectimax2.mjs`)

```text
STATS { decisions, aiCalls, turns, leaves, ms, aiMs, viewMs, aiDraws,   // today
        speedInfo }                                                      // 017: speedInfo(X, S) calls
```

Expected per decision: `speedInfo` <= ply-2 nodes + root actions + mid-turn Gyro Ball evaluations (today about
247 k per run; after, about 55 k).

## Bench report additions (`sim/bench.mjs`, `platsim bench`)

```text
interp_steps: number        // INTERP_STATS.steps delta over the run
interp_dispatches: number   // INTERP_STATS.dispatches delta
```

## Relationships

- `DispatchTable` is consumed only by `runSection`; `ins.a` / `ins.jt` by `makeCtx`'s `arg` / `target`.
- `SpeedPair` is built by `compareBattlerSpeed` on first use per adapter per decision and read by its three
  callers (`speedValuesNow`, the policy's `speedInfo`, `IfSpeedCompareEqualTo`).
- The policy's `damageTable` reads the 015 `battlers` / `fields` caches through `damageInput` and never writes to
  them; `fix()` writes to the copies.
- The replay fixture (015) is unchanged and validates every change above end to end.
