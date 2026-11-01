// T039 tests: sim/ai/adapter.mjs answers in decomp encodings, checked against Showdown's own state.
// Decomp values are copied from pokeplatinum/ files and cited (path:line). Enum values are the
// 0-based position in the generated/*.txt list (line - 1; none of the lists used here has `=`).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle, Dex } from '../showdown.mjs';
import { createAdapter, decompTables } from '../ai/adapter.mjs';
import { loadConstants } from '../ai/constants.mjs';

const C = loadConstants();
const K = (n) => C.get(n);
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });

function makeBattle() {
  return new Battle({
    formatid: 'gen4customgame',
    seed: [1, 2, 3, 4],
    p1: { name: 'Player', team: [
      mon('garchomp', ['swordsdance', 'stealthrock', 'raindance', 'earthquake'], { item: 'leftovers', ability: 'Sand Veil' }),
      mon('blissey', ['softboiled', 'toxic', 'seismictoss', 'protect'], { ability: 'Natural Cure' }),
    ] },
    p2: { name: 'AI', team: [
      mon('blissey', ['toxic', 'leechseed', 'softboiled', 'thunderwave'], { ability: 'Natural Cure' }),
      mon('garchomp', ['earthquake', 'dragonclaw', 'swordsdance', 'protect'], { ability: 'Sand Veil' }),
    ] },
  });
}

test('constants: generated enums number from 0 in file order (positive controls)', () => {
  assert.equal(K('SPECIES_GARCHOMP'), 445); // generated/species.txt:446
  assert.equal(K('MOVE_EARTHQUAKE'), 89); // generated/moves.txt:90
  assert.equal(K('TYPE_DRAGON'), 16); // generated/pokemon_types.txt:17
  assert.equal(K('ITEM_LEFTOVERS'), 234); // generated/items.txt:235
  assert.equal(K('HOLD_EFFECT_HP_RESTORE_GRADUAL'), 69); // generated/item_hold_effects.txt:70
  assert.equal(K('SIDE_CONDITION_STEALTH_ROCK'), 1 << 7); // constants/battle/condition.h:95
  assert.equal(K('VOLATILE_CONDITION_TORMENT'), (1 << 31) | 0); // condition.h:63, int32
  assert.equal(K('AI_BATTLER_ATTACKER_PARTNER'), 3); // constants/battle/trainer_ai.h:31-32 (1 ^ 2)
  assert.equal(K('DEFAULT_STAT_STAGE'), 6); // constants/battle/battle_script.h:5
});

test('decomp move/item/species tables', () => {
  const T = decompTables();
  // res/moves/earthquake/data.json:9-11
  assert.equal(T.moves[89].power, 100);
  assert.equal(T.moves[89].type, K('TYPE_GROUND'));
  assert.equal(T.moves[89].class, K('CLASS_PHYSICAL'));
  // res/items/data/leftovers.json:17,20
  assert.equal(T.items[234].holdEffect, 69);
  assert.equal(T.items[234].flingPower, 10);
  // res/pokemon/garchomp/data.json:10,30
  assert.deepEqual(T.species[445].types, [16, 4]);
  assert.deepEqual(T.species[445].abilities, [K('ABILITY_SAND_VEIL'), 0]);
});

test('every decomp move/ability matches Showdown by num; every Showdown-known item too', () => {
  const T = decompTables();
  const dex = Dex.mod('gen4');
  const toID = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  const renamed = [];
  let moves = 0;
  for (const m of T.moves) {
    if (!m || m.id === 0) continue;
    moves++;
    const s = dex.moves.all().find((x) => x.num === m.id);
    assert.ok(s, `no Showdown move with num ${m.id} (${m.constant})`);
    if (toID(s.name) !== toID(m.name)) renamed.push(`${m.name}->${s.name}`);
  }
  assert.equal(moves, 467); // generated/moves.txt: MOVE_POUND (:2) .. MOVE_SHADOW_FORCE (:468)
  // Name differences are renames only (decomp names from res/moves/*/data.json "name").
  assert.deepEqual(renamed.sort(), ['Faint Attack->Feint Attack', 'Hi Jump Kick->High Jump Kick', 'SmellingSalt->Smelling Salts', 'ViceGrip->Vise Grip']);
  for (const e of C.lists.get('abilities')) {
    if (e.value === 0 || !e.name.startsWith('ABILITY_')) continue;
    const a = dex.abilities.all().find((x) => x.num === e.value);
    assert.ok(a && toID(a.name) === toID(e.name.slice(8)), e.name);
  }
  let items = 0;
  for (const it of T.items) {
    if (!it) continue;
    const s = dex.items.get(toID(it.name));
    if (!s.exists) continue; // non-battle items (potions, balls) are not in Showdown
    items++;
    assert.equal(s.num, it.id, it.constant);
  }
  assert.ok(items > 150, `items matched: ${items}`);
});

