// T048: sim/ai/choose.mjs — TrainerAI_Init / EvalMoves / MainSingles, the AI RNG, CheckInvalidMoves.
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c, BL = pokeplatinum/src/battle/battle_lib.c.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { AIRng, aiProgram, aiSeedFromBattleSeed, checkInvalidMoves, recordLastMove, newKnowledge, thinkingMaskOf, trainerAIInit, trainerAIMain, MOVES_AFFECTED_BY_GRAVITY, MOVES_AFFECTED_BY_HEAL_BLOCK } from '../ai/choose.mjs';
import { successors } from '../ai/parse.mjs';
import { HANDLERS, makeCtx } from '../ai/interp.mjs';
import { B, gd, leagueBattle, setLastMove, stubRng, trainerByKey } from './ai_fixtures.mjs';

const prog = aiProgram();
const K = (n) => prog.constants.get(n);

test('AIRng is BattleSystem_RandNext: u32 LCG *1103515245 +24691, returns state/65536 (battle_system.c:1308-1312, math_util.h:8-10)', () => {
  // Independent reference in BigInt.
  const ref = (seed, n) => {
    let s = BigInt(seed);
    const out = [];
    for (let i = 0; i < n; i++) {
      s = (s * 1103515245n + 24691n) % 4294967296n;
      out.push(Number(s / 65536n));
    }
    return out;
  };
  // Hand-checked first value from seed 0: state = 0*1103515245 + 24691 = 24691; 24691 / 65536 = 0.
  const r0 = new AIRng(0);
  assert.equal(r0.next(), 0);
  assert.equal(r0.state, 24691);
  for (const seed of [0, 1, 0x12345678, 0xffffffff]) {
    const r = new AIRng(seed);
    assert.deepEqual(Array.from({ length: 1000 }, () => r.next()), ref(seed, 1000));
    assert.equal(r.draws, 1000);
  }
  // clone() continues identically and independently (look-ahead use, T050)
  const a = new AIRng(42);
  a.next();
  const b = a.clone();
  assert.deepEqual([a.next(), a.next()], [b.next(), b.next()]);
});

test('AI seed derivation: first 4 bytes of sha256(`${battle.prngSeed}|trainer-ai`), deterministic, seed-sensitive', () => {
  const s = 'sodium,' + 'ab'.repeat(16);
  const want = parseInt(createHash('sha256').update(`${s}|trainer-ai`).digest('hex').slice(0, 8), 16);
  assert.equal(aiSeedFromBattleSeed(s), want);
  assert.equal(aiSeedFromBattleSeed(s), aiSeedFromBattleSeed(s));
  assert.notEqual(aiSeedFromBattleSeed(s), aiSeedFromBattleSeed('sodium,' + 'ac'.repeat(16)));
});

test('thinkingMaskOf: League flags from trainers.json -> FlagTable bits (Lucian adds SETUP_FIRST_TURN, bit 3)', () => {
  assert.equal(thinkingMaskOf(prog, trainerByKey('elite_four_aaron').ai_flags), 0b0111);
  assert.equal(thinkingMaskOf(prog, trainerByKey('champion_cynthia').ai_flags), 0b0111);
  assert.equal(thinkingMaskOf(prog, trainerByKey('elite_four_lucian').ai_flags), 0b1111);
  assert.throws(() => thinkingMaskOf(prog, ['AI_FLAG_NOT_A_FLAG']));
});

test('BL tables parsed from battle_lib.c (gravity / heal block move lists)', () => {
  assert.ok(MOVES_AFFECTED_BY_GRAVITY.names.includes('MOVE_FLY') && MOVES_AFFECTED_BY_GRAVITY.names.length === 6);
  assert.ok(MOVES_AFFECTED_BY_HEAL_BLOCK.names.includes('MOVE_RECOVER') && MOVES_AFFECTED_BY_HEAL_BLOCK.names.includes('MOVE_WISH'));
});

