// Trainer-AI opcode handlers: flow group (see ../OPCODES.md column "File" and ../INTERFACE.md).
// Each handler: (ctx, ins) => void. Cite the trainer_ai.c handler line in a comment for each.
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c.
//
// Integer model: AIScript_Read (TAI:2726) returns the script word as `int`; AI_CONTEXT.calcTemp is
// `int` (ai_context.h:16); moveScore is `s8[4]` (ai_context.h:14). Arguments are coerced to int32
// with `| 0` so values parsed above 2^31 compare as the game's int would.

const int = (v) => v | 0;
const calcTemp = (ctx) => int(ctx.mem.calcTemp);
// Conditional jump shared by the IfLoaded*/IfTemp* compare handlers: reads `loaded_val`, then
// AIScript_Iter(jump) when the predicate holds; otherwise the cursor falls through.
const jumpIf = (ctx, ins, cond) => { if (cond) ctx.jump(ins); };

// AICmd_IfLoadedInTable / NotInTable scan: AIScript_ReadOffset(ofs) (TAI:2741) reads
// aiScriptTemp[cursor + ofs] with the cursor two words past the table word (after both reads), i.e.
// at ins.word + 3. The table word holds (table - thisWord - 2) (aicmd.inc:167-177), so the first
// read lands on the table's first word. The loop stops at `val != 0xFFFFFFFF`: int vs unsigned
// literal, so an int word of -1 ends the scan (OPCODES.md trap 12). Returns true if calcTemp matches.
function loadedInTable(ctx, ins) {
  const img = ctx.prog.image;
  const cursor = ins.word + 3;
  let ofs = int(ctx.arg(ins, 'table'));
  const temp = calcTemp(ctx);
  for (;;) {
    const at = cursor + ofs;
    if (at < 0 || at >= img.length) throw new Error(`${ins.name} (script.s:${ins.line}) table scan left the script image at word ${at}`);
    const val = img[at];
    if ((val >>> 0) === 0xFFFFFFFF) return false;
    if (temp === val) return true;
    ofs++;
  }
}

export const handlers = {
  // AICmd_AddToMoveScore, TAI:576-586. `moveScore[slot] += val` stores into an s8, so the sum wraps
  // to 8 bits (trap 1); then `< 0` clamps to 0.
  AddToMoveScore(ctx, ins) {
    const m = ctx.mem;
    const slot = m.moveSlot;
    const val = int(ctx.arg(ins, 'i'));
    m.moveScore[slot] = ((int(m.moveScore[slot]) + val) << 24) >> 24;
    if (m.moveScore[slot] < 0) m.moveScore[slot] = 0;
  },

  // AICmd_IfLoadedLessThan, TAI:762-772: calcTemp < val.
  IfLoadedLessThan(ctx, ins) { jumpIf(ctx, ins, calcTemp(ctx) < int(ctx.arg(ins, 'loaded_val'))); },

  // AICmd_IfLoadedGreaterThan, TAI:774-784: calcTemp > val.
  IfLoadedGreaterThan(ctx, ins) { jumpIf(ctx, ins, calcTemp(ctx) > int(ctx.arg(ins, 'loaded_val'))); },

  // AICmd_IfLoadedEqualTo, TAI:786-796: calcTemp == val.
  IfLoadedEqualTo(ctx, ins) { jumpIf(ctx, ins, calcTemp(ctx) === int(ctx.arg(ins, 'loaded_val'))); },

  // AICmd_IfLoadedNotEqualTo, TAI:798-808: calcTemp != val.
  IfLoadedNotEqualTo(ctx, ins) { jumpIf(ctx, ins, calcTemp(ctx) !== int(ctx.arg(ins, 'loaded_val'))); },

  // AICmd_IfLoadedMask, TAI:810-820: (calcTemp & mask) != 0.
  IfLoadedMask(ctx, ins) { jumpIf(ctx, ins, (calcTemp(ctx) & int(ctx.arg(ins, 'loaded_val'))) !== 0); },

  // AICmd_IfLoadedNotMask, TAI:822-832: (calcTemp & mask) == FALSE.
  IfLoadedNotMask(ctx, ins) { jumpIf(ctx, ins, (calcTemp(ctx) & int(ctx.arg(ins, 'loaded_val'))) === 0); },

  // AICmd_IfLoadedInTable, TAI:858-874: jump on the first table entry equal to calcTemp.
  // Macro name is `IfLoadedinTable` (aicmd.inc:167); parse.mjs keeps the macro's spelling.
  IfLoadedinTable(ctx, ins) { jumpIf(ctx, ins, loadedInTable(ctx, ins)); },

  // AICmd_IfLoadedNotInTable, TAI:876-892: return (fall through) on a match, else jump.
  IfLoadedNotinTable(ctx, ins) { jumpIf(ctx, ins, !loadedInTable(ctx, ins)); },

  // AICmd_IfTempEqualTo, TAI:1078-1088: val == calcTemp.
  IfTempEqualTo(ctx, ins) { jumpIf(ctx, ins, int(ctx.arg(ins, 'loaded_val')) === calcTemp(ctx)); },

  // AICmd_GoTo, TAI:2561-2566: unconditional AIScript_Iter(jump).
  GoTo(ctx, ins) { ctx.jump(ins); },

  // AICmd_PopOrEnd, TAI:2568-2577. AIScript_PopCursor (TAI:2687-2696): if scriptStackSize is
  // nonzero, pop scriptStackPointer[--size] into the cursor; else set AI_STATUS_FLAG_DONE, which
  // TrainerAI_EvalMoves (TAI:507-518) treats as "this move's evaluation is over" -> ctx.end().
  // mem.stack holds return points as instruction indices (the C stores the word cursor that
  // AICmd_PushAndGoTo, TAI:2554, pushed: the word after its jump argument = the next instruction).
  // The C does not check for underflow beyond the size test; overflow (> AI_MAX_STACK_SIZE) is
  // PushAndGoTo's concern.
  PopOrEnd(ctx) {
    const stack = ctx.mem.stack;
    if (stack && stack.length) {
      ctx.next = stack.pop();
      return;
    }
    ctx.end();
  },
};
