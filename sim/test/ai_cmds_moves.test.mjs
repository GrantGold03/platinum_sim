// T042 tests: sim/ai/cmds/moves.mjs. Each test runs a real instruction from
// pokeplatinum/src/battle/trainer_ai/script.s (found by name + script.s line, args decoded by
// parse.mjs) against a real gen4customgame Battle and a hand-built AI_CONTEXT memory.
// Handler lines are pokeplatinum/src/battle/trainer_ai/trainer_ai.c (TAI).
// Decomp values are read through the constants loader and cited (path:line); enum value = line - 1.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle } from '../showdown.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { parseAiScript } from '../ai/parse.mjs';
import { HANDLERS, makeCtx } from '../ai/interp.mjs';
import { handlers as movesHandlers } from '../ai/cmds/moves.mjs';
import { loadConstants } from '../ai/constants.mjs';

const C = loadConstants();
const K = (n) => C.get(n);
const prog = parseAiScript();

const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });

// p1 = player (battler 0 = AI_CONTEXT.defender), p2 = AI (battler 1 = AI_CONTEXT.attacker).
function makeBattle({ p1 = ['swordsdance', 'protect', 'sleeptalk', 'earthquake'], p2 = ['toxic', 'leechseed', 'softboiled', 'thunderwave'] } = {}) {
  return new Battle({
    formatid: 'gen4customgame',
    seed: [1, 2, 3, 4],
    p1: { name: 'Player', team: [mon('garchomp', p1, { ability: 'Sand Veil' })] },
    p2: { name: 'AI', team: [mon('blissey', p2, { ability: 'Natural Cure' })] },
  });
}

function makeMem(over = {}) {
  return {
    move: 0, moveSlot: 0, moveScore: [100, 100, 100, 100], moveDamageRolls: [100, 100, 100, 100],
    calcTemp: 0,
    battlerMoves: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    battlerAbilities: [0, 0, 0, 0], battlerHeldItems: [0, 0, 0, 0], stack: [],
    ...over,
  };
}

function setup(battle, memOver) {
  const ai = createAdapter(battle);
  let draws = 0;
  const ctx = makeCtx({ prog, ai, mem: makeMem(memOver), rand: () => { draws++; return 0; } });
  return { ai, ctx, draws: () => draws };
}

function ins(name, line) {
  const i = prog.instructions.find((x) => x.name === name && x.line === line);
  if (!i) throw new Error(`no ${name} at script.s:${line}`);
  return i;
}

// Run one instruction the way runSection does (next defaults to index + 1).
function run(ctx, i) {
  ctx.next = i.index + 1;
  HANDLERS[i.name](ctx, i);
  return ctx.next;
}

const ALL = ['IfMoveEqualTo', 'IfAttackerHasNoDamagingMoves', 'LoadBattlerPreviousMove', 'LoadCurrentMoveEffect',
  'IfCurrentMoveEffectEqualTo', 'IfMoveKnown', 'IfMoveNotKnown', 'IfMoveEffectKnown', 'IfMoveEffectNotKnown',
  'LoadPowerOfLoadedMove', 'LoadEffectOfLoadedMove', 'LoadCurrentMovePP', 'IfCanUseLastResort',
  'LoadDefenderLastUsedMoveClass'];

test('moves.mjs implements exactly the 14 OPCODES.md "moves" rows, and HANDLERS uses them', () => {
  assert.deepEqual(Object.keys(movesHandlers).sort(), ALL.slice().sort());
  for (const n of ALL) assert.equal(HANDLERS[n], movesHandlers[n], n);
});

test('constants used below (positive controls against the decomp lists)', () => {
  assert.equal(K('BATTLE_EFFECT_PROTECT'), 111); // generated/move_battle_effects.txt:112
  assert.equal(K('BATTLE_EFFECT_STATUS_BADLY_POISON'), 33); // generated/move_battle_effects.txt:34
  assert.equal(K('CLASS_PHYSICAL'), 0); // generated/move_classes.txt:1
  assert.equal(K('CLASS_STATUS'), 2); // generated/move_classes.txt:3
});

