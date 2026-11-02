# Contract: trainer-AI interpreter and parser additions (`sim/ai/parse.mjs`, `sim/ai/interp.mjs`, `sim/ai/choose.mjs`)

Existing exports keep their names, signatures and results except where stated. The script is the decomp's and is
never edited.

## `parseAiScript(...)` (unchanged signature; output extended)

After today's passes, `indexInstructions(prog)` runs and sets on every instruction `ins.a` (argument name ->
value, null-prototype object; the same `value` as the matching `args[]` entry, for every argument kind) and
`ins.jt` (argument name -> `targetInstr`, for `jump` arguments). On the first instruction of every maximal run of
two or more consecutive `IfCurrentMoveEffectEqualTo` instructions, after splitting runs at every entry point (jump
targets, label instructions, the instruction after every `PushAndGoTo`), it sets `ins.dispatch = { table, after,
length }` (data-model.md). `args[]`, `labels`, `image`, `wordToInstr`, `flagTable` are unchanged.

`effectRuns(prog)` (exported for tests) returns `[{ start, end, head: ins, split: boolean }]` for every run found,
before and after splitting.

## `runSection(ctx, start, { maxSteps = 200000, onStep } = {})`

The one interpreter loop (the tracing copy in `choose.mjs` is removed). Per iteration: read `ins`; if
`ins.dispatch`, set `ctx.next = ins.dispatch.table.get(ctx.ai.moveData(ctx.mem.move & 0xffff).effect) ??
ins.dispatch.after` and count a dispatch; else look up the handler (unknown -> `AIUnimplemented`, as today), set
`ctx.next = ins.index + 1`, call it. Then, when `onStep` is given, call `onStep(ins, before, after)` with the
current move slot's score before and after the step (what `runSectionTraced` passed). Then `ctx.pc = ctx.next`.
`INTERP_STATS.steps` grows by 1 per iteration, `dispatches` by 1 per dispatch step. `maxSteps` counts iterations
(a dispatch is one). The termination error message is unchanged.

Semantics of a dispatch step: identical to executing the run's instructions one by one from the head (first
matching entry jumps; no match falls through to `after`). A missing move-table row throws from `ai.moveData` as
the handler does today.

## `makeCtx({ prog, ai, mem, rand, extra })` (unchanged signature)

- `ctx.arg(ins, name)`: returns `ins.a[name]`; throws `` `${ins.name} (script.s:${ins.line}) has no argument ${name}` ``
  when the name is absent (today's message).
- `ctx.target(ins, name = 'jump')`: returns `ins.jt[name]`; throws `` `${ins.name} (script.s:${ins.line}) has no jump target ${name}` ``
  when absent (today's message).
- `ctx.jump`, `ctx.end`, `ctx.battler`: unchanged.

## `INTERP_STATS`

`{ steps, dispatches }`, exported from `interp.mjs`, diagnostics, never reset by the module. Tests and
`bench.mjs` read deltas.

## Traces (`choose.mjs`)

`trainerAIMain(st, battler, { trace })`: the default trace (every `AddToMoveScore`: `{ flagBit, slot, line, add,
before, after }`) is unchanged. The full trace (`trace: 'full'`) records one entry per executed step: for a
dispatch step `{ flagBit, slot, line: <head's line>, op: 'IfCurrentMoveEffectEqualTo', jumped: <true iff a match> }`.

## Unchanged

Handler files under `cmds/` (they still call `ctx.arg` / `ctx.target` / `ctx.jump`), `HANDLERS`, `AIUnimplemented`,
`successors`, `reachableFrom`, `aiProgram()` (returns the indexed program), `OPCODES.md` counts (the run's
instructions are still instructions).
