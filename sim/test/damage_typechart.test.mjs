// Feature 016 (FR-004, SC-004): the type-chart plan replayed per roll equals the per-roll reference.
//
// `applyTypeChart` (plan + replay) is compared with `applyTypeChartDirect` (the per-roll body as of main 19519ed,
// kept as the reference, Constitution VI) over two generated layers (spec Clarifications 2026-11-01):
//   - synthetic matchups in the damage port's input shape, every field drawn independently from a seeded PRNG,
//     with scenario templates so every rule is exercised at least 100 times (coverage counters below);
//   - real-data matchups: species types, abilities, moves (power > 0) and items from the decomp tables.
// For every matchup and each of the 16 damage rolls both sides must agree on damage, status mask and total
// multiplier. A positive control shows that a plan with one step removed or a STAB step flipped is detected.
// `calcDamage` (one plan per call) is checked against a 16-fold direct computation, normal and critical.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  applyTypeChart, applyTypeChartDirect, typeChartPlan, replayTypeChart, calcDamage, calcBaseDamage,
  applyScriptMultipliers, applyVariance, critMultiplier, DAMAGE_STATS, ENUMS, MOVE_STATUS, moveData, itemData,
} from '../damage.mjs';
import { decompTables } from '../ai/adapter.mjs';

const SEED = 0x016c0de;
const N_SYNTH = 20000;
const N_REAL = 1500;

function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(SEED);
const ri = (n) => Math.floor(rng() * n);
const pick = (arr) => arr[ri(arr.length)];
const chance = (p) => rng() < p;

const T = decompTables();
const MOVE_CONSTS = T.moves.filter(Boolean).map((m) => m.constant).filter((c) => c !== 'MOVE_NONE');
const TYPES = ENUMS.types.filter((t) => t !== 'TYPE_MYSTERY');
const ABILITIES = ['ABILITY_LEVITATE', 'ABILITY_WONDER_GUARD', 'ABILITY_FILTER', 'ABILITY_SOLID_ROCK', 'ABILITY_TINTED_LENS',
  'ABILITY_ADAPTABILITY', 'ABILITY_SCRAPPY', 'ABILITY_MOLD_BREAKER', 'ABILITY_NORMALIZE', 'ABILITY_KLUTZ', 'ABILITY_INTIMIDATE',
  'ABILITY_PRESSURE', 'ABILITY_SAND_VEIL', 'ABILITY_NATURAL_CURE', 'ABILITY_BLAZE', 'ABILITY_TORRENT', 'ABILITY_THICK_FAT',
  'ABILITY_HUGE_POWER', 'ABILITY_SNIPER', 'ABILITY_SUPER_LUCK', 'ABILITY_BATTLE_ARMOR', 'ABILITY_NONE'];
const ITEMS = ['ITEM_NONE', 'ITEM_EXPERT_BELT', 'ITEM_IRON_BALL', 'ITEM_LIFE_ORB', 'ITEM_ORAN_BERRY', 'ITEM_LEFTOVERS',
  'ITEM_CHOICE_BAND', 'ITEM_CHARCOAL', 'ITEM_WISE_GLASSES', 'ITEM_METRONOME', 'ITEM_SCOPE_LENS'];
for (const a of ABILITIES) assert.ok(ENUMS.abilities.includes(a), a);
for (const i of ITEMS) itemData(i); // throws if the decomp has no data file
const SPECIES_CONSTS = T.species.filter(Boolean).map((s) => s.constant);
const STATUSES = ['', '', '', 'brn', 'par', 'psn', 'tox', 'slp', 'frz'];
const WEATHERS = ['', '', 'sun', 'rain', 'sand', 'hail', 'fog'];

