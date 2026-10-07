// T043 tests: damage-group AI opcodes (sim/ai/cmds/damage.mjs) and the AI damage estimator
// (sim/ai/calcdamage.mjs). TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c.
//
// Every opcode test runs a real `ins` from parseAiScript() (found by name + script.s line) on a
// real gen4customgame Battle through the adapter. Stats used in the hand arithmetic are Showdown's
// storedStats of the built mons; the test asserts them first, so a changed stat formula fails
// loudly rather than silently changing the expected numbers.
//
// Hand arithmetic follows BattleSystem_CalcMoveDamage (battle_lib.c:6601-7079):
//   base = ((atk * power * (2*L/5 + 2)) / def) / 50 + 2   (all integer divisions; L = 50 -> 22)
// then the type chart (battle_lib.c:2560-2679: STAB *15/10, then each chart entry), then
// TrainerAI_CalcDamage's BattleSystem_Divide(damage * variance, 100) (TAI:3109).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Battle } from '../showdown.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { parseAiScript } from '../ai/parse.mjs';
import { makeCtx, HANDLERS } from '../ai/interp.mjs';
import { DECOMP_ROOT } from '../ai/constants.mjs';
import * as cd from '../ai/calcdamage.mjs';

const prog = parseAiScript();
const insAt = (name, line) => {
  const ins = prog.instructions.find((i) => i.name === name && i.line === line);
  if (!ins) throw new Error(`no ${name} at script.s:${line}`);
  return ins;
};

const IV31 = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const EV0 = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, x = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs: IV31, evs: EV0, item: '', ...x });
const BRONZONG = mon('bronzong', ['gyroball', 'explosion', 'hiddenpower', 'earthquake'], { ability: 'Levitate' });
const SNORLAX = mon('snorlax', ['bodyslam', 'rest', 'curse', 'crunch'], { ability: 'Thick Fat' });

function setup({ player = [SNORLAX], ai = [BRONZONG], randVals = [], mem = {} } = {}) {
  const battle = new Battle({ formatid: 'gen4customgame', seed: [1, 2, 3, 4], p1: { name: 'P', team: player }, p2: { name: 'AI', team: ai } });
  const adapter = createAdapter(battle);
  const draws = [];
  const queue = randVals.slice();
  const rand = () => {
    if (!queue.length) throw new Error('test rand exhausted');
    const v = queue.shift();
    draws.push(v);
    return v;
  };
  const m = { move: 0, moveSlot: 0, moveScore: [100, 100, 100, 100], moveDamageRolls: [100, 100, 100, 100], calcTemp: 0,
    monSpeedValues: [100, 20, 0, 0], ...mem };
  const ctx = makeCtx({ prog, ai: adapter, mem: m, rand });
  return { battle, ai: adapter, ctx, draws, K: (n) => adapter.constants.get(n) };
}
const run = (ctx, ins) => { ctx.next = ins.index + 1; HANDLERS[ins.name](ctx, ins); return ctx.next; };
const calc = (s, moveName, extra = {}) => {
  const a = s.ai.attacker;
  return cd.calcDamage(s.ctx, { move: s.K(moveName), heldItem: s.ai.heldItem(a), ivs: s.ai.ivs(a), attacker: a,
    ability: s.ai.battlerAbility(a), embargoTurns: 0, variance: 100, ...extra });
};

// L50, Serious, 31 IVs, 0 EVs (asserted in the first test).
const BRONZONG_ATK = 109, BRONZONG_SPA = 99, SNORLAX_DEF = 85, SNORLAX_SPD = 130, SNORLAX_ATK = 130;

test('battle fixture stats (inputs to the hand arithmetic)', () => {
  const s = setup();
  assert.deepEqual(s.battle.p2.active[0].storedStats, { atk: 109, def: 136, spa: 99, spd: 136, spe: 53 });
  assert.deepEqual(s.battle.p1.active[0].storedStats, { atk: 130, def: 85, spa: 85, spd: 130, spe: 50 });
  assert.equal(s.ai.attacker, 1);
  assert.equal(s.ai.defender, 0);
});