test('IfMoveEqualTo (TAI:834) script.s:57 MOVE_FISSURE -> Basic_CheckForImmunity', () => {
  const { ctx, draws } = setup(makeBattle());
  const i = ins('IfMoveEqualTo', 57);
  assert.equal(i.args[0].value, K('MOVE_FISSURE'));
  ctx.mem.move = K('MOVE_FISSURE');
  assert.equal(run(ctx, i), i.args[1].targetInstr);
  ctx.mem.move = K('MOVE_HORN_DRILL');
  assert.equal(run(ctx, i), i.index + 1);
  assert.equal(draws(), 0);
});

test('IfAttackerHasNoDamagingMoves (TAI:913) script.s:2688', () => {
  const i = ins('IfAttackerHasNoDamagingMoves', 2688);
  // AI Blissey with Toxic/Leech Seed/Soft-Boiled/Thunder Wave: all power 0
  // (res/moves/toxic/data.json:12 "power": 0 etc.) -> jump.
  let s = setup(makeBattle());
  assert.equal(run(s.ctx, i), i.args[0].targetInstr);
  // AI memory of the attacker is irrelevant: the handler reads battleMons[attacker].moves.
  s.ctx.mem.battlerMoves[1] = [K('MOVE_EARTHQUAKE'), 0, 0, 0];
  assert.equal(run(s.ctx, i), i.args[0].targetInstr);
  // One damaging move (Earthquake power 100, res/moves/earthquake/data.json:11) -> no jump.
  s = setup(makeBattle({ p2: ['toxic', 'earthquake'] }));
  assert.equal(run(s.ctx, i), i.index + 1);
  assert.equal(s.draws(), 0);
});

test('LoadBattlerPreviousMove (TAI:1068) script.s:1913 DEFENDER reads movePrevByBattler', () => {
  const battle = makeBattle();
  const { ctx, draws } = setup(battle, { calcTemp: 1234 });
  const i = ins('LoadBattlerPreviousMove', 1913);
  assert.equal(run(ctx, i), i.index + 1);
  assert.equal(ctx.mem.calcTemp, 0); // MOVE_NONE before anything was used
  battle.makeChoices('move swordsdance', 'move toxic');
  assert.equal(battle.p1.active[0].lastMove.id, 'swordsdance', 'positive control: move recorded');
  run(ctx, i);
  assert.equal(ctx.mem.calcTemp, K('MOVE_SWORDS_DANCE'));
  assert.equal(draws(), 0);
});

test('LoadCurrentMoveEffect (TAI:1164) script.s:6425', () => {
  const { ctx, draws } = setup(makeBattle(), { move: K('MOVE_PROTECT') });
  const i = ins('LoadCurrentMoveEffect', 6425);
  assert.equal(run(ctx, i), i.index + 1);
  // res/moves/protect/data.json:16 BATTLE_EFFECT_PROTECT
  assert.equal(ctx.mem.calcTemp, K('BATTLE_EFFECT_PROTECT'));
  assert.equal(draws(), 0);
});

test('IfCurrentMoveEffectEqualTo (TAI:1441) script.s:134 BATTLE_EFFECT_STATUS_SLEEP', () => {
  const { ctx, draws } = setup(makeBattle(), { move: K('MOVE_HYPNOSIS') });
  const i = ins('IfCurrentMoveEffectEqualTo', 134);
  assert.equal(i.args[0].value, K('BATTLE_EFFECT_STATUS_SLEEP'));
  // res/moves/hypnosis/data.json:16 BATTLE_EFFECT_STATUS_SLEEP -> jump
  assert.equal(run(ctx, i), i.args[1].targetInstr);
  ctx.mem.move = K('MOVE_TOXIC'); // res/moves/toxic/data.json:16 STATUS_BADLY_POISON
  assert.equal(run(ctx, i), i.index + 1);
  assert.equal(draws(), 0);
});

