// sim/damage.mjs — port of the Pokemon Platinum damage formula (T037).
//
// PURPOSE (plan.md Complexity Tracking): this port is used ONLY as
//   (1) the trainer AI's damage estimator (T043),
//   (2) the player policy's model (T049 greedy, T050 expectimax2),
//   (3) a cross-check of Showdown's damage (sim/test/damage.test.mjs).
// It NEVER resolves real battle damage; Showdown does that.
//
// SOURCES (pokeplatinum @ c248fb3f; "PP" below = pokeplatinum/):
//   PP/src/battle/battle_lib.c:6601-7079  BattleSystem_CalcMoveDamage     -> calcBaseDamage()
//   PP/src/battle/battle_lib.c:7081-7094  BattleSystem_CalcDamageVariance -> applyVariance()
//   PP/src/battle/battle_lib.c:7097-7146  sCriticalStageRates / BattleSystem_CalcCriticalMulti -> critMultiplier(), critChance()
//   PP/src/battle/battle_lib.c:2399-2517  sTypeMatchupMultipliers (type chart, parsed from the C at load time)
//   PP/src/battle/battle_lib.c:2529-2558  BasicTypeMulApplies
//   PP/src/battle/battle_lib.c:2560-2679  BattleSystem_ApplyTypeChart       -> applyTypeChart()
//   PP/src/battle/battle_lib.c:7542-7581  ApplyTypeMultiplier
//   PP/src/battle/battle_lib.c:3599-3618  BattleSystem_Divide
//   PP/src/battle/battle_script.c:1323-1365 BattleScript_CalcMoveDamage (crit x, Life Orb, Metronome item, Me First)
//   PP/src/battle/battle_script.c:1380-1389 BtlCmd_CalcDamage (then variance)
//   PP/src/battle/battle_controller_player.c:2350-2372 CheckTypeChart (type chart applied AFTER variance)
// Tables (type chart, stat-stage fractions, type-boosting items, punching moves, crit rates) are
// parsed from battle_lib.c at module load; move data from PP/res/moves/<name>/data.json; item
// hold effects/params from PP/res/items/data/<name>.json; enum orders from PP/generated/*.txt.
//
// ORDER OF A REAL HIT (battle):
//   base = CalcMoveDamage(..., critMul)               (ends with "+2")  battle_lib.c:7079
//   base *= critMul                                                      battle_script.c:1344
//   Life Orb: base*(100+30)/100                                          battle_script.c:1346-1348
//   Metronome item: base*(10+turns)/10                                   battle_script.c:1350-1352
//   Me First: base*15/10                                                 battle_script.c:1354-1362
//   variance: base*(100-rand%16)/100, min 1                              battle_lib.c:7081-7094
//   type chart: STAB, per-entry type multipliers, Filter/Solid Rock, Expert Belt, Tinted Lens
//                                                                        battle_lib.c:2560-2679
// rolls[i] is the damage for variance multiplier (85 + i), i = 0..15 (i.e. rand%16 = 15 - i).
//
// MECHANICS COVERED (every branch of the functions above), given the caller supplies the state:
//   stats/stages (incl. crit stage-ignoring), level, move power/type/class/effect, powerMul
//   (Revenge/Pursuit-style doubling, passed in), Charge, Helping Hand, Technician, Huge/Pure Power,
//   Slow Start, type-boosting items (plates/incense/etc via sTypeBoostingItems), Choice Band/Specs,
//   Soul Dew, DeepSeaTooth/Scale, Light Ball, Metal Powder, Thick Club, Adamant/Lustrous/Griseous
//   Orb, Muscle Band, Wise Glasses, Thick Fat, Hustle, Guts, Marvel Scale, Plus/Minus, Mud/Water
//   Sport, Overgrow/Blaze/Torrent/Swarm, Heatproof, Dry Skin (fire power), Simple, Unaware,
//   Rivalry, Iron Fist, Solar Power, sandstorm Rock SpD boost, Flower Gift (atk/spdef), Explosion/
//   Self-Destruct defense halving, burn, Reflect/Light Screen (incl. Brick Break bypass, doubles 2/3),
//   doubles spread 3/4, rain/sun, Solar Beam in bad weather, Cloud Nine/Air Lock, Flash Fire, +2,
//   crit multiplier (2, Sniper 3), Life Orb, Metronome item, Me First, variance, STAB/Adaptability,
//   Normalize, type chart incl. Foresight/Scrappy ghost immunities, Iron Ball/Ingrain/Gravity/Roost
//   Flying-immunity removal, Miracle Eye, Levitate, Magnet Rise, Wonder Guard, Filter, Solid Rock,
//   Expert Belt, Tinted Lens, Mold Breaker (for every "ignorable" ability), Klutz/Embargo (item
//   suppressed), ability suppression (Gastro Acid), Gravity/Ingrain suppressing Levitate.
//
// MECHANICS NOT COVERED (each is a future divergence-ledger entry, T053):
//   - Variable-power / variable-type moves are NOT computed here: Gyro Ball, Eruption/Water Spout,
//     Flail/Reversal, Low Kick/Grass Knot, Return/Frustration, Hidden Power, Weather Ball, Natural
//     Gift, Judgment, Punishment, Wring Out/Crush Grip, Magnitude, Present, Trump Card, Fling,
//     Payback/Assurance/Avalanche/Revenge/Facade/SmellingSalt/Wake-Up Slap/Brine/Pursuit doublings.
//     The caller must pass move.power / move.type / powerMul (as the game passes inPower/inType).
//   - Fixed-damage and OHKO moves (Seismic Toss, Night Shade, Dragon Rage, Sonic Boom, Super Fang,
//     Endeavor, Psywave, Counter, Mirror Coat, Metal Burst, Bide, Fissure etc.).
//   - Multi-hit moves (each hit is one calcDamage; hit counts not modelled), Future Sight/Doom
//     Desire (battle_script.c:6079), Beat Up, Struggle recoil, confusion self-hit
//     (battle_controller_player.c:2215).
//   - Type-resist berries (Occa etc.): NOT FOUND in decomp C — `grep -rn WEAKEN_SE src include`
//     hits only src/battle/trainer_ai/script.s; the positive control HOLD_EFFECT_CHOICE_ATK is found
//     in battle_lib.c. Their in-game damage effect is therefore UNVERIFIED and not ported.
//   - Substitute, Focus Sash/Band, Sturdy, Endure, False Swipe caps, HP clamping (damage > HP).
//   - Doubles: branches are ported but need caller-supplied alive counts; UNTESTED.
//   - Battle Frontier flag (Soul Dew) assumed false.
//   - Accuracy/evasion, crit RNG, and move priority are outside this function (critChance() is
//     provided for the policy).
//
// INPUT CONVENTIONS: decomp constant names as strings (TYPE_FIRE, ABILITY_THICK_FAT, ITEM_LIFE_ORB,
// MOVE_EARTHQUAKE, SPECIES_GARCHOMP). See calcDamage() for the object shape. fromShowdown() builds
// it from live Showdown Pokemon objects (this file does NOT import Showdown; it only reads fields).

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
export const DECOMP = join(here, '../pokeplatinum');
const BATTLE_LIB = 'src/battle/battle_lib.c';

