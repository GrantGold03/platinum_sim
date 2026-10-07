// T041 tests: sim/ai/cmds/battler.mjs. Each opcode runs from a real instruction of
// pokeplatinum/src/battle/trainer_ai/script.s (found by name + script line, so argument decoding is
// parse.mjs's), over a real gen4customgame Battle driven into the needed state with the battle's own
// moves, and a hand-built AI_CONTEXT memory. Battler 1 = the AI (attacker), battler 0 = the player
// (defender), as the adapter defines them.
// Decomp values are cited path:line (PP = pokeplatinum/). Where a state could not be reached with
// moves, the test says "direct state edit".
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle } from '../showdown.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { parseAiScript } from '../ai/parse.mjs';
import { makeCtx, HANDLERS } from '../ai/interp.mjs';
import { handlers as battlerHandlers } from '../ai/cmds/battler.mjs';
import { loadConstants } from '../ai/constants.mjs';

const C = loadConstants();
const K = (n) => C.get(n);
const prog = parseAiScript();
const P = 0; // player = AI_CONTEXT.defender
const A = 1; // AI = AI_CONTEXT.attacker

const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });

function setup(p1, p2, { seed = [1, 2, 3, 4], adapterOpts = {} } = {}) {
  const battle = new Battle({
    formatid: 'gen4customgame', seed,
    p1: { name: 'Player', team: p1 },
    p2: { name: 'AI', team: p2 },
  });
  const ai = createAdapter(battle, adapterOpts);
  return { battle, ai };
}

// AI_CONTEXT memory (include/battle/ai_context.h:9-50 member names).
const newMem = (over = {}) => ({
  move: 0, moveSlot: 0, moveScore: [100, 100, 100, 100], moveDamageRolls: [100, 100, 100, 100], calcTemp: -12345,
  battlerMoves: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
  battlerAbilities: [0, 0, 0, 0], battlerHeldItems: [0, 0, 0, 0], stack: [], ...over,
});

// Scripted RandNext stream (u16 values) with a call counter.
function scriptedRand(values = []) {
  const q = values.slice();
  const r = () => { r.calls++; if (!q.length) throw new Error('test rand stream exhausted'); return q.shift(); };
  r.calls = 0;
  return r;
}

function ctxFor(ai, { mem = newMem(), rand = scriptedRand() } = {}) {
  return makeCtx({ prog, ai, mem, rand });
}

function insAt(name, line) {
  const ins = prog.instructions.find((i) => i.name === name && i.line === line);
  assert.ok(ins, `no ${name} at script.s:${line}`);
  return ins;
}

// Runs one instruction as runSection does (ctx.next defaults to index + 1).
function run(ctx, ins) {
  ctx.next = ins.index + 1;
  HANDLERS[ins.name](ctx, ins);
  return ctx.next;
}
const jumped = (ctx, ins) => run(ctx, ins) === ins.args.find((a) => a.name === 'jump').targetInstr;
const fell = (ctx, ins) => run(ctx, ins) === ins.index + 1;

test('battler.mjs exports exactly the 31 "battler" opcodes of OPCODES.md, all wired into HANDLERS', () => {
  const expected = ['IfHPPercentLessThan', 'IfHPPercentGreaterThan', 'IfHPPercentEqualTo', 'IfHPPercentNotEqualTo',
    'IfStatus', 'IfNotStatus', 'IfVolatileStatus', 'IfNotVolatileStatus', 'IfMoveEffect', 'IfNotMoveEffect',
    'LoadTypeFrom', 'IfSpeedCompareEqualTo', 'LoadBattlerAbility', 'IfStatStageLessThan', 'IfStatStageGreaterThan',
    'IfStatStageEqualTo', 'IfStatStageNotEqualTo', 'IfBattlerUnderEffect', 'LoadHeldItem', 'LoadHeldItemEffect',
    'LoadGender', 'LoadStockpileCount', 'LoadRecycleItem', 'LoadProtectChain', 'IfLevel', 'IfTargetIsNotTaunted',
    'CheckBattlerAbility', 'IfHeldItemEqualTo', 'LoadFlingPower', 'SumPositiveStatStages', 'DiffStatStages'];
  assert.equal(expected.length, 31);
  assert.deepEqual(Object.keys(battlerHandlers).sort(), expected.slice().sort());
  for (const n of expected) assert.equal(HANDLERS[n], battlerHandlers[n], n);
});