function synthBattler() {
  const t1 = pick(TYPES);
  const t2 = chance(0.25) ? t1 : pick(TYPES);
  const flag = () => chance(1 / 8);
  return {
    species: pick(SPECIES_CONSTS), level: 1 + ri(100), types: [t1, t2],
    stats: { atk: 20 + ri(400), def: 20 + ri(400), spa: 20 + ri(400), spd: 20 + ri(400) },
    stages: { atk: ri(13) - 6, def: ri(13) - 6, spa: ri(13) - 6, spd: ri(13) - 6 },
    hp: 1 + ri(400), maxhp: 401,
    ability: pick(ABILITIES), abilitySuppressed: flag(), item: pick(ITEMS), embargo: flag(),
    status: pick(STATUSES), gender: pick(['M', 'F', 'N']),
    flashFire: flag(), charge: flag(), helpingHand: flag(), slowStartActive: flag(), metronomeTurns: ri(5), meFirst: flag(),
    transformed: false, foresight: flag(), magnetRise: flag(), ingrain: flag(), roosting: flag(), miracleEye: flag(),
    focusEnergy: flag(), noCritical: false,
  };
}
function fieldFor(att, def) {
  return {
    weather: pick(WEATHERS), gravity: chance(1 / 8), mudSport: chance(1 / 8), waterSport: chance(1 / 8),
    defenderSide: { reflect: chance(0.2), lightScreen: chance(0.2), luckyChant: chance(0.1) },
    abilitiesOnField: [att.ability, def.ability], attackerSideAbilities: [att.ability], defenderSideAbilities: [def.ability],
  };
}
function synthMove() {
  return {
    id: chance(0.01) ? 'MOVE_STRUGGLE' : pick(MOVE_CONSTS),
    power: chance(1 / 8) ? 1 + ri(250) : undefined,
    type: chance(1 / 8) ? pick(TYPES) : undefined,
    powerMul: 10,
  };
}
// Scenario templates: applied to about 30% of synthetic matchups so the rare rules are reached (coverage >= 100).
const TEMPLATES = [
  (m) => { m.defender.types = ['TYPE_GHOST', pick(TYPES)]; m.move.type = pick(['TYPE_NORMAL', 'TYPE_FIGHTING']); if (chance(0.5)) m.defender.foresight = true; else m.attacker.ability = 'ABILITY_SCRAPPY'; },
  (m) => { m.defender.types = ['TYPE_FLYING', pick(TYPES)]; m.move.type = 'TYPE_GROUND'; const k = ri(3); if (k === 0) m.defender.item = 'ITEM_IRON_BALL'; else if (k === 1) m.defender.ingrain = true; else m.field.gravity = true; },
  (m) => { m.defender.types = ['TYPE_FLYING', pick(TYPES)]; m.defender.roosting = true; m.move.type = pick(['TYPE_GROUND', 'TYPE_ELECTRIC', 'TYPE_ROCK']); },
  (m) => { m.defender.types = ['TYPE_DARK', pick(TYPES)]; m.defender.miracleEye = true; m.move.type = 'TYPE_PSYCHIC'; },
  (m) => { m.defender.ability = 'ABILITY_WONDER_GUARD'; m.attacker.ability = chance(0.3) ? 'ABILITY_MOLD_BREAKER' : 'ABILITY_PRESSURE'; },
  (m) => { m.defender.ability = 'ABILITY_LEVITATE'; m.move.type = 'TYPE_GROUND'; if (chance(0.3)) m.defender.item = 'ITEM_IRON_BALL'; },
  (m) => { m.defender.magnetRise = true; m.defender.ability = 'ABILITY_PRESSURE'; m.move.type = 'TYPE_GROUND'; },
  (m) => { m.defender.ability = pick(['ABILITY_FILTER', 'ABILITY_SOLID_ROCK']); m.defender.types = ['TYPE_GRASS', 'TYPE_GRASS']; m.move.type = 'TYPE_FIRE'; },
  (m) => { m.attacker.item = 'ITEM_EXPERT_BELT'; m.defender.types = ['TYPE_GRASS', 'TYPE_GRASS']; m.move.type = 'TYPE_FIRE'; },
  (m) => { m.attacker.ability = 'ABILITY_TINTED_LENS'; m.defender.types = ['TYPE_WATER', 'TYPE_WATER']; m.move.type = 'TYPE_FIRE'; },
  (m) => { m.attacker.ability = 'ABILITY_ADAPTABILITY'; m.attacker.types = ['TYPE_FIRE', 'TYPE_FIRE']; m.move.type = 'TYPE_FIRE'; },
  (m) => { m.attacker.ability = 'ABILITY_NORMALIZE'; },
  (m) => { m.move.id = 'MOVE_STRUGGLE'; },
];
function synthMatchup() {
  const attacker = synthBattler(), defender = synthBattler();
  const m = { attacker, defender, move: synthMove(), field: fieldFor(attacker, defender) };
  if (chance(0.3)) pick(TEMPLATES)(m);
  m.field.abilitiesOnField = [m.attacker.ability, m.defender.ability];
  m.field.attackerSideAbilities = [m.attacker.ability];
  m.field.defenderSideAbilities = [m.defender.ability];
  return m;
}
const REAL_SPECIES = T.species.filter(Boolean);
const REAL_MOVES = T.moves.filter((m) => m && m.power > 0 && m.constant !== 'MOVE_NONE');
const REAL_ITEMS = [null, ...T.items.filter(Boolean)];
function realBattler() {
  const sp = pick(REAL_SPECIES);
  const types = sp.types.map((n) => ENUMS.types[n]);
  if (types.length === 1) types.push(types[0]);
  const abil = pick(sp.abilities.filter((a) => a !== 0));
  const item = pick(REAL_ITEMS);
  return {
    species: sp.constant, level: 40 + ri(60), types,
    stats: { atk: 60 + ri(300), def: 60 + ri(300), spa: 60 + ri(300), spd: 60 + ri(300) },
    stages: { atk: ri(13) - 6, def: ri(13) - 6, spa: ri(13) - 6, spd: ri(13) - 6 },
    hp: 1 + ri(400), maxhp: 401,
    ability: abil === undefined ? 'ABILITY_NONE' : ENUMS.abilities[abil], abilitySuppressed: false,
    item: item ? item.constant : 'ITEM_NONE', embargo: false, status: pick(STATUSES), gender: 'M',
    flashFire: false, charge: false, helpingHand: false, slowStartActive: false, metronomeTurns: 0, meFirst: false,
    transformed: false, foresight: false, magnetRise: false, ingrain: false, roosting: false, miracleEye: false,
    focusEnergy: false, noCritical: false,
  };
}
function realMatchup() {
  const attacker = realBattler(), defender = realBattler();
  return { attacker, defender, move: { id: pick(REAL_MOVES).constant, powerMul: 10 }, field: fieldFor(attacker, defender) };
}

