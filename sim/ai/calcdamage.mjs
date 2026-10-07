// T043: the trainer AI's damage estimator.
//
// Ports, from pokeplatinum/src/battle/trainer_ai/trainer_ai.c (TAI below, @ c248fb3f):
//   TAI:31-45     sNoDamageCalcMoveEffects            -> NO_DAMAGE_CALC_EFFECTS (parsed from the C)
//   TAI:48-60     sAltPowerMoveEffects                -> ALT_POWER_EFFECTS      (parsed from the C)
//   TAI:236-241   TrainerAI_Init damage rolls         -> drawMoveDamageRolls()
//   TAI:2799-2849 TrainerAI_CalcAllDamage             -> calcAllDamage()
//   TAI:2868-3112 TrainerAI_CalcDamage                -> calcDamage()
//   TAI:3127-3247 TrainerAI_MoveType                  -> moveType()
//   TAI:3560-3598 AI_HasSuperEffectiveMove (singles)  -> hasSuperEffectiveMove()
// over sim/damage.mjs (T037), which ports BattleSystem_CalcMoveDamage (battle_lib.c:6601-7079)
// and BattleSystem_ApplyTypeChart (battle_lib.c:2560-2679).
//
// The AI path differs from a real hit (sim/damage.mjs header): critical multiplier 1, NO
// BattleScript_CalcMoveDamage post-multipliers (Life Orb, Metronome, Me First), the type chart
// applied straight after CalcMoveDamage, then `BattleSystem_Divide(damage * variance, 100)`
// (TAI:3109) instead of BattleSystem_CalcDamageVariance.
//
// Every function takes `env` = { ai, rand, mem }:
//   ai   - the adapter (sim/ai/adapter.mjs); ai.defender is AI_CONTEXT.defender.
//   rand - BattleSystem_RandNext (u16). Drawn only by Psywave (TAI:3015) and Magnitude (TAI:3030).
//   mem  - AI_CONTEXT memory: moveDamageRolls[4] (ai_context.h:24), and monSpeedValues[4]
//          (battleCtx->monSpeedValues, battle_context.h:259, u32), which is NOT AI memory: the game
//          writes it as a side effect of every BattleSystem_CompareBattlerSpeed call
//          (battle_lib.c:1372-1373: the AI's IfSpeedCompareEqualTo and the engine's turn ordering).
//          Only Gyro Ball reads it (TAI:2996). The caller must keep it current.
// A ctx from interp.mjs's makeCtx satisfies `env` directly.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DECOMP_ROOT, readList } from './constants.mjs';
import { fromShowdown, calcBaseDamage, applyTypeChart as dmgApplyTypeChart, battleDivide, MOVE_STATUS, ENUMS } from '../damage.mjs';

const TAI_PATH = 'src/battle/trainer_ai/trainer_ai.c';
const taiLines = readFileSync(join(DECOMP_ROOT, TAI_PATH), 'utf8').split('\n');
const idiv = (a, b) => Math.trunc(a / b);

// ---------- tables parsed from the decomp ----------

// `static const u16 <name>[] = { A, B, ..., 0xFFFF };` -> ['A', 'B', ...] (terminator dropped).
function parseU16Table(name) {
  const start = taiLines.findIndex((l) => l.startsWith(`static const u16 ${name}[]`));
  if (start < 0) throw new Error(`calcdamage: ${name} not found in ${TAI_PATH}`);
  const out = [];
  for (let i = start + 1; i < taiLines.length; i++) {
    const t = taiLines[i].trim();
    if (t.startsWith('};')) break;
    const m = t.match(/^([A-Z0-9_x]+),?$/);
    if (!m) throw new Error(`calcdamage: unexpected line in ${name} at ${TAI_PATH}:${i + 1}: ${t}`);
    if (m[1] === '0xFFFF') return { names: out, line: start + 1 };
    out.push(m[1]);
  }
  throw new Error(`calcdamage: ${name} has no 0xFFFF terminator`);
}
export const NO_DAMAGE_CALC_EFFECTS = parseU16Table('sNoDamageCalcMoveEffects'); // TAI:31
export const ALT_POWER_EFFECTS = parseU16Table('sAltPowerMoveEffects'); // TAI:48

