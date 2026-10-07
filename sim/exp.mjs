// Experience, participation and mid-battle level-up for the player side (T036).
//
// Game rules ported (pokeplatinum @ pinned commit; line numbers are from that tree):
//
// Participation ("sideGetExpMask", one bitmask per side, bit = player party slot):
//   - BattleSystem_ClearSideExpGain (src/battle/battle_lib.c:1456-1459) clears the enemy side's mask.
//   - BattleSystem_FlagBattlerExpGain (battle_lib.c:1461-1479) ORs in the player's active party slot
//     (selectedPartySlot[0]; [2] only in doubles) when the enemy battler's curHP != 0 and no
//     battler involved is in battlersSwitchingMask (only set for doubles partners,
//     battle_lib.c:2032-2033, so it never applies in these singles battles).
//   - Callers (src/battle/battle_script.c:455-626, show-encounter / show-pokemon commands):
//     an ENEMY mon entering -> clear the mask, then flag (mask = {player active slot});
//     a PLAYER mon entering -> flag only (mask |= {its slot}).
//   Here: Showdown `switchIn` (also used for drags, U-turn, Baton Pass) is wrapped per battle.
//   At battle start both leads are already in (Showdown starts in the constructor), which gives
//   mask = {lead}, the same as the game's BTLSCR_ENEMY-then-BTLSCR_PLAYER order.
//
// Exp per fainted enemy (BtlCmd_CalcExpGain, battle_script.c:2187-2248):
//   - only for an enemy battler and a battle type that allows exp (battle_script.c:2196);
//   - over the player's party, counting only mons with species and HP != 0 (:2201-2214):
//       totalMonsGainingExp = those in the mask; totalMonsWithExpShare = those holding
//       HOLD_EFFECT_EXP_SHARE (in the mask or not);
//   - `u16 exp = baseExp; exp = (exp * level) / 7;`  -> u16 truncation of floor(base*lvl/7) (:2216-2217)
//   - with any Exp. Share holder: gained = (exp/2)/nGaining, shared = (exp/2)/nShare (:2220-2231);
//     otherwise gained = exp/nGaining, shared = 0 (:2232-2239); each floored to a minimum of 1.
// Per mon (BattleScript_GetExpTask, battle_script.c:9685, SEQ_GET_EXP_START :9725-9778), slots in
// party order, for mons in the mask or holding Exp. Share:
//   - only if HP != 0 and level != MAX_POKEMON_LEVEL (:9740);
//   - total = gained if in the mask (:9741-9743); += shared if Exp. Share holder (:9745-9747);
//   - Lucky Egg (HOLD_EFFECT_EXP_UP): total = total*150/100 (:9749-9751);
//   - trainer battle: total = total*150/100 (:9753-9755);
//   - not OT (traded): total*170/100 if the mon's language differs from the game's, else
//     total*150/100 (:9757-9765). FR-008a: in-game NPC trade mons are not OT.
//   All in u32 integer arithmetic, applied in that order.
//   - exp += total; EV gain (BattleScript_CalcEffortValues :9776) adds nothing once the EV sum
//     is MAX_EVS_ALL_STATS (battle_script.c:10237), which every build has (FR-008: 85 x 6), so it
//     is not modelled.
// Level-up (SEQ_GET_EXP_CHECK_LEVEL_UP :9824 -> Pokemon_ShouldLevelUp, src/pokemon.c:3501-3526):
//   exp is capped at the max-level table value; while exp >= table[level+1], level += 1 and
//   Pokemon_CalcStats (src/pokemon.c:564-645) recomputes stats and raises current HP by the max-HP
//   increase if current HP != 0 (:633-641). Applied mid-battle (T009 method, research R5).
//   New moves (SEQ_GET_EXP_CHECK_LEARN_MOVE :10003) and evolution are DECLINED (spec Edge Cases).
//   NOTE: in the game a mon with an empty move slot learns the move without a prompt
//   (Pokemon_LevelUpMove default branch, battle_script.c:10021-10035); such cases are reported as
//   `auto_learn_in_game` in exp events so the divergence is visible.
import { speciesRecord } from './gamedata.mjs';

export const STAT_KEYS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];

// ---- Stats: Pokemon_CalcStats (src/pokemon.c:564) + Pokemon_GetNatureStatValue (:2593) ---------
export function natureStat(gd, nature, value, key) {
  const aff = gd.constants.nature_affinities[nature]?.[key];
  if (aff === undefined) throw new Error(`unknown nature ${nature}`);
  const v = value & 0xffff; // u16 monStatValue parameter
  if (aff === 1) return ((v * 110) & 0xffff) / 100 | 0; // `u16 result = v*110; result /= 100;`
  if (aff === -1) return ((v * 90) & 0xffff) / 100 | 0;
  return v;
}