test('CheckInvalidMoves (BL:2255-2318): 0 PP, Taunt (power 0 moves), Encore', () => {
  // Cynthia's lead Spiritomb has Dark Pulse, Psychic, Silver Wind, Shadow Ball (all damaging).
  const { battle, st, p2 } = leagueBattle('champion_cynthia', [B('lucario', 56, ['aura_sphere', 'taunt', 'encore', 'extreme_speed'], 'ABILITY_STEADFAST')]);
  const mon = p2.active[0];
  assert.equal(checkInvalidMoves(st.ai, 1), 0);
  mon.moveSlots[2].pp = 0; // Silver Wind out of PP
  assert.equal(checkInvalidMoves(st.ai, 1), 0b0100);
  mon.moveSlots[2].pp = 5;
  // Taunt: only moves with MOVE_DATA power 0 become invalid -> none of Spiritomb's
  mon.addVolatile('taunt');
  assert.equal(checkInvalidMoves(st.ai, 1), 0);
  // Roserade (Energy Ball, Sludge Bomb, Toxic, Extrasensory): Toxic (power 0) is invalid under Taunt
  const rose = p2.pokemon.find((p) => p.platsimSlot === 1);
  battle.actions.switchIn(rose, 0);
  rose.addVolatile('taunt');
  assert.equal(checkInvalidMoves(st.ai, 1), 0b0100);
  // opMask without CHECK_INVALID_TAUNTED ignores it
  assert.equal(checkInvalidMoves(st.ai, 1, 0, ~K('CHECK_INVALID_TAUNTED')), 0);
  rose.removeVolatile('taunt');
  // Encore on Sludge Bomb: every other slot invalid (no opMask test, BL:2296-2299)
  setLastMove(battle, rose, 'sludgebomb');
  rose.addVolatile('encore');
  assert.equal(checkInvalidMoves(st.ai, 1), 0b1101);
});

