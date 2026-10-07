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

// Runs one flag section for the current ctx.mem.moveSlot, starting at instruction index `start`,
// until a handler calls ctx.end(). Mirrors the per-move loop body of TrainerAI_EvalMoves
// (pokeplatinum/src/battle/trainer_ai/trainer_ai.c:483).
export function runSection(ctx, start, { maxSteps = 200000 } = {}) {
  ctx.pc = start;
  ctx.done = false;
  for (let steps = 0; !ctx.done; steps++) {
    if (steps >= maxSteps) throw new Error(`AI section did not terminate after ${maxSteps} steps (started at instruction ${start})`);
    const ins = ctx.prog.instructions[ctx.pc];
    if (!ins) throw new Error(`AI pc ${ctx.pc} out of range`);
    const fn = HANDLERS[ins.name];
    if (!fn) throw new AIUnimplemented(ins.name, ins.line);
    ctx.next = ins.index + 1;
    fn(ctx, ins);
    ctx.pc = ctx.next;
  }
}

// Helpers handlers use; created once per decision by the caller (T045).
export function makeCtx({ prog, ai, mem, rand, extra = {} }) {
  const ctx = {
    prog, ai, mem, rand,
    pc: 0, next: 0, done: false,
    // Value of a named argument (labels resolve to their instruction index via `target`).
    arg: (ins, name) => {
      const a = ins.args.find((x) => x.name === name);
      if (!a) throw new Error(`${ins.name} (script.s:${ins.line}) has no argument ${name}`);
      return a.value;
    },
    target: (ins, name = 'jump') => {
      const a = ins.args.find((x) => x.name === name);
      if (!a || a.targetInstr === undefined) throw new Error(`${ins.name} (script.s:${ins.line}) has no jump target ${name}`);
      return a.targetInstr;
    },
    jump: (ins, name = 'jump') => { ctx.next = ctx.target(ins, name); },
    end: () => { ctx.done = true; },
    // AIScript_Battler (trainer_ai.c:2765): ATTACKER -> AI_CONTEXT.attacker, anything else -> defender.
    battler: (value) => (value === ai.constants.get('AI_BATTLER_ATTACKER') ? ai.attacker : ai.defender),
    ...extra,
  };
  return ctx;
}