test('tables parsed from the decomp (positive controls)', () => {
  const K = setup().K;
  // TAI:32 first entry, TAI:44 last entry before 0xFFFF (TAI:45).
  assert.equal(cd.NO_DAMAGE_CALC_EFFECTS.names[0], 'BATTLE_EFFECT_HALVE_DEFENSE');
  assert.equal(cd.NO_DAMAGE_CALC_EFFECTS.names.at(-1), 'BATTLE_EFFECT_RECOIL_HALF');
  assert.equal(cd.NO_DAMAGE_CALC_EFFECTS.names.length, 13);
  // TAI:49 .. TAI:59
  assert.equal(cd.ALT_POWER_EFFECTS.names[0], 'BATTLE_EFFECT_RANDOM_POWER_BASED_ON_IVS');
  assert.equal(cd.ALT_POWER_EFFECTS.names.at(-1), 'BATTLE_EFFECT_INCREASE_POWER_WITH_WEIGHT');
  assert.equal(cd.ALT_POWER_EFFECTS.names.length, 11);
  // include/data/battle/weight_to_power.h:2-7
  assert.deepEqual(cd.WEIGHT_TO_POWER, [[100, 20], [250, 40], [500, 60], [1000, 80], [2000, 100], [0xFFFF, 0xFFFF]]);
  // TAI:2898-2964 (16 HOLD_EFFECT_ARCEUS_* cases); first: FIGHTING -> TYPE_FIGHTING
  assert.deepEqual(cd.JUDGMENT_TYPES[0], ['HOLD_EFFECT_ARCEUS_FIGHTING', 'TYPE_FIGHTING']);
  assert.equal(K('BATTLE_EFFECT_HALVE_DEFENSE'), 7); // generated/move_battle_effects.txt:8
});

test('drawMoveDamageRolls: 100 - RandNext() % 16 for each of 4 slots (TAI:236-241)', () => {
  const vals = [0, 15, 16, 0xFFFF];
  const draws = [];
  const rolls = cd.drawMoveDamageRolls(() => { const v = vals[draws.length]; draws.push(v); return v; });
  // 0%16=0 ->100; 15 -> 85; 16%16=0 -> 100; 65535%16=15 -> 85
  assert.deepEqual(rolls, [100, 85, 100, 85]);
  assert.equal(draws.length, 4);
});

test('TrainerAI_CalcDamage: Explosion has a value but is excluded by CalcAllDamage (TAI:31-45, 2808-2836)', () => {
  const s = setup();
  // Explosion (res/moves/explosion/data.json: power 250, BATTLE_EFFECT_HALVE_DEFENSE, normal, physical):
  // calcDamage itself does not filter; defense halved (battle_lib.c:6943-6945) 85 -> 42.
  // 109*250 = 27250; *22 = 599500; /42 = 14273; /50 = 285; +2 = 287; Bronzong not Normal -> no STAB.
  assert.equal(calc(s, 'MOVE_EXPLOSION'), Math.trunc(Math.trunc(BRONZONG_ATK * 250 * 22 / Math.trunc(SNORLAX_DEF / 2)) / 50) + 2);
  assert.equal(calc(s, 'MOVE_EXPLOSION'), 287);
  const all = cd.calcAllDamage(s.ctx, { attacker: 1, moves: s.ai.moves(1), heldItem: 0, ivs: s.ai.ivs(1),
    ability: s.ai.battlerAbility(1), embargoTurns: 0, varyDamage: 0 });
  // slot order: gyroball, explosion, hiddenpower, earthquake. Explosion is slot 1.
  assert.equal(all.damageVals[1], 0);
  assert.equal(all.max, 109);
  assert.equal(s.draws.length, 0);
});