test('TrainerAI_Init (TAI:211-256): scores 100, invalid -> 0, four rolls 100 - RandNext % 16 in slot order', () => {
  const { st, p2 } = leagueBattle('champion_cynthia', [B('lucario', 56, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST')]);
  p2.active[0].moveSlots[3].pp = 0; // slot 3 invalid
  st.rng = stubRng([3, 18, 15, 0xffff]);
  const mem = trainerAIInit(st, 1, 0xf);
  assert.deepEqual(mem.moveScore, [100, 100, 100, 0]);
  // 100 - 3 % 16 = 97; 100 - 18 % 16 = 98; 100 - 15 = 85; 100 - 65535 % 16 = 85
  assert.deepEqual(mem.moveDamageRolls, [97, 98, 85, 85]);
  assert.equal(st.rng.draws, 4);
  assert.equal(mem.calcTemp, 0);
  assert.deepEqual(mem.stack, []);
  assert.equal(mem.thinkingMask, 0b0111);
  // initScore bit 2 clear -> slot 2 starts at 0 (TAI:223-231)
  st.rng = stubRng();
  assert.deepEqual(trainerAIInit(st, 1, 0b1011).moveScore, [100, 100, 0, 0]);
});

test('TrainerAI_RecordLastMove (TAI:2705-2717): appends movePrevByBattler[defender] once', () => {
  const { battle, st, p1 } = leagueBattle('elite_four_aaron', [B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL')]);
  const kn = newKnowledge();
  recordLastMove(st.ai, kn, 0); // MOVE_NONE: matches the empty slot 0 -> nothing recorded
  assert.deepEqual(kn.battlerMoves[0], [0, 0, 0, 0]);
  setLastMove(battle, p1.active[0], 'earthquake');
  recordLastMove(st.ai, kn, 0);
  recordLastMove(st.ai, kn, 0); // already known -> unchanged
  setLastMove(battle, p1.active[0], 'crunch');
  recordLastMove(st.ai, kn, 0);
  assert.deepEqual(kn.battlerMoves[0], [K('MOVE_EARTHQUAKE'), K('MOVE_CRUNCH'), 0, 0]);
});

test('TrainerAI_MainSingles tie break: one RandNext % numMaxScoreMoves over the tied slots (TAI:311-336)', () => {
  const { st } = leagueBattle('elite_four_bertha', [B('gyarados', 56, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE')], { rng: stubRng([], 255) });
  const r = trainerAIMain(st, 1);
  // golden B1: Whiscash scores [89, 99, 100, 100], ties [2, 3]; tie draw 255 % 2 = 1 -> slot 3
  assert.deepEqual(r.scores, [89, 99, 100, 100]);
  assert.deepEqual(r.ties, [2, 3]);
  assert.equal(r.slot, 3);
});

test('s8 moveScore wrap (trap 1) is real in the handler, and unreachable for the League flags', () => {
  // Handler level: 120 + 10 wraps to -126 in an s8, then clamps to 0 (TAI:576-586).
  const { st } = leagueBattle('elite_four_aaron', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  const plus10 = prog.instructions.find((i) => i.name === 'AddToMoveScore' && (i.args[0].value | 0) === 10);
  const mem = { moveSlot: 0, moveScore: [120, 100, 100, 100] };
  const ctx = makeCtx({ prog, ai: st.ai, mem, rand: () => 0 });
  HANDLERS.AddToMoveScore(ctx, plus10);
  assert.equal(mem.moveScore[0], 0);
  // Reachability: the largest NET sum of AddToMoveScore values along any path of each League
  // section (path-insensitive, so an over-approximation; PushAndGoTo is unreachable so PopOrEnd
  // ends the section). From the base score 100 a move would need +28 to pass 127.
  const memo = new Map();
  const gain = (i) => {
    if (memo.has(i)) return memo.get(i);
    const ins = prog.instructions[i];
    const own = ins.name === 'AddToMoveScore' ? (ins.args[0].value | 0) : 0;
    const succ = successors(prog, ins);
    const best = succ.length ? Math.max(...succ.map(gain)) : 0;
    memo.set(i, own + best);
    return own + best;
  };
  const sectionGain = (flag) => gain(prog.labels[prog.flagTable.find((f) => f.flag === flag).label].instr);
  const g = Object.fromEntries(['AI_FLAG_BASIC', 'AI_FLAG_EVAL_ATTACK', 'AI_FLAG_EXPERT', 'AI_FLAG_SETUP_FIRST_TURN'].map((f) => [f, sectionGain(f)]));
  // Positive control: EvalAttack's best path is the +2 then +4 kill bonus (script.s:6408-6412).
  assert.equal(g.AI_FLAG_EVAL_ATTACK, 6);
  const total = Object.values(g).reduce((a, b) => a + b, 0);
  assert.ok(total < 28, `max net gain ${total} would reach 128`);
  assert.equal(total, 25); // Basic 3, EvalAttack 6, Expert 14, SetupFirstTurn 2 (2026-10-07)
});

test('full decision draws in C order: Init 4, script draws, then 1 tie-break draw', () => {
  // Lucian's Mr. Mime turn 1 (golden L1). The stub counts every call.
  const { st } = leagueBattle('elite_four_lucian', [B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL')], { rng: stubRng([], 255) });
  assert.equal(st.rng.draws, 4); // createAIState: speedRand[0..3] (BL:2024)
  const r = trainerAIMain(st, 1, { trace: true });
  // 4 rolls + Expert Reflect (IfRandomLessThan 128, 64) + Expert Light Screen (128) +
  // SetupFirstTurn (IfRandomLessThan 80) on Reflect and Light Screen + 1 tie break = 4+2+1+2+1 = 10
  assert.equal(st.rng.draws - 4, 10);
  assert.equal(r.slot, 2);
  void gd;
});