test('IfMoveKnown (TAI:1627): DEFENDER reads AI memory (script.s:1438), ATTACKER the real moves (script.s:2852)', () => {
  const { ctx, draws } = setup(makeBattle({ p2: ['toxic', 'psychup'] }));
  const d = ins('IfMoveKnown', 1438); // DEFENDER, MOVE_SLEEP_TALK
  assert.equal(d.args[1].value, K('MOVE_SLEEP_TALK'));
  // The player's Garchomp really knows Sleep Talk, but the AI has not seen it -> no jump.
  assert.ok(ctx.ai.moves(0).includes(K('MOVE_SLEEP_TALK')), 'positive control: real moveset has it');
  assert.equal(run(ctx, d), d.index + 1);
  ctx.mem.battlerMoves[0] = [K('MOVE_EARTHQUAKE'), K('MOVE_SLEEP_TALK'), 0, 0];
  assert.equal(run(ctx, d), d.args[2].targetInstr);

  const a = ins('IfMoveKnown', 2852); // ATTACKER, MOVE_PSYCH_UP
  assert.equal(run(ctx, a), a.args[2].targetInstr);
  const s2 = setup(makeBattle());
  s2.ctx.mem.battlerMoves[1] = [K('MOVE_PSYCH_UP'), 0, 0, 0]; // memory ignored for the attacker
  assert.equal(run(s2.ctx, a), a.index + 1);
  assert.equal(draws() + s2.draws(), 0);
});

test('IfMoveNotKnown (TAI:1683): ATTACKER script.s:2994, DEFENDER script.s:3730', () => {
  const { ctx, draws } = setup(makeBattle({ p1: ['uturn', 'earthquake'], p2: ['toxic', 'focuspunch'] }));
  const a = ins('IfMoveNotKnown', 2994); // ATTACKER, MOVE_FOCUS_PUNCH
  assert.equal(run(ctx, a), a.index + 1); // known -> no jump
  const s2 = setup(makeBattle());
  assert.equal(run(s2.ctx, a), a.args[2].targetInstr); // not known -> jump

  const d = ins('IfMoveNotKnown', 3730); // DEFENDER, MOVE_U_TURN
  assert.equal(d.args[1].value, K('MOVE_U_TURN'));
  // Player really has U-turn, AI memory empty -> "not known" -> jump.
  assert.equal(run(ctx, d), d.args[2].targetInstr);
  ctx.mem.battlerMoves[0] = [0, 0, 0, K('MOVE_U_TURN')];
  assert.equal(run(ctx, d), d.index + 1);
  assert.equal(draws() + s2.draws(), 0);
});

test('IfMoveEffectKnown (TAI:1739): ATTACKER script.s:1816, DEFENDER script.s:3964', () => {
  const a = ins('IfMoveEffectKnown', 1816); // ATTACKER, BATTLE_EFFECT_RECOVER_DAMAGE_SLEEP
  let s = setup(makeBattle({ p2: ['toxic', 'dreameater'] })); // res/moves/dream_eater/data.json:16
  assert.equal(run(s.ctx, a), a.args[2].targetInstr);
  s = setup(makeBattle());
  assert.equal(run(s.ctx, a), a.index + 1);

  const d = ins('IfMoveEffectKnown', 3964); // DEFENDER, BATTLE_EFFECT_PROTECT
  assert.equal(d.args[1].value, K('BATTLE_EFFECT_PROTECT'));
  // Player really knows Protect; AI memory empty -> no jump.
  assert.equal(run(s.ctx, d), d.index + 1);
  s.ctx.mem.battlerMoves[0] = [K('MOVE_EARTHQUAKE'), K('MOVE_PROTECT'), 0, 0];
  assert.equal(run(s.ctx, d), d.args[2].targetInstr);
  assert.equal(s.draws(), 0);
});

test('IfMoveEffectNotKnown (TAI:1781) script.s:2670 DEFENDER BATTLE_EFFECT_STEAL_STATUS_MOVE', () => {
  const { ctx, draws } = setup(makeBattle({ p1: ['snatch', 'earthquake'] }));
  const d = ins('IfMoveEffectNotKnown', 2670);
  assert.equal(d.args[1].value, K('BATTLE_EFFECT_STEAL_STATUS_MOVE'));
  assert.equal(run(ctx, d), d.args[2].targetInstr); // AI has not seen Snatch -> jump
  ctx.mem.battlerMoves[0] = [K('MOVE_SNATCH'), 0, 0, 0]; // res/moves/snatch/data.json:16
  assert.equal(run(ctx, d), d.index + 1);
  assert.equal(draws(), 0);
});