test('TrainerAI_CalcDamage: Hidden Power power/type from the IVs argument (TAI:2973-2993)', () => {
  const s = setup();
  // All IVs 31: bit1 set in all six -> 63 -> 63*40/63+30 = 70; bit0 set in all six -> 63*15/63+1 = 16,
  // >= TYPE_MYSTERY (9, generated/pokemon_types.txt:10) -> 17 = TYPE_DARK (pokemon_types.txt:18).
  // Special: 99*70 = 6930; *22 = 152460; /130 = 1172; /50 = 23; +2 = 25; Dark vs Normal neutral, no STAB.
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER'), Math.trunc(Math.trunc(Math.trunc(BRONZONG_SPA * 70 * 22 / SNORLAX_SPD) / 50)) + 2);
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER'), 25);
  assert.equal(cd.moveType(s.ctx, 1, s.K('MOVE_HIDDEN_POWER')), s.K('TYPE_DARK'));
  // IVs all 30: bit1 set -> power 70; bit0 clear -> type 0*15/63+1 = 1 = TYPE_FIGHTING (pokemon_types.txt:2).
  // Base as above = 25, then Fighting vs Normal x2 (battle_lib.c:2440): 25*20/10 = 50.
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER', { ivs: [30, 30, 30, 30, 30, 30] }), 50);
  // IVs all 0: power 30, Fighting: 99*30=2970*22=65340/130=502/50=10+2=12, x2 = 24.
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER', { ivs: [0, 0, 0, 0, 0, 0] }), 24);
});

test('TrainerAI_CalcDamage: Hidden Power power is exact (sensitive to +-1 power)', () => {
  // L100 Alakazam (Psychic; Dark HP is not STAB) so one power point moves the result by ~2.
  const s = setup({ ai: [mon('alakazam', ['hiddenpower'], { level: 100, ability: 'Synchronize' })] });
  const spa = s.battle.p2.active[0].storedStats.spa;
  assert.equal(spa, 306); // base 135 (res/pokemon/alakazam/data.json:7) -> 2*135+31 + 5 at L100
  const lvl = Math.trunc(2 * 100 / 5) + 2; // 42
  // IVs [31, 31, 30, 31, 30, 31] (HP, Atk, Def, Spe, SpA, SpD): bit1 set in all -> power 70;
  // bit0 = 1,1,0,1,0,1 -> 1 + 2 + 8 + 32 = 43 -> 43*15/63 + 1 = 11 -> >= 9 -> 12 = TYPE_GRASS
  // (generated/pokemon_types.txt:13). Grass vs Normal neutral.
  const ivs = [31, 31, 30, 31, 30, 31];
  const exp70 = Math.trunc(Math.trunc(spa * 70 * lvl / SNORLAX_SPD) / 50) + 2;
  // 306*70 = 21420; *42 = 899640; /130 = 6920; /50 = 138; +2 = 140
  assert.equal(exp70, 140);
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER', { ivs }), 140);
  // IVs with bit1 only in HP: power = 1*40/63 + 30 = 30; type 0 -> 1 = Fighting, x2 vs Normal.
  const exp30 = (Math.trunc(Math.trunc(spa * 30 * lvl / SNORLAX_SPD) / 50) + 2) * 2; // 385560/130 = 2965; /50 = 59; +2 = 61; x2 = 122
  assert.equal(calc(s, 'MOVE_HIDDEN_POWER', { ivs: [2, 0, 0, 0, 0, 0] }), exp30);
  assert.equal(exp30, 122);
});

test('TrainerAI_CalcDamage: Gyro Ball uses monSpeedValues (TAI:2995-3003)', () => {
  const s = setup({ mem: { monSpeedValues: [100, 20, 0, 0] } });
  // power = 1 + 25*100/20 = 126. Physical Steel: 109*126 = 13734; *22 = 302148; /85 = 3554; /50 = 71; +2 = 73;
  // STAB (Bronzong Steel, res/pokemon/bronzong/data.json:10) 73*15/10 = 109; Steel vs Normal neutral.
  assert.equal(calc(s, 'MOVE_GYRO_BALL'), 109);
  // Cap: 1 + 25*200/10 = 501 -> 150: 109*150=16350*22=359700/85=4231/50=84+2=86, *15/10 = 129.
  s.ctx.mem.monSpeedValues = [200, 10, 0, 0];
  assert.equal(calc(s, 'MOVE_GYRO_BALL'), 129);
  // Missing speeds: refuses instead of guessing.
  delete s.ctx.mem.monSpeedValues;
  assert.throws(() => calc(s, 'MOVE_GYRO_BALL'), /monSpeedValues/);
});

