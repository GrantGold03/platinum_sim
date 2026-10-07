// T040 tests: sim/ai/cmds/flow.mjs. Every instruction is a real one from parseAiScript(), found by
// name and pokeplatinum/src/battle/trainer_ai/script.s line; constants come from the decomp via
// loadConstants() and are cited. Each handler runs against a real gen4customgame Battle + adapter.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle } from '../showdown.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { parseAiScript } from '../ai/parse.mjs';
import { HANDLERS, makeCtx, runSection } from '../ai/interp.mjs';
import { handlers as FLOW } from '../ai/cmds/flow.mjs';

const prog = parseAiScript();
const K = (n) => prog.constants.get(n);
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });
const battle = new Battle({
  formatid: 'gen4customgame',
  seed: [1, 2, 3, 4],
  p1: { name: 'Player', team: [mon('garchomp', ['swordsdance', 'earthquake'], { ability: 'Sand Veil' })] },
  p2: { name: 'AI', team: [mon('blissey', ['toxic', 'softboiled'], { ability: 'Natural Cure' })] },
});
const ai = createAdapter(battle);

const FLOW_OPS = ['AddToMoveScore', 'IfLoadedLessThan', 'IfLoadedGreaterThan', 'IfLoadedEqualTo', 'IfLoadedNotEqualTo',
  'IfLoadedMask', 'IfLoadedNotMask', 'IfLoadedinTable', 'IfLoadedNotinTable', 'IfTempEqualTo', 'GoTo', 'PopOrEnd'];

function at(name, line) {
  const ins = prog.instructions.find((i) => i.name === name && i.line === line);
  if (!ins) throw new Error(`no ${name} at script.s:${line}`);
  return ins;
}

function mem(over = {}) {
  return { move: 0, moveSlot: 0, moveScore: [100, 100, 100, 100], moveDamageRolls: [100, 100, 100, 100], calcTemp: 0,
    battlerMoves: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]], battlerAbilities: [0, 0, 0, 0],
    battlerHeldItems: [0, 0, 0, 0], stack: [], ...over };
}

// Runs one instruction the way runSection does (ctx.next preset to fall-through). rand must not be drawn.
function run(ins, m) {
  let draws = 0;
  const ctx = makeCtx({ prog, ai, mem: m, rand: () => { draws++; return 0; } });
  ctx.pc = ins.index;
  ctx.next = ins.index + 1;
  HANDLERS[ins.name](ctx, ins);
  return { ctx, draws };
}

function expectJump(ins, m, taken) {
  const { ctx, draws } = run(ins, m);
  assert.equal(ctx.next, taken ? ins.args.find((a) => a.kind === 'jump').targetInstr : ins.index + 1,
    `${ins.name} script.s:${ins.line} calcTemp=${m.calcTemp} expected ${taken ? 'jump' : 'fall-through'}`);
  assert.equal(ctx.done, false);
  assert.equal(draws, 0);
  return ctx;
}

test('flow.mjs exports exactly the OPCODES.md "flow" rows, all wired into HANDLERS', () => {
  assert.deepEqual(Object.keys(FLOW).sort(), [...FLOW_OPS].sort());
  for (const n of FLOW_OPS) assert.equal(HANDLERS[n], FLOW[n]);
});

