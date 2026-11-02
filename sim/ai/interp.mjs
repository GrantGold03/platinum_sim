// Trainer-AI bytecode interpreter core (shared by T040–T047).
// Runs instructions parsed by parse.mjs from pokeplatinum/src/battle/trainer_ai/script.s.
// Opcode handlers live in cmds/{flow,battler,moves,damage,misc}.mjs; each exports
// `handlers = { <MacroName>: (ctx, ins) => void }`. See INTERFACE.md for the contract.
import { handlers as flow } from './cmds/flow.mjs';
import { handlers as battler } from './cmds/battler.mjs';
import { handlers as moves } from './cmds/moves.mjs';
import { handlers as damage } from './cmds/damage.mjs';
import { handlers as misc } from './cmds/misc.mjs';

export class AIUnimplemented extends Error {
  constructor(name, line) {
    super(`ai_unimplemented: ${name} (script.s:${line})`);
    this.kind = 'ai_unimplemented';
    this.opcode = name;
    this.line = line;
  }
}

function mergeHandlers(groups) {
  const out = Object.create(null);
  for (const [group, table] of Object.entries(groups)) {
    for (const [name, fn] of Object.entries(table)) {
      if (out[name]) throw new Error(`AI opcode ${name} implemented in two command files (${group})`);
      out[name] = fn;
    }
  }
  return out;
}

export const HANDLERS = mergeHandlers({ flow, battler, moves, damage, misc });

// Feature 017 (specs/017-exact-dispatch-speedups/contracts/interp-api.md): process-wide counters, one integer
// increment per interpreter step; `dispatches` counts fused effect-check runs answered in one step. Diagnostics
// only, never reset by the module; sim/bench.mjs reports the deltas (`interp_steps`, `interp_dispatches`).
export const INTERP_STATS = { steps: 0, dispatches: 0 };

// Runs one flag section for the current ctx.mem.moveSlot, starting at instruction index `start`,
// until a handler calls ctx.end(). Mirrors the per-move loop body of TrainerAI_EvalMoves
// (pokeplatinum/src/battle/trainer_ai/trainer_ai.c:483). This is the only interpreter loop (017): `onStep(ins,
// before, after)`, when given, is called after every step with the current move slot's score before and after it
// (the trace hook choose.mjs evalMoves uses). A run of consecutive IfCurrentMoveEffectEqualTo checks whose head
// carries `ins.dispatch` (parse.mjs indexInstructions) is answered in one step: the first entry equal to the current
// move's effect (MOVE_DATA(AI_CONTEXT.move).effect, TAI:1441-1451) is the destination, otherwise the instruction after
// the run; identical to stepping through the checks, which read nothing else and change nothing. A dispatch counts as
// one step for `maxSteps` and INTERP_STATS.
export function runSection(ctx, start, { maxSteps = 200000, onStep } = {}) {
  ctx.pc = start;
  ctx.done = false;
  const instructions = ctx.prog.instructions;
  for (let steps = 0; !ctx.done; steps++) {
    if (steps >= maxSteps) throw new Error(`AI section did not terminate after ${maxSteps} steps (started at instruction ${start})`);
    INTERP_STATS.steps++;
    const ins = instructions[ctx.pc];
    if (!ins) throw new Error(`AI pc ${ctx.pc} out of range`);
    const before = onStep ? ctx.mem.moveScore[ctx.mem.moveSlot] : 0;
    const d = ins.dispatch;
    if (d) {
      const target = d.table.get(ctx.ai.moveData(ctx.mem.move & 0xffff).effect);
      ctx.next = target !== undefined ? target : d.after;
      INTERP_STATS.dispatches++;
    } else {
      const fn = HANDLERS[ins.name];
      if (!fn) throw new AIUnimplemented(ins.name, ins.line);
      ctx.next = ins.index + 1;
      fn(ctx, ins);
    }
    if (onStep) onStep(ins, before, ctx.mem.moveScore[ctx.mem.moveSlot]);
    ctx.pc = ctx.next;
  }
}

// Helpers handlers use; created once per decision by the caller (T045).
export function makeCtx({ prog, ai, mem, rand, extra = {} }) {
  const ctx = {
    prog, ai, mem, rand,
    pc: 0, next: 0, done: false,
    // Value of a named argument (labels resolve to their instruction index via `target`). 017: read from the
    // parse-time index (ins.a / ins.jt, parse.mjs indexInstructions) instead of scanning ins.args; same errors.
    arg: (ins, name) => {
      if (!(name in ins.a)) throw new Error(`${ins.name} (script.s:${ins.line}) has no argument ${name}`);
      return ins.a[name];
    },
    target: (ins, name = 'jump') => {
      const t = ins.jt[name];
      if (t === undefined) throw new Error(`${ins.name} (script.s:${ins.line}) has no jump target ${name}`);
      return t;
    },
    jump: (ins, name = 'jump') => { ctx.next = ctx.target(ins, name); },
    end: () => { ctx.done = true; },
    // AIScript_Battler (trainer_ai.c:2765): ATTACKER -> AI_CONTEXT.attacker, anything else -> defender.
    battler: (value) => (value === ai.constants.get('AI_BATTLER_ATTACKER') ? ai.attacker : ai.defender),
    ...extra,
  };
  return ctx;
}