// ---------------------------------------------------------------------------------------------
// Integer helpers that mirror C semantics.
const idiv = (a, b) => Math.trunc(a / b); // C int division truncates toward zero
const u16 = (x) => x & 0xffff; // assignment into a u16 (attackStat, movePower, ...)
const s8 = (x) => (x << 24) >> 24; // assignment into an s8 (stat stages)
const s32 = (x) => x | 0; // assignment into an s32/int (damage)

// BattleSystem_Divide — PP/src/battle/battle_lib.c:3599-3618 (non-zero dividend never yields 0)
export function battleDivide(dividend, divisor) {
  if (dividend === 0) return dividend;
  const signedFloor = dividend < 0 ? -1 : 1;
  let q = idiv(dividend, divisor);
  if (q === 0) q = signedFloor;
  return q;
}

// ---------------------------------------------------------------------------------------------
// Decomp data loading (read once at module load).
const readText = (rel) => readFileSync(join(DECOMP, rel), 'utf8');
const enumList = (rel) => readText(rel).split('\n').map((s) => s.trim()).filter(Boolean);

// Enum orders: index == game id (and == Showdown `num` for moves/items/abilities/species).
export const ENUMS = {
  moves: enumList('generated/moves.txt'),
  items: enumList('generated/items.txt'),
  abilities: enumList('generated/abilities.txt'),
  species: enumList('generated/species.txt'),
  types: enumList('generated/pokemon_types.txt'),
};

function definedInt(rel, name) {
  const m = readText(rel).match(new RegExp(`#define\\s+${name}\\s+(\\d+)`));
  if (!m) throw new Error(`damage.mjs: ${name} not found in ${rel}`);
  return Number(m[1]);
}
// PP/include/constants/battle.h:144-146
const TYPE_MULTI = {
  TYPE_MULTI_IMMUNE: definedInt('include/constants/battle.h', 'TYPE_MULTI_IMMUNE'),
  TYPE_MULTI_NOT_VERY_EFF: definedInt('include/constants/battle.h', 'TYPE_MULTI_NOT_VERY_EFF'),
  TYPE_MULTI_SUPER_EFF: definedInt('include/constants/battle.h', 'TYPE_MULTI_SUPER_EFF'),
};
// PP/include/constants/battle/battle_script.h:4-6
const MIN_STAT_STAGE = definedInt('include/constants/battle/battle_script.h', 'MIN_STAT_STAGE');
const DEFAULT_STAT_STAGE = definedInt('include/constants/battle/battle_script.h', 'DEFAULT_STAT_STAGE');
const MAX_STAT_STAGE = definedInt('include/constants/battle/battle_script.h', 'MAX_STAT_STAGE');

// Extract the body of `static const ... <name>[]... = { ... };` from battle_lib.c with its line.
function cTableBody(name) {
  const lines = readText(BATTLE_LIB).split('\n');
  const start = lines.findIndex((l) => /^static const/.test(l) && l.includes(` ${name}[`) && l.trim().endsWith('{'));
  if (start < 0) throw new Error(`damage.mjs: table ${name} not found in ${BATTLE_LIB}`);
  const body = [];
  for (let i = start + 1; i < lines.length; i++) {
    if (/^};/.test(lines[i])) break;
    body.push({ text: lines[i].replace(/\/\/.*$/, ''), line: i + 1 });
  }
  return { body, line: start + 1 };
}

// sTypeMatchupMultipliers — PP/src/battle/battle_lib.c:2399. Entries kept IN TABLE ORDER because
// the game applies them sequentially with truncation (order matters for mixed SE/NVE).
function parseTypeChart() {
  const { body, line } = cTableBody('sTypeMatchupMultipliers');
  const entries = [];
  for (const { text, line: ln } of body) {
    const m = text.match(/\{\s*([A-Z_0-9x]+)\s*,\s*([A-Z_0-9x]+)\s*,\s*([A-Z_]+)\s*\}/);
    if (!m) continue;
    const mul = TYPE_MULTI[m[3]];
    if (mul === undefined) throw new Error(`damage.mjs: unknown multiplier ${m[3]} at battle_lib.c:${ln}`);
    entries.push({ atk: m[1], def: m[2], mul, line: ln }); // 0xFE / 0xFF kept as the strings
  }
  if (entries.at(-1)?.atk !== '0xFF') throw new Error('damage.mjs: type chart terminator missing');
  return { entries, line };
}
export const TYPE_CHART = parseTypeChart();

// sStatStageBoosts — PP/src/battle/battle_lib.c:6550
function parseFractions(name) {
  const { body } = cTableBody(name);
  const out = [];
  for (const { text } of body) {
    const m = text.match(/\{\s*(\d+)\s*,\s*(\d+)\s*\}/);
    if (m) out.push({ numerator: Number(m[1]), denominator: Number(m[2]) });
  }
  return out;
}
const STAT_STAGE_BOOSTS = parseFractions('sStatStageBoosts');
if (STAT_STAGE_BOOSTS.length !== 13) throw new Error('damage.mjs: sStatStageBoosts must have 13 rows');

// sTypeBoostingItems — PP/src/battle/battle_lib.c:6514
function parsePairs(name) {
  const { body } = cTableBody(name);
  const out = [];
  for (const { text } of body) {
    const m = text.match(/\{\s*([A-Z_]+)\s*,\s*([A-Z_]+)\s*\}/);
    if (m) out.push({ itemEffect: m[1], type: m[2] });
  }
  return out;
}
const TYPE_BOOSTING_ITEMS = parsePairs('sTypeBoostingItems');

// sPunchingMoves — PP/src/battle/battle_lib.c:6566 ; sCriticalStageRates — :7097
function parseList(name, re) {
  const { body } = cTableBody(name);
  const out = [];
  for (const { text } of body) for (const m of text.matchAll(re)) out.push(m[1]);
  return out;
}
const PUNCHING_MOVES = new Set(parseList('sPunchingMoves', /(MOVE_[A-Z_0-9]+)/g));
const CRIT_STAGE_RATES = parseList('sCriticalStageRates', /(\d+)\s*,/g).map(Number);