// The Judgment switch inside TrainerAI_CalcDamage (TAI:2897-2970): HOLD_EFFECT_ARCEUS_* -> TYPE_*.
function parseJudgmentSwitch() {
  const fn = taiLines.findIndex((l) => l.startsWith('static s32 TrainerAI_CalcDamage('));
  const start = taiLines.findIndex((l, i) => i > fn && l.trim() === 'case MOVE_JUDGMENT:');
  const out = [];
  for (let i = start + 1; i < taiLines.length; i++) {
    const t = taiLines[i].trim();
    if (t === 'default:') break;
    const c = t.match(/^case (HOLD_EFFECT_\w+):$/);
    if (c) {
      const ty = taiLines[i + 1].trim().match(/^type = (TYPE_\w+);$/);
      if (!ty) throw new Error(`calcdamage: Judgment case without type at ${TAI_PATH}:${i + 2}`);
      out.push([c[1], ty[1]]);
    }
  }
  if (out.length !== 16) throw new Error(`calcdamage: expected 16 Judgment cases, got ${out.length}`);
  return out;
}
export const JUDGMENT_TYPES = parseJudgmentSwitch();

// sWeightToPower — include/data/battle/weight_to_power.h:1-8 ({weight in hectograms, power}).
function parseWeightToPower() {
  const text = readFileSync(join(DECOMP_ROOT, 'include/data/battle/weight_to_power.h'), 'utf8');
  const rows = [...text.matchAll(/\{\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*\}/g)].map((m) => [Number(m[1]), Number(m[2])]);
  if (rows.at(-1)?.[0] !== 0xFFFF) throw new Error('calcdamage: sWeightToPower terminator missing');
  return rows;
}
export const WEIGHT_TO_POWER = parseWeightToPower();

// STAT_* order (generated/pokemon_stats.txt:1-6): HP, ATTACK, DEFENSE, SPEED, SPECIAL_ATTACK, SPECIAL_DEFENSE.
const STATS = readList('pokemon_stats').map((e) => {
  if (!/^STAT_\w+$/.test(e.raw)) throw new Error(`calcdamage: unexpected generated/pokemon_stats.txt:${e.line}: ${e.raw}`);
  return e.raw;
});
const STAT_INDEX = Object.fromEntries(STATS.map((n, i) => [n, i]));
const STAT = new Proxy(STAT_INDEX, {
  get(t, k) { if (!(k in t)) throw new Error(`calcdamage: unknown stat ${String(k)}`); return t[k]; },
});

// ---------- species weight (battleMons[b].weight, battle_lib.c:150) ----------
// Pokedex_HeightWeightData_Weight comes from the dataproc build: hectograms =
// round(LB_TO_KG(weight_pounds - override) * 10), or round(weight_kilograms * 10)
// (tools/dataproc/src/speciesproc.c:696, 698-716, 735-752). The override list is read from that C.
const SPECIESPROC = 'tools/dataproc/src/speciesproc.c';
function parseWeightOverrides() {
  const lines = readFileSync(join(DECOMP_ROOT, SPECIESPROC), 'utf8').split('\n');
  const start = lines.findIndex((l) => l.includes('species_weight_rounding_override(enum Species species) {'));
  if (start < 0) throw new Error(`calcdamage: species_weight_rounding_override not found in ${SPECIESPROC}`);
  const out = new Map();
  let pending = [];
  for (let i = start + 1; i < lines.length; i++) {
    const t = lines[i].trim();
    let m = t.match(/^case (SPECIES_\w+):$/);
    if (m) { pending.push(m[1]); continue; }
    m = t.match(/^return (-?[\d.]+);$/);
    if (m) { for (const s of pending) out.set(s, Number(m[1])); pending = []; continue; }
    if (t.startsWith('default:')) break;
  }
  if (out.size === 0) throw new Error('calcdamage: no weight overrides parsed');
  return out;
}
const WEIGHT_OVERRIDES = parseWeightOverrides();
const weightCache = new Map();
// `speciesConst` e.g. 'SPECIES_SNORLAX'. Base form data (res/pokemon/<name>/data.json).
export function speciesWeightHg(speciesConst) {
  if (weightCache.has(speciesConst)) return weightCache.get(speciesConst);
  const dir = speciesConst.replace(/^SPECIES_/, '').toLowerCase();
  const d = JSON.parse(readFileSync(join(DECOMP_ROOT, 'res/pokemon', dir, 'data.json'), 'utf8')).pokedex_data;
  let kg;
  if (d.weight_kilograms !== undefined) kg = d.weight_kilograms;
  else if (d.weight_pounds !== undefined) kg = (d.weight_pounds - (WEIGHT_OVERRIDES.get(speciesConst) ?? 0.0)) * 0.45359237;
  else throw new Error(`calcdamage: no weight for ${speciesConst}`);
  const hg = Math.round(kg * 10); // C round(): half away from zero; equal to Math.round for kg >= 0
  weightCache.set(speciesConst, hg);
  return hg;
}