test('battler ids, BattleMon fields and turn counters track Showdown', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const [P, A] = [0, 1];
  assert.equal(ai.pokemon(P), battle.p1.active[0]);
  assert.equal(ai.pokemon(A), battle.p2.active[0]);
  assert.equal(ai.pokemon(2), null);
  assert.equal(ai.exists(3), false);
  assert.equal(ai.side(P), 0);
  assert.equal(ai.side(A), 1);
  assert.equal(ai.species(P), 445);
  assert.deepEqual(ai.types(P), [16, 4]); // same as res/pokemon/garchomp/data.json:10
  assert.deepEqual(ai.types(A), [0, 0]); // res/pokemon/blissey/data.json:10
  assert.deepEqual(ai.moves(P), [K('MOVE_SWORDS_DANCE'), K('MOVE_STEALTH_ROCK'), K('MOVE_RAIN_DANCE'), 89]);
  assert.equal(ai.heldItem(P), 234);
  assert.equal(ai.itemHoldEffect(ai.heldItem(P)), 69);
  assert.equal(ai.ability(P), K('ABILITY_SAND_VEIL')); // Showdown slot 0 ability
  assert.equal(ai.curHP(A), battle.p2.active[0].hp);
  assert.equal(ai.stat(P, K('BATTLE_STAT_SPEED')), battle.p1.active[0].storedStats.spe);
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6);
  assert.equal(ai.ppCur(P, 0), battle.p1.active[0].moveSlots[0].pp);
  // First decision: totalTurns 0, leads have fakeOutTurnNumber 0.
  assert.equal(battle.turn, 1);
  assert.equal(ai.totalTurns(), 0);
  assert.equal(ai.moveEffectsData(A).fakeOutTurnNumber, 0);
  assert.equal(ai.movePrevByBattler(P), 0);

  battle.makeChoices('move swordsdance', 'move toxic');
  assert.equal(ai.totalTurns(), 1);
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6 + battle.p1.active[0].boosts.atk);
  assert.equal(battle.p1.active[0].boosts.atk, 2, 'positive control: Swords Dance applied');
  assert.equal(ai.movePrevByBattler(P), K('MOVE_SWORDS_DANCE'));
  // Toxic: Showdown status 'tox' -> MON_CONDITION_TOXIC (condition.h:14).
  // With this seed Toxic hits (positive control); after one residual the counter is 1
  // (MON_CONDITION_TOXIC_COUNTER_0 = 1 << 8, condition.h:15).
  assert.equal(battle.p1.active[0].status, 'tox');
  assert.equal(ai.status(P), K('MON_CONDITION_TOXIC') | K('MON_CONDITION_TOXIC_COUNTER_0'));

  battle.makeChoices('move stealthrock', 'move leechseed');
  assert.ok(battle.p2.sideConditions.stealthrock, 'positive control: Stealth Rock set on p2');
  assert.ok(ai.sideConditionsMask(1) & K('SIDE_CONDITION_STEALTH_ROCK'));
  assert.equal(ai.sideConditionsMask(0) & K('SIDE_CONDITION_STEALTH_ROCK'), 0);
  // Leech Seed hits with this seed; the bit is on the seeded mon (subscript_leech_seed_start.s:15)
  // and LEECH_SEED_RECIPIENT (moves.h:8-9) holds the seeder's battler id, 1.
  assert.ok(battle.p1.active[0].volatiles.leechseed, 'positive control: seeded');
  assert.equal(ai.moveEffectsMask(P), K('MOVE_EFFECT_LEECH_SEED') | 1);
  assert.equal(ai.moveEffectsMask(A), 0);

  battle.makeChoices('move raindance', 'move softboiled');
  assert.equal(battle.field.weather, 'raindance');
  assert.ok(ai.fieldConditionsMask() & K('FIELD_CONDITION_RAINING_TEMP')); // move weather has a duration
  assert.equal(ai.fieldConditionsMask() & K('FIELD_CONDITION_RAINING_PERM'), 0);
  // Soft-Boiled at full HP fails in Showdown -> movePrevByBattler MOVE_NONE (game clears it when
  // the move did not succeed, battle_controller_player.c:3944-3948).
  assert.equal(battle.p2.active[0].lastMove.id, 'softboiled');
  assert.equal(battle.p2.active[0].moveLastTurnResult, false);
  assert.equal(ai.movePrevByBattler(A), 0);
  assert.equal(ai.movePrevByBattler(P), K('MOVE_RAIN_DANCE'));
  assert.equal(ai.totalTurns(), 3);

  // Switch: party order stays in game order; the incoming mon's fakeOutTurnNumber is
  // totalTurns + 1 at the switch (battle_lib.c:2117) = 4 here.
  battle.makeChoices('switch 2', 'move toxic');
  assert.equal(battle.p1.active[0].species.id, 'blissey');
  assert.equal(ai.selectedPartySlot(P), 1);
  assert.equal(ai.party(P)[0].species, 445);
  assert.equal(ai.party(P)[1].species, 242); // generated/species.txt:243
  assert.equal(ai.moveEffectsData(P).fakeOutTurnNumber, 4);
  assert.equal(ai.totalTurns(), 4);
  // => AICmd_LoadIsFirstTurnInBattle (trainer_ai.c:2480-2492): fakeOut < totalTurns is false -> TRUE.
  assert.equal(ai.moveEffectsData(P).fakeOutTurnNumber < ai.totalTurns(), false);
  // The AI's own lead has been in since turn 0: not its first turn.
  assert.equal(ai.moveEffectsData(A).fakeOutTurnNumber < ai.totalTurns(), true);
  // Stat stages reset for the new mon.
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6);
});

