// T045: the trainer AI's move choice.
//
// Ports, from pokeplatinum/src/battle/trainer_ai/trainer_ai.c (TAI below, @ c248fb3f):
//   TAI:211-256   TrainerAI_Init            -> trainerAIInit()
//   TAI:258-277   TrainerAI_Main            -> trainerAIMain() (singles branch only)
//   TAI:286-339   TrainerAI_MainSingles     -> trainerAIMain()
//   TAI:483-526   TrainerAI_EvalMoves       -> evalMoves()
//   TAI:2705-2717 TrainerAI_RecordLastMove  -> recordLastMove()
// and from pokeplatinum/src/battle/battle_lib.c (BL below):
//   BL:2255-2318  BattleSystem_CheckInvalidMoves (with BL:3316 Move_Imprisoned,
//                 BL:3383-3404 Move_FailsInHighGravity, BL:3406-3440 Move_HealBlocked)
//   BL:5352-5363, 5438-5442 Battler_HeldItem / Battler_HeldItemEffect
//   pokeplatinum/src/battle/battle_system.c:1308-1312 BattleSystem_RandNext -> AIRng
//
// Integer widths (include/battle/ai_context.h):
//   moveScore s8[4] (:14) — handled by cmds/flow.mjs AddToMoveScore; copied into u8 here (TAI:316)
//   moveDamageRolls u8[4] (:24), calcTemp int (:16), thinkingMask u32 (:17), stateFlags u8 (:19)
//
// RNG (OPCODES.md trap 2). The game draws every AI random number from the battle's one LCG
// (BattleSystem_RandNext). Here the AI owns a separate stream that is a byte-exact port of that LCG
// (seedRandNext = seedRandNext * 1103515245 + 24691, return seedRandNext / 65536 as u16;
// LCRNG_MULTIPLIER / LCRNG_INCREMENT / LCRNG_DIVISOR, include/math_util.h:8-10). Its 32-bit seed is
// derived from the Showdown battle seed:
//     aiSeed = first 4 bytes (big-endian u32) of sha256(`${battle.prngSeed}|trainer-ai`)
// so the same battle seed always gives the same AI decisions, the AI never consumes Showdown's
// battle PRNG (which keeps the battle reproducible and lets look-ahead clone the AI stream with
// AIRng.clone()), and draws happen in the C's call order. This stream is NOT the cartridge's
// stream: the cartridge interleaves AI draws with engine draws, which Showdown does not reproduce.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DECOMP_ROOT } from './constants.mjs';
import { HANDLERS, AIUnimplemented, makeCtx, runSection } from './interp.mjs';
import { parseAiScript } from './parse.mjs';
import * as calcdamage from './calcdamage.mjs';
import { compareBattlerSpeed } from './cmds/battler.mjs';

// ---------------------------------------------------------------------------------------------
// RNG

const LCRNG_MULTIPLIER = 1103515245; // include/math_util.h:8
const LCRNG_INCREMENT = 24691; // include/math_util.h:9
// LCRNG_DIVISOR 65536 (include/math_util.h:10): u32 / 65536 == u32 >>> 16

export class AIRng {
  constructor(seed) {
    this.state = seed >>> 0;
    this.draws = 0;
  }

  // BattleSystem_RandNext (battle_system.c:1308-1312): u32 state, u16 result.
  next() {
    this.state = (Math.imul(this.state, LCRNG_MULTIPLIER) + LCRNG_INCREMENT) >>> 0;
    this.draws++;
    return (this.state >>> 16) & 0xffff;
  }

  clone() {
    const r = new AIRng(this.state);
    r.draws = this.draws;
    return r;
  }
}

export function aiSeedFromBattleSeed(prngSeed) {
  const s = Array.isArray(prngSeed) ? prngSeed.join(',') : String(prngSeed);
  return parseInt(createHash('sha256').update(`${s}|trainer-ai`, 'utf8').digest('hex').slice(0, 8), 16) >>> 0;
}

// ---------------------------------------------------------------------------------------------
// Program (parsed once per process)