export function calcStats(gd, rec, ivs, evs, level, nature) {
  const b = rec.base_stats;
  const out = {};
  // SPECIES_SHEDINJA has max HP 1 (src/pokemon.c:598-599)
  out.hp = rec.key === 'shedinja' ? 1
    : Math.floor(((2 * b.hp + ivs.hp + Math.floor(evs.hp / 4)) * level) / 100) + level + 10;
  for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) {
    const raw = Math.floor(((2 * b[k] + ivs[k] + Math.floor(evs[k] / 4)) * level) / 100) + 5;
    out[k] = natureStat(gd, nature, raw, k);
  }
  return out;
}

// ---- Exp tables (res/pokemon/.shared/exp_tables.csv via data/generated/exp.json) ---------------
export const maxLevel = (gd) => gd.exp.max_level;
export const expAt = (gd, rate, level) => gd.exp.tables[rate][level];

// SpeciesData_GetLevelAt (src/pokemon.c:2378)
export function levelFromExp(gd, rate, exp) {
  const t = gd.exp.tables[rate];
  let i = 1;
  while (i < maxLevel(gd) + 1 && t[i] <= exp) i++;
  return i - 1;
}

// ---- Pure exp arithmetic -----------------------------------------------------------------------
// battle_script.c:2216-2217
export const baseExpYield = (baseExp, faintedLevel) => Math.floor((baseExp * faintedLevel) / 7) & 0xffff;

/**
 * Exp each party slot receives for one fainted enemy.
 * party[i] = {alive, inMask, expShare, luckyEgg, traded, foreignLanguage, atMaxLevel}
 * Returns {exp, gained, shared, nGaining, nShare, totals: [per slot]}.
 */
export function expForFaint({ baseExp, faintedLevel, party, trainerBattle = true }) {
  const exp = baseExpYield(baseExp, faintedLevel);
  let nGaining = 0;
  let nShare = 0;
  for (const m of party) {
    if (!m.alive) continue; // `Pokemon_GetValue(mon, MON_DATA_HP)` (battle_script.c:2204)
    if (m.inMask) nGaining++;
    if (m.expShare) nShare++;
  }
  let gained;
  let shared;
  // nGaining == 0 would divide by zero in C; it cannot matter (no live mon in the mask receives
  // `gained`), so `gained` is left 0 here.
  const div = (a, b) => (b ? Math.floor(a / b) : 0);
  if (nShare) {
    gained = Math.max(1, div(Math.floor(exp / 2), nGaining));
    shared = Math.max(1, Math.floor(Math.floor(exp / 2) / nShare));
  } else {
    gained = Math.max(1, div(exp, nGaining));
    shared = 0;
  }
  const totals = party.map((m) => {
    if (!(m.inMask || m.expShare) || !m.alive || m.atMaxLevel) return 0;
    let total = 0;
    if (m.inMask) total = gained;
    if (m.expShare) total += shared;
    if (m.luckyEgg) total = Math.floor((total * 150) / 100);
    if (trainerBattle) total = Math.floor((total * 150) / 100);
    if (m.traded) total = Math.floor((total * (m.foreignLanguage ? 170 : 150)) / 100);
    return total;
  });
  return { exp, gained, shared, nGaining, nShare, totals };
}

/** Add exp to a party-state member; returns the levels passed through (Pokemon_ShouldLevelUp loop). */
export function addExp(gd, member, amount) {
  const rate = member.rec.exp_rate;
  const cap = expAt(gd, rate, maxLevel(gd)); // pokemon.c:3507-3512
  member.exp = Math.min(member.exp + amount, cap);
  const levels = [];
  while (member.level + 1 <= maxLevel(gd) && member.exp >= expAt(gd, rate, member.level + 1)) {
    member.level += 1; // pokemon.c:3518-3522
    levels.push(member.level);
  }
  return levels;
}

// ---- Showdown side -----------------------------------------------------------------------------
/** Overwrite a Showdown Pokemon's level and stats with the decomp values (T009 method). */
export function applyStats(pokemon, level, stats, { adjustHp = true } = {}) {
  const oldMax = pokemon.maxhp;
  pokemon.level = level;
  pokemon.set.level = level;
  pokemon.baseStoredStats = { ...stats };
  if (!pokemon.transformed) for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) pokemon.storedStats[k] = stats[k];
  pokemon.baseMaxhp = stats.hp;
  pokemon.maxhp = stats.hp;
  // Pokemon_CalcStats: curHP += newMax - oldMax when curHP != 0 (src/pokemon.c:633-641)
  if (adjustHp && pokemon.hp > 0) pokemon.hp = Math.max(1, pokemon.hp + stats.hp - oldMax);
  if (!adjustHp) pokemon.hp = Math.min(pokemon.hp, stats.hp);
  if (typeof pokemon.getUpdatedDetails === 'function') pokemon.details = pokemon.getUpdatedDetails();
}