test('TrainerAI_CalcDamage: fixed damage ignores STAB/effectiveness but not immunity (TAI:3005-3016, 3093, 3104)', () => {
  const machamp = mon('machamp', ['seismictoss', 'nightshade', 'dragonrage', 'psywave'], { ability: 'Guts' });
  const s = setup({ ai: [machamp], randVals: [0xFFFF] });
  // Seismic Toss = level 50 (Fighting vs Normal would be x2, ignored); roll 85 -> Divide(4250, 100) = 42.
  assert.equal(calc(s, 'MOVE_SEISMIC_TOSS'), 50);
  assert.equal(calc(s, 'MOVE_SEISMIC_TOSS', { variance: 85 }), 42);
  // Night Shade (Ghost) vs Normal: TYPE_MULTI_IMMUNE (battle_lib.c:2490) still flags INEFFECTIVE -> 0.
  assert.equal(calc(s, 'MOVE_NIGHT_SHADE'), 0);
  // Dragon Rage = 40.
  assert.equal(calc(s, 'MOVE_DRAGON_RAGE'), 40);
  // Psywave draws one value: 50 * (65535 % 11 + 5) / 10 = 50 * 13 / 10 = 65 (65535 = 11*5957 + 8).
  assert.equal(calc(s, 'MOVE_PSYWAVE'), 65);
  assert.deepEqual(s.draws, [0xFFFF]);
});

test('TrainerAI_CalcDamage: Low Kick / Grass Knot power from defender weight (TAI:3055-3072)', () => {
  const s = setup();
  // Snorlax weight: res/pokemon/snorlax/data.json:134 weight_pounds 1014.1 -> round(1014.1*0.45359237*10)
  // = 4600 hg (tools/dataproc/src/speciesproc.c:696, 735-752). > 2000 -> table end -> power 120.
  assert.equal(cd.speciesWeightHg('SPECIES_SNORLAX'), 4600);
  assert.equal(s.battle.p1.active[0].getWeight(), 4600); // cross-check only (Showdown)
  // Physical Fighting 120: 109*120=13080*22=287760/85=3385/50=67+2=69; x2 vs Normal (battle_lib.c:2440) = 138.
  assert.equal(calc(s, 'MOVE_LOW_KICK'), 138);
  // Pikachu: res/pokemon/pikachu/data.json:112 weight_pounds 13.2 -> round(59.87) = 60 hg <= 100 -> power 20.
  assert.equal(cd.speciesWeightHg('SPECIES_PIKACHU'), 60);
  const p = setup({ player: [mon('pikachu', ['thundershock'], { ability: 'Static' })] });
  const pk = p.battle.p1.active[0].storedStats;
  // Grass Knot special Grass 20 vs Electric: chart has no Grass->Electric entry: neutral.
  const expected = Math.trunc(Math.trunc(BRONZONG_SPA * 20 * 22 / pk.spd) / 50) + 2;
  assert.equal(calc(p, 'MOVE_GRASS_KNOT'), expected);
});