test('IfHPPercent*: curHP*100/maxHP truncates (u32); boundary at 50% after Super Fang', () => {
  // AI Garchomp: base HP 108 (PP/res/pokemon/garchomp/data.json:3) -> odd maxHP at L50/31 IV.
  const { battle, ai } = setup(
    [mon('raticate', ['superfang', 'growl', 'tailwhip', 'leer'])],
    [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'earthquake'])],
  );
  let ctx = ctxFor(ai);
  // Full HP: IfHPPercentEqualTo ATTACKER 100 (script.s:2649) jumps; NotEqualTo 100 (:513) does not.
  assert.ok(jumped(ctx, insAt('IfHPPercentEqualTo', 2649)));
  assert.ok(fell(ctx, insAt('IfHPPercentNotEqualTo', 513)));
  assert.ok(jumped(ctx, insAt('IfHPPercentGreaterThan', 1869))); // 100 > 50
  assert.ok(fell(ctx, insAt('IfHPPercentLessThan', 337))); // 100 < 51 false

  battle.makeChoices('move superfang', 'move swordsdance');
  const g = battle.p2.active[0];
  assert.equal(g.maxhp % 2, 1, 'precondition: odd maxHP');
  assert.equal(g.hp, g.maxhp - Math.floor(g.maxhp / 2), 'positive control: Super Fang hit');
  // ceil(m/2)*100/m truncates to exactly 50.
  assert.equal(Math.floor((g.hp * 100) / g.maxhp), 50);
  ctx = ctxFor(ai);
  assert.ok(fell(ctx, insAt('IfHPPercentEqualTo', 2649)));
  assert.ok(jumped(ctx, insAt('IfHPPercentNotEqualTo', 513)));
  assert.ok(fell(ctx, insAt('IfHPPercentGreaterThan', 1869)), '50 > 50 is false');
  assert.ok(jumped(ctx, insAt('IfHPPercentLessThan', 337)), '50 < 51');
  assert.equal(ctx.rand.calls, 0);
  // A partner battler (script.s:6663, doubles-only code) is refused, not mapped to the defender.
  assert.throws(() => run(ctx, insAt('IfHPPercentEqualTo', 6663)), /partner battler/);
});