/**
 * Attaches participation tracking and exp/level-up to one battle.
 * `party` is the gauntlet's player state array (index = original party slot); each member has
 * {rec, level, exp, ivs, evs, nature, itemRec, traded, foreignLanguage, moves:[keys]}.
 * Showdown Pokemon objects carry `platsimSlot` (set by team.mjs).
 */
export class ExpTracker {
  constructor(gd, battle, party, { trainerBattle = true, battleIndex = 0, events = [] } = {}) {
    this.gd = gd;
    this.battle = battle;
    this.party = party;
    this.trainerBattle = trainerBattle;
    this.battleIndex = battleIndex;
    this.events = events;
    this.p1 = battle.sides[0];
    this.p2 = battle.sides[1];
    const lead = this.p1.active[0];
    this.mask = new Set(lead ? [lead.platsimSlot] : []);

    const tracker = this;
    const actions = battle.actions;
    const origSwitchIn = actions.switchIn;
    actions.switchIn = function (pokemon, ...rest) {
      const r = origSwitchIn.call(this, pokemon, ...rest);
      if (r === true) tracker.onSwitchIn(pokemon);
      return r;
    };
    battle.onEvent('Faint', battle.format, (target) => tracker.onFaint(target));
  }

  onSwitchIn(pokemon) {
    if (pokemon.side === this.p2) {
      // BTLSCR_ENEMY / SWITCHED_MON (enemy): ClearSideExpGain + FlagBattlerExpGain (battle_script.c:469-479, 512-521)
      this.mask = new Set();
      const act = this.p1.active[0];
      if (act && pokemon.hp > 0) this.mask.add(act.platsimSlot);
    } else {
      // player mon shown: FlagBattlerExpGain(ENEMY_1) only if the enemy's curHP != 0 (battle_lib.c:1469)
      const foe = this.p2.active[0];
      if (foe && foe.hp > 0 && !foe.fainted) this.mask.add(pokemon.platsimSlot);
    }
  }

  sdPokemon(slot) {
    return this.p1.pokemon.find((p) => p.platsimSlot === slot);
  }

  onFaint(target) {
    if (target.side !== this.p2) return; // exp only for a defeated enemy (battle_script.c:2196)
    const gd = this.gd;
    const rec = target.platsimRec;
    const party = this.party.map((m, slot) => {
      const sd = this.sdPokemon(slot);
      const he = m.itemRec?.hold_effect;
      return {
        alive: !!sd && sd.hp > 0,
        inMask: this.mask.has(slot),
        expShare: he === 'HOLD_EFFECT_EXP_SHARE',
        luckyEgg: he === 'HOLD_EFFECT_EXP_UP',
        traded: !!m.traded,
        foreignLanguage: !!m.foreignLanguage,
        atMaxLevel: m.level === maxLevel(gd),
      };
    });
    const r = expForFaint({ baseExp: rec.base_exp, faintedLevel: target.level, party, trainerBattle: this.trainerBattle });
    const gains = [];
    r.totals.forEach((amount, slot) => {
      if (!amount) return;
      const m = this.party[slot];
      const fromLevel = m.level;
      const levels = addExp(gd, m, amount);
      const g = { slot, exp: amount, total_exp: m.exp, level: m.level };
      if (levels.length) {
        const stats = calcStats(gd, m.rec, m.ivs, m.evs, m.level, m.nature);
        applyStats(this.sdPokemon(slot), m.level, stats);
        g.from_level = fromLevel;
        const learn = m.rec.learnset_level
          .filter(([lv, mv]) => levels.includes(lv) && !m.moves.includes(mv.replace(/^MOVE_/, '').toLowerCase()))
          .map(([lv, mv]) => mv);
        if (learn.length) {
          g.declined_moves = learn; // spec Edge Cases: keep current moves
          if (m.moves.length < 4) g.auto_learn_in_game = true; // battle_script.c:10021
        }
      }
      gains.push(g);
    });
    this.events.push({
      battle: this.battleIndex, turn: this.battle.turn, fainted: rec.key, fainted_level: target.level,
      participants: [...this.mask].sort((a, b) => a - b), exp: r.exp, gained: r.gained, shared: r.shared, gains,
    });
  }
}

export { speciesRecord };
