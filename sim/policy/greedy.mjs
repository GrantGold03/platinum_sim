// Player policy `greedy-v1` (T049). A deliberately simple baseline for the T056 benchmark; it is
// NOT the strong player (that is expectimax2-v2, the default; expectimax2-v1, T050, is kept for
// reproducing recorded results).
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
//   - 024: Return, Grass Knot, Low Kick and Gyro Ball (the moves the optimizer offers) are scored at the
//     power the game computes (sim/variable_power.mjs): Return at the attacker's friendship (Showdown's
//     default 255 -> 102; the simulator assumes max friendship, as legality does), Grass Knot / Low Kick
//     from the foe's species weight tier (the decomp boundary rule), Gyro Ball from the two Pokemon's
//     speed STATS at their levels (`storedStats.spe`), not the game's in-battle speed values (stages,
//     paralysis, items): greedy has no AI adapter and also scores benched members, so this is an
//     approximation of the screening heuristic (plan Complexity Tracking).
//   - Every other variable-power / fixed-damage / OHKO move (decomp power 1: Seismic Toss, Night Shade,
//     Hidden Power, Frustration, Magnitude, Flail, Fissure, Counter, ... — see damage.mjs "MECHANICS NOT
//     COVERED") scores 0: damage.mjs needs the caller to pass their power, which greedy does not compute
//     for them; scoring them 0 is the conservative choice.
//   - Moves with a fixed nominal power that the game varies at run time (Eruption, Water Spout,
//     Brine, Payback, Facade, Weather Ball, Wake-Up Slap, ...) are scored at their data power.
//   - Multi-hit moves are scored as one hit. Crits are ignored. Damage is not capped at the
//     foe's remaining HP (the task defines the score as the uncapped expected damage).
//   - Absorbing abilities (Water/Volt Absorb, Flash Fire, Dry Skin water, Motor Drive) are only
//     modelled as far as damage.mjs models them.
//   - Moves Showdown offers that have no decomp move (e.g. `recharge`) score 0.
import { ENUMS, calcDamage, fromShowdown } from '../damage.mjs';
import { OFFERED_VARIABLE, gyroBallPower, returnPower, speciesWeightHg, weightTierPower } from '../variable_power.mjs'; // 024

export const GREEDY = 'greedy-v1';

// Decomp move record for a Showdown move id, or undefined.
function decompMove(gd, sdId) {
  const key = gd.fromSdMove.get(sdId);
  return key === undefined ? undefined : gd.moves[key];
}

/** Expected damage of `attacker` using Showdown move `sdId` on `foe` (see header). */
export function expectedDamage(gd, battle, attacker, foe, sdId) {
  const md = decompMove(gd, sdId);
  if (!md || md.category === 'CLASS_STATUS') return 0;
  let power;
  if (md.power <= 1) {
    power = variablePowerFor(md.const, attacker, foe); // 024: the four offered moves
    if (!power) return 0;
  }
  const { rolls } = calcDamage(fromShowdown(battle, attacker, foe, sdId, power ? { power } : {}));
  const mean = rolls.reduce((a, b) => a + b, 0) / rolls.length;
  const hit = md.accuracy === 0 ? 1 : md.accuracy / 100;
  return mean * hit;
}

// 024: the computed power of an offered variable-power move for `attacker` on `foe` (Showdown Pokemon), else 0.
export function variablePowerFor(moveConst, attacker, foe) {
  if (!OFFERED_VARIABLE.has(moveConst)) return 0;
  switch (moveConst) {
    case 'MOVE_RETURN': return returnPower(attacker.happiness ?? 255);
    case 'MOVE_GRASS_KNOT': case 'MOVE_LOW_KICK': return weightTierPower(speciesWeightHg(ENUMS.species[foe.species.num]));
    case 'MOVE_GYRO_BALL': return gyroBallPower(attacker.storedStats.spe, foe.storedStats.spe);
    default: return 0;
  }
}

const foeOf = (battle, side) => battle.sides[side.n ^ 1].active[0];

/** Scores of the request's move list (index-aligned with request.active[0].moves). */
export function moveScores(gd, battle, side, request) {
  const mon = side.active[0];
  const foe = foeOf(battle, side);
  return request.active[0].moves.map((m) => (m.disabled ? -1 : expectedDamage(gd, battle, mon, foe, m.id)));
}

/** Best expected damage of a (benched) party member against the current foe (or `foe`: 023, the
 * announced Shift replacement, a benched Showdown Pokemon; field abilities are read from the standing
 * Pokemon, so a benched foe's weather or Cloud Nine is not seen: a known limit of this control player). */
export function memberScore(gd, battle, side, pokemon, foe = foeOf(battle, side)) {
  let best = 0;
  for (const s of pokemon.moveSlots) {
    if (s.pp <= 0 || s.disabled) continue;
    best = Math.max(best, expectedDamage(gd, battle, pokemon, foe, s.id));
  }
  return best;
}

const argmax = (xs) => xs.reduce((bi, x, i) => (x > xs[bi] ? i : bi), 0);

export const greedy = {
  name: GREEDY,
  choose({ gd, battle, side, request }) {
    if (!request || request.wait || request.teamPreview) return 'default';
    if (request.forceSwitch) {
      // 'switch N' addresses side.pokemon[N-1] (the order request.side.pokemon reports).
      let best = -1;
      let bestScore = -1;
      side.pokemon.forEach((p, i) => {
        if (p.isActive || p.fainted || p.hp <= 0) return;
        const s = memberScore(gd, battle, side, p);
        if (s > bestScore) { best = i; bestScore = s; }
      });
      // No legal switch target: let Showdown resolve it ('default' passes).
      return best < 0 ? 'default' : `switch ${best + 1}`;
    }
    const scores = moveScores(gd, battle, side, request);
    return `move ${argmax(scores) + 1}`;
  },
  // 023 Shift: switch when a bench member's best expected damage on the announced foe strictly beats
  // the active's (the same scale as the forced-switch pick); ties stay.
  shiftChoice({ gd, battle, side }, incoming) {
    const cur = memberScore(gd, battle, side, side.active[0], incoming);
    let best = -1, bs = -Infinity;
    side.pokemon.forEach((p, i) => {
      if (p.isActive || p.fainted || p.hp <= 0) return;
      const s = memberScore(gd, battle, side, p, incoming);
      if (s > bs) { bs = s; best = i; }
    });
    if (best >= 0 && bs > cur) {
      return { choice: `switch ${best + 1}`, reason: `active ${cur.toFixed(1)} < ${side.pokemon[best].species.name} ${bs.toFixed(1)} vs ${incoming.species.name}` };
    }
    return { choice: null, reason: `active ${cur.toFixed(1)} >= best bench ${best >= 0 ? bs.toFixed(1) : 'none'} vs ${incoming.species.name}` };
  },
};
