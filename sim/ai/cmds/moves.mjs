// Trainer-AI opcode handlers: moves group (see ../OPCODES.md column "File" and ../INTERFACE.md).
// Each handler: (ctx, ins) => void. Each is a line-by-line port of the AICmd_* function in
// pokeplatinum/src/battle/trainer_ai/trainer_ai.c (TAI below); the line cited is the handler's
// `static void AICmd_...` line.
//
// Every handler starts with AIScript_Iter(battleCtx, 1) and reads its arguments in order; the
// interpreter (interp.mjs) has already done the equivalent (ins.args, ctx.next = ins.index + 1).
//
// Integer widths (include/battle/ai_context.h, include/battle/battle_mon.h):
//   AI_CONTEXT.move u16 (ai_context.h:12), moveSlot u8 (:11), calcTemp int (:16),
//   battlerMoves u16[MAX_BATTLERS][4] (:27); BattleMon moves u16[4], ppCur u8[4];
//   battleCtx->movePrevByBattler u16 (battle_context.h:275); battle_mon.h:64, :99. Script arguments are `int`
//   (AIScript_Read, TAI:2726-2732).
//
// AI memory vs. truth (OPCODES.md trap 5): IfMoveKnown / IfMoveNotKnown / IfMoveEffectKnown /
// IfMoveEffectNotKnown read the real moveset for AI_BATTLER_ATTACKER and AI_CONTEXT.battlerMoves
// (ctx.mem.battlerMoves) for AI_BATTLER_DEFENDER.

const LEARNED_MOVES_MAX = 4; // include/constants/moves.h:8
const MOVE_NONE = 0; // generated/moves.txt:1

const u8 = (x) => x & 0xff;
const u16 = (x) => x & 0xffff;
const int = (x) => x | 0;

// AIScript_Battler (TAI:2765-2782), full port including the partner cases (ctx.battler only maps
// ATTACKER vs everything else). The parameter is `u8 inBattler`, so the script int is truncated.
// The return type is u8.
function aiScriptBattler(ctx, inBattler) {
  const K = (n) => ctx.ai.constants.get(n);
  switch (u8(inBattler)) {
    case K('AI_BATTLER_ATTACKER'): return u8(ctx.ai.attacker);
    case K('AI_BATTLER_DEFENDER'): return u8(ctx.ai.defender);
    case K('AI_BATTLER_ATTACKER_PARTNER'): return u8(ctx.ai.attacker ^ 2);
    case K('AI_BATTLER_DEFENDER_PARTNER'): return u8(ctx.ai.defender ^ 2);
    default: return u8(ctx.ai.defender);
  }
}

// MOVE_DATA(move) (battle/common.h:25) = aiContext.moveTable[move]; moveTable is indexed by the
// u16 move id in every caller below except LoadPowerOfLoadedMove / LoadEffectOfLoadedMove, which
// index by calcTemp (int). adapter.moveData throws on an id with no row instead of reading
// out-of-bounds memory.
const moveData = (ctx, move) => ctx.ai.moveData(move);

// Battler_CountMoves (pokeplatinum/src/battle/battle_lib.c:3461-3471): index of the first
// MOVE_NONE slot, i.e. the number of leading known moves.
function battlerCountMoves(ctx, battler) {
  const moves = ctx.ai.moves(battler);
  let i;
  for (i = 0; i < LEARNED_MOVES_MAX; i++) {
    if (moves[i] === MOVE_NONE) break;
  }
  return i;
}