test('IfStatus / IfNotStatus read the defender status mask after Thunder Wave', () => {
  const { battle, ai } = setup(
    [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'])],
    [mon('starmie', ['thunderwave', 'recover', 'surf', 'psychic'])],
  );
  let ctx = ctxFor(ai);
  assert.ok(fell(ctx, insAt('IfStatus', 290))); // DEFENDER MON_CONDITION_ANY, healthy
  assert.ok(jumped(ctx, insAt('IfNotStatus', 3027))); // DEFENDER not ANY
  battle.makeChoices('move growl', 'move thunderwave');
  assert.equal(battle.p1.active[0].status, 'par', 'positive control: paralysed');
  ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfStatus', 290)));
  assert.ok(jumped(ctx, insAt('IfStatus', 4167))); // DEFENDER PARALYSIS
  assert.ok(fell(ctx, insAt('IfStatus', 1893))); // DEFENDER SLEEP
  assert.ok(jumped(ctx, insAt('IfNotStatus', 324))); // DEFENDER not SLEEP
  assert.ok(jumped(ctx, insAt('IfNotStatus', 2213))); // DEFENDER not TOXIC
  assert.ok(fell(ctx, insAt('IfNotStatus', 3027)));
  assert.ok(fell(ctx, insAt('IfStatus', 1237))); // ATTACKER ANY: AI is healthy
});

test('IfVolatileStatus / IfNotVolatileStatus: Focus Energy, and Torment (bit 31, negative int32 mask)', () => {
  const { battle, ai } = setup(
    [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'])],
    [mon('starmie', ['focusenergy', 'torment', 'surf', 'psychic'])],
  );
  let ctx = ctxFor(ai);
  assert.ok(fell(ctx, insAt('IfVolatileStatus', 594))); // ATTACKER FOCUS_ENERGY
  assert.ok(jumped(ctx, insAt('IfNotVolatileStatus', 6064))); // ATTACKER not FOCUS_ENERGY
  assert.ok(fell(ctx, insAt('IfVolatileStatus', 876))); // DEFENDER TORMENT
  battle.makeChoices('move growl', 'move focusenergy');
  battle.makeChoices('move growl', 'move torment');
  assert.ok(battle.p2.active[0].volatiles.focusenergy, 'positive control: Focus Energy');
  assert.ok(battle.p1.active[0].volatiles.torment, 'positive control: Torment');
  // VOLATILE_CONDITION_TORMENT is (1 << 31) (PP/include/constants/battle/condition.h:63).
  assert.ok(insAt('IfVolatileStatus', 876).args[1].value < 0);
  ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfVolatileStatus', 594)));
  assert.ok(fell(ctx, insAt('IfNotVolatileStatus', 6064)));
  assert.ok(jumped(ctx, insAt('IfVolatileStatus', 876)));
  assert.ok(fell(ctx, insAt('IfVolatileStatus', 599))); // DEFENDER CONFUSION
});

test('IfMoveEffect / IfNotMoveEffect: Leech Seed on the defender', () => {
  const { battle, ai } = setup(
    [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'])],
    [mon('venusaur', ['leechseed', 'ingrain', 'sleeppowder', 'gigadrain'])],
  );
  let ctx = ctxFor(ai);
  assert.ok(fell(ctx, insAt('IfMoveEffect', 641)));
  assert.ok(jumped(ctx, insAt('IfNotMoveEffect', 2222)));
  battle.makeChoices('move growl', 'move leechseed');
  assert.ok(battle.p1.active[0].volatiles.leechseed, 'positive control: seeded');
  battle.makeChoices('move growl', 'move ingrain');
  assert.ok(battle.p2.active[0].volatiles.ingrain, 'positive control: Ingrain');
  ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfMoveEffect', 641))); // DEFENDER LEECH_SEED
  assert.ok(fell(ctx, insAt('IfNotMoveEffect', 2222)));
  assert.ok(jumped(ctx, insAt('IfMoveEffect', 908))); // ATTACKER INGRAIN
  assert.ok(fell(ctx, insAt('IfNotMoveEffect', 2227))); // ATTACKER not INGRAIN
  assert.ok(jumped(ctx, insAt('IfNotMoveEffect', 2233))); // ATTACKER not AQUA_RING
});

test('LoadTypeFrom: battler types, table move type (Hidden Power stays Normal), partner in singles', () => {
  const { ai } = setup(
    [mon('garchomp', ['earthquake', 'growl', 'tailwhip', 'leer'])],
    [mon('starmie', ['hiddenpower', 'recover', 'surf', 'psychic'])],
  );
  const ctx = ctxFor(ai, { mem: newMem({ move: K('MOVE_EARTHQUAKE') }) });
  // Garchomp TYPE_DRAGON / TYPE_GROUND (PP/res/pokemon/garchomp/data.json:10-13),
  // Starmie TYPE_WATER / TYPE_PSYCHIC (PP/res/pokemon/starmie/data.json:10-13).
  run(ctx, insAt('LoadTypeFrom', 521)); assert.equal(ctx.mem.calcTemp, K('TYPE_DRAGON'));
  run(ctx, insAt('LoadTypeFrom', 524)); assert.equal(ctx.mem.calcTemp, K('TYPE_GROUND'));
  run(ctx, insAt('LoadTypeFrom', 681)); assert.equal(ctx.mem.calcTemp, K('TYPE_WATER'));
  run(ctx, insAt('LoadTypeFrom', 683)); assert.equal(ctx.mem.calcTemp, K('TYPE_PSYCHIC'));
  // MOVE_DATA(move).type: earthquake TYPE_GROUND (PP/res/moves/earthquake/data.json:10).
  run(ctx, insAt('LoadTypeFrom', 82)); assert.equal(ctx.mem.calcTemp, K('TYPE_GROUND'));
  // Hidden Power's table type is TYPE_NORMAL (PP/res/moves/hidden_power/data.json:11), not the IV type.
  ctx.mem.move = K('MOVE_HIDDEN_POWER');
  run(ctx, insAt('LoadTypeFrom', 82)); assert.equal(ctx.mem.calcTemp, K('TYPE_NORMAL'));
  // BattleSystem_GetPartner returns the battler itself outside doubles (battle_system.c:400-402).
  run(ctx, insAt('LoadTypeFrom', 6906)); assert.equal(ctx.mem.calcTemp, K('TYPE_WATER'));
  run(ctx, insAt('LoadTypeFrom', 6908)); assert.equal(ctx.mem.calcTemp, K('TYPE_PSYCHIC'));
  assert.equal(ctx.next, insAt('LoadTypeFrom', 6908).index + 1);
  assert.equal(ctx.rand.calls, 0);
});

test('IfSpeedCompareEqualTo: faster/slower without RNG, equal speed draws one RandNext', () => {
  const FASTER = insAt('IfSpeedCompareEqualTo', 1179); // COMPARE_SPEED_FASTER
  const TIE = insAt('IfSpeedCompareEqualTo', 1505); // COMPARE_SPEED_TIE
  const SLOWER = insAt('IfSpeedCompareEqualTo', 1864); // COMPARE_SPEED_SLOWER
  // AI Starmie (base speed 115, PP/res/pokemon/starmie/data.json:6) vs player Blissey.
  {
    const { ai } = setup([mon('blissey', ['softboiled', 'thunderwave', 'trickroom', 'leer'])], [mon('starmie', ['recover', 'surf', 'psychic', 'growl'])]);
    const ctx = ctxFor(ai);
    assert.ok(ai.stat(A, K('BATTLE_STAT_SPEED')) > ai.stat(P, K('BATTLE_STAT_SPEED')));
    assert.ok(jumped(ctx, FASTER));
    assert.ok(fell(ctx, SLOWER));
    assert.ok(fell(ctx, TIE));
    assert.equal(ctx.rand.calls, 0);
    // monSpeedValues side effect (battle_lib.c:1372-1373).
    assert.deepEqual(ctx.mem.monSpeedValues.slice(0, 2), [ai.stat(P, K('BATTLE_STAT_SPEED')), ai.stat(A, K('BATTLE_STAT_SPEED'))]);
  }
  // Paralysis divides by 4 (battle_lib.c:1259-1260): Thunder Wave makes the AI slower.
  {
    const { battle, ai } = setup([mon('blissey', ['softboiled', 'thunderwave', 'trickroom', 'leer'])], [mon('starmie', ['recover', 'surf', 'psychic', 'growl'])]);
    battle.makeChoices('move thunderwave', 'move recover');
    assert.equal(battle.p2.active[0].status, 'par', 'positive control: AI paralysed');
    const ctx = ctxFor(ai);
    assert.ok(jumped(ctx, SLOWER));
    assert.equal(ctx.mem.monSpeedValues[A], Math.floor(ai.stat(A, K('BATTLE_STAT_SPEED')) / 4));
    assert.equal(ctx.rand.calls, 0);
  }
  // Trick Room (battle_lib.c:1432-1439): the slower AI Blissey compares FASTER.
  {
    const { battle, ai } = setup([mon('starmie', ['recover', 'trickroom', 'psychic', 'growl'])], [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'])]);
    const ctx0 = ctxFor(ai);
    assert.ok(jumped(ctx0, SLOWER), 'precondition: slower without Trick Room');
    battle.makeChoices('move trickroom', 'move growl');
    assert.ok(battle.field.pseudoWeather.trickroom, 'positive control: Trick Room up');
    const ctx = ctxFor(ai);
    assert.ok(jumped(ctx, FASTER));
    assert.equal(ctx.rand.calls, 0);
  }
  // Mirror match: equal speed -> RandNext() & 1: 1 -> TIE, 0 -> FASTER (battle_lib.c:1445-1446).
  {
    const team = () => [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'earthquake'])];
    const { ai } = setup(team(), team());
    assert.equal(ai.stat(A, K('BATTLE_STAT_SPEED')), ai.stat(P, K('BATTLE_STAT_SPEED')));
    let ctx = ctxFor(ai, { rand: scriptedRand([0x0001]) });
    assert.ok(jumped(ctx, TIE));
    assert.equal(ctx.rand.calls, 1);
    ctx = ctxFor(ai, { rand: scriptedRand([0xfffe]) });
    assert.ok(fell(ctx, TIE));
    assert.equal(ctx.rand.calls, 1);
    ctx = ctxFor(ai, { rand: scriptedRand([0x0002]) });
    assert.ok(jumped(ctx, FASTER));
    assert.equal(ctx.rand.calls, 1);
  }
  // Choice Scarf x1.5 (battle_lib.c:1248-1250): AI Garchomp (122) vs player Starmie (135) -> 183.
  {
    const p1 = () => [mon('starmie', ['recover', 'surf', 'psychic', 'growl'])];
    let { ai } = setup(p1(), [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'earthquake'])]);
    assert.ok(jumped(ctxFor(ai), SLOWER));
    ({ ai } = setup(p1(), [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'earthquake'], { item: 'choicescarf' })]));
    // HOLD_EFFECT_CHOICE_SPEED (PP/res/items/data/choice_scarf.json:17).
    assert.equal(ai.itemHoldEffect(ai.heldItem(A)), K('HOLD_EFFECT_CHOICE_SPEED'));
    const ctx = ctxFor(ai);
    assert.ok(jumped(ctx, FASTER));
    assert.equal(ctx.mem.monSpeedValues[A], Math.floor(ai.stat(A, K('BATTLE_STAT_SPEED')) * 15 / 10));
  }
});