const SUPER = MOVE_STATUS.SUPER_EFFECTIVE, NVE = MOVE_STATUS.NOT_VERY_EFFECTIVE;
function moveTypeOf(m) {
  if (m.attacker.ability === 'ABILITY_NORMALIZE' && !m.attacker.abilitySuppressed) return 'TYPE_NORMAL';
  if (m.move.type && m.move.type !== 'TYPE_NORMAL') return m.move.type;
  return moveData(m.move.id).type;
}

function compareOne(m, opts, pre, counters) {
  const plan = typeChartPlan(m, opts);
  let first = null;
  for (let i = 0; i < 16; i++) {
    const d = applyVariance(pre, 85 + i);
    const direct = applyTypeChartDirect(m, d, opts);
    const viaApply = applyTypeChart(m, d, opts);
    const viaReplay = replayTypeChart(plan, d);
    assert.deepEqual(viaApply, direct, `applyTypeChart roll ${i} ${JSON.stringify({ m, opts, pre })}`);
    assert.deepEqual(viaReplay, direct, `replayTypeChart roll ${i}`);
    if (i === 0) first = direct;
  }
  if (!counters) return plan;
  const mask = first.moveStatusMask;
  const mt = moveTypeOf(m);
  const def = m.defender, att = m.attacker;
  const md = moveData(m.move.id);
  const hit = (k) => { counters[k] = (counters[k] ?? 0) + 1; };
  if (mask & MOVE_STATUS.INEFFECTIVE) hit('immune');
  if (mask & MOVE_STATUS.LEVITATED) hit('levitate');
  if (mask & MOVE_STATUS.MAGNET_RISE) hit('magnetRise');
  if (mask & MOVE_STATUS.WONDER_GUARD) hit('wonderGuard');
  if (plan.steps.some((s) => s.op === 'div34')) hit('filterSolidRock');
  if (plan.steps.some((s) => s.op === 'pct')) hit('expertBelt');
  if (att.ability === 'ABILITY_TINTED_LENS' && !att.abilitySuppressed && (mask & NVE) && md.power && !opts.ignoreTypeChecks) hit('tintedLens');
  if (plan.steps[0]?.op === 'stab15') hit('stab');
  if (plan.steps[0]?.op === 'x2' && att.ability === 'ABILITY_ADAPTABILITY') hit('adaptability');
  if (def.types.includes('TYPE_GHOST') && (mt === 'TYPE_NORMAL' || mt === 'TYPE_FIGHTING') && (def.foresight || att.ability === 'ABILITY_SCRAPPY')) hit('foresightScrappy');
  if (att.ability === 'ABILITY_NORMALIZE') hit('normalize');
  if (m.move.type) hit('typeOverride');
  if (opts.ignoreTypeChecks) hit('ignoreTypeChecks');
  if (opts.moveStatusMask) hit('seedMask');
  if (pre === 0) hit('zeroDamage');
  if (m.move.id === 'MOVE_STRUGGLE') hit('struggle');
  if (mask & SUPER) hit('superEffective');
  if (mask & NVE) hit('notVeryEffective');
  if (def.types.includes('TYPE_FLYING') && mt === 'TYPE_GROUND' && (def.item === 'ITEM_IRON_BALL' || def.ingrain || m.field.gravity)) hit('groundedFlying');
  if (def.roosting && def.types.includes('TYPE_FLYING')) hit('roost');
  if (def.miracleEye && def.types.includes('TYPE_DARK') && mt === 'TYPE_PSYCHIC') hit('miracleEye');
  return plan;
}
const REQUIRED = ['immune', 'levitate', 'magnetRise', 'wonderGuard', 'filterSolidRock', 'expertBelt', 'tintedLens', 'stab',
  'adaptability', 'foresightScrappy', 'normalize', 'typeOverride', 'ignoreTypeChecks', 'seedMask', 'zeroDamage', 'struggle',
  'superEffective', 'notVeryEffective', 'groundedFlying', 'roost', 'miracleEye'];