// Move data — PP/res/moves/<lowercase constant>/data.json
const moveCache = new Map();
export function moveData(moveConst) {
  if (moveCache.has(moveConst)) return moveCache.get(moveConst);
  const dir = moveConst.replace(/^MOVE_/, '').toLowerCase();
  const path = join(DECOMP, 'res/moves', dir, 'data.json');
  if (!existsSync(path)) throw new Error(`damage.mjs: no decomp move data for ${moveConst} (${path})`);
  const j = JSON.parse(readFileSync(path, 'utf8'));
  const d = { id: moveConst, name: j.name, power: j.power, type: j.type, class: j.class,
    effect: j.effect.type, range: j.range, src: `pokeplatinum/res/moves/${dir}/data.json` };
  moveCache.set(moveConst, d);
  return d;
}

// Item data — PP/res/items/data/<lowercase constant>.json (holdEffect, effectParam)
const itemCache = new Map();
export function itemData(itemConst) {
  if (!itemConst || itemConst === 'ITEM_NONE') return { holdEffect: 'HOLD_EFFECT_NONE', effectParam: 0 };
  if (itemCache.has(itemConst)) return itemCache.get(itemConst);
  const file = itemConst.replace(/^ITEM_/, '').toLowerCase();
  const path = join(DECOMP, 'res/items/data', `${file}.json`);
  if (!existsSync(path)) throw new Error(`damage.mjs: no decomp item data for ${itemConst} (${path})`);
  const j = JSON.parse(readFileSync(path, 'utf8'));
  const d = { holdEffect: j.holdEffect, effectParam: j.effectParam, src: `pokeplatinum/res/items/data/${file}.json` };
  itemCache.set(itemConst, d);
  return d;
}

// MOVE_STATUS_* bits — PP/include/constants/battle/moves.h:58-89
export const MOVE_STATUS = {
  SUPER_EFFECTIVE: 1 << 1,
  NOT_VERY_EFFECTIVE: 1 << 2,
  INEFFECTIVE: 1 << 3,
  LEVITATED: 1 << 11,
  WONDER_GUARD: 1 << 18,
  MAGNET_RISE: 1 << 20,
};
MOVE_STATUS.BASIC_EFFECTIVENESS = MOVE_STATUS.SUPER_EFFECTIVE | MOVE_STATUS.NOT_VERY_EFFECTIVE; // :89
MOVE_STATUS.DID_NOT_AFFECT = MOVE_STATUS.INEFFECTIVE | MOVE_STATUS.WONDER_GUARD; // :86
MOVE_STATUS.IMMUNE = MOVE_STATUS.DID_NOT_AFFECT | MOVE_STATUS.LEVITATED | MOVE_STATUS.MAGNET_RISE; // :87

// ---------------------------------------------------------------------------------------------
// Normalised battler / field state.
//
// battler = {
//   species: 'SPECIES_GARCHOMP', level, types: ['TYPE_DRAGON','TYPE_GROUND'] (single type => same twice),
//   stats: {atk, def, spa, spd}, stages: {atk, def, spa, spd} (-6..+6), hp, maxhp,
//   ability: 'ABILITY_...', abilitySuppressed (Gastro Acid), item: 'ITEM_...', embargo,
//   status: '' | 'brn' | 'par' | 'psn' | 'tox' | 'slp' | 'frz', gender: 'M'|'F'|'N',
//   flashFire, charge, helpingHand, slowStartActive, metronomeTurns, meFirst, transformed,
//   // defender-side volatiles used by the type chart:
//   foresight, magnetRise, ingrain, roosting, miracleEye,
// }
// field = {
//   weather: '' | 'sun' | 'rain' | 'sand' | 'hail' | 'fog',
//   abilitiesOnField: [...] (alive battlers; default [attacker, defender] abilities) — Cloud Nine/Air Lock,
//   attackerSideAbilities / defenderSideAbilities: alive battlers on that side incl. self (Plus/Minus, Flower Gift),
//   defenderSide: { reflect, lightScreen, luckyChant },
//   gravity, mudSport, waterSport,
//   doubles, defenderSideAlive, aliveOpponentsOfAttacker (doubles only; UNTESTED)
// }
// move = { id: 'MOVE_...', power?: inPower override, type?: inType override, powerMul?: 10|20 }

function effAbility(b, field) {
  // Battler_Ability — PP/src/battle/battle_lib.c:3088-3106
  if (b.abilitySuppressed && b.ability !== 'ABILITY_MULTITYPE') return 'ABILITY_NONE';
  if (field.gravity && b.ability === 'ABILITY_LEVITATE') return 'ABILITY_NONE';
  if (b.ingrain && b.ability === 'ABILITY_LEVITATE') return 'ABILITY_NONE';
  return b.ability || 'ABILITY_NONE';
}
function effItem(b, ability) {
  // Battler_HeldItem — PP/src/battle/battle_lib.c:5352-5363 (Klutz / Embargo => ITEM_NONE)
  if (ability === 'ABILITY_KLUTZ') return 'ITEM_NONE';
  if (b.embargo) return 'ITEM_NONE';
  return b.item || 'ITEM_NONE';
}
// Battler_IgnorableAbility — PP/src/battle/battle_lib.c:3108-3123
const ignorable = (attAbility, defAbility, ability) => attAbility !== 'ABILITY_MOLD_BREAKER' && defAbility === ability;

function weatherFlags(field) {
  // FIELD_CONDITION_* — PP/include/constants/battle/condition.h:110-140
  const w = field.weather || '';
  return {
    sunny: w === 'sun',
    raining: w === 'rain',
    sandstorm: w === 'sand',
    solarDown: w === 'rain' || w === 'sand' || w === 'hail' || w === 'fog', // FIELD_CONDITION_SOLAR_DOWN :136
  };
}
function noCloudNine(field, att, def) {
  // NO_CLOUD_NINE — PP/include/battle/common.h:63-64
  const abil = field.abilitiesOnField ?? [att, def];
  return !abil.includes('ABILITY_CLOUD_NINE') && !abil.includes('ABILITY_AIR_LOCK');
}
const hasStatus = (b) => !!(b.status && b.status !== '');