test('FlagMoveDamageScore (TAI:1012-1066), script.s:62', () => {
  const ins = insAt('FlagMoveDamageScore', 62);
  assert.equal(ctxArg(ins, 'bool'), 0); // USE_MAX_DAMAGE (constants/battle/trainer_ai.h:45)
  const s = setup();
  const { ctx, K } = s;
  // Damage: gyroball 109, explosion excluded (0), hidden power 25, earthquake 58.
  ctx.mem.move = K('MOVE_GYRO_BALL'); ctx.mem.moveSlot = 0;
  assert.equal(run(ctx, ins), ins.index + 1);
  assert.equal(ctx.mem.calcTemp, K('AI_MOVE_IS_HIGHEST_DAMAGE'));
  ctx.mem.move = K('MOVE_EARTHQUAKE'); ctx.mem.moveSlot = 3;
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, K('AI_NOT_HIGHEST_DAMAGE'));
  ctx.mem.move = K('MOVE_EXPLOSION'); ctx.mem.moveSlot = 1;
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, K('AI_NO_COMPARISON_MADE'));
  // Make Earthquake (58) the strict max: gyro power 1 + 25*1/1 = 26 -> 24.
  ctx.mem.monSpeedValues = [1, 1, 0, 0];
  ctx.mem.move = K('MOVE_EARTHQUAKE'); ctx.mem.moveSlot = 3;
  run(ctx, ins);
  assert.equal(ctx.mem.calcTemp, K('AI_MOVE_IS_HIGHEST_DAMAGE'));
  assert.equal(s.draws.length, 0);
});

test('FlagMoveDamageScore: a tie counts as highest ("no move does strictly more")', () => {
  const s = setup({ ai: [mon('bronzong', ['earthquake', 'earthquake', 'explosion', 'hiddenpower'], { ability: 'Levitate' })] });
  s.ctx.mem.move = s.K('MOVE_EARTHQUAKE'); s.ctx.mem.moveSlot = 1;
  run(s.ctx, insAt('FlagMoveDamageScore', 62));
  assert.equal(s.ctx.mem.calcTemp, s.K('AI_MOVE_IS_HIGHEST_DAMAGE'));
});

test('IfCurrentMoveKills (TAI:1525-1567), script.s:6358, kill check at low HP', () => {
  const ins = insAt('IfCurrentMoveKills', 6358);
  const s = setup();
  const { ctx, K, battle } = s;
  const target = ins.args.find((a) => a.name === 'jump').targetInstr;
  ctx.mem.move = K('MOVE_EARTHQUAKE'); ctx.mem.moveSlot = 3;
  // 109*100=10900*22=239800/85=2821/50=56+2=58 (Ground vs Normal neutral, no STAB)
  assert.equal(Math.trunc(Math.trunc(BRONZONG_ATK * 100 * 22 / SNORLAX_DEF) / 50) + 2, 58);
  assert.equal(run(ctx, ins), ins.index + 1); // 235 HP
  battle.p1.active[0].hp = 59;
  assert.equal(run(ctx, ins), ins.index + 1);
  battle.p1.active[0].hp = 58; // curHP <= damage
  assert.equal(run(ctx, ins), target);
  battle.p1.active[0].hp = 1;
  ctx.mem.move = K('MOVE_EXPLOSION'); ctx.mem.moveSlot = 1; // ineligible: never jumps
  assert.equal(run(ctx, ins), ins.index + 1);
  assert.equal(s.draws.length, 0);
});

test('IfCurrentMoveKills with ROLL_FOR_DAMAGE uses moveDamageRolls[moveSlot]', () => {
  // Real script with only the argument changed, so the ins comes from the real parser.
  const text = readFileSync(join(DECOMP_ROOT, 'src/battle/trainer_ai/script.s'), 'utf8').split('\n');
  assert.equal(text[6357].trim(), 'IfCurrentMoveKills USE_MAX_DAMAGE, EvalAttack_ApplyKillBonuses');
  text[6357] = '    IfCurrentMoveKills ROLL_FOR_DAMAGE, EvalAttack_ApplyKillBonuses';
  const p2 = parseAiScript({ scriptText: text.join('\n') });
  const ins = p2.instructions.find((i) => i.line === 6358);
  assert.equal(ins.args[0].value, 1); // ROLL_FOR_DAMAGE (constants/battle/trainer_ai.h:46)
  const s = setup({ mem: { moveDamageRolls: [100, 100, 100, 85] } });
  const ctx = makeCtx({ prog: p2, ai: s.ai, mem: s.ctx.mem, rand: s.ctx.rand });
  ctx.mem.move = s.K('MOVE_EARTHQUAKE'); ctx.mem.moveSlot = 3;
  // Divide(58*85, 100) = 49
  s.battle.p1.active[0].hp = 50;
  assert.equal(run(ctx, ins), ins.index + 1);
  s.battle.p1.active[0].hp = 49;
  assert.equal(run(ctx, ins), ins.args[1].targetInstr);
});