test('AddToMoveScore: s8 add, wrap past 127, clamp below 0 (TAI:576; trap 1)', () => {
  const minus8 = at('AddToMoveScore', 514); // script.s:514 AddToMoveScore -8
  assert.equal(minus8.args[0].value, -8);
  let m = mem({ moveSlot: 2 });
  run(minus8, m);
  assert.deepEqual(m.moveScore, [100, 100, 92, 100]);
  m = mem({ moveSlot: 1, moveScore: [100, 5, 100, 100] });
  run(minus8, m);
  assert.deepEqual(m.moveScore, [100, 0, 100, 100]); // 5 - 8 = -3 -> clamped 0
  m = mem({ moveSlot: 0, moveScore: [8, 0, 0, 0] });
  run(minus8, m);
  assert.equal(m.moveScore[0], 0); // exactly 0 stays 0

  const plus8 = at('AddToMoveScore', 869); // script.s:869 AddToMoveScore 8
  assert.equal(plus8.args[0].value, 8);
  m = mem({ moveSlot: 3, moveScore: [100, 100, 100, 119] });
  run(plus8, m);
  assert.equal(m.moveScore[3], 127); // 119 + 8 fits s8
  m = mem({ moveSlot: 3, moveScore: [100, 100, 100, 120] });
  const { ctx, draws } = run(plus8, m);
  assert.equal(m.moveScore[3], 0); // 128 wraps to -128 in s8, then < 0 -> 0
  assert.equal(ctx.next, plus8.index + 1);
  assert.equal(draws, 0);
});

test('IfLoadedLessThan (TAI:762)', () => {
  const ins = at('IfLoadedLessThan', 1205); // script.s:1205 IfLoadedLessThan 10, ScoreMinus10
  assert.equal(ins.args[0].value, 10);
  expectJump(ins, mem({ calcTemp: 9 }), true);
  expectJump(ins, mem({ calcTemp: 10 }), false);
  expectJump(ins, mem({ calcTemp: -1 }), true); // int compare, signed
});

test('IfLoadedGreaterThan (TAI:774)', () => {
  const ins = at('IfLoadedGreaterThan', 2590); // script.s:2590 IfLoadedGreaterThan 3, ...
  assert.equal(ins.args[0].value, 3);
  expectJump(ins, mem({ calcTemp: 4 }), true);
  expectJump(ins, mem({ calcTemp: 3 }), false);
  expectJump(ins, mem({ calcTemp: 0xFFFFFFFF }), false); // int -1, not 4294967295
});

test('IfLoadedEqualTo (TAI:786)', () => {
  const ins = at('IfLoadedEqualTo', 63); // script.s:63 IfLoadedEqualTo AI_NO_COMPARISON_MADE, ...
  assert.equal(ins.args[0].value, K('AI_NO_COMPARISON_MADE'));
  expectJump(ins, mem({ calcTemp: K('AI_NO_COMPARISON_MADE') }), true);
  expectJump(ins, mem({ calcTemp: K('AI_NO_COMPARISON_MADE') + 1 }), false);
});

test('IfLoadedNotEqualTo (TAI:798)', () => {
  const ins = at('IfLoadedNotEqualTo', 118); // script.s:118 IfLoadedNotEqualTo ABILITY_SOUNDPROOF, ...
  assert.equal(ins.args[0].value, K('ABILITY_SOUNDPROOF'));
  expectJump(ins, mem({ calcTemp: K('ABILITY_SOUNDPROOF') }), false);
  expectJump(ins, mem({ calcTemp: K('ABILITY_LEVITATE') }), true);
});

test('IfLoadedMask (TAI:810)', () => {
  const ins = at('IfLoadedMask', 1194); // script.s:1194 IfLoadedMask BATTLE_TYPE_FRONTIER, ScoreMinus10
  const f = K('BATTLE_TYPE_FRONTIER');
  assert.equal(ins.args[0].value, f);
  expectJump(ins, mem({ calcTemp: f | K('BATTLE_TYPE_TRAINER') }), true);
  expectJump(ins, mem({ calcTemp: K('BATTLE_TYPE_TRAINER') }), false);
});

test('IfLoadedNotMask (TAI:822)', () => {
  const ins = at('IfLoadedNotMask', 895); // script.s:895 IfLoadedNotMask BATTLE_TYPE_DOUBLES, ScoreMinus10
  const d = K('BATTLE_TYPE_DOUBLES');
  assert.equal(ins.args[0].value, d);
  expectJump(ins, mem({ calcTemp: K('BATTLE_TYPE_TRAINER') }), true);
  expectJump(ins, mem({ calcTemp: d | K('BATTLE_TYPE_TRAINER') }), false);
});