function prepare({ attacker, defender, move, field = {} }) {
  const f = { defenderSide: {}, ...field };
  const md = moveData(move.id);
  const attAbility = effAbility(attacker, f);
  const defAbility = effAbility(defender, f);
  const attItem = itemData(effItem(attacker, attAbility));
  const defItem = itemData(effItem(defender, defAbility));
  return { f, md, attAbility, defAbility, attItem, defItem };
}

// ---------------------------------------------------------------------------------------------
// BattleSystem_CalcMoveDamage — PP/src/battle/battle_lib.c:6601-7079. Returns damage + 2.
export function calcBaseDamage({ attacker, defender, move, field = {}, critMul = 1 }) {
  const { f, md, attAbility, defAbility, attItem, defItem } = prepare({ attacker, defender, move, field });
  if (!(critMul === 1 || critMul > 1)) throw new Error('critMul must be >= 1'); // :6633 GF_ASSERT

  // :6635-6643 stats (u16) and stages (s8, relative to DEFAULT_STAT_STAGE)
  let attackStat = u16(attacker.stats.atk);
  let defenseStat = u16(defender.stats.def);
  let spAttackStat = u16(attacker.stats.spa);
  let spDefenseStat = u16(defender.stats.spd);
  let attackStage = s8(attacker.stages?.atk ?? 0);
  let defenseStage = s8(defender.stages?.def ?? 0);
  let spAttackStage = s8(attacker.stages?.spa ?? 0);
  let spDefenseStage = s8(defender.stages?.spd ?? 0);
  const attackerLevel = attacker.level & 0xff;
  const [attType1, attType2] = attacker.types;
  const [defType1, defType2] = defender.types;

  // :6676-6681 power: prefer inPower
  let movePower = u16(move.power ? move.power : md.power);
  // :6683-6689 type: Normalize; inType == TYPE_NORMAL (0) means "use move data"
  let moveType;
  if (attAbility === 'ABILITY_NORMALIZE') moveType = 'TYPE_NORMAL';
  else if (!move.type || move.type === 'TYPE_NORMAL') moveType = md.type;
  else moveType = move.type;

  // :6687-6688 powerMul (10 normally; 20 for Revenge/Pursuit-style doubling)
  const powerMul = move.powerMul ?? 10;
  if (powerMul < 10) throw new Error('powerMul must be >= 10'); // :6687 GF_ASSERT
  movePower = u16(idiv(movePower * powerMul, 10));
  // :6690-6692 Charge
  if (attacker.charge && moveType === 'TYPE_ELECTRIC') movePower = u16(movePower * 2);
  // :6694-6696 Helping Hand
  if (attacker.helpingHand) movePower = u16(idiv(movePower * 15, 10));
  // :6698-6702 Technician
  if (attAbility === 'ABILITY_TECHNICIAN' && move.id !== 'MOVE_STRUGGLE' && movePower <= 60) {
    movePower = u16(idiv(movePower * 15, 10));
  }
  const moveClass = md.class; // :6704
  // :6706-6708 Huge Power / Pure Power
  if (attAbility === 'ABILITY_HUGE_POWER' || attAbility === 'ABILITY_PURE_POWER') attackStat = u16(attackStat * 2);
  // :6709-6714 Slow Start (caller supplies whether the 5-turn window is active)
  if (attAbility === 'ABILITY_SLOW_START' && attacker.slowStartActive) attackStat = u16(idiv(attackStat, 2));

  const aEff = attItem.holdEffect;
  const aPow = attItem.effectParam;
  const dEff = defItem.holdEffect;
  // :6716-6722 type-boosting items
  for (const t of TYPE_BOOSTING_ITEMS) {
    if (aEff === t.itemEffect && moveType === t.type) {
      movePower = u16(idiv(movePower * (100 + aPow), 100));
      break;
    }
  }
  // :6724-6729 Choice Band / Choice Specs
  if (aEff === 'HOLD_EFFECT_CHOICE_ATK') attackStat = u16(idiv(attackStat * 150, 100));
  if (aEff === 'HOLD_EFFECT_CHOICE_SPATK') spAttackStat = u16(idiv(spAttackStat * 150, 100));
  // :6730-6739 Soul Dew (BATTLE_TYPE_FRONTIER assumed false)
  const isLati = (s) => s === 'SPECIES_LATIOS' || s === 'SPECIES_LATIAS';
  if (aEff === 'HOLD_EFFECT_LATI_SPECIAL' && isLati(attacker.species)) spAttackStat = u16(idiv(spAttackStat * 150, 100));
  if (dEff === 'HOLD_EFFECT_LATI_SPECIAL' && isLati(defender.species)) spDefenseStat = u16(idiv(spDefenseStat * 150, 100));
  // :6740-6747 DeepSeaTooth / DeepSeaScale
  if (aEff === 'HOLD_EFFECT_CLAMPERL_SPATK' && attacker.species === 'SPECIES_CLAMPERL') spAttackStat = u16(spAttackStat * 2);
  if (dEff === 'HOLD_EFFECT_CLAMPERL_SPDEF' && defender.species === 'SPECIES_CLAMPERL') spDefenseStat = u16(spDefenseStat * 2);
  // :6748-6751 Light Ball (doubles POWER in the game)
  if (aEff === 'HOLD_EFFECT_PIKA_SPATK_UP' && attacker.species === 'SPECIES_PIKACHU') movePower = u16(movePower * 2);
  // :6752-6755 Metal Powder
  if (dEff === 'HOLD_EFFECT_DITTO_DEF_UP' && defender.species === 'SPECIES_DITTO') defenseStat = u16(defenseStat * 2);
  // :6756-6759 Thick Club
  if (aEff === 'HOLD_EFFECT_CUBONE_ATK_UP'
      && (attacker.species === 'SPECIES_CUBONE' || attacker.species === 'SPECIES_MAROWAK')) attackStat = u16(attackStat * 2);
  // :6760-6774 Adamant / Lustrous / Griseous Orb
  if (aEff === 'HOLD_EFFECT_DIALGA_BOOST' && (moveType === 'TYPE_DRAGON' || moveType === 'TYPE_STEEL')
      && attacker.species === 'SPECIES_DIALGA') movePower = u16(idiv(movePower * (100 + aPow), 100));
  if (aEff === 'HOLD_EFFECT_PALKIA_BOOST' && (moveType === 'TYPE_DRAGON' || moveType === 'TYPE_WATER')
      && attacker.species === 'SPECIES_PALKIA') movePower = u16(idiv(movePower * (100 + aPow), 100));
  if (aEff === 'HOLD_EFFECT_GIRATINA_BOOST' && (moveType === 'TYPE_DRAGON' || moveType === 'TYPE_GHOST')
      && !attacker.transformed && attacker.species === 'SPECIES_GIRATINA') movePower = u16(idiv(movePower * (100 + aPow), 100));
  // :6775-6782 Muscle Band / Wise Glasses
  if (aEff === 'HOLD_EFFECT_POWER_UP_PHYS' && moveClass === 'CLASS_PHYSICAL') movePower = u16(idiv(movePower * (100 + aPow), 100));
  if (aEff === 'HOLD_EFFECT_POWER_UP_SPEC' && moveClass === 'CLASS_SPECIAL') movePower = u16(idiv(movePower * (100 + aPow), 100));

  // :6784-6787 Thick Fat (power halved)
  if (ignorable(attAbility, defAbility, 'ABILITY_THICK_FAT') && (moveType === 'TYPE_FIRE' || moveType === 'TYPE_ICE')) {
    movePower = u16(idiv(movePower, 2));
  }
  // :6789-6794 Hustle, Guts
  if (attAbility === 'ABILITY_HUSTLE') attackStat = u16(idiv(attackStat * 150, 100));
  if (attAbility === 'ABILITY_GUTS' && hasStatus(attacker)) attackStat = u16(idiv(attackStat * 150, 100));
  // :6796-6799 Marvel Scale
  if (ignorable(attAbility, defAbility, 'ABILITY_MARVEL_SCALE') && hasStatus(defender)) defenseStat = u16(idiv(defenseStat * 150, 100));
  // :6801-6808 Plus / Minus (COUNT_ALIVE_BATTLERS_OUR_SIDE)
  const attSide = f.attackerSideAbilities ?? [attAbility];
  const defSide = f.defenderSideAbilities ?? [defAbility];
  if (attAbility === 'ABILITY_PLUS' && attSide.includes('ABILITY_MINUS')) spAttackStat = u16(idiv(spAttackStat * 150, 100));
  if (attAbility === 'ABILITY_MINUS' && attSide.includes('ABILITY_PLUS')) spAttackStat = u16(idiv(spAttackStat * 150, 100));
  // :6810-6817 Mud Sport / Water Sport
  if (moveType === 'TYPE_ELECTRIC' && f.mudSport) movePower = u16(idiv(movePower, 2));
  if (moveType === 'TYPE_FIRE' && f.waterSport) movePower = u16(idiv(movePower, 2));
  // :6819-6838 pinch abilities (curHP <= maxHP/3)
  const pinch = attacker.hp <= idiv(attacker.maxhp, 3);
  if (moveType === 'TYPE_GRASS' && attAbility === 'ABILITY_OVERGROW' && pinch) movePower = u16(idiv(movePower * 150, 100));
  if (moveType === 'TYPE_FIRE' && attAbility === 'ABILITY_BLAZE' && pinch) movePower = u16(idiv(movePower * 150, 100));
  if (moveType === 'TYPE_WATER' && attAbility === 'ABILITY_TORRENT' && pinch) movePower = u16(idiv(movePower * 150, 100));
  if (moveType === 'TYPE_BUG' && attAbility === 'ABILITY_SWARM' && pinch) movePower = u16(idiv(movePower * 150, 100));
  // :6840-6847 Heatproof, Dry Skin (fire power x1.25)
  if (moveType === 'TYPE_FIRE' && ignorable(attAbility, defAbility, 'ABILITY_HEATPROOF')) movePower = u16(idiv(movePower, 2));
  if (moveType === 'TYPE_FIRE' && ignorable(attAbility, defAbility, 'ABILITY_DRY_SKIN')) movePower = u16(idiv(movePower * 125, 100));

  // :6849-6884 Simple (attacker's own, and defender's when not Mold Breaker'd), clamped
  const lo = MIN_STAT_STAGE - DEFAULT_STAT_STAGE;
  const hi = MAX_STAT_STAGE - DEFAULT_STAT_STAGE;
  const clampStage = (x) => Math.min(hi, Math.max(lo, s8(x)));
  if (attAbility === 'ABILITY_SIMPLE') {
    attackStage = clampStage(attackStage * 2);
    spAttackStage = clampStage(spAttackStage * 2);
  }
  if (ignorable(attAbility, defAbility, 'ABILITY_SIMPLE')) {
    defenseStage = clampStage(defenseStage * 2);
    spDefenseStage = clampStage(spDefenseStage * 2);
  }
  // :6886-6894 Unaware
  if (ignorable(attAbility, defAbility, 'ABILITY_UNAWARE')) { attackStage = 0; spAttackStage = 0; }
  if (attAbility === 'ABILITY_UNAWARE') { defenseStage = 0; spDefenseStage = 0; }
  // :6896-6899 back to table indices
  attackStage += DEFAULT_STAT_STAGE;
  defenseStage += DEFAULT_STAT_STAGE;
  spAttackStage += DEFAULT_STAT_STAGE;
  spDefenseStage += DEFAULT_STAT_STAGE;

  // :6901-6912 Rivalry
  const g1 = attacker.gender ?? 'N';
  const g2 = defender.gender ?? 'N';
  if (attAbility === 'ABILITY_RIVALRY' && g1 === g2 && g1 !== 'N' && g2 !== 'N') movePower = u16(idiv(movePower * 125, 100));
  if (attAbility === 'ABILITY_RIVALRY' && g1 !== g2 && g1 !== 'N' && g2 !== 'N') movePower = u16(idiv(movePower * 75, 100));
  // :6914-6919 Iron Fist
  if (PUNCHING_MOVES.has(move.id) && attAbility === 'ABILITY_IRON_FIST') movePower = u16(idiv(movePower * 12, 10));

  const w = weatherFlags(f);
  const ncn = noCloudNine(f, attAbility, defAbility);
  // :6921-6941 weather stat modifiers
  if (ncn) {
    if (w.sunny && attAbility === 'ABILITY_SOLAR_POWER') spAttackStat = u16(idiv(spAttackStat * 15, 10));
    if (w.sandstorm && (defType1 === 'TYPE_ROCK' || defType2 === 'TYPE_ROCK')) spDefenseStat = u16(idiv(spDefenseStat * 15, 10));
    if (w.sunny && attSide.includes('ABILITY_FLOWER_GIFT')) attackStat = u16(idiv(attackStat * 15, 10));
    if (w.sunny && attAbility !== 'ABILITY_MOLD_BREAKER' && defSide.includes('ABILITY_FLOWER_GIFT')) {
      spDefenseStat = u16(idiv(spDefenseStat * 15, 10));
    }
  }
  // :6943-6945 Explosion / Self-Destruct
  if (md.effect === 'BATTLE_EFFECT_HALVE_DEFENSE') defenseStat = u16(idiv(defenseStat, 2));

  const doubles = !!f.doubles;
  const stageMul = (stat, stage) => idiv(stat * STAT_STAGE_BOOSTS[stage].numerator, STAT_STAGE_BOOSTS[stage].denominator);
  let damage = 0;
  let stageDivisor = 0;
  const lvlFactor = idiv(attackerLevel * 2, 5) + 2;
  if (moveClass === 'CLASS_PHYSICAL') {
    // :6947-6958 attack (crit ignores non-positive attack stages)
    if (critMul > 1) damage = attackStage > DEFAULT_STAT_STAGE ? stageMul(attackStat, attackStage) : attackStat;
    else damage = stageMul(attackStat, attackStage);
    damage = s32(damage * movePower); // :6960
    damage = s32(damage * lvlFactor); // :6961
    // :6963-6973 defense (crit ignores non-negative defense stages)
    if (critMul > 1) stageDivisor = defenseStage < DEFAULT_STAT_STAGE ? stageMul(defenseStat, defenseStage) : defenseStat;
    else stageDivisor = stageMul(defenseStat, defenseStage);
    damage = idiv(damage, stageDivisor); // :6975
    damage = idiv(damage, 50); // :6976
    // :6978-6980 burn
    if (attacker.status === 'brn' && attAbility !== 'ABILITY_GUTS') damage = idiv(damage, 2);
    // :6982-6992 Reflect
    if (f.defenderSide.reflect && critMul === 1 && md.effect !== 'BATTLE_EFFECT_REMOVE_SCREENS') {
      if (doubles && f.defenderSideAlive === 2) damage = idiv(damage * 2, 3);
      else damage = idiv(damage, 2);
    }
  } else if (moveClass === 'CLASS_SPECIAL') {
    // :6993-7004
    if (critMul > 1) damage = spAttackStage > DEFAULT_STAT_STAGE ? stageMul(spAttackStat, spAttackStage) : spAttackStat;
    else damage = stageMul(spAttackStat, spAttackStage);
    damage = s32(damage * movePower); // :7006
    damage = s32(damage * lvlFactor); // :7007
    // :7009-7019
    if (critMul > 1) stageDivisor = spDefenseStage < DEFAULT_STAT_STAGE ? stageMul(spDefenseStat, spDefenseStage) : spDefenseStat;
    else stageDivisor = stageMul(spDefenseStat, spDefenseStage);
    damage = idiv(damage, stageDivisor); // :7021
    damage = idiv(damage, 50); // :7022
    // :7023-7033 Light Screen
    if (f.defenderSide.lightScreen && critMul === 1 && md.effect !== 'BATTLE_EFFECT_REMOVE_SCREENS') {
      if (doubles && f.defenderSideAlive === 2) damage = idiv(damage * 2, 3);
      else damage = idiv(damage, 2);
    }
  }
  // CLASS_STATUS: damage stays 0 (then +2), as in the C.

  // :7036-7044 doubles spread reduction (UNTESTED)
  if (doubles && md.range === 'RANGE_ADJACENT_OPPONENTS' && f.defenderSideAlive === 2) damage = idiv(damage * 3, 4);
  if (doubles && md.range === 'RANGE_ALL_ADJACENT' && (f.aliveOpponentsOfAttacker ?? 0) >= 2) damage = idiv(damage * 3, 4);

  // :7046-7072 weather damage modifiers
  if (ncn) {
    if (w.raining) {
      if (moveType === 'TYPE_FIRE') damage = idiv(damage, 2);
      else if (moveType === 'TYPE_WATER') damage = idiv(damage * 15, 10);
    }
    if (w.solarDown && move.id === 'MOVE_SOLAR_BEAM') damage = idiv(damage, 2);
    if (w.sunny) {
      if (moveType === 'TYPE_FIRE') damage = idiv(damage * 15, 10);
      else if (moveType === 'TYPE_WATER') damage = idiv(damage, 2);
    }
  }
  // :7074-7076 Flash Fire
  if (attacker.flashFire && moveType === 'TYPE_FIRE') damage = idiv(damage * 15, 10);

  return damage + 2; // :7078
}