test('Showdown status and volatiles map to condition.h bits', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const p = battle.p1.active[0];
  // Set states directly (read-only adapter: this only checks the encoding).
  p.setStatus('par');
  assert.equal(ai.status(0), K('MON_CONDITION_PARALYSIS'));
  p.addVolatile('substitute');
  p.addVolatile('focusenergy');
  const v = ai.statusVolatile(0);
  assert.ok(v & K('VOLATILE_CONDITION_SUBSTITUTE'));
  assert.ok(v & K('VOLATILE_CONDITION_FOCUS_ENERGY'));
  assert.equal(v & K('VOLATILE_CONDITION_CONFUSION'), 0);
  battle.p2.addSideCondition('reflect', battle.p2.active[0]);
  assert.ok(ai.sideConditionsMask(1) & K('SIDE_CONDITION_REFLECT'));
  battle.field.addPseudoWeather('trickroom', battle.p2.active[0]);
  assert.ok(ai.fieldConditionsMask() & K('FIELD_CONDITION_TRICK_ROOM'));
  assert.equal(ai.fieldConditionsMask() & K('FIELD_CONDITION_GRAVITY'), 0);
});

// ---------------------------------------------------------------------------------------------
// Feature 015: per-decision cache of the damage-formula inputs (contracts/adapter-api.md).