// The `switch (inBattler)` in IfMoveKnown / IfMoveNotKnown switches on the int read from the
// script, not on the resolved battler.
function moveKnownIndex(ctx, ins) {
  const K = (n) => ctx.ai.constants.get(n);
  const inBattler = int(ctx.arg(ins, 'battler'));
  const move = int(ctx.arg(ins, 'move'));
  const battler = aiScriptBattler(ctx, inBattler);
  let i;
  switch (inBattler) {
    case K('AI_BATTLER_ATTACKER'): {
      const moves = ctx.ai.moves(battler);
      for (i = 0; i < LEARNED_MOVES_MAX; i++) if (u16(moves[i]) === move) break;
      return i;
    }
    case K('AI_BATTLER_ATTACKER_PARTNER'): {
      if (ctx.ai.curHP(battler) === 0) return null; // `break` without jumping either way
      const moves = ctx.ai.moves(battler);
      for (i = 0; i < LEARNED_MOVES_MAX; i++) if (u16(moves[i]) === move) break;
      return i;
    }
    case K('AI_BATTLER_DEFENDER'): {
      const known = ctx.mem.battlerMoves[battler];
      for (i = 0; i < LEARNED_MOVES_MAX; i++) if (u16(known[i]) === move) break;
      return i;
    }
    default:
      return null; // no jump
  }
}

// IfMoveEffectKnown / IfMoveEffectNotKnown: the switch has only ATTACKER and DEFENDER cases.
function moveEffectKnownIndex(ctx, ins) {
  const K = (n) => ctx.ai.constants.get(n);
  const inBattler = int(ctx.arg(ins, 'battler'));
  const effect = int(ctx.arg(ins, 'battle_effect'));
  const battler = aiScriptBattler(ctx, inBattler);
  let moves;
  switch (inBattler) {
    case K('AI_BATTLER_ATTACKER'): moves = ctx.ai.moves(battler); break;
    case K('AI_BATTLER_DEFENDER'): moves = ctx.mem.battlerMoves[battler]; break;
    default: return null; // no jump
  }
  let i;
  for (i = 0; i < LEARNED_MOVES_MAX; i++) {
    const m = u16(moves[i]);
    if (m && moveData(ctx, m).effect === effect) break;
  }
  return i;
}