// BattleScript_CalcMoveDamage post-multipliers — PP/src/battle/battle_script.c:1323-1365
export function applyScriptMultipliers({ attacker, defender, move, field = {} }, base, critMul) {
  const { attItem } = prepare({ attacker, defender, move, field });
  let damage = s32(base * critMul); // :1344
  if (attItem.holdEffect === 'HOLD_EFFECT_HP_DRAIN_ON_ATK') { // Life Orb :1346-1348
    damage = idiv(damage * (100 + attItem.effectParam), 100);
  }
  if (attItem.holdEffect === 'HOLD_EFFECT_BOOST_REPEATED') { // Metronome item :1350-1352
    damage = idiv(damage * (10 + (attacker.metronomeTurns ?? 0)), 10);
  }
  if (attacker.meFirst) damage = idiv(damage * 15, 10); // :1354-1362 (caller decides the turn-order window)
  return damage;
}

// BattleSystem_CalcDamageVariance — PP/src/battle/battle_lib.c:7081-7094. `multiplier` = 100 - rand%16.
export function applyVariance(damage, multiplier) {
  if (damage) {
    damage = idiv(s32(damage * multiplier), 100);
    if (damage === 0) damage = 1;
  }
  return damage;
}

// BasicTypeMulApplies — PP/src/battle/battle_lib.c:2529-2558
function basicTypeMulApplies(entry, defender, defItemEffect, field) {
  let result = true;
  if ((defItemEffect === 'HOLD_EFFECT_SPEED_DOWN_GROUNDED' || defender.ingrain)
      && entry.def === 'TYPE_FLYING' && entry.mul === TYPE_MULTI.TYPE_MULTI_IMMUNE) result = false;
  if (defender.roosting && entry.def === 'TYPE_FLYING') result = false;
  if (field.gravity && entry.def === 'TYPE_FLYING' && entry.mul === TYPE_MULTI.TYPE_MULTI_IMMUNE) result = false;
  if (defender.miracleEye && entry.def === 'TYPE_DARK' && entry.mul === TYPE_MULTI.TYPE_MULTI_IMMUNE) result = false;
  return result;
}