// ---------- helpers over the adapter ----------

const K = (ai, n) => ai.constants.get(n);
const effectIn = (ai, table, effect) => table.names.some((n) => K(ai, n) === effect);
const typeName = (t) => (t === 0 ? undefined : (ENUMS.types[t] ?? `TYPE_INVALID_${t}`));

// BattleSystem_GetItemData(item, ITEM_PARAM_*) for the params used here.
function itemParam(ai, item, which) {
  const d = ai.itemData(item);
  if (!d) throw new Error(`calcdamage: no item data for item id ${item}`);
  if (which === 'holdEffect') return d.holdEffect;
  if (which === 'naturalGiftPower') return d.naturalGiftPower;
  // naturalGiftType: `null` in the JSON is stored as (u8)~0 truncated to 5 bits = 31
  // (tools/dataproc/src/itemproc.c:194-199).
  if (which === 'naturalGiftType') return d.naturalGiftType === undefined ? 31 : d.naturalGiftType;
  throw new Error(`calcdamage: unknown item param ${which}`);
}
// Battler_HeldItem (battle_lib.c:5352-5363): ITEM_NONE under Klutz or Embargo.
function battlerHeldItem(ai, b) {
  if (ai.battlerAbility(b) === K(ai, 'ABILITY_KLUTZ')) return K(ai, 'ITEM_NONE');
  if (ai.moveEffectsData(b).embargoTurns) return K(ai, 'ITEM_NONE');
  return ai.heldItem(b);
}
function judgmentType(ai, holdEffect) {
  for (const [he, ty] of JUDGMENT_TYPES) if (K(ai, he) === holdEffect) return K(ai, ty);
  return K(ai, 'TYPE_NORMAL');
}

// Damage-port input for `move` used by `attacker` against `defender`, with the game's
// inPower (u16, battle_lib.c:6606) / inType (0 = TYPE_NORMAL = "use move data").
function portInput(ai, attacker, defender, move, power, type) {
  const att = ai.pokemon(attacker);
  const def = ai.pokemon(defender);
  if (!att || !def) throw new Error(`calcdamage: battler ${att ? defender : attacker} is empty`);
  return fromShowdown(ai.battle, att, def, move, { power: power & 0xffff, type: typeName(type), powerMul: 10 });
}

// Eligibility used by FlagMoveDamageScore (TAI:1023-1036) and IfCurrentMoveKills (TAI:1538-1553):
// alt-power effect, or power > 1 and not a no-damage-calc effect.
export function damageCheckApplies(ai, move) {
  const md = ai.moveData(move);
  return effectIn(ai, ALT_POWER_EFFECTS, md.effect) || (md.power > 1 && !effectIn(ai, NO_DAMAGE_CALC_EFFECTS, md.effect));
}

// TrainerAI_Init, TAI:236-241: one roll per move slot, `100 - RandNext() % 16` (u8), drawn for all
// four slots in slot order, whether or not the move is valid.
export function drawMoveDamageRolls(rand) {
  const rolls = [];
  for (let i = 0; i < 4; i++) rolls.push((100 - (rand() % 16)) & 0xff);
  return rolls;
}