test('IfLoadedinTable (TAI:858): scans prog.image to TABLE_END', () => {
  const ins = at('IfLoadedinTable', 1213); // script.s:1213 IfLoadedInTable Basic_FlingItems_Poison, Basic_FlingPoison
  // Table at script.s:1288-1291: HOLD_EFFECT_PSN_USER, HOLD_EFFECT_STRENGTHEN_POISON, TABLE_END.
  const tbl = prog.labels.Basic_FlingItems_Poison;
  assert.equal(ins.word + 3 + ins.args[0].value, tbl.word); // cursor after reads + ofs = first entry
  assert.equal(prog.image[tbl.word + 2], -1); // TABLE_END read as int
  expectJump(ins, mem({ calcTemp: K('HOLD_EFFECT_PSN_USER') }), true);
  expectJump(ins, mem({ calcTemp: K('HOLD_EFFECT_STRENGTHEN_POISON') }), true);
  expectJump(ins, mem({ calcTemp: K('HOLD_EFFECT_BRN_USER') }), false); // next table's entry (script.s:1294)
  expectJump(ins, mem({ calcTemp: -1 }), false); // the terminator ends the scan; never matches
});

test('IfLoadedNotinTable (TAI:876): jump only when no entry matches', () => {
  const ins = at('IfLoadedNotinTable', 1057); // script.s:1057 IfLoadedNotInTable Basic_NaturalGiftBerries, ScoreMinus10
  assert.equal(ins.word + 3 + ins.args[0].value, prog.labels.Basic_NaturalGiftBerries.word);
  expectJump(ins, mem({ calcTemp: K('ITEM_CHERI_BERRY') }), false); // script.s:1062, first entry
  expectJump(ins, mem({ calcTemp: K('ITEM_LEPPA_BERRY') }), false); // script.s:1067
  expectJump(ins, mem({ calcTemp: K('ITEM_LEFTOVERS') }), true);
  expectJump(ins, mem({ calcTemp: -1 }), true);
});

test('IfTempEqualTo (TAI:1078)', () => {
  const ins = at('IfTempEqualTo', 83); // script.s:83 IfTempEqualTo TYPE_ELECTRIC, ScoreMinus12
  assert.equal(ins.args[0].value, K('TYPE_ELECTRIC'));
  expectJump(ins, mem({ calcTemp: K('TYPE_ELECTRIC') }), true);
  expectJump(ins, mem({ calcTemp: K('TYPE_WATER') }), false);
});

test('GoTo (TAI:2561)', () => {
  const ins = at('GoTo', 79); // script.s:79 GoTo Basic_NoImmunityAbility
  const m = mem();
  const ctx = expectJump(ins, m, true);
  assert.equal(ctx.next, prog.labels.Basic_NoImmunityAbility.instr);
  assert.deepEqual(m, mem());
});

test('PopOrEnd (TAI:2568): pop the return stack, else end this move', () => {
  const ins = at('PopOrEnd', 286); // script.s:286
  let m = mem({ stack: [7, 42] });
  let { ctx, draws } = run(ins, m);
  assert.equal(ctx.next, 42);
  assert.deepEqual(m.stack, [7]);
  assert.equal(ctx.done, false);
  assert.equal(draws, 0);
  m = mem();
  ({ ctx, draws } = run(ins, m));
  assert.equal(ctx.done, true);
  assert.equal(ctx.next, ins.index + 1);
  assert.deepEqual(m.stack, []);
  assert.equal(draws, 0);
});

test('runSection: ScoreMinus10 (script.s:1591-1593) subtracts 10 and ends via PopOrEnd', () => {
  const start = prog.labels.ScoreMinus10.instr;
  const m = mem({ moveSlot: 1 });
  const ctx = makeCtx({ prog, ai, mem: m, rand: () => { throw new Error('no draw expected'); } });
  runSection(ctx, start);
  assert.deepEqual(m.moveScore, [100, 90, 100, 100]);
  assert.equal(ctx.done, true);
});