test('IfSpeedCompareEqualTo: Quick Claw uses speedRand[battler] % (100 / 20) and needs it supplied', () => {
  // Quick Claw: HOLD_EFFECT_SOMETIMES_PRIORITY, effectParam 20 (PP/res/items/data/quick_claw.json:16-17).
  const p1 = () => [mon('starmie', ['recover', 'surf', 'psychic', 'growl'])];
  const p2 = () => [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'], { item: 'quickclaw' })];
  const FASTER = insAt('IfSpeedCompareEqualTo', 1179);
  let { ai } = setup(p1(), p2());
  assert.throws(() => run(ctxFor(ai), FASTER), /speedRand/);
  let speedRand = 5; // 5 % 5 == 0 -> quick claw activates
  ({ ai } = setup(p1(), p2(), { adapterOpts: { speedRand: (b) => (b === A ? speedRand : 0) } }));
  let ctx = ctxFor(ai);
  assert.ok(jumped(ctx, FASTER));
  speedRand = 3; // 3 % 5 != 0 -> slower Blissey stays slower
  ctx = ctxFor(ai);
  assert.ok(fell(ctx, FASTER));
  assert.ok(jumped(ctx, insAt('IfSpeedCompareEqualTo', 1864)));
  assert.equal(ctx.rand.calls, 0);
});

test('LoadBattlerAbility: attacker real; defender from AI memory, trap abilities, or a coin flip', () => {
  const ins69 = insAt('LoadBattlerAbility', 69); // ATTACKER
  const ins71 = insAt('LoadBattlerAbility', 71); // DEFENDER
  // Starmie: ILLUMINATE / NATURAL_CURE (PP/res/pokemon/starmie/data.json:30).
  const { battle, ai } = setup(
    [mon('starmie', ['recover', 'surf', 'psychic', 'growl'], { ability: 'Natural Cure' })],
    [mon('blissey', ['gastroacid', 'growl', 'tailwhip', 'leer'], { ability: 'Serene Grace' })],
  );
  let ctx = ctxFor(ai);
  run(ctx, ins69);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_SERENE_GRACE'));
  assert.equal(ctx.next, ins69.index + 1);
  // Unknown two-ability defender: RandNext() & 1 -> 1 gives ability1, 0 gives ability2 (TAI:1195-1199).
  ctx = ctxFor(ai, { rand: scriptedRand([1]) });
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_ILLUMINATE'));
  assert.equal(ctx.rand.calls, 1);
  ctx = ctxFor(ai, { rand: scriptedRand([2]) });
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_NATURAL_CURE'));
  assert.equal(ctx.rand.calls, 1);
  // Known ability in AI memory wins (even if it is not the real one) and draws nothing.
  ctx = ctxFor(ai, { mem: newMem({ battlerAbilities: [K('ABILITY_ILLUMINATE'), 0, 0, 0] }) });
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_ILLUMINATE'));
  assert.equal(ctx.rand.calls, 0);
  // Gastro Acid -> ABILITY_NONE.
  battle.makeChoices('move growl', 'move gastroacid');
  assert.ok(battle.p1.active[0].volatiles.gastroacid, 'positive control: Gastro Acid');
  ctx = ctxFor(ai, { mem: newMem({ battlerAbilities: [K('ABILITY_NATURAL_CURE'), 0, 0, 0] }) });
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_NONE'));
  assert.equal(ctx.rand.calls, 0);
});

test('LoadBattlerAbility: Arena Trap is read from the truth; a one-ability species draws nothing', () => {
  const ins71 = insAt('LoadBattlerAbility', 71);
  // Dugtrio SAND_VEIL / ARENA_TRAP (PP/res/pokemon/dugtrio/data.json:30).
  let { ai } = setup([mon('dugtrio', ['earthquake', 'growl', 'tailwhip', 'leer'], { ability: 'Arena Trap' })], [mon('blissey', ['growl'])]);
  let ctx = ctxFor(ai);
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_ARENA_TRAP'));
  assert.equal(ctx.rand.calls, 0);
  // Garchomp SAND_VEIL / ABILITY_NONE (PP/res/pokemon/garchomp/data.json:30).
  ({ ai } = setup([mon('garchomp', ['earthquake'], { ability: 'Sand Veil' })], [mon('blissey', ['growl'])]));
  ctx = ctxFor(ai);
  run(ctx, ins71);
  assert.equal(ctx.mem.calcTemp, K('ABILITY_SAND_VEIL'));
  assert.equal(ctx.rand.calls, 0);
});

test('CheckBattlerAbility: AI_HAVE / AI_NOT_HAVE / AI_UNKNOWN without RNG', () => {
  const ins = insAt('CheckBattlerAbility', 441); // DEFENDER, ABILITY_SPEED_BOOST
  // Yanma SPEED_BOOST / COMPOUND_EYES, Ninjask SPEED_BOOST / NONE (PP/res/pokemon/{yanma,ninjask}/data.json:30).
  const check = (species, ability, mem) => {
    const { ai } = setup([mon(species, ['growl'], { ability })], [mon('blissey', ['growl'])]);
    const ctx = ctxFor(ai, { mem });
    run(ctx, ins);
    assert.equal(ctx.rand.calls, 0);
    assert.equal(ctx.next, ins.index + 1);
    return ctx.mem.calcTemp;
  };
  // Two abilities, one of them expected -> pretend unknown (TAI:1242-1247).
  assert.equal(check('yanma', 'Speed Boost'), K('AI_UNKNOWN'));
  // Only ability is Speed Boost.
  assert.equal(check('ninjask', 'Speed Boost'), K('AI_HAVE'));
  // Two abilities, neither expected -> ability1 -> not have.
  assert.equal(check('starmie', 'Natural Cure'), K('AI_NOT_HAVE'));
  // Known in AI memory.
  assert.equal(check('yanma', 'Compound Eyes', newMem({ battlerAbilities: [K('ABILITY_SPEED_BOOST'), 0, 0, 0] })), K('AI_HAVE'));
  assert.equal(check('yanma', 'Speed Boost', newMem({ battlerAbilities: [K('ABILITY_COMPOUND_EYES'), 0, 0, 0] })), K('AI_NOT_HAVE'));
  // ATTACKER (script.s:6927, LEVITATE) reads the real ability.
  const { ai } = setup([mon('starmie', ['growl'])], [mon('gengar', ['growl'], { ability: 'Levitate' })]);
  const ctx = ctxFor(ai);
  run(ctx, insAt('CheckBattlerAbility', 6927));
  assert.equal(ctx.mem.calcTemp, K('AI_HAVE'));
});

test('IfStatStage*: stages 0..12 in BATTLE_STAT order (SPEED is index 3)', () => {
  const { battle, ai } = setup(
    [mon('blissey', ['scaryface', 'doubleteam', 'softboiled', 'leer'])],
    [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'earthquake'])],
  );
  battle.makeChoices('move scaryface', 'move swordsdance');
  battle.makeChoices('move doubleteam', 'move swordsdance');
  battle.makeChoices('move doubleteam', 'move swordsdance');
  const g = battle.p2.active[0];
  assert.equal(g.boosts.atk, 6, 'positive control: +6 Attack');
  assert.equal(g.boosts.spe, -2, 'positive control: -2 Speed');
  assert.equal(battle.p1.active[0].boosts.evasion, 2, 'positive control: +2 evasion');
  const ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfStatStageEqualTo', 350))); // ATTACKER ATK == 12
  assert.ok(jumped(ctx, insAt('IfStatStageGreaterThan', 346))); // ATK > 8
  assert.ok(fell(ctx, insAt('IfStatStageLessThan', 480))); // ATK < 6
  assert.ok(jumped(ctx, insAt('IfStatStageLessThan', 482))); // SPEED (4) < 6
  assert.ok(fell(ctx, insAt('IfStatStageEqualTo', 371))); // SPEED == 12
  assert.ok(fell(ctx, insAt('IfStatStageGreaterThan', 489))); // DEFENDER SPEED > 6
  assert.ok(jumped(ctx, insAt('IfStatStageGreaterThan', 493))); // DEFENDER EVASION (8) > 6
  assert.ok(jumped(ctx, insAt('IfStatStageNotEqualTo', 1479))); // DEFENDER EVASION != 0
  assert.ok(fell(ctx, insAt('IfStatStageEqualTo', 463))); // DEFENDER EVASION == 0
  assert.equal(ctx.rand.calls, 0);
});