test('015 damageInput: deep-equals fromShowdown for every pair and move; cached within a decision; fresh after beginDecision', async () => {
  const { fromShowdown } = await import('../damage.mjs');
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const mons = [...battle.p1.pokemon, ...battle.p2.pokemon];
  const MOVES = [['earthquake', { power: 100, type: 'TYPE_GROUND', powerMul: 10 }], ['toxic', { power: 0, type: 'TYPE_POISON', powerMul: 10 }],
    ['hiddenpower', { power: 70, type: 'TYPE_ICE', powerMul: 10 }], [89, { power: 0, type: undefined, powerMul: 10 }]];
  let pairs = 0;
  for (const a of mons) for (const d of mons) for (const [mv, o] of MOVES) {
    assert.deepEqual(ai.damageInput(a, d, mv, o), fromShowdown(battle, a, d, mv, o));
    pairs++;
  }
  assert.equal(pairs, 4 * 4 * MOVES.length);
  // (b) cached: the same struct object comes back; builds do not grow, hits do
  const [a, d] = [battle.p1.active[0], battle.p2.active[0]];
  const s0 = { ...ai.cacheStats };
  const i1 = ai.damageInput(a, d, 'earthquake', MOVES[0][1]);
  const i2 = ai.damageInput(a, d, 'earthquake', MOVES[0][1]);
  assert.equal(i1.attacker, i2.attacker);
  assert.equal(i1.defender, i2.defender);
  assert.equal(ai.cacheStats.builds, s0.builds, 'no new build for a repeated pair');
  assert.equal(ai.cacheStats.hits, s0.hits + 4, "two calls, attacker and defender each");
  assert.equal(ai.cacheStats.builds, mons.length, 'one build per Pokemon in the decision, regardless of calls');
  // (c) control: a change to the battle without beginDecision is NOT seen (the cache really caches) ...
  a.boosts.atk = 2;
  const stale = ai.damageInput(a, d, 'earthquake', MOVES[0][1]);
  assert.equal(stale.attacker.stages.atk, 0);
  assert.equal(fromShowdown(battle, a, d, 'earthquake', MOVES[0][1]).attacker.stages.atk, 2);
  // ... and is seen after beginDecision
  const dec0 = ai.cacheStats.decisions;
  ai.beginDecision();
  assert.equal(ai.cacheStats.decisions, dec0 + 1);
  const fresh = ai.damageInput(a, d, 'earthquake', MOVES[0][1]);
  assert.equal(fresh.attacker.stages.atk, 2);
  assert.deepEqual(fresh, fromShowdown(battle, a, d, 'earthquake', MOVES[0][1]));
  assert.equal(ai.cacheStats.builds, mons.length + 2, 'the two structs were rebuilt after beginDecision');
  a.boosts.atk = 0;
  // (d) non-singles throws like fromShowdown
  const gt = battle.gameType;
  battle.gameType = 'doubles';
  assert.throws(() => ai.damageInput(a, d, 'earthquake', MOVES[0][1]), /only singles/);
  assert.throws(() => fromShowdown(battle, a, d, 'earthquake', MOVES[0][1]), /only singles/);
  battle.gameType = gt;
  assert.throws(() => ai.damageInput(a, d, 99999, MOVES[0][1]), /no decomp move/);
});

test('015 freeze guard: with PLATSIM_AI_FREEZE=1 a write to a cached struct throws TypeError; without it, it does not (control)', async () => {
  const { spawnSync } = await import('node:child_process');
  const script = `
    import { Battle } from ${JSON.stringify(new URL('../showdown.mjs', import.meta.url).href)};
    import { createAdapter } from ${JSON.stringify(new URL('../ai/adapter.mjs', import.meta.url).href)};
    const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
    const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });
    const battle = new Battle({ formatid: 'gen4customgame', seed: [1, 2, 3, 4],
      p1: { name: 'P', team: [mon('garchomp', ['earthquake'], { ability: 'Sand Veil' })] },
      p2: { name: 'AI', team: [mon('blissey', ['toxic'], { ability: 'Natural Cure' })] } });
    const ai = createAdapter(battle);
    const o = { power: 100, type: 'TYPE_GROUND', powerMul: 10 };
    const inp = ai.damageInput(battle.p1.active[0], battle.p2.active[0], 'earthquake', o);
    // 016: the plan and pre-variance memos are frozen too
    const plan = ai.typeChartPlan(battle.p1.active[0], battle.p2.active[0], 'earthquake', o);
    const pv = ai.preVariance(battle.p1.active[0], battle.p2.active[0], 'earthquake', o, 0);
    const results = [];
    for (const f of [() => { inp.attacker.hp = 1; }, () => { inp.field.defenderSide.reflect = true; }, () => { inp.field.abilitiesOnField.push('x'); },
      () => { plan.steps.push({ op: 'x2' }); }, () => { pv.damage = 1; }]) {
      try { f(); results.push('no throw'); } catch (e) { results.push(e.constructor.name); }
    }
    console.log(results.join(','));
  `;
  const run = (env) => spawnSync(process.execPath, ['--input-type=module', '-e', script], { env: { ...process.env, ...env }, encoding: 'utf8' });
  const on = run({ PLATSIM_AI_FREEZE: '1', PLATSIM_AI_CHECK: '' });
  assert.equal(on.status, 0, on.stderr);
  assert.equal(on.stdout.trim(), 'TypeError,TypeError,TypeError,TypeError,TypeError');
  const off = run({ PLATSIM_AI_FREEZE: '', PLATSIM_AI_CHECK: '' });
  assert.equal(off.status, 0, off.stderr);
  assert.equal(off.stdout.trim(), 'no throw,no throw,no throw,no throw,no throw');
});