let progCache = null;
export function aiProgram() {
  if (!progCache) progCache = parseAiScript();
  return progCache;
}

// AI_FLAG_* names (trainers.json `ai_flags`) -> thinkingMask (bit i = FlagTable entry i,
// parse.mjs resolveFlagTable). TAI:250: thinkingMask = trainers[battler].header.aiMask.
export function thinkingMaskOf(prog, flagNames) {
  let mask = 0;
  for (const f of flagNames) {
    const e = prog.flagTable.find((x) => x.flag === f);
    if (!e) throw new Error(`choose: unknown AI flag ${f}`);
    mask |= 1 << e.bit;
  }
  return mask >>> 0;
}

// ---------------------------------------------------------------------------------------------
// BattleSystem_CheckInvalidMoves (BL:2255-2318)

function parseBattleLibMoveList(name) {
  const lines = readFileSync(join(DECOMP_ROOT, 'src/battle/battle_lib.c'), 'utf8').split('\n');
  const start = lines.findIndex((l) => l.startsWith(`static const u16 ${name}[]`));
  if (start < 0) throw new Error(`choose: ${name} not found in battle_lib.c`);
  const out = [];
  for (let i = start + 1; i < lines.length && !lines[i].startsWith('};'); i++) {
    const m = lines[i].trim().match(/^(MOVE_[A-Z0-9_]+),?$/);
    if (m) out.push(m[1]);
  }
  return { names: out, line: start + 1 };
}
export const MOVES_AFFECTED_BY_GRAVITY = parseBattleLibMoveList('sMovesAffectedByGravity'); // BL:3374
export const MOVES_AFFECTED_BY_HEAL_BLOCK = parseBattleLibMoveList('sMovesAffectedByHealBlock'); // BL:3399

const K = (ai, n) => ai.constants.get(n);

// Battler_HeldItem (BL:5352-5363) -> Battler_HeldItemEffect (BL:5438-5442)
export function battlerHeldItemEffect(ai, b) {
  if (ai.battlerAbility(b) === K(ai, 'ABILITY_KLUTZ')) return ai.itemHoldEffect(0);
  if (ai.moveEffectsData(b).embargoTurns) return ai.itemHoldEffect(0);
  return ai.itemHoldEffect(ai.heldItem(b));
}

// Move_Imprisoned (BL:3316-3339): any battler on the other side with MOVE_EFFECT_IMPRISON knows `move`.
function moveImprisoned(ai, battler, move) {
  let result = false;
  for (let i = 0; i < ai.maxBattlers; i++) {
    if (ai.side(i) !== ai.side(battler) && (ai.moveEffectsMask(i) & K(ai, 'MOVE_EFFECT_IMPRISON'))) {
      if (ai.moves(i).includes(move)) result = true;
    }
  }
  return result;
}

/**
 * BattleSystem_CheckInvalidMoves(battler, invalidMoves, opMask) (BL:2255-2318). Returns the
 * invalid-slot bit mask. Differences, all forced by the read-only adapter:
 *  - the C clears moveEffectsData.choiceLockedMove when the locked move is no longer known
 *    (BL:2306-2307); here that write is only applied locally for this call.
 *  - healBlockTurns (BL:3431) is read as "MOVE_EFFECT_HEAL_BLOCK set": the Showdown 'healblock'
 *    volatile exists exactly while the turn counter is nonzero.
 */