test('SumPositiveStatStages / DiffStatStages', () => {
  const { battle, ai } = setup(
    [mon('garchomp', ['swordsdance', 'dragondance', 'protect', 'leer'])],
    [mon('blissey', ['scaryface', 'swordsdance', 'softboiled', 'growl'])],
  );
  battle.makeChoices('move swordsdance', 'move scaryface');
  battle.makeChoices('move dragondance', 'move softboiled');
  const p = battle.p1.active[0];
  assert.deepEqual([p.boosts.atk, p.boosts.spe], [3, -1], 'positive control: player +3 Atk, -1 Spe');
  const ctx = ctxFor(ai);
  run(ctx, insAt('SumPositiveStatStages', 5926)); // DEFENDER
  assert.equal(ctx.mem.calcTemp, 3, 'negative stages are not counted');
  run(ctx, insAt('DiffStatStages', 1395)); // DEFENDER ATTACK - ATTACKER ATTACK
  assert.equal(ctx.mem.calcTemp, 3);
  run(ctx, insAt('DiffStatStages', 1400)); // SP_ATTACK
  assert.equal(ctx.mem.calcTemp, 0);
  battle.makeChoices('move leer', 'move swordsdance');
  battle.makeChoices('move leer', 'move swordsdance');
  assert.equal(battle.p2.active[0].boosts.atk, 4, 'positive control: AI +4 Atk');
  run(ctx, insAt('DiffStatStages', 1395));
  assert.equal(ctx.mem.calcTemp, -1);
  assert.equal(ctx.next, insAt('DiffStatStages', 1395).index + 1);
});