// Feature 016 (FR-005, FR-006): the trainer AI's pre-variance damage and the type-chart plan, memoised per decision
// on the cached input structs (contracts/adapter-api.md).
test('016 preVariance / typeChartPlan: equal to the direct computation on the cached inputs; memoised per decision; dropped by beginDecision', async () => {
  const { typeChartPlan, replayTypeChart, calcBaseDamage } = await import('../damage.mjs');
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const [a, d] = [battle.p1.active[0], battle.p2.active[0]];
  const CASES = [['earthquake', { power: 100, type: 'TYPE_GROUND', powerMul: 10 }, 0], ['toxic', { power: 0, type: 'TYPE_POISON', powerMul: 10 }, 0],
    ['dragonrage', { power: 0, type: 'TYPE_DRAGON', powerMul: 10 }, 40], [89, { power: 0, type: undefined, powerMul: 10 }, 0]];
  for (const [mv, o, fixed] of CASES) {
    const input = ai.damageInput(a, d, mv, o);
    const ignore = fixed !== 0;
    const direct = typeChartPlan(input, { ignoreTypeChecks: ignore, moveStatusMask: 0 });
    assert.deepEqual(ai.typeChartPlan(a, d, mv, o, { ignoreTypeChecks: ignore }), direct, `plan ${mv}`);
    const r = replayTypeChart(direct, fixed === 0 ? calcBaseDamage({ ...input, critMul: 1 }) : fixed);
    assert.deepEqual(ai.preVariance(a, d, mv, o, fixed), { damage: r.damage, moveStatusMask: r.moveStatusMask }, `preVariance ${mv}`);
  }
  // memoised: the same object comes back, no new build, hits grow
  const s0 = { ...ai.cacheStats };
  const p1 = ai.preVariance(a, d, 'earthquake', CASES[0][1], 0);
  const p2 = ai.preVariance(a, d, 'earthquake', CASES[0][1], 0);
  assert.equal(p1, p2);
  assert.equal(ai.cacheStats.preVariance, s0.preVariance, 'no new pre-variance build for a repeated call');
  assert.equal(ai.cacheStats.preVarianceHits, s0.preVarianceHits + 2);
  const q1 = ai.typeChartPlan(a, d, 'earthquake', CASES[0][1]);
  const q2 = ai.typeChartPlan(a, d, 'earthquake', CASES[0][1]);
  assert.equal(q1, q2);
  assert.equal(ai.cacheStats.plans, s0.plans, 'no new plan for a repeated call');
  assert.ok(ai.cacheStats.planHits >= s0.planHits + 2);
  // a different fixed damage or type is a different entry
  assert.notEqual(ai.preVariance(a, d, 'earthquake', CASES[0][1], 40), p1);
  assert.notEqual(ai.preVariance(a, d, 'earthquake', { ...CASES[0][1], type: 'TYPE_FIRE' }, 0), p1);
  // dropped by beginDecision: rebuilt (new object, equal value)
  const b0 = ai.cacheStats.preVariance;
  ai.beginDecision();
  const p3 = ai.preVariance(a, d, 'earthquake', CASES[0][1], 0);
  assert.notEqual(p3, p1);
  assert.deepEqual(p3, p1);
  assert.equal(ai.cacheStats.preVariance, b0 + 1);
  // non-singles throws like damageInput
  const gt = battle.gameType;
  battle.gameType = 'doubles';
  assert.throws(() => ai.preVariance(a, d, 'earthquake', CASES[0][1], 0), /only singles/);
  battle.gameType = gt;
});