// ---------- TrainerAI_CalcDamage (TAI:2868-3112) ----------
// args: { move, heldItem, ivs[6] (STAT_* order), attacker, ability, embargoTurns, variance (u8) }.
// The defender is always AI_CONTEXT.defender (TAI:2878). heldItem/ability/embargoTurns are used
// only by Natural Gift and Judgment here; BattleSystem_CalcMoveDamage and ApplyTypeChart read the
// attacker's real battle state (battle_lib.c:6635-6668, 2577-2582).
export function calcDamage(env, { move, heldItem, ivs, attacker, ability, embargoTurns, variance }) {
  const { ai } = env;
  const defender = ai.defender;
  let damage = 0;
  let power = 0;
  let type = 0;
  const mv = (n) => K(ai, n);

  switch (move) {
    case mv('MOVE_NATURAL_GIFT'): // TAI:2885-2895
      if (ability !== mv('ABILITY_KLUTZ') && embargoTurns === 0) {
        power = itemParam(ai, heldItem, 'naturalGiftPower');
        type = power ? itemParam(ai, heldItem, 'naturalGiftType') : K(ai, 'TYPE_NORMAL');
      }
      break;
    case mv('MOVE_JUDGMENT'): // TAI:2897-2971
      if (ability !== mv('ABILITY_KLUTZ') && embargoTurns === 0) {
        power = 0;
        type = judgmentType(ai, itemParam(ai, heldItem, 'holdEffect'));
      }
      break;
    case mv('MOVE_HIDDEN_POWER'): { // TAI:2973-2993
      const iv = (s) => ivs[STAT[s]] & 0xff;
      power = ((iv('STAT_HP') & 2) >> 1)
        | ((iv('STAT_ATTACK') & 2) >> 0)
        | ((iv('STAT_DEFENSE') & 2) << 1)
        | ((iv('STAT_SPEED') & 2) << 2)
        | ((iv('STAT_SPECIAL_ATTACK') & 2) << 3)
        | ((iv('STAT_SPECIAL_DEFENSE') & 2) << 4);
      type = ((iv('STAT_HP') & 1) >> 0)
        | ((iv('STAT_ATTACK') & 1) << 1)
        | ((iv('STAT_DEFENSE') & 1) << 2)
        | ((iv('STAT_SPEED') & 1) << 3)
        | ((iv('STAT_SPECIAL_ATTACK') & 1) << 4)
        | ((iv('STAT_SPECIAL_DEFENSE') & 1) << 5);
      power = idiv(power * 40, 63) + 30;
      type = idiv(type * 15, 63) + 1;
      if (type >= K(ai, 'TYPE_MYSTERY')) type++;
      break;
    }
    case mv('MOVE_GYRO_BALL'): { // TAI:2995-3003; monSpeedValues is u32[4] (battle_context.h:259)
      const sv = env.mem?.monSpeedValues;
      const d = sv?.[defender];
      const a = sv?.[attacker];
      if (d === undefined || a === undefined) throw new Error('calcdamage: Gyro Ball needs mem.monSpeedValues (battleCtx->monSpeedValues)');
      if ((a >>> 0) === 0) throw new Error('calcdamage: Gyro Ball with monSpeedValues[attacker] == 0 (division by zero in the game)');
      power = 1 + Math.floor(((25 * (d >>> 0)) >>> 0) / (a >>> 0));
      if (power > 150) power = 150;
      type = K(ai, 'TYPE_NORMAL');
      break;
    }
    case mv('MOVE_DRAGON_RAGE'): // TAI:3005-3007
      damage = 40;
      break;
    case mv('MOVE_SEISMIC_TOSS'): // TAI:3009-3012
    case mv('MOVE_NIGHT_SHADE'):
      damage = ai.level(attacker);
      break;
    case mv('MOVE_PSYWAVE'): // TAI:3014-3016 (draws RNG)
      damage = idiv(ai.level(attacker) * ((env.rand() % 11) + 5), 10);
      break;
    case mv('MOVE_RETURN'): // TAI:3018-3021
      power = idiv(ai.friendship(attacker) * 10, 25);
      type = K(ai, 'TYPE_NORMAL');
      break;
    case mv('MOVE_FRUSTRATION'): // TAI:3023-3026
      power = idiv((255 - ai.friendship(attacker)) * 10, 25);
      type = K(ai, 'TYPE_NORMAL');
      break;
    case mv('MOVE_MAGNITUDE'): // TAI:3028-3049 (draws RNG)
      power = env.rand() % 100;
      if (power < 5) power = 10;
      else if (power < 15) power = 30;
      else if (power < 35) power = 50;
      else if (power < 65) power = 70;
      else if (power < 85) power = 90;
      else if (power < 95) power = 110;
      else power = 150;
      type = K(ai, 'TYPE_NORMAL');
      break;
    case mv('MOVE_SONIC_BOOM'): // TAI:3051-3053
      damage = 20;
      break;
    case mv('MOVE_LOW_KICK'): // TAI:3055-3072
    case mv('MOVE_GRASS_KNOT'): {
      const weight = speciesWeightHg(ENUMS.species[ai.species(defender)]);
      let i;
      for (i = 0; WEIGHT_TO_POWER[i][0] !== 0xFFFF; i++) {
        if (WEIGHT_TO_POWER[i][0] >= weight) break;
      }
      power = WEIGHT_TO_POWER[i][0] !== 0xFFFF ? WEIGHT_TO_POWER[i][1] : 120;
      break;
    }
    default: // TAI:3074-3078
      power = 0;
      type = K(ai, 'TYPE_NORMAL');
      break;
  }

  const input = portInput(ai, attacker, defender, move, power, type);
  let ignoreTypeChecks = false;
  if (damage === 0) {
    // TAI:3081-3091: BattleSystem_CalcMoveDamage(..., criticalMul 1). Side/field conditions are
    // the defender side's and the field's, which fromShowdown reads from the live battle.
    damage = calcBaseDamage({ ...input, critMul: 1 });
  } else {
    ignoreTypeChecks = true; // TAI:3093 SYSCTL_IGNORE_TYPE_CHECKS (cleared again at TAI:3104)
  }
  // TAI:3096-3103
  const r = dmgApplyTypeChart(input, damage, { ignoreTypeChecks, moveStatusMask: 0 });
  damage = r.damage | 0;
  if (r.moveStatusMask & MOVE_STATUS.IMMUNE) damage = 0; // TAI:3106-3107
  else damage = battleDivide((damage * (variance & 0xff)) | 0, 100); // TAI:3109
  return damage;
}