test('IfBattlerUnderEffect: Disable and Encore turn counters', () => {
  // AI Blissey is slower than the player's Garchomp, so the player has a last move to disable.
  const { battle, ai } = setup(
    [mon('garchomp', ['swordsdance', 'protect', 'dragonclaw', 'leer'])],
    [mon('blissey', ['disable', 'encore', 'softboiled', 'leer'])],
    { seed: [5, 6, 7, 8] }, // Disable (80% accuracy in Gen 4) hits with this seed
  );
  let ctx = ctxFor(ai);
  assert.ok(fell(ctx, insAt('IfBattlerUnderEffect', 652)));
  assert.ok(fell(ctx, insAt('IfBattlerUnderEffect', 657)));
  battle.makeChoices('move swordsdance', 'move disable');
  assert.ok(battle.p1.active[0].volatiles.disable, 'positive control: Disable');
  ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfBattlerUnderEffect', 652))); // CHECK_DISABLE
  assert.ok(fell(ctx, insAt('IfBattlerUnderEffect', 657))); // CHECK_ENCORE
  battle.makeChoices('move leer', 'move encore');
  assert.ok(battle.p1.active[0].volatiles.encore, 'positive control: Encore');
  assert.ok(jumped(ctx, insAt('IfBattlerUnderEffect', 657)));
});