test('016 CHECK mode: one Aaron battle per policy compares every memo hit (checks > 0, 0 mismatches); a corrupted memo is reported; off by default', async () => {
  const { spawnSync } = await import('node:child_process');
  const url = (p) => JSON.stringify(new URL(p, import.meta.url).href);
  const run = (script, env) => spawnSync(process.execPath, ['--input-type=module', '-e', script], { env: { ...process.env, ...env }, encoding: 'utf8', timeout: 300000 });
  const clean = `
    import { gd } from ${url('./ai_fixtures.mjs')};
    import { runGauntlet } from ${url('../gauntlet.mjs')};
    import { benchRequests } from ${url('../bench.mjs')};
    import { CHECK_STATS } from ${url('../ai/adapter.mjs')};
    for (const policy of ['expectimax2-v2', 'expectimax2-v1']) {
      const [req] = benchRequests({ n: 1, teams: ['bench'], trainers: ['aaron'], policy });
      runGauntlet(gd, req);
    }
    console.log(JSON.stringify(CHECK_STATS));
  `;
  const on = run(clean, { PLATSIM_AI_CHECK: '1', PLATSIM_AI_FREEZE: '' });
  assert.equal(on.status, 0, on.stderr);
  const stats = JSON.parse(on.stdout.trim().split('\n').pop());
  assert.ok(stats.checks > 0, `checks ${stats.checks}`);
  assert.equal(stats.mismatches, 0);
  const corrupt = `
    import { Battle } from ${url('../showdown.mjs')};
    import { createAdapter } from ${url('../ai/adapter.mjs')};
    const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
    const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });
    const battle = new Battle({ formatid: 'gen4customgame', seed: [1, 2, 3, 4],
      p1: { name: 'P', team: [mon('garchomp', ['earthquake'], { ability: 'Sand Veil' })] },
      p2: { name: 'AI', team: [mon('blissey', ['toxic'], { ability: 'Natural Cure' })] } });
    const ai = createAdapter(battle);
    const [a, d] = [battle.p1.active[0], battle.p2.active[0]];
    const o = { power: 100, type: 'TYPE_GROUND', powerMul: 10 };
    const e = ai.preVariance(a, d, 'earthquake', o, 0);
    e.damage = e.damage + 1;
    ai.preVariance(a, d, 'earthquake', o, 0);
    console.log('no throw');
  `;
  const bad = run(corrupt, { PLATSIM_AI_CHECK: '1', PLATSIM_AI_FREEZE: '' });
  assert.notEqual(bad.status, 0, 'the corrupted memo must be reported');
  assert.match(bad.stderr, /CHECK mismatch preVariance/);
  const off = run(corrupt, { PLATSIM_AI_CHECK: '', PLATSIM_AI_FREEZE: '' });
  assert.equal(off.status, 0, off.stderr);
  assert.equal(off.stdout.trim(), 'no throw');
});

