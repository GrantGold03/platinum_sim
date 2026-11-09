// Feature 024: the game's formulas for moves whose power is computed at use (one source of truth for
// the trainer-AI port, the strong player's lookahead and the screening player).
//   Return / Frustration  res/battle/scripts/effects/effect_script_0121.s:5-7 / 0123.s:5-8 (friendship*10/25; (255-f)*10/25)
//   Low Kick / Grass Knot  src/battle/battle_script.c:6808-6828 BtlCmd_CalcWeightBasedPower with sWeightToPower
//                          (include/data/battle/weight_to_power.h): the first limit >= weight gives the power, else 120,
//                          so a weight exactly on a limit takes the LOWER tier (Showdown breaks at weight >= limit:
//                          ledger entry mech-weight-tier-boundary).
//   Gyro Ball              src/battle/battle_script.c:7123-7133 BtlCmd_CalcGyroBallPower: 1 + 25*speed[def]/speed[att],
//                          capped at 150 (integer division; the game's monSpeedValues).
// Species weight (hectograms) as the dataproc build computes it: round(kg*10) from res/pokemon/<name>/data.json
// (weight_kilograms, or weight_pounds minus the species_weight_rounding_override of tools/dataproc/src/speciesproc.c,
// times 0.45359237). Pure functions; the only I/O is the cached decomp reads.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DECOMP_ROOT } from './ai/constants.mjs';

// sWeightToPower — include/data/battle/weight_to_power.h:1-8 ({weight in hectograms, power}).
function parseWeightToPower() {
  const text = readFileSync(join(DECOMP_ROOT, 'include/data/battle/weight_to_power.h'), 'utf8');
  const rows = [...text.matchAll(/\{\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*\}/g)].map((m) => [Number(m[1]), Number(m[2])]);
  if (rows.at(-1)?.[0] !== 0xFFFF) throw new Error('variable_power: sWeightToPower terminator missing');
  return rows;
}
export const WEIGHT_TO_POWER = parseWeightToPower();

const SPECIESPROC = 'tools/dataproc/src/speciesproc.c';
function parseWeightOverrides() {
  const lines = readFileSync(join(DECOMP_ROOT, SPECIESPROC), 'utf8').split('\n');
  const start = lines.findIndex((l) => l.includes('species_weight_rounding_override(enum Species species) {'));
  if (start < 0) throw new Error(`variable_power: species_weight_rounding_override not found in ${SPECIESPROC}`);
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
  if (out.size === 0) throw new Error('variable_power: no weight overrides parsed');
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
  else throw new Error(`variable_power: no weight for ${speciesConst}`);
  const hg = Math.round(kg * 10); // C round(): half away from zero; equal to Math.round for kg >= 0
  weightCache.set(speciesConst, hg);
  return hg;
}

/** Low Kick / Grass Knot power for a target of `weightHg` hectograms (battle_script.c:6815-6824). */
export function weightTierPower(weightHg) {
  let i;
  for (i = 0; WEIGHT_TO_POWER[i][0] !== 0xFFFF; i++) if (WEIGHT_TO_POWER[i][0] >= weightHg) break;
  return WEIGHT_TO_POWER[i][0] !== 0xFFFF ? WEIGHT_TO_POWER[i][1] : 120;
}

/** Return's power at `friendship` (0..255): friendship*10/25, integer division. */
export const returnPower = (friendship) => Math.trunc(friendship * 10 / 25);

/** Frustration's power at `friendship`: (255-friendship)*10/25. */
export const frustrationPower = (friendship) => Math.trunc((255 - friendship) * 10 / 25);

/** Gyro Ball power from the attacker's and defender's speed values; 0 when the attacker's speed is 0
 * (the game would divide by zero; the trainer-AI port throws for that case before calling this). */
export function gyroBallPower(attackerSpeed, defenderSpeed) {
  if (!attackerSpeed) return 0;
  return Math.min(150, 1 + Math.floor((25 * defenderSpeed) / attackerSpeed));
}

/** The four moves the optimizer offers (feature 024), by decomp constant. */
export const OFFERED_VARIABLE = new Set(['MOVE_RETURN', 'MOVE_GRASS_KNOT', 'MOVE_LOW_KICK', 'MOVE_GYRO_BALL']);