export function checkInvalidMoves(ai, battler, invalidMoves = 0, opMask = ~0) {
  const itemEffect = battlerHeldItemEffect(ai, battler);
  const moves = ai.moves(battler);
  const med = ai.moveEffectsData(battler);
  const prev = ai.movePrevByBattler(battler);
  const tormented = (ai.statusVolatile(battler) & K(ai, 'VOLATILE_CONDITION_TORMENT')) !== 0;
  const gravity = (ai.fieldConditionsMask() & K(ai, 'FIELD_CONDITION_GRAVITY')) !== 0;
  const healBlocked = (ai.moveEffectsMask(battler) & K(ai, 'MOVE_EFFECT_HEAL_BLOCK')) !== 0;
  const C = (n) => K(ai, n);
  const choice = [C('HOLD_EFFECT_CHOICE_ATK'), C('HOLD_EFFECT_CHOICE_SPEED'), C('HOLD_EFFECT_CHOICE_SPATK')].includes(itemEffect);
  let choiceLockedMove = med.choiceLockedMove;
  for (let i = 0; i < 4; i++) {
    const bit = 1 << i;
    if (moves[i] === 0 && (opMask & C('CHECK_INVALID_NO_MOVE'))) invalidMoves |= bit;
    if (ai.ppCur(battler, i) === 0 && (opMask & C('CHECK_INVALID_NO_PP'))) invalidMoves |= bit;
    if (moves[i] === med.disabledMove && (opMask & C('CHECK_INVALID_DISABLED'))) invalidMoves |= bit;
    if (moves[i] === prev && (opMask & C('CHECK_INVALID_TORMENTED')) && tormented) invalidMoves |= bit;
    if (med.tauntedTurns && (opMask & C('CHECK_INVALID_TAUNTED')) && ai.moveData(moves[i]).power === 0) invalidMoves |= bit;
    if (moveImprisoned(ai, battler, moves[i]) && (opMask & C('CHECK_INVALID_IMPRISONED'))) invalidMoves |= bit;
    if (gravity && MOVES_AFFECTED_BY_GRAVITY.names.some((n) => C(n) === moves[i]) && (opMask & C('CHECK_INVALID_GRAVITY'))) invalidMoves |= bit;
    if (healBlocked && MOVES_AFFECTED_BY_HEAL_BLOCK.names.some((n) => C(n) === moves[i]) && (opMask & C('CHECK_INVALID_HEAL_BLOCK'))) invalidMoves |= bit;
    // BL:2296-2299: Encore has no opMask test.
    if (med.encoredMove && med.encoredMove !== moves[i]) invalidMoves |= bit;
    if (choice && (opMask & C('CHECK_INVALID_CHOICE_ITEM'))) {
      // Battler_SlotForMove == LEARNED_MOVES_MAX -> clear the lock (BL:2305-2307)
      if (!moves.includes(choiceLockedMove)) choiceLockedMove = 0;
      else if (choiceLockedMove && choiceLockedMove !== moves[i]) invalidMoves |= bit;
    }
  }
  return invalidMoves & 0xffffffff;
}

// ---------------------------------------------------------------------------------------------
// AI memory

// AI_CONTEXT fields that survive across decisions (everything at or after battlerMoves in
// ai_context.h:26-44 is not cleared by TrainerAI_Init's memset, TAI:217-221; the whole struct is
// cleared once at battle start, battle_controller_player.c:4800).
export function newKnowledge() {
  return {
    battlerMoves: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]], // u16[4][4]
    battlerAbilities: [0, 0, 0, 0], // u8[4]
    battlerHeldItems: [0, 0, 0, 0], // u16[4]
  };
}

// TrainerAI_RecordLastMove (TAI:2705-2717): append movePrevByBattler[defender] to the defender's
// known moves unless already known; MOVE_NONE matches the first empty slot and stops the loop.
export function recordLastMove(ai, knowledge, defender) {
  const known = knowledge.battlerMoves[defender];
  const prev = ai.movePrevByBattler(defender);
  for (let i = 0; i < 4; i++) {
    if (known[i] === prev) break;
    if (known[i] === 0) {
      known[i] = prev;
      break;
    }
  }
}

// ---------------------------------------------------------------------------------------------
// TrainerAI_Init (TAI:211-256)

/**
 * @param st  { ai, knowledge, rng (AIRng), thinkingMask, monSpeedValues? }
 * Returns AI_CONTEXT memory for one decision. Draws 4 RNG values (TAI:240).
 */