test('015 Constants.get fast path: a cold instance and a warmed one agree on every symbol; errors unchanged', async () => {
  const { Constants } = await import('../ai/constants.mjs');
  const warm = loadConstants();
  const cold = new Constants(warm.root);
  cold.defs = warm.defs; cold.lists = warm.lists; // same definitions, empty memo
  let n = 0, same = 0, throws = 0;
  for (const name of warm.defs.keys()) {
    n++;
    let w, c, we, ce;
    try { w = warm.get(name); w = warm.get(name); } catch (e) { we = e.message; }
    try { c = cold.get(name); } catch (e) { ce = e.message; }
    if (we || ce) { assert.equal(we, ce, name); throws++; continue; }
    assert.equal(c, w, name);
    assert.equal(typeof w, 'number', `${name} is a number (the memo never holds undefined)`);
    same++;
  }
  assert.ok(n > 1000 && same > 1000, `${n} symbols, ${same} equal, ${throws} throw on both`);
  for (const v of warm.values.values()) assert.notEqual(v, undefined);
  assert.throws(() => warm.get('NO_SUCH_SYMBOL_015'), /unknown symbol NO_SUCH_SYMBOL_015/);
  assert.throws(() => cold.get('NO_SUCH_SYMBOL_015'), /unknown symbol NO_SUCH_SYMBOL_015/);
  const cyc = new Constants(warm.root);
  cyc.define('X015_A', { expr: 'X015_B', src: 'test' });
  cyc.define('X015_B', { expr: 'X015_A', src: 'test' });
  assert.throws(() => cyc.get('X015_A'), /recursive definition X015_A -> X015_B -> X015_A/);
});

// Feature 016 (FR-008): the Showdown-id -> decomp-number mappers are built once per (dex, decomp tables) and shared
// by every adapter; a shared set equals a freshly built one over every identifier the decomp knows.
test('016 shared mappers: shared == fresh over every engine identifier the decomp knows; same errors; one set per dex', async () => {
  const { makeMappers } = await import('../ai/adapter.mjs');
  const { ENUMS } = await import('../damage.mjs');
  const battle = makeBattle();
  const T = decompTables();
  const fresh = makeMappers(battle.dex, T);
  const a = createAdapter(battle), b = createAdapter(battle);
  assert.equal(a.mappers, b.mappers, 'two adapters on the same dex share one mapper set');
  assert.notEqual(a.mappers, fresh);
  const toID = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
  let n = 0;
  for (const m of battle.dex.moves.all()) if (m.num > 0 && T.moves[m.num]) { assert.equal(a.mappers.move(m.id), fresh.move(m.id), m.id); n++; }
  for (const ab of battle.dex.abilities.all()) if (ab.num > 0 && C.nameOf('abilities', ab.num)) { assert.equal(a.mappers.ability(ab.id), fresh.ability(ab.id), ab.id); n++; }
  for (const it of battle.dex.items.all()) if (it.num > 0 && T.items[it.num] && toID(T.items[it.num].name) === it.id) { assert.equal(a.mappers.item(it.id), fresh.item(it.id), it.id); n++; }
  const TYPES = ENUMS.types.filter((t) => t.startsWith('TYPE_')); // the list ends with the count sentinel
  for (const t of TYPES) {
    const name = t === 'TYPE_MYSTERY' ? '???' : t.slice(5)[0] + t.slice(6).toLowerCase();
    assert.equal(a.mappers.type(name), fresh.type(name), name); n++;
  }
  for (const p of [...battle.p1.pokemon, ...battle.p2.pokemon]) { assert.equal(a.mappers.species(p.species), fresh.species(p.species), p.species.id); n++; }
  assert.ok(n > 700, `${n} identifiers compared`);
  assert.equal(a.mappers.move(''), 0); assert.equal(a.mappers.ability(''), 0); assert.equal(a.mappers.item(''), 0);
  // unknown identifiers: same message on both
  const msg = (f) => { try { f(); return 'no throw'; } catch (e) { return e.message; } };
  for (const [kind, id] of [['move', 'notamove'], ['ability', 'notanability'], ['item', 'notanitem'], ['type', 'Fairy']]) {
    const s = msg(() => a.mappers[kind](id)), f = msg(() => fresh[kind](id));
    assert.notEqual(s, 'no throw', `${kind} ${id} must throw`);
    assert.equal(s, f);
  }
  // positive control: the lookups above went through the shared set's own Maps
  assert.ok(a.mappers.caches.move.size > 300 && a.mappers.caches.type.size === TYPES.length, `shared caches: ${a.mappers.caches.move.size} moves, ${a.mappers.caches.type.size} types`);
});