// ApplyTypeMultiplier — PP/src/battle/battle_lib.c:7542-7581
function applyTypeMultiplier(mul, damage, update, st, ignoreChecks) {
  if (!ignoreChecks && damage) damage = battleDivide(damage * mul, 10);
  if (mul === TYPE_MULTI.TYPE_MULTI_IMMUNE) {
    st.mask |= MOVE_STATUS.INEFFECTIVE;
    st.mask &= ~MOVE_STATUS.NOT_VERY_EFFECTIVE;
    st.mask &= ~MOVE_STATUS.SUPER_EFFECTIVE;
  } else if (mul === TYPE_MULTI.TYPE_MULTI_NOT_VERY_EFF) {
    if (update) {
      if (st.mask & MOVE_STATUS.SUPER_EFFECTIVE) st.mask &= ~MOVE_STATUS.SUPER_EFFECTIVE;
      else st.mask |= MOVE_STATUS.NOT_VERY_EFFECTIVE;
    }
  } else if (mul === TYPE_MULTI.TYPE_MULTI_SUPER_EFF) {
    if (update) {
      if (st.mask & MOVE_STATUS.NOT_VERY_EFFECTIVE) st.mask &= ~MOVE_STATUS.NOT_VERY_EFFECTIVE;
      else st.mask |= MOVE_STATUS.SUPER_EFFECTIVE;
    }
  }
  return damage;
}