export const handlers = {
  // AICmd_IfMoveEqualTo, TAI:834-844: if (AI_CONTEXT.move == val) jump.
  IfMoveEqualTo(ctx, ins) {
    const val = int(ctx.arg(ins, 'move'));
    if (u16(ctx.mem.move) === val) ctx.jump(ins);
  },

  // AICmd_IfAttackerHasNoDamagingMoves, TAI:913-929: jump if no attacker move is
  // (move != MOVE_NONE && MOVE_DATA(move).power != 0). Real moveset (battleMons[attacker].moves).
  IfAttackerHasNoDamagingMoves(ctx, ins) {
    const moves = ctx.ai.moves(ctx.ai.attacker);
    let i;
    for (i = 0; i < LEARNED_MOVES_MAX; i++) {
      if (moves[i] !== MOVE_NONE && moveData(ctx, moves[i]).power) break;
    }
    if (i === LEARNED_MOVES_MAX) ctx.jump(ins);
  },

  // AICmd_LoadBattlerPreviousMove, TAI:1068-1076: calcTemp = battleCtx->movePrevByBattler[battler]
  // (real battle state, not AI memory; OPCODES.md trap 6).
  LoadBattlerPreviousMove(ctx, ins) {
    const battler = aiScriptBattler(ctx, ctx.arg(ins, 'battler'));
    ctx.mem.calcTemp = int(u16(ctx.ai.movePrevByBattler(battler)));
  },

  // AICmd_LoadCurrentMoveEffect, TAI:1164-1168: calcTemp = MOVE_DATA(AI_CONTEXT.move).effect.
  LoadCurrentMoveEffect(ctx, ins) {
    ctx.mem.calcTemp = int(moveData(ctx, u16(ctx.mem.move)).effect);
  },

  // AICmd_IfCurrentMoveEffectEqualTo, TAI:1441-1451: if (MOVE_DATA(move).effect == expected) jump.
  IfCurrentMoveEffectEqualTo(ctx, ins) {
    const expected = int(ctx.arg(ins, 'battle_effect'));
    if (moveData(ctx, u16(ctx.mem.move)).effect === expected) ctx.jump(ins);
  },

  // AICmd_IfMoveKnown, TAI:1627-1681: ATTACKER: real moves; ATTACKER_PARTNER: real moves unless
  // curHP == 0; DEFENDER: AI_CONTEXT.battlerMoves[battler]; anything else: no jump.
  // Jump if found (i < LEARNED_MOVES_MAX).
  IfMoveKnown(ctx, ins) {
    const i = moveKnownIndex(ctx, ins);
    if (i !== null && i < LEARNED_MOVES_MAX) ctx.jump(ins);
  },

  // AICmd_IfMoveNotKnown, TAI:1683-1737: same split; jump if not found (i == LEARNED_MOVES_MAX).
  IfMoveNotKnown(ctx, ins) {
    const i = moveKnownIndex(ctx, ins);
    if (i !== null && i === LEARNED_MOVES_MAX) ctx.jump(ins);
  },

  // AICmd_IfMoveEffectKnown, TAI:1739-1779: any nonzero move whose MOVE_DATA.effect == effect;
  // ATTACKER real moves, DEFENDER AI memory, other values: no jump.
  IfMoveEffectKnown(ctx, ins) {
    const i = moveEffectKnownIndex(ctx, ins);
    if (i !== null && i < LEARNED_MOVES_MAX) ctx.jump(ins);
  },

  // AICmd_IfMoveEffectNotKnown, TAI:1781-1821: negation (i == LEARNED_MOVES_MAX), same split.
  IfMoveEffectNotKnown(ctx, ins) {
    const i = moveEffectKnownIndex(ctx, ins);
    if (i !== null && i === LEARNED_MOVES_MAX) ctx.jump(ins);
  },

  // AICmd_LoadPowerOfLoadedMove, TAI:2526-2530: calcTemp = MOVE_DATA(calcTemp).power.
  LoadPowerOfLoadedMove(ctx, ins) {
    ctx.mem.calcTemp = int(moveData(ctx, int(ctx.mem.calcTemp)).power);
  },

  // AICmd_LoadEffectOfLoadedMove, TAI:2532-2536: calcTemp = MOVE_DATA(calcTemp).effect.
  LoadEffectOfLoadedMove(ctx, ins) {
    ctx.mem.calcTemp = int(moveData(ctx, int(ctx.mem.calcTemp)).effect);
  },

  // AICmd_LoadCurrentMovePP, TAI:2024-2028:
  // calcTemp = battleMons[AI_CONTEXT.attacker].ppCur[AI_CONTEXT.moveSlot] (u8).
  LoadCurrentMovePP(ctx, ins) {
    ctx.mem.calcTemp = int(u8(ctx.ai.ppCur(ctx.ai.attacker, u8(ctx.mem.moveSlot))));
  },

  // AICmd_IfCanUseLastResort, TAI:2030-2042: jump if
  // lastResortCount >= Battler_CountMoves(battler) - 1 && Battler_CountMoves(battler) > 1.
  IfCanUseLastResort(ctx, ins) {
    const battler = aiScriptBattler(ctx, ctx.arg(ins, 'battler'));
    const numKnownMoves = battlerCountMoves(ctx, battler);
    if (ctx.ai.moveEffectsData(battler).lastResortCount >= numKnownMoves - 1 && numKnownMoves > 1) {
      ctx.jump(ins);
    }
  },

  // AICmd_LoadDefenderLastUsedMoveClass, TAI:2050-2054:
  // calcTemp = MOVE_DATA(movePrevByBattler[AI_CONTEXT.defender]).class (MOVE_NONE's row if none).
  LoadDefenderLastUsedMoveClass(ctx, ins) {
    ctx.mem.calcTemp = int(moveData(ctx, u16(ctx.ai.movePrevByBattler(ctx.ai.defender))).class);
  },
};
