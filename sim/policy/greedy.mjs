// Player policy `greedy-v1` (T049). A deliberately simple baseline for the T056 benchmark; it is
// NOT the strong player (that is expectimax2-v1, T050, research R7).
//
// Rule:
//   - Move request: score every move in the Showdown request's `active[0].moves` (the list
//     Showdown already filtered for lock-in / Struggle / Recharge) that is not `disabled`, and
//     send `move <i>` for the highest score. Ties go to the lowest slot (deterministic).
//   - Never switches voluntarily.
//   - Forced switch (own active fainted, or a U-turn/Baton Pass style switch request): send
//     `switch <n>` for the non-active, non-fainted party member whose best move (PP > 0, not
//     disabled) scores highest against the current foe. Ties go to the lowest party position.
//   - Any other request (team preview, wait): Showdown `default`.
//
// Score of a move = expected damage against the foe's current active:
//     mean(calcDamage(...).rolls) × hitChance
//   - rolls: the 16 variance rolls of sim/damage.mjs calcDamage (decomp port; non-crit only),
//     built from the live Showdown state by fromShowdown() (stats, stages, abilities, items,
//     weather, screens). Type immunity gives 0.
//   - hitChance = accuracy / 100 from the decomp move data (data/generated/moves.json, from
//     PP/res/moves/<move>/data.json); accuracy 0 means the move never misses
//     (PP/src/battle/battle_controller_player.c:2900-2903 `if (hitRate == 0) return 0;`), so 1.
//     Accuracy/evasion stages, Compound Eyes, Sand Veil, Bright Powder etc. are NOT modelled.
//   - Status moves (CLASS_STATUS, power 0) score 0.
//   - Variable-power / fixed-damage / OHKO moves (decomp power 1: Seismic Toss, Night Shade,
//     Low Kick, Grass Knot, Gyro Ball, Return, Hidden Power, Flail, Fissure, Counter, ... — see
//     damage.mjs "MECHANICS NOT COVERED") score 0. damage.mjs needs the caller to pass their
//     power, which greedy does not compute; scoring them 0 is the conservative choice and means
//     greedy prefers any fixed-power damaging move over them.
//   - Moves with a fixed nominal power that the game varies at run time (Eruption, Water Spout,
//     Brine, Payback, Facade, Weather Ball, Wake-Up Slap, ...) are scored at their data power.
//   - Multi-hit moves are scored as one hit. Crits are ignored. Damage is not capped at the
//     foe's remaining HP (the task defines the score as the uncapped expected damage).
//   - Absorbing abilities (Water/Volt Absorb, Flash Fire, Dry Skin water, Motor Drive) are only
//     modelled as far as damage.mjs models them.
//   - Moves Showdown offers that have no decomp move (e.g. `recharge`) score 0.
import { calcDamage, fromShowdown, ENUMS } from '../damage.mjs';
import { WEIGHT_TO_POWER, speciesWeightHg } from '../ai/calcdamage.mjs';

export const GREEDY = 'greedy-v1';
// greedy-v2 (feature 010, research R4): identical to greedy-v1 except that the variable-power attacks the
// optimizer offers (Return, Grass Knot, Low Kick, Gyro Ball) are scored at their real power instead of 0, so
// the team screen judges the teams that will play. Same formulas as expectimax2's variablePower
// (trainer_ai.c refs there). Every other power-1 move still scores 0. greedy-v1 is unchanged.
export const GREEDY_V2 = 'greedy-v2';

// Power of a variable-power attack (greedy-v2 only), or undefined (score 0, as in greedy-v1).
function variablePowerV2(md, attacker, foe) {
  const e = md.effect.replace(/^BATTLE_EFFECT_/, '');
  switch (e) {
    case 'POWER_BASED_ON_FRIENDSHIP': return Math.trunc((attacker.happiness ?? 0) * 10 / 25); // Return
    case 'INCREASE_POWER_WITH_WEIGHT': { // Grass Knot, Low Kick
      const weight = speciesWeightHg(ENUMS.species[foe.species.num]);
      let i;
      for (i = 0; WEIGHT_TO_POWER[i][0] !== 0xFFFF; i++) if (WEIGHT_TO_POWER[i][0] >= weight) break;
      return WEIGHT_TO_POWER[i][0] !== 0xFFFF ? WEIGHT_TO_POWER[i][1] : 120;
    }
    case 'POWER_BASED_ON_LOW_SPEED': { // Gyro Ball
      const a = attacker.getStat('spe'), d = foe.getStat('spe');
      return a ? Math.min(150, 1 + Math.floor((25 * d) / a)) : undefined;
    }
    default: return undefined;
  }
}

// Decomp move record for a Showdown move id, or undefined.
function decompMove(gd, sdId) {
  const key = gd.fromSdMove.get(sdId);
  return key === undefined ? undefined : gd.moves[key];
}

/** Expected damage of `attacker` using Showdown move `sdId` on `foe` (see header). */
export function expectedDamage(gd, battle, attacker, foe, sdId, v2 = false) {
  const md = decompMove(gd, sdId);
  if (!md || md.category === 'CLASS_STATUS') return 0;
  let power;
  if (md.power <= 1) {
    power = v2 ? variablePowerV2(md, attacker, foe) : undefined;
    if (!power || power <= 0) return 0;
  }
  const { rolls } = calcDamage(fromShowdown(battle, attacker, foe, sdId, power === undefined ? {} : { power }));
  const mean = rolls.reduce((a, b) => a + b, 0) / rolls.length;
  const hit = md.accuracy === 0 ? 1 : md.accuracy / 100;
  return mean * hit;
}

const foeOf = (battle, side) => battle.sides[side.n ^ 1].active[0];

/** Scores of the request's move list (index-aligned with request.active[0].moves). */
export function moveScores(gd, battle, side, request, v2 = false) {
  const mon = side.active[0];
  const foe = foeOf(battle, side);
  return request.active[0].moves.map((m) => (m.disabled ? -1 : expectedDamage(gd, battle, mon, foe, m.id, v2)));
}

/** Best expected damage of a (benched) party member against the current foe. */
export function memberScore(gd, battle, side, pokemon, v2 = false) {
  const foe = foeOf(battle, side);
  let best = 0;
  for (const s of pokemon.moveSlots) {
    if (s.pp <= 0 || s.disabled) continue;
    best = Math.max(best, expectedDamage(gd, battle, pokemon, foe, s.id, v2));
  }
  return best;
}

const argmax = (xs) => xs.reduce((bi, x, i) => (x > xs[bi] ? i : bi), 0);

function makeGreedy(name, v2) {
  return {
  name,
  choose({ gd, battle, side, request }) {
    if (!request || request.wait || request.teamPreview) return 'default';
    if (request.forceSwitch) {
      // 'switch N' addresses side.pokemon[N-1] (the order request.side.pokemon reports).
      let best = -1;
      let bestScore = -1;
      side.pokemon.forEach((p, i) => {
        if (p.isActive || p.fainted || p.hp <= 0) return;
        const s = memberScore(gd, battle, side, p, v2);
        if (s > bestScore) { best = i; bestScore = s; }
      });
      // No legal switch target: let Showdown resolve it ('default' passes).
      return best < 0 ? 'default' : `switch ${best + 1}`;
    }
    const scores = moveScores(gd, battle, side, request, v2);
    return `move ${argmax(scores) + 1}`;
  },
  };
}

export const greedy = makeGreedy(GREEDY, false);
export const greedyV2 = makeGreedy(GREEDY_V2, true);