// Move IDs whose effect is not on its damaging turn — MoveIsOnDamagingTurn, battle_lib.c:7588.
// Only consulted for Wonder Guard; the port treats every call as the damaging turn (the hit we compute).

// BattleSystem_ApplyTypeChart — PP/src/battle/battle_lib.c:2560-2679.
// `ignoreTypeChecks` mirrors SYSCTL_IGNORE_TYPE_CHECKS (set by the AI for fixed-damage moves,
// trainer_ai.c:3093). Returns { damage, moveStatusMask, totalMul }.
export function applyTypeChart({ attacker, defender, move, field = {} }, damage, { ignoreTypeChecks = false, moveStatusMask = 0 } = {}) {
  const { f, md, attAbility, defAbility, attItem, defItem } = prepare({ attacker, defender, move, field });
  const st = { mask: moveStatusMask };
  let totalMul = 1;
  if (move.id === 'MOVE_STRUGGLE') return { damage, moveStatusMask: st.mask, totalMul }; // :2571-2573

  // :2580-2586 type: Normalize, inType (non-zero), move data
  let moveType;
  if (attAbility === 'ABILITY_NORMALIZE') moveType = 'TYPE_NORMAL';
  else if (move.type && move.type !== 'TYPE_NORMAL') moveType = move.type;
  else moveType = md.type;
  const movePower = md.power; // :2588 (MOVE_DATA power, not inPower)

  // :2590-2596 STAB / Adaptability
  if (!ignoreTypeChecks && attacker.types.includes(moveType)) {
    if (attAbility === 'ABILITY_ADAPTABILITY') damage = s32(damage * 2);
    else damage = idiv(damage * 15, 10);
  }

  const [defType1, defType2] = defender.types;
  const defItemEffect = defItem.holdEffect;
  if (ignorable(attAbility, defAbility, 'ABILITY_LEVITATE') && moveType === 'TYPE_GROUND'
      && defItemEffect !== 'HOLD_EFFECT_SPEED_DOWN_GROUNDED') {
    st.mask |= MOVE_STATUS.LEVITATED; // :2598-2601
  } else if (defender.magnetRise && !defender.ingrain && moveType === 'TYPE_GROUND'
      && defItemEffect !== 'HOLD_EFFECT_SPEED_DOWN_GROUNDED') {
    st.mask |= MOVE_STATUS.MAGNET_RISE; // :2602-2606
  } else {
    // :2607-2646 walk the chart in table order
    for (const entry of TYPE_CHART.entries) {
      if (entry.atk === '0xFF') break;
      if (entry.atk === '0xFE') {
        // :2613-2621 Foresight / Scrappy stop before the ghost immunities
        if (defender.foresight || attAbility === 'ABILITY_SCRAPPY') break;
        continue;
      }
      if (entry.atk === moveType) {
        if (entry.def === defType1 && basicTypeMulApplies(entry, defender, defItemEffect, f)) {
          damage = applyTypeMultiplier(entry.mul, damage, movePower, st, ignoreTypeChecks);
          if (entry.mul === TYPE_MULTI.TYPE_MULTI_SUPER_EFF) totalMul *= 2;
        }
        if (entry.def === defType2 && defType1 !== defType2 && basicTypeMulApplies(entry, defender, defItemEffect, f)) {
          damage = applyTypeMultiplier(entry.mul, damage, movePower, st, ignoreTypeChecks);
          if (entry.mul === TYPE_MULTI.TYPE_MULTI_SUPER_EFF) totalMul *= 2;
        }
      }
    }
  }

  // :2649-2677 Wonder Guard / Filter / Solid Rock / Expert Belt / Tinted Lens
  if (ignorable(attAbility, defAbility, 'ABILITY_WONDER_GUARD')
      && (!(st.mask & MOVE_STATUS.SUPER_EFFECTIVE)
        || (st.mask & MOVE_STATUS.BASIC_EFFECTIVENESS) === MOVE_STATUS.BASIC_EFFECTIVENESS)
      && movePower) {
    st.mask |= MOVE_STATUS.WONDER_GUARD;
  } else if (!ignoreTypeChecks) {
    if ((st.mask & MOVE_STATUS.SUPER_EFFECTIVE) && movePower) {
      if (ignorable(attAbility, defAbility, 'ABILITY_FILTER') || ignorable(attAbility, defAbility, 'ABILITY_SOLID_ROCK')) {
        damage = battleDivide(damage * 3, 4);
      }
      if (attItem.holdEffect === 'HOLD_EFFECT_POWER_UP_SE') damage = idiv(damage * (100 + attItem.effectParam), 100);
    }
    if ((st.mask & MOVE_STATUS.NOT_VERY_EFFECTIVE) && movePower) {
      if (attAbility === 'ABILITY_TINTED_LENS') damage = s32(damage * 2);
    }
  } else {
    st.mask &= ~MOVE_STATUS.SUPER_EFFECTIVE;
    st.mask &= ~MOVE_STATUS.NOT_VERY_EFFECTIVE;
  }
  return { damage, moveStatusMask: st.mask, totalMul };
}