const synthOpts = () => ({ ignoreTypeChecks: chance(0.25), moveStatusMask: chance(1 / 8) ? pick([SUPER, NVE]) : 0 });
const synthPre = () => (chance(1 / 16) ? 0 : ri(401));

test(`016 equivalence: applyTypeChart (plan + replay) == applyTypeChartDirect over ${N_SYNTH} synthetic and ${N_REAL} real-data matchups x 16 rolls`, (t) => {
  const t0 = process.hrtime.bigint();
  const counters = {};
  for (let n = 0; n < N_SYNTH; n++) compareOne(synthMatchup(), synthOpts(), synthPre(), counters);
  for (let n = 0; n < N_REAL; n++) compareOne(realMatchup(), { ignoreTypeChecks: false, moveStatusMask: 0 }, ri(401), null);
  const sec = Number(process.hrtime.bigint() - t0) / 1e9;
  t.diagnostic(`seed ${SEED.toString(16)}, ${N_SYNTH} synthetic + ${N_REAL} real matchups, ${sec.toFixed(1)} s; coverage ${JSON.stringify(counters)}`);
  for (const k of REQUIRED) assert.ok((counters[k] ?? 0) >= 100, `coverage ${k}: ${counters[k] ?? 0} < 100`);
});

test('016 positive control: a plan with one multiplier step removed, or STAB flipped, is detected against the direct result', () => {
  let controlled = 0;
  for (let guard = 0; controlled < 200 && guard < 20000; guard++) {
    const m = synthMatchup();
    const opts = { ignoreTypeChecks: false, moveStatusMask: 0 };
    const plan = typeChartPlan(m, opts);
    if (plan.struggle) continue;
    // Immune plans (a 0x step) make every later step moot; the control needs a plan whose steps all matter.
    if (plan.mask & MOVE_STATUS.INEFFECTIVE) continue;
    const mulIdx = plan.steps.findIndex((s) => s.op === 'mul');
    if (mulIdx < 0) continue;
    const pre = 50 + ri(351);
    const dropped = { ...plan, steps: plan.steps.filter((_, i) => i !== mulIdx) };
    const flipped = { ...plan, steps: plan.steps[0]?.op === 'stab15' ? plan.steps.slice(1) : [{ op: 'stab15' }, ...plan.steps] };
    let diffDropped = 0, diffFlipped = 0;
    for (let i = 0; i < 16; i++) {
      const d = applyVariance(pre, 85 + i);
      const direct = applyTypeChartDirect(m, d, opts);
      if (replayTypeChart(dropped, d).damage !== direct.damage) diffDropped++;
      if (replayTypeChart(flipped, d).damage !== direct.damage) diffFlipped++;
    }
    assert.ok(diffDropped > 0, `dropped step not detected: ${JSON.stringify({ plan, pre })}`);
    assert.ok(diffFlipped > 0, `flipped STAB not detected: ${JSON.stringify({ plan, pre })}`);
    controlled++;
  }
  assert.equal(controlled, 200);
});