test('LoadHeldItem (truth) vs LoadHeldItemEffect / IfHeldItemEqualTo (AI memory for the player)', () => {
  const { ai } = setup(
    [mon('starmie', ['recover'], { item: 'leftovers' })],
    [mon('blissey', ['softboiled'], { item: 'shinystone' })],
  );
  const LEFTOVERS = K('ITEM_LEFTOVERS');
  const SHINY = K('ITEM_SHINY_STONE');
  let ctx = ctxFor(ai);
  run(ctx, insAt('LoadHeldItem', 902)); // DEFENDER: real item even though unrevealed
  assert.equal(ctx.mem.calcTemp, LEFTOVERS);
  run(ctx, insAt('LoadHeldItem', 1056)); // ATTACKER
  assert.equal(ctx.mem.calcTemp, SHINY);
  // DEFENDER hold effect from AI memory: ITEM_NONE -> HOLD_EFFECT_NONE (PP/res/items/data/none.json).
  run(ctx, insAt('LoadHeldItemEffect', 3412));
  assert.equal(ctx.mem.calcTemp, K('HOLD_EFFECT_NONE'));
  ctx.mem.battlerHeldItems[P] = LEFTOVERS;
  run(ctx, insAt('LoadHeldItemEffect', 3412));
  // HOLD_EFFECT_HP_RESTORE_GRADUAL (PP/res/items/data/leftovers.json:17).
  assert.equal(ctx.mem.calcTemp, K('HOLD_EFFECT_HP_RESTORE_GRADUAL'));
  run(ctx, insAt('LoadHeldItemEffect', 1212)); // ATTACKER: real Shiny Stone, HOLD_EFFECT_NONE (shiny_stone.json:17)
  assert.equal(ctx.mem.calcTemp, K('HOLD_EFFECT_NONE'));
  // IfHeldItemEqualTo: own side real item, other side AI memory.
  ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfHeldItemEqualTo', 1176))); // ATTACKER SHINY_STONE
  const { ai: ai2 } = setup([mon('starmie', ['recover'], { item: 'shinystone' })], [mon('blissey', ['softboiled'])]);
  ctx = ctxFor(ai2);
  assert.ok(fell(ctx, insAt('IfHeldItemEqualTo', 1169)), 'player holds it but the AI does not know');
  ctx.mem.battlerHeldItems[P] = SHINY;
  assert.ok(jumped(ctx, insAt('IfHeldItemEqualTo', 1169)));
  assert.equal(ctx.rand.calls, 0);
});