// ---------- TrainerAI_CalcAllDamage (TAI:2799-2849) ----------
// Returns { max, damageVals }. `moves` is a u16[4] (0 = MOVE_NONE).
export function calcAllDamage(env, { attacker, moves, heldItem, ivs, ability, embargoTurns, varyDamage }) {
  const { ai } = env;
  const damageVals = [0, 0, 0, 0];
  for (let i = 0; i < 4; i++) {
    const m = moves[i] ?? 0;
    const md = ai.moveData(m);
    if (effectIn(ai, ALT_POWER_EFFECTS, md.effect)
        || (m !== 0 && !effectIn(ai, NO_DAMAGE_CALC_EFFECTS, md.effect) && md.power > 1)) {
      // TAI:2829-2833: `varyDamage == TRUE` (TRUE = 1)
      const roll = varyDamage === 1 ? env.mem.moveDamageRolls[i] & 0xff : 100;
      damageVals[i] = calcDamage(env, { move: m, heldItem, ivs, attacker, ability, embargoTurns, variance: roll });
    } else {
      damageVals[i] = 0;
    }
  }
  let max = 0; // TAI:2842-2846
  for (let i = 0; i < 4; i++) if (max < damageVals[i]) max = damageVals[i];
  return { max, damageVals };
}

// ---------- TrainerAI_MoveType (TAI:3127-3247) ----------
export function moveType(env, battler, move) {
  const { ai } = env;
  switch (move) {
    case K(ai, 'MOVE_NATURAL_GIFT'): // Battler_NaturalGiftType, battle_lib.c:5471-5475
      return itemParam(ai, battlerHeldItem(ai, battler), 'naturalGiftType');
    case K(ai, 'MOVE_JUDGMENT'): // Battler_HeldItemEffect, battle_lib.c:5438-5442
      return judgmentType(ai, itemParam(ai, battlerHeldItem(ai, battler), 'holdEffect'));
    case K(ai, 'MOVE_HIDDEN_POWER'): { // TAI:3208-3220, the battler's own IVs
      const iv = ai.ivs(battler);
      const v = (s) => iv[STAT[s]] & 1;
      let r = (v('STAT_HP') >> 0) | (v('STAT_ATTACK') << 1) | (v('STAT_DEFENSE') << 2)
        | (v('STAT_SPEED') << 3) | (v('STAT_SPECIAL_ATTACK') << 4) | (v('STAT_SPECIAL_DEFENSE') << 5);
      r = idiv(r * 15, 63) + 1;
      if (r >= K(ai, 'TYPE_MYSTERY')) r++;
      return r;
    }
    case K(ai, 'MOVE_WEATHER_BALL'): { // TAI:3222-3240; NO_CLOUD_NINE, WEATHER_IS_* (battle/common.h:63-71)
      let result = K(ai, 'TYPE_NORMAL'); // `result` is uninitialised in the C if no weather bit matches; see below
      const fc = ai.fieldConditionsMask();
      if (noCloudNine(ai) && (fc & K(ai, 'FIELD_CONDITION_WEATHER'))) {
        let set = false;
        if (fc & K(ai, 'FIELD_CONDITION_RAINING')) { result = K(ai, 'TYPE_WATER'); set = true; }
        if (fc & K(ai, 'FIELD_CONDITION_SANDSTORM')) { result = K(ai, 'TYPE_ROCK'); set = true; }
        if (fc & K(ai, 'FIELD_CONDITION_SUNNY')) { result = K(ai, 'TYPE_FIRE'); set = true; }
        if (fc & K(ai, 'FIELD_CONDITION_HAILING')) { result = K(ai, 'TYPE_ICE'); set = true; }
        if (!set) throw new Error('calcdamage: Weather Ball type read uninitialised in the game (weather bit without rain/sand/sun/hail, e.g. fog)');
      } else {
        // C leaves `result` uninitialised here (TAI:3222-3240 has no else); the value the game
        // returns is whatever the register holds. UNVERIFIED; refuse rather than guess.
        throw new Error('calcdamage: Weather Ball type without weather is uninitialised in TrainerAI_MoveType (TAI:3222-3240)');
      }
      return result;
    }
    default:
      return K(ai, 'TYPE_NORMAL');
  }
}