test('IfMoveEffectivenessEquals (TAI:1311-1346): BASE, IMMUNE, DOUBLE, mapped STAB*2 and STAB/2', () => {
  const immune = insAt('IfMoveEffectivenessEquals', 68);
  const double = insAt('IfMoveEffectivenessEquals', 97);
  const half = insAt('IfMoveEffectivenessEquals', 1830);
  assert.equal(immune.args[0].text, 'TYPE_MULTI_IMMUNE');
  assert.equal(double.args[0].text, 'TYPE_MULTI_DOUBLE_DAMAGE');
  assert.equal(half.args[0].text, 'TYPE_MULTI_HALF_DAMAGE');
  const jumped = (ctx, ins) => run(ctx, ins) === ins.args[1].targetInstr;

  // Earthquake vs Snorlax: 40 (no STAB, neutral) = TYPE_MULTI_BASE_DAMAGE: none of the three jumps.
  let s = setup();
  s.ctx.mem.move = s.K('MOVE_EARTHQUAKE');
  assert.equal(jumped(s.ctx, immune), false);
  assert.equal(jumped(s.ctx, double), false);
  assert.equal(jumped(s.ctx, half), false);

  // vs Gengar (Ghost/Poison, Levitate: res/pokemon/gengar/data.json:10, 30): Earthquake -> LEVITATED -> IMMUNE.
  s = setup({ player: [mon('gengar', ['shadowball'], { ability: 'Levitate' })] });
  s.ctx.mem.move = s.K('MOVE_EARTHQUAKE');
  assert.equal(jumped(s.ctx, immune), true);
  // Hidden Power (Dark from 31 IVs) vs Ghost x2 (battle_lib.c:2499): 40 -> 80 = DOUBLE directly.
  s.ctx.mem.move = s.K('MOVE_HIDDEN_POWER');
  assert.equal(jumped(s.ctx, double), true);
  assert.equal(jumped(s.ctx, immune), false);

  // Gyro Ball (Steel, STAB) vs Golem (Rock/Ground, golem/data.json:10): 40*15/10 = 60, x2 (battle_lib.c:2506)
  // = 120 = STAB*2 -> TYPE_MULTI_DOUBLE_DAMAGE.
  s = setup({ player: [mon('golem', ['rockslide'], { ability: 'Sturdy' })] });
  s.ctx.mem.move = s.K('MOVE_GYRO_BALL');
  assert.equal(jumped(s.ctx, double), true);
  // Gyro Ball vs Skarmory (Steel/Flying, skarmory/data.json:10): 60 * 5/10 (battle_lib.c:2507) = 30 = STAB/2 -> HALF.
  s = setup({ player: [mon('skarmory', ['spikes'], { ability: 'Keen Eye' })] });
  s.ctx.mem.move = s.K('MOVE_GYRO_BALL');
  assert.equal(jumped(s.ctx, half), true);
  assert.equal(s.draws.length, 0);
});