test('LoadFlingPower: item fling power, 0 under Embargo', () => {
  const { battle, ai } = setup(
    [mon('starmie', ['embargo', 'recover', 'surf', 'psychic'])],
    [mon('blissey', ['softboiled', 'growl', 'tailwhip', 'leer'], { item: 'quickclaw' })],
  );
  const ins = insAt('LoadFlingPower', 1204); // ATTACKER
  let ctx = ctxFor(ai);
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, 80); // PP/res/items/data/quick_claw.json:20
  battle.makeChoices('move embargo', 'move growl');
  assert.ok(battle.p2.active[0].volatiles.embargo, 'positive control: Embargo');
  ctx = ctxFor(ai);
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, 0); // Battler_ItemFlingPower (battle_lib.c:5491-5495)
});

test('LoadGender / LoadStockpileCount / LoadRecycleItem', () => {
  const { battle, ai } = setup(
    [mon('starmie', ['thunderwave', 'recover', 'surf', 'psychic'])],
    [mon('blissey', ['stockpile', 'growl', 'tailwhip', 'leer'], { item: 'lumberry', gender: 'F' })],
  );
  const ctx = ctxFor(ai);
  run(ctx, insAt('LoadGender', 736)); // ATTACKER
  assert.equal(ctx.mem.calcTemp, K('GENDER_FEMALE')); // generated/genders.txt:2
  run(ctx, insAt('LoadGender', 742)); // DEFENDER: Starmie is genderless
  assert.equal(ctx.mem.calcTemp, K('GENDER_NONE'));
  run(ctx, insAt('LoadStockpileCount', 837));
  assert.equal(ctx.mem.calcTemp, 0);
  run(ctx, insAt('LoadRecycleItem', 913));
  assert.equal(ctx.mem.calcTemp, K('ITEM_NONE'));
  battle.makeChoices('move thunderwave', 'move stockpile');
  battle.makeChoices('move recover', 'move stockpile');
  assert.equal(battle.p2.active[0].item, '', 'positive control: Lum Berry consumed');
  run(ctx, insAt('LoadStockpileCount', 837));
  assert.equal(ctx.mem.calcTemp, 2);
  run(ctx, insAt('LoadRecycleItem', 913));
  assert.equal(ctx.mem.calcTemp, K('ITEM_LUM_BERRY'));
  run(ctx, insAt('LoadRecycleItem', 1189)); // DEFENDER: nothing consumed
  assert.equal(ctx.mem.calcTemp, K('ITEM_NONE'));
});

test('LoadProtectChain: protectSuccessTurns only while the last move is Protect/Detect/Endure', () => {
  const { battle, ai } = setup(
    [mon('starmie', ['recover', 'surf', 'psychic', 'growl'])],
    [mon('garchomp', ['protect', 'swordsdance', 'dragonclaw', 'earthquake'])],
  );
  const ins = insAt('LoadProtectChain', 3545); // ATTACKER
  const ctx = ctxFor(ai);
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, 0);
  battle.makeChoices('move growl', 'move protect');
  assert.ok(battle.p2.active[0].volatiles.stall, 'positive control: Protect succeeded');
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, 1);
  battle.makeChoices('move growl', 'move swordsdance');
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, 0, 'last move is Swords Dance');
  run(ctx, insAt('LoadProtectChain', 4931)); // DEFENDER never protected
  assert.equal(ctx.mem.calcTemp, 0);
});

test('IfLevel / IfTargetIsNotTaunted', () => {
  const { battle, ai } = setup(
    [mon('starmie', ['recover', 'surf', 'psychic', 'growl'], { level: 60 })],
    [mon('blissey', ['taunt', 'growl', 'tailwhip', 'leer'])],
  );
  let ctx = ctxFor(ai);
  assert.ok(jumped(ctx, insAt('IfLevel', 563))); // CHECK_LOWER_THAN_TARGET: 50 < 60
  const { ai: same } = setup([mon('starmie', ['recover'])], [mon('blissey', ['growl'])]);
  assert.ok(fell(ctxFor(same), insAt('IfLevel', 563)), '50 < 50 is false');
  const notTaunted = insAt('IfTargetIsNotTaunted', 3129);
  assert.ok(jumped(ctx, notTaunted));
  battle.makeChoices('move growl', 'move taunt');
  assert.ok(battle.p1.active[0].volatiles.taunt, 'positive control: Taunt');
  ctx = ctxFor(ai);
  assert.ok(fell(ctx, notTaunted));
  assert.equal(ctx.rand.calls, 0);
});