function direct16(core, crit) {
  const critMul = crit ? critMultiplier(core) : 1;
  const base = calcBaseDamage({ ...core, critMul });
  const preVariance = applyScriptMultipliers(core, base, critMul);
  const rolls = [];
  let moveStatusMask = 0;
  for (let i = 0; i < 16; i++) {
    const r = applyTypeChartDirect(core, applyVariance(preVariance, 85 + i));
    moveStatusMask = r.moveStatusMask;
    rolls.push(r.damage);
  }
  const immune = !!(moveStatusMask & MOVE_STATUS.IMMUNE);
  const out = immune ? rolls.map(() => 0) : rolls;
  return { rolls: out, min: out[0], max: out[15], immune, moveStatusMask, critMul, base, preVariance };
}

test('016 calcDamage (one plan per call) equals the 16-fold direct computation, normal and critical, over 300 synthetic matchups', () => {
  let compared = 0, threw = 0;
  for (let n = 0; n < 300; n++) {
    const m = synthMatchup();
    const core = { attacker: m.attacker, defender: m.defender, move: m.move, field: m.field };
    for (const crit of [false, true]) {
      let expected, err;
      try { expected = direct16(core, crit); } catch (e) { err = e; }
      if (err) { assert.throws(() => calcDamage({ ...core, crit }), { message: err.message }); threw++; continue; }
      assert.deepEqual(calcDamage({ ...core, crit }), expected, JSON.stringify({ core, crit }));
      compared++;
    }
  }
  assert.ok(compared >= 500, `compared ${compared} (threw ${threw})`);
});

test('016 DAMAGE_STATS: one calcDamage call builds one plan and replays it 16 times; the reference is not called', () => {
  const m = synthMatchup();
  const core = { attacker: m.attacker, defender: m.defender, move: m.move, field: m.field };
  const s0 = { ...DAMAGE_STATS };
  calcDamage(core);
  assert.equal(DAMAGE_STATS.plans - s0.plans, 1);
  assert.equal(DAMAGE_STATS.replays - s0.replays, 16);
  assert.equal(DAMAGE_STATS.direct - s0.direct, 0);
  applyTypeChartDirect(core, 100);
  assert.equal(DAMAGE_STATS.direct - s0.direct, 1, 'positive control: the reference counter moves when the reference runs');
});