test('IfPartyMemberDealsMoreDamage (TAI:2106-2174), script.s:5118', () => {
  const ins = insAt('IfPartyMemberDealsMoreDamage', 5118);
  const target = ins.args.find((a) => a.name === 'jump').targetInstr;
  // Active Bronzong max vs Snorlax with speeds [1,1]: Earthquake 58.
  // Machamp's Low Kick computed with attacker = AI_CONTEXT.attacker (Bronzong's stats/types): 138 > 58.
  const strong = mon('machamp', ['lowkick', 'bulkup', 'protect', 'rest'], { ability: 'Guts' });
  let s = setup({ ai: [BRONZONG, strong], mem: { monSpeedValues: [1, 1, 0, 0] } });
  assert.equal(run(s.ctx, ins), target);
  // Fainted party member is skipped.
  s.battle.p2.pokemon[1].hp = 0;
  assert.equal(run(s.ctx, ins), ins.index + 1);

  // Weak set: Seismic Toss = the ACTIVE battler's level (50), Dragon Rage 40, Sonic Boom 20, Psywave draws.
  const weak = mon('machamp', ['seismictoss', 'dragonrage', 'sonicboom', 'psywave'], { ability: 'Guts' });
  // rand 0: Psywave = 50*5/10 = 25 -> max 50 < 58 -> no jump.
  s = setup({ ai: [BRONZONG, weak], randVals: [0], mem: { monSpeedValues: [1, 1, 0, 0] } });
  assert.equal(run(s.ctx, ins), ins.index + 1);
  assert.deepEqual(s.draws, [0]);
  // rand 65535: Psywave = 50*13/10 = 65 > 58 -> jump.
  s = setup({ ai: [BRONZONG, weak], randVals: [0xFFFF], mem: { monSpeedValues: [1, 1, 0, 0] } });
  assert.equal(run(s.ctx, ins), target);
  assert.deepEqual(s.draws, [0xFFFF]);
});

test('IfHasSuperEffectiveMove (TAI:2176-2185, AI_HasSuperEffectiveMove TAI:3560)', () => {
  const ins = insAt('IfHasSuperEffectiveMove', 5106);
  // vs Snorlax: Steel/Normal/Dark/Ground all neutral -> no jump.
  let s = setup();
  assert.equal(run(s.ctx, ins), ins.index + 1);
  // vs Gengar: Hidden Power Dark is SE vs Ghost (battle_lib.c:2499) -> jump; no RNG with flag TRUE.
  s = setup({ player: [mon('gengar', ['shadowball'], { ability: 'Levitate' })] });
  assert.equal(run(s.ctx, ins), ins.args[0].targetInstr);
  assert.equal(s.draws.length, 0);
});

test('IfBattlerDealsMoreDamage (TAI:2187-2241), script.s:5528: defender = AI_CONTEXT.defender (trap 4)', () => {
  const ins = insAt('IfBattlerDealsMoreDamage', 5528);
  assert.equal(ins.args[0].text, 'AI_BATTLER_DEFENDER');
  const target = ins.args[2].targetInstr;
  const s = setup({ mem: { monSpeedValues: [1, 1, 0, 0] } }); // AI max = Earthquake 58
  // No previous move: MOVE_NONE (res/moves/none/data.json: physical, Normal, power 0) is still computed:
  // 0 + 2 = 2, Snorlax STAB 2*15/10 = 3 -> 3 < 58 -> no jump.
  assert.equal(s.ai.movePrevByBattler(0), 0);
  assert.equal(cd.calcDamage(s.ctx, { move: 0, heldItem: 0, ivs: s.ai.ivs(1), attacker: 0, ability: s.ai.battlerAbility(0),
    embargoTurns: 0, variance: 100 }), 3);
  assert.equal(run(s.ctx, ins), ins.index + 1);
  // Snorlax uses Body Slam (a real turn). Computed vs Snorlax itself (AI_CONTEXT.defender):
  // 130*85 = 11050; *22 = 243100; /85 = 2860; /50 = 57; +2 = 59; STAB 59*15/10 = 88 > 58 -> jump.
  s.battle.makeChoices('move bodyslam', 'move hiddenpower');
  assert.equal(s.ai.movePrevByBattler(0), s.K('MOVE_BODY_SLAM'));
  assert.equal(Math.trunc((Math.trunc(Math.trunc(SNORLAX_ATK * 85 * 22 / SNORLAX_DEF) / 50) + 2) * 15 / 10), 88);
  assert.equal(run(s.ctx, ins), target);
});

function ctxArg(ins, name) { return ins.args.find((a) => a.name === name).value; }