// NO_CLOUD_NINE (battle/common.h:63-64): BattleSystem_CountAbility(COUNT_ALIVE_BATTLERS)
// (battle_lib.c:2952-2958) finds neither Cloud Nine nor Air Lock.
function noCloudNine(ai) {
  for (let b = 0; b < ai.maxBattlers; b++) {
    const a = ai.battlerAbility(b);
    if ((a === K(ai, 'ABILITY_CLOUD_NINE') || a === K(ai, 'ABILITY_AIR_LOCK')) && ai.curHP(b)) return false;
  }
  return true;
}

// BattleSystem_ApplyTypeChart(move, inType, attacker, defender, damage, &mask) with
// SYSCTL_IGNORE_TYPE_CHECKS clear. Returns { damage, moveStatusMask }.
export function applyTypeChart(env, { move, type, attacker, defender, damage }) {
  const input = portInput(env.ai, attacker, defender, move, 0, type);
  const r = dmgApplyTypeChart(input, damage, { ignoreTypeChecks: false, moveStatusMask: 0 });
  return { damage: r.damage, moveStatusMask: r.moveStatusMask };
}

// AI_HasSuperEffectiveMove(battler, flag) (TAI:3560-3598), singles only. The opposite slot
// (BattleSystem_GetBattlerType(battler) ^ 1) is battler ^ 1 in a single battle (battler ids equal
// battler types 0/1 there). With flag TRUE it draws no RNG.
export function hasSuperEffectiveMove(env, battler, flag) {
  const { ai } = env;
  if (ai.battleType() & K(ai, 'BATTLE_TYPE_DOUBLES')) throw new Error('calcdamage: AI_HasSuperEffectiveMove doubles branch not ported');
  const defender = battler ^ 1;
  if ((ai.battlersSwitchingMask() & (1 << defender)) === 0) {
    const moves = ai.moves(battler);
    for (let i = 0; i < 4; i++) {
      const move = moves[i];
      const type = moveType(env, battler, move); // TAI:3578: computed before the `if (move)` check
      if (move) {
        const { moveStatusMask } = applyTypeChart(env, { move, type, attacker: battler, defender, damage: 0 });
        if (moveStatusMask & K(ai, 'MOVE_STATUS_SUPER_EFFECTIVE')) {
          if (flag) return true;
          if (env.rand() % 10 !== 0) return true; // TAI:3588
        }
      }
    }
  }
  return false; // TAI:3597-3599 (not doubles)
}