// BattleSystem_CalcCriticalMulti — PP/src/battle/battle_lib.c:7105-7146, split into the
// deterministic part (given that the crit roll succeeded) and the chance.
export function critBlocked({ attacker, defender, move, field = {} }) {
  const { f, attAbility, defAbility } = prepare({ attacker, defender, move, field });
  return ignorable(attAbility, defAbility, 'ABILITY_BATTLE_ARMOR')
    || ignorable(attAbility, defAbility, 'ABILITY_SHELL_ARMOR')
    || !!f.defenderSide.luckyChant
    || !!defender.noCritical; // MOVE_EFFECT_NO_CRITICAL
}
export function critMultiplier(input) {
  if (critBlocked(input)) return 1;
  const { attAbility } = prepare(input);
  return attAbility === 'ABILITY_SNIPER' ? 3 : 2; // :7142-7144
}
// Probability of a crit; `criticalStage` = battleCtx->criticalBoosts (move's high-crit stage).
export function critChance(input, criticalStage = 0) {
  if (critBlocked(input)) return 0;
  const { attacker } = input;
  const { attAbility, attItem } = prepare(input);
  const e = attItem.holdEffect;
  let stage = (attacker.focusEnergy ? 2 : 0) // :7123-7128
    + (e === 'HOLD_EFFECT_CRITRATE_UP' ? 1 : 0)
    + criticalStage
    + (attAbility === 'ABILITY_SUPER_LUCK' ? 1 : 0)
    + (e === 'HOLD_EFFECT_CHANSEY_CRITRATE_UP' && attacker.species === 'SPECIES_CHANSEY' ? 2 : 0)
    + (e === 'HOLD_EFFECT_FARFETCHD_CRITRATE_UP' && attacker.species === 'SPECIES_FARFETCHD' ? 2 : 0);
  if (stage > 4) stage = 4; // :7130-7132
  return 1 / CRIT_STAGE_RATES[stage];
}

// ---------------------------------------------------------------------------------------------
// Full battle-order damage (BtlCmd_CalcDamage then CheckTypeChart). `crit`: true => the crit roll
// succeeded (multiplier from critMultiplier(); Battle/Shell Armor / Lucky Chant force 1).
// Returns { rolls[16] (multiplier 85..100), min, max, immune, moveStatusMask, critMul, base, preVariance }.
export function calcDamage(input) {
  const { attacker, defender, move, field = {}, crit = false } = input;
  const critMul = crit ? critMultiplier(input) : 1;
  const base = calcBaseDamage({ attacker, defender, move, field, critMul });
  const preVariance = applyScriptMultipliers({ attacker, defender, move, field }, base, critMul);
  const rolls = [];
  let moveStatusMask = 0;
  for (let i = 0; i < 16; i++) {
    const v = applyVariance(preVariance, 85 + i);
    const r = applyTypeChart({ attacker, defender, move, field }, v);
    moveStatusMask = r.moveStatusMask;
    rolls.push(r.damage);
  }
  const immune = !!(moveStatusMask & MOVE_STATUS.IMMUNE);
  const out = immune ? rolls.map(() => 0) : rolls;
  return { rolls: out, min: out[0], max: out[15], immune, moveStatusMask, critMul, base, preVariance };
}

// ---------------------------------------------------------------------------------------------
// Adapter: live Showdown Pokemon objects -> port inputs. Reads object fields only (no Showdown
// import). Move data always comes from the decomp, keyed by Showdown move `num` == decomp index
// (PP/generated/moves.txt order). Types are the live Showdown types (Roost/Conversion aware).
const typeConst = (t) => `TYPE_${t.toUpperCase()}`;
const WEATHER = { sunnyday: 'sun', raindance: 'rain', sandstorm: 'sand', hail: 'hail' };

export function battlerFromShowdown(p) {
  const types = p.getTypes().map(typeConst);
  if (types.length === 1) types.push(types[0]);
  const v = p.volatiles || {};
  return {
    species: ENUMS.species[p.species.num],
    level: p.level,
    types,
    stats: { atk: p.storedStats.atk, def: p.storedStats.def, spa: p.storedStats.spa, spd: p.storedStats.spd },
    stages: { atk: p.boosts.atk, def: p.boosts.def, spa: p.boosts.spa, spd: p.boosts.spd },
    hp: p.hp,
    maxhp: p.maxhp,
    ability: ENUMS.abilities[p.getAbility().num] ?? 'ABILITY_NONE',
    abilitySuppressed: !!v.gastroacid,
    item: p.item ? ENUMS.items[p.getItem().num] : 'ITEM_NONE',
    embargo: !!v.embargo,
    status: p.status || '',
    gender: p.gender || 'N',
    flashFire: !!v.flashfire,
    charge: !!v.charge,
    helpingHand: !!v.helpinghand,
    slowStartActive: !!v.slowstart,
    metronomeTurns: v.metronome?.numConsecutive ?? 0,
    meFirst: false,
    transformed: !!p.transformed,
    foresight: !!v.foresight,
    magnetRise: !!v.magnetrise,
    ingrain: !!v.ingrain,
    roosting: !!v.roost,
    miracleEye: !!v.miracleeye,
    focusEnergy: !!v.focusenergy,
  };
}

export function fromShowdown(battle, attackerPoke, defenderPoke, moveIdOrNum, { crit = false, power, type, powerMul } = {}) {
  if (battle.gameType !== 'singles') throw new Error('damage.mjs adapter: only singles is covered');
  const num = typeof moveIdOrNum === 'number' ? moveIdOrNum : battle.dex.moves.get(moveIdOrNum).num;
  const moveConst = ENUMS.moves[num];
  if (!moveConst) throw new Error(`damage.mjs adapter: no decomp move for num ${num}`);
  const active = battle.getAllActive();
  const abilitiesOnField = active.filter((p) => p.hp > 0).map((p) => battlerFromShowdown(p))
    .map((b) => (b.abilitySuppressed ? 'ABILITY_NONE' : b.ability));
  const attacker = battlerFromShowdown(attackerPoke);
  const defender = battlerFromShowdown(defenderPoke);
  const ds = defenderPoke.side.sideConditions;
  const anyVol = (id) => active.some((p) => p.volatiles[id]) || !!battle.field.pseudoWeather[id];
  const field = {
    weather: WEATHER[battle.field.weather] ?? '',
    abilitiesOnField,
    attackerSideAbilities: [attacker.abilitySuppressed ? 'ABILITY_NONE' : attacker.ability],
    defenderSideAbilities: [defender.abilitySuppressed ? 'ABILITY_NONE' : defender.ability],
    defenderSide: { reflect: !!ds.reflect, lightScreen: !!ds.lightscreen, luckyChant: !!ds.luckychant },
    gravity: !!battle.field.pseudoWeather.gravity,
    mudSport: anyVol('mudsport'),
    waterSport: anyVol('watersport'),
  };
  return { attacker, defender, move: { id: moveConst, power, type, powerMul }, field, crit };
}
