# Trainer-AI handler interface (T040–T047)

The core loop is `interp.mjs` (`runSection`, `makeCtx`). Opcode handlers live in
`cmds/{flow,battler,moves,damage,misc}.mjs`. The group for each opcode is the "File" column of
`OPCODES.md`. Each command file exports:

```js
export const handlers = { IfRandomLessThan(ctx, ins) { ... }, ... };
```

- **Signature**: `(ctx, ins) => void`. `ins` is a parsed instruction from `parse.mjs`:
  `{index, op, name, args:[{name, kind, value, label?, targetInstr?}], line, word, size}`.
- **Duplicates**: an opcode implemented in two files throws at import (`mergeHandlers`).
- **Unknown opcodes**: an opcode with no handler throws `AIUnimplemented` (`kind: 'ai_unimplemented'`, with
  the name and script line). It is never skipped silently.
- **Citations**: every handler has a comment citing its `trainer_ai.c` handler line, and each branch must match
  the C exactly. Integer widths matter (s8 move score, u8/u16/u32 truncation).

## ctx

| Member | Meaning |
|---|---|
| `ctx.prog` | parsed program: `instructions`, `labels`, `image` (32-bit words, as the game reads them), `wordToInstr`, `constants` |
| `ctx.ai` | adapter from `adapter.mjs` (read-only battle queries in the game's encodings). `ctx.ai.constants.get(NAME)` resolves decomp constants. |
| `ctx.mem` | AI_CONTEXT memory, owned by the caller (T045), mutable by handlers. Fields: `move`, `moveSlot`, `moveScore[4]` (s8 semantics), `moveDamageRolls[4]`, `calcTemp`, `battlerMoves[4][4]`, `battlerAbilities[4]`, `battlerHeldItems[4]`, `stack` (call/return), plus anything else a handler needs. Name each field after the `AIContext` member in `include/battle/ai_context.h`. |
| `ctx.rand()` | `BattleSystem_RandNext` semantics: returns a **u16** (`battle_system.c:1308-1312`). Draws come from the AI's own seeded stream, **not** Showdown's battle PRNG, so that look-ahead can run the AI on hypothetical states without disturbing the real battle. Draw in the same order the C does. |
| `ctx.arg(ins, name)` | the value of an argument |
| `ctx.target(ins, name='jump')` | jump target as an instruction index |
| `ctx.jump(ins, name='jump')` | take a jump: sets `ctx.next` |
| `ctx.next` | the next instruction index, which defaults to `ins.index + 1`. A handler that jumps or returns sets it. |
| `ctx.end()` | stop the current section (`End` / end of script for this move) |
| `ctx.battler(value)` | `AIScript_Battler`: AI_BATTLER_ATTACKER (1) → `ai.attacker`, anything else → `ai.defender` |
| `ctx.damage` | `sim/ai/calcdamage.mjs` (passed in by `choose.mjs` via `makeCtx({extra})`), a wrapper over `sim/damage.mjs` implementing `TrainerAI_CalcDamage` (trap 7 in OPCODES.md) |

Handlers may add helpers to `ctx` only through `makeCtx({extra})` (as `choose.mjs` does); don't mutate `interp.mjs`.

## Tests

- **File**: one file per group, `sim/test/ai_cmds_<group>.test.mjs`, with at least one test per opcode. Use a
  real `gen4customgame` Battle (see `sim/spikes/*.mjs` and `sim/test/ai_adapter.test.mjs`) and a `mem`
  object you build.
- **Running an instruction**: run a single instruction with `HANDLERS[name](ctx, ins)`, using a real `ins`
  taken from `prog.instructions` (find one by name and line) so the argument decoding is the real one.
- **Assertions**: check `ctx.next`, `ctx.mem` and the `ctx.rand` call counts.

## Decision layer (T045-T047)

| File | Ports |
|---|---|
| `choose.mjs` | `TrainerAI_Init` / `EvalMoves` / `MainSingles` / `RecordLastMove`, `BattleSystem_CheckInvalidMoves`, `AIRng` (byte-exact `BattleSystem_RandNext` LCG) |
| `switch.mjs` | `TrainerAI_ShouldSwitch` + helpers, `BattleAI_PostKOSwitchIn` (u8 overflow kept), `BattleSystem_CalcEffectiveness`, `TypeMatchupMultiplier`, `Move_CalcVariableType` |
| `items.mjs` | `InitAI` item compaction, `TrainerAI_ShouldUseItem` (Full Restore only; slot rule; no-break double consumption), `TrainerAI_PickCommand` |
| `patches.mjs` | Dex patches: `trainerfullrestore` runs in `beforeTurnCallback` and cancels its move action; Taunt/Encore exempt it |
| `opponent.mjs` | the `decomp-ai` opponent policy: per-battle state, log -> AI memory / `moveHit` / `speedRand`, Showdown choice strings |

- **RNG**: one `AIRng` per battle, seeded with the first 4 bytes of `sha256(`${battle.prngSeed}|trainer-ai`)`.
  `ctx.rand` in a decision is `st.rng.next()`. Draw order: 4 `speedRand` at battle start, then per decision
  PickCommand draws, Init's 4 rolls, script draws, the tie break; 4 `speedRand` after every turn that had a
  move request (pre-move phase, battle_controller_player.c:853-856).
- **ctx.damage** is `calcdamage.mjs`; `mem.monSpeedValues` is pre-filled per decision by `speedValuesNow()`.
- **Divergence counters**: `AGGREGATE` / `st.stats` (`invalidChoice`, `trappedSwitch`, `lockMismatch`).