export function trainerAIInit(st, battler, initScore = 0xf) {
  const { ai } = st;
  const mem = {
    // cleared by the memset (TAI:217-221)
    evalStep: 0, moveSlot: 0, move: 0,
    moveScore: [0, 0, 0, 0],
    calcTemp: 0, thinkingMask: 0, stateFlags: 0, thinkingBitShift: 0,
    moveDamageRolls: [0, 0, 0, 0],
    // persistent (not cleared)
    battlerMoves: st.knowledge.battlerMoves,
    battlerAbilities: st.knowledge.battlerAbilities,
    battlerHeldItems: st.knowledge.battlerHeldItems,
    // scriptStackPointer / scriptStackSize = 0 (TAI:244)
    stack: [],
    attacker: battler,
    defender: battler ^ 1, // BattleSystem_RandomOpponent in singles (BL:4193-4195): no RNG
    // battleCtx->monSpeedValues (battle_context.h:259) is engine state, not AI memory; see
    // speedValuesBeforeDecision() in opponent.mjs.
    monSpeedValues: st.monSpeedValues ? [...st.monSpeedValues] : [0, 0, 0, 0],
  };
  for (let i = 0; i < 4; i++) {
    mem.moveScore[i] = (initScore & 1) ? 100 : 0; // TAI:223-231
    initScore >>= 1;
  }
  const invalid = checkInvalidMoves(ai, battler, 0, ~0); // TAI:234
  for (let i = 0; i < 4; i++) {
    if (invalid & (1 << i)) mem.moveScore[i] = 0;
    mem.moveDamageRolls[i] = (100 - (st.rng.next() % 16)) & 0xff; // TAI:240 (u8)
  }
  // TAI:246-255: not a roamer, not doubles -> trainer aiMask
  mem.thinkingMask = st.thinkingMask >>> 0;
  mem.invalidMoves = invalid;
  return mem;
}

// ---------------------------------------------------------------------------------------------
// TrainerAI_EvalMoves (TAI:483-526)

// runSection with a per-instruction hook, for traces (identical loop to interp.mjs runSection).
function runSectionTraced(ctx, start, onStep, maxSteps = 200000) {
  ctx.pc = start;
  ctx.done = false;
  for (let steps = 0; !ctx.done; steps++) {
    if (steps >= maxSteps) throw new Error(`AI section did not terminate after ${maxSteps} steps`);
    const ins = ctx.prog.instructions[ctx.pc];
    const fn = HANDLERS[ins.name];
    if (!fn) throw new AIUnimplemented(ins.name, ins.line);
    ctx.next = ins.index + 1;
    const before = ctx.mem.moveScore[ctx.mem.moveSlot];
    fn(ctx, ins);
    onStep(ins, before, ctx.mem.moveScore[ctx.mem.moveSlot]);
    ctx.pc = ctx.next;
  }
}

const AI_STATUS_FLAG_BREAK = 1 << 3; // include/constants/battle/trainer_ai.h:19

function evalMoves(ctx, sectionStart, trace) {
  const { ai, mem } = ctx;
  const a = mem.attacker;
  const moves = ai.moves(a);
  for (mem.moveSlot = 0; mem.moveSlot < 4;) {
    // AI_EVAL_STEP_INIT (TAI:487-497)
    mem.move = ai.ppCur(a, mem.moveSlot) === 0 ? 0 : moves[mem.moveSlot];
    // AI_EVAL_STEP_EVAL (TAI:499-519)
    if (mem.move !== 0) {
      if (trace) {
        runSectionTraced(ctx, sectionStart, (ins, before, after) => {
          if (ins.name === 'AddToMoveScore') {
            trace.push({ flagBit: mem.thinkingBitShift, slot: mem.moveSlot, line: ins.line, add: ctx.arg(ins, 'i') | 0, before, after });
          } else if (trace.full) {
            trace.push({ flagBit: mem.thinkingBitShift, slot: mem.moveSlot, line: ins.line, op: ins.name, jumped: ctx.next !== ins.index + 1 });
          }
        });
      } else {
        runSection(ctx, sectionStart);
      }
    } else {
      mem.moveScore[mem.moveSlot] = 0;
    }
    mem.moveSlot++;
    if (mem.stateFlags & AI_STATUS_FLAG_BREAK) break; // TAI:510-515
  }
}