test('LoadPowerOfLoadedMove (TAI:2526) script.s:2039', () => {
  const { ctx, draws } = setup(makeBattle(), { calcTemp: K('MOVE_EARTHQUAKE') });
  const i = ins('LoadPowerOfLoadedMove', 2039);
  assert.equal(run(ctx, i), i.index + 1);
  assert.equal(ctx.mem.calcTemp, 100); // res/moves/earthquake/data.json:11
  ctx.mem.calcTemp = 0; // MOVE_NONE row: res/moves/none/data.json:11 power 0
  run(ctx, i);
  assert.equal(ctx.mem.calcTemp, 0);
  assert.equal(draws(), 0);
});

test('LoadEffectOfLoadedMove (TAI:2532) script.s:3016', () => {
  const { ctx, draws } = setup(makeBattle(), { calcTemp: K('MOVE_TOXIC') });
  const i = ins('LoadEffectOfLoadedMove', 3016);
  assert.equal(run(ctx, i), i.index + 1);
  assert.equal(ctx.mem.calcTemp, K('BATTLE_EFFECT_STATUS_BADLY_POISON')); // res/moves/toxic/data.json:16
  assert.equal(draws(), 0);
});

test('LoadCurrentMovePP (TAI:2024) script.s:5327 reads attacker ppCur[moveSlot]', () => {
  const battle = makeBattle();
  const { ctx, draws } = setup(battle, { moveSlot: 0 });
  const i = ins('LoadCurrentMovePP', 5327);
  run(ctx, i);
  const before = ctx.mem.calcTemp;
  assert.equal(before, battle.p2.active[0].moveSlots[0].pp);
  assert.ok(before > 0);
  battle.makeChoices('move earthquake', 'move toxic'); // AI uses slot 0
  run(ctx, i);
  assert.equal(ctx.mem.calcTemp, before - 1, 'positive control: PP spent shows up');
  ctx.mem.moveSlot = 1;
  run(ctx, i);
  assert.equal(ctx.mem.calcTemp, battle.p2.active[0].moveSlots[1].pp);
  assert.equal(draws(), 0);
});

test('IfCanUseLastResort (TAI:2030) script.s:1422 ATTACKER', () => {
  const i = ins('IfCanUseLastResort', 1422);
  // Two moves: Battler_CountMoves = 2 (battle_lib.c:3461-3471); needs lastResortCount >= 1.
  const battle = makeBattle({ p2: ['lastresort', 'toxic'] });
  const s = setup(battle);
  assert.equal(run(s.ctx, i), i.index + 1); // count 0 < 1
  battle.makeChoices('move earthquake', 'move toxic');
  assert.equal(s.ai.moveEffectsData(1).lastResortCount, 1, 'positive control: used move counted');
  assert.equal(run(s.ctx, i), i.args[1].targetInstr);
  // One move: 0 >= 0 but numKnownMoves > 1 fails -> no jump.
  const s1 = setup(makeBattle({ p2: ['lastresort'] }));
  assert.equal(run(s1.ctx, i), i.index + 1);
  // Four moves, none used -> no jump.
  const s4 = setup(makeBattle());
  assert.equal(run(s4.ctx, i), i.index + 1);
  assert.equal(s.draws() + s1.draws() + s4.draws(), 0);
});

test('LoadDefenderLastUsedMoveClass (TAI:2050) script.s:2041', () => {
  const battle = makeBattle();
  const { ctx, draws } = setup(battle, { calcTemp: 99 });
  const i = ins('LoadDefenderLastUsedMoveClass', 2041);
  assert.equal(run(ctx, i), i.index + 1);
  // No previous move: MOVE_DATA(MOVE_NONE).class = CLASS_PHYSICAL (res/moves/none/data.json:9).
  assert.equal(ctx.mem.calcTemp, K('CLASS_PHYSICAL'));
  battle.makeChoices('move swordsdance', 'move toxic');
  run(ctx, i);
  assert.equal(ctx.mem.calcTemp, K('CLASS_STATUS')); // res/moves/swords_dance/data.json:10
  assert.equal(draws(), 0);
});