// ---------------------------------------------------------------------------------------------
// TrainerAI_Main + TrainerAI_MainSingles

/**
 * Runs TrainerAI_Main for the AI battler (singles). Returns
 *   { slot, scores (s8 values after evaluation), rolls, invalidMoves, ties, trace? }
 * `st` = { ai, prog, knowledge, rng, thinkingMask, monSpeedValues? }.
 * opts.trace: collect every AddToMoveScore (flag bit, slot, script.s line, value); 'full' also
 * records every other executed instruction (line, op, jumped).
 */
export function trainerAIMain(st, battler = 1, opts = {}) {
  const { ai } = st;
  const prog = st.prog ?? aiProgram();
  if (ai.battleType() & K(ai, 'BATTLE_TYPE_DOUBLES')) throw new Error('choose: TrainerAI_MainDoubles is not ported');
  const mem = trainerAIInit(st, battler, 0xf); // AI_INIT_SCORE_ALL_MOVES (constants/battle/trainer_ai.h:14)
  const rand = () => st.rng.next();
  const ctx = makeCtx({ prog, ai, mem, rand, extra: { damage: calcdamage } });
  const trace = opts.trace ? [] : null;
  if (trace && opts.trace === 'full') trace.full = true;

  recordLastMove(ai, st.knowledge, mem.defender); // TAI:295

  // TAI:297-309
  while (mem.thinkingMask) {
    if (mem.thinkingMask & 1) { // AI_FLAG_BASIC == bit 0
      const entry = prog.flagTable[mem.thinkingBitShift];
      const start = prog.labels[entry.label].instr;
      evalMoves(ctx, start, trace);
    }
    mem.thinkingMask = mem.thinkingMask >>> 1;
    mem.thinkingBitShift++;
    mem.moveSlot = 0;
  }

  // TAI:311-336 (ESCAPE / SAFARI flags are set only by unreachable opcodes)
  const moves = ai.moves(mem.attacker);
  const u8 = (x) => x & 0xff;
  const maxScoreMoves = [u8(mem.moveScore[0])];
  const maxScoreMoveSlots = [0];
  let numMaxScoreMoves = 1;
  for (let i = 1; i < 4; i++) {
    if (moves[i]) {
      // u8 maxScoreMoves[0] vs s8 moveScore[i]: both promote to int (TAI:320, 326)
      if (maxScoreMoves[0] === mem.moveScore[i]) {
        maxScoreMoves[numMaxScoreMoves] = u8(mem.moveScore[i]);
        maxScoreMoveSlots[numMaxScoreMoves++] = i;
      }
      if (maxScoreMoves[0] < mem.moveScore[i]) {
        numMaxScoreMoves = 1;
        maxScoreMoves[0] = u8(mem.moveScore[i]);
        maxScoreMoveSlots[0] = i;
      }
    }
  }
  const ties = maxScoreMoveSlots.slice(0, numMaxScoreMoves);
  const slot = maxScoreMoveSlots[st.rng.next() % numMaxScoreMoves]; // TAI:334
  return { slot, scores: [...mem.moveScore], rolls: [...mem.moveDamageRolls], invalidMoves: mem.invalidMoves, ties, trace, mem };
}

// Fills battleCtx->monSpeedValues the way the engine's last BattleSystem_CompareBattlerSpeed did
// (battle_lib.c:1372-1373), by running the same comparison on the current state with a throwaway
// RNG (so the AI stream is not touched). UNVERIFIED approximation: the game's values come from the
// engine's most recent comparison (turn ordering), which can predate changes made later in that
// turn (e.g. a speed boost). Only Gyro Ball reads it (TAI:2995-3003).
export function speedValuesNow(ai) {
  const mem = { monSpeedValues: [0, 0, 0, 0] };
  const ctx = { ai, mem, rand: () => 0 };
  if (ai.exists(0) && ai.exists(1)) compareBattlerSpeed(ctx, 1, 0);
  return mem.monSpeedValues;
}
