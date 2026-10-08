// Player policies `expectimax2-v1` (T050, research R7, spec FR-013) and `expectimax2-v2` (the
// default strong player since the policy-reversal fix): model-based 2-ply expectimax. One search,
// two versions; they differ only in the options listed under VERSIONS. Everything below describes
// both unless it says otherwise.
//
// VERSIONS (V1_OPTS / V2_OPTS):
//   expectimax2-v1  W_ALIVE 1.0, W_FR 0.45, no koStop. Kept registered, unchanged, so recorded
//                   results (T056, the T058 / US1 optimizer runs) stay reproducible.
//   expectimax2-v2  koStop (see HORIZON), W_ALIVE 0.25, W_FR 0.10. Why: on a quick-run screening
//                   finalist (L58 Infernape/Staraptor/Luxray/Garchomp/Gyarados/Gardevoir with plates
//                   and Sitrus Berries) v1 cleared 109/400 vs greedy-v1 348/400 (McNemar p = 4e-60),
//                   nearly all losses to Cynthia. Measured cause: in 1027 Cynthia decisions on 40
//                   losing-heavy runs v1 switched voluntarily 516 times where greedy attacked, 248 of
//                   them with the foe at 25-50% HP (switch loops instead of finishing a damaged
//                   Spiritomb), and it picked weaker or immune moves to keep a foe out of the KO /
//                   Full Restore range. Two model errors produced this:
//                   (1) the horizon (HORIZON below);
//                   (2) the leaf weights. A logistic fit of P(win this battle) on leaf features over
//                   78,585 decisions of 1,600 greedy-v1 gauntlets on four teams (bias, sum of HP
//                   fractions, alive count per side, usable Full Restores) gives an alive weight of
//                   0.18-0.27 per member relative to 1.0 per full HP bar and a Full Restore weight of
//                   about 0.07 (-0.05 in Cynthia-only data). v1's 1.0 / 0.45 overvalued keeping a
//                   damaged member alive (retreat by switching, taking the hit on a healthy member)
//                   and making the AI burn a Full Restore. v2 uses 0.25 / 0.10 (inside / near the fit).
//                   Ablation on 200 paired runs of that team: koStop alone with v1 weights 138/200,
//                   v2 weights without koStop 135/200, both 171/200 (greedy 169/200).
//
// HORIZON (v2 koStop). After a KO the side that lost a member sends in a replacement it chooses
// (the AI's PostKOSwitchIn picks a counter). With a fixed 2-ply horizon a KO at ply 1 lets that
// replacement act inside the search, while a KO delayed to ply 2 (after a switch, a weaker move, or
// letting the AI waste its turn on a Full Restore) never shows it. v1 therefore preferred delaying
// KOs indefinitely: e.g. Infernape 71/179 vs Spiritomb 65/143 scored Flamethrower (a KO) 0.256 and
// "switch to Garchomp" 0.691, then Garchomp switched to Luxray, and so on. v2 values a ply-1 branch
// in which an active member fainted by the leaf right away (a KO ends the line), so no line is
// credited for pushing the replacement's turn beyond the horizon. Symmetric: a branch in which OUR
// active fainted at ply 1 also stops there. Heuristic status: this is a search-depth rule, not a game
// fact; its effect is measured (VERSIONS), not derived.
//
// WHAT IT DOES (one decision):
//   1. Actions: the legal moves of the Showdown request (`active[0].moves`, not `disabled`) and,
//      unless `trapped`, a switch to every non-fainted benched member. A forced switch
//      (`forceSwitch`) has only the switches. A request with one legal option is answered
//      directly. Never an item (FR-011): the policy can only emit `move N` / `switch N` (or
//      `default` for team preview / wait).
//   2. Opponent prediction: the game's own trainer AI (sim/ai: pickCommand -> ShouldSwitch /
//      ShouldUseItem (Full Restore) / TrainerAI_Main, and BattleAI_PostKOSwitchIn for
//      replacements) is RUN on the state. Its RNG is NOT the real AI stream: the policy does not
//      know the opponent's RNG (a human cannot), so it draws K independent sample streams
//      (AIRng seeded from sha256(prngSeed|<policy name>) mixed with the turn, depth, sample index
//      and a state hash) and uses the empirical distribution of the AI's choices. The real AI
//      stream, the real AI state and the real battle PRNG are never read for prediction and never
//      advanced (sim/test/determinism.test.mjs checks the battle PRNG and AI RNG are untouched).
//      Root (ply 1): K_ROOT samples on the live battle through a read-only adapter. Ply 2:
//      K_PLY2 samples on a HYPOTHETICAL state (see "State model").
//   3. Outcomes of a turn: switches and the AI's Full Restore first, then moves in decomp turn
//      order (battle_controller_player.c:707-790 BattleControllerPlayer_CalcTurnOrder: item/party
//      commands before FIGHT; FIGHT ordered by move priority, MOVE_DATA(move).priority,
//      battle_lib.c:1375-1398, then BattleSystem_CompareBattlerSpeed, ported in
//      sim/ai/cmds/battler.mjs compareBattlerSpeed; a speed tie is a 50/50 branch). Each attack
//      branches on: hit chance (decomp formula battle_controller_player.c:2865-2960 with the
//      HitRateByStage table parsed from include/data/hit_rate_stages.h: accuracy/evasion stages,
//      Simple, Unaware, Compound Eyes, Hustle, Sand Veil / Snow Cloak, BrightPowder-type and
//      Wide Lens-type items), the 16 damage rolls of sim/damage.mjs (decomp port) and the crit
//      chance (damage.mjs critChance, HIGH_CRITICAL effects = +1 stage) with the crit rolls, and
//      full paralysis (1/4) / freeze thaw (1/5) / sleep counters. The 32 weighted rolls are
//      compressed per attack into: KO (exact probability of damage >= current HP) and up to two
//      non-KO buckets (weighted means of the lower / upper halves). Identical end states merge.
//   4. Two plies: ply 1 = each of our actions vs the predicted reply; ply 2 = from every
//      resulting state, after post-KO replacements (the opponent's from the AI's PostKOSwitchIn,
//      ours by a damage-race heuristic), the best of our MOVES (switches are not searched at ply 2)
//      vs the AI's predicted reply on that hypothetical state; then the leaf evaluation.
//      Q(a) = E_opp E_outcomes[ max_a' E_opp' E_outcomes'[ leaf ] ] (v2: a ply-1 outcome in which
//      an active member fainted is valued leaf(outcome), see HORIZON). Ties go to the first action
//      in request order (moves, then switches by party position): deterministic.
//
// LEAF EVALUATION (from the player's point of view; higher is better), on the state after ply 2:
//   + sum over our members of value(m)  - sum over the opponent's members of value(m)
//     value(m) = 0 if fainted, else W_ALIVE (v1 1.0, v2 0.25) + hp/maxhp - statusPenalty(m)
//     statusPenalty: slp 0.25, frz 0.40, par 0.15, brn 0.15 (0.30 if its best move is physical),
//     psn 0.08, tox 0.12  (a status on the opponent therefore counts for us)
//   - opponent Full Restores: W_FR (v1 0.45, v2 0.10) per Full Restore the AI could still use. If the opponent's
//     active is alive below maxHP/4 (the AI's own trigger, TAI:4099-4104) and the slot rule
//     (TAI:4092) lets it use one, the leaf assumes it will: that member is valued at full HP and
//     one Full Restore is spent.
//   + boosts of each active (ours +, theirs -), scaled by its hp fraction: 0.10 per stage of the
//     better of Atk/SpA, 0.05 Spe, 0.04 Def and SpD, 0.06 evasion, 0.03 accuracy.
//   + 0.05 per remaining turn/5 of our Reflect / Light Screen (minus the opponent's).
//   - 0.10 if our active must recharge (plus the opponent's).
//   +-100 when one side has no members left (win / loss).
//   HP is restored between League battles (FR-012), so only winning the current battle matters;
//   the leaf is a proxy for P(win this battle). The constants are policy tuning, not game facts.
//
// STATE MODEL (the hypothetical states the search and the AI run on):
//   Per member: hp, status (+ sleep counter, toxic counter), stat stages, move PP, held item
//   (consumed Sitrus / Focus Sash), recharge / charge-turn locks, Yawn countdown, last move.
//   Per side: the active member, Reflect / Light Screen turns. Opponent: the AI's trainerItems
//   (Full Restores). Weather is the live field's and is held fixed.
//   The AI and the damage port read Showdown objects, so a hypothetical state is MATERIALISED as
//   a "shadow" battle: Object.create() over the live Battle / Side / Pokemon objects with the
//   modelled fields as own properties (hp, status, statusState, boosts, volatiles, moveSlots,
//   item, isActive, side, lastMove, activeTurns; side.active / pokemon / foe / sideConditions;
//   battle.sides / p1 / p2 / turn). Everything not modelled is read through the prototype from the
//   live objects; nothing is written to them. Measured (T050, Cynthia battle after 6 turns, machine
//   under load): Battle toJSON+fromJSON clone 3.6 ms vs shadow state + battle + adapter 46 us
//   (~78x). A clone could also only resolve a turn by SAMPLING Showdown's PRNG, not enumerate the
//   rolls. Checked: the AI on a shadow of the current state chooses exactly what it chooses on the
//   live battle (sim/test/expectimax2.test.mjs). A member that switched in (in the model) has no
//   volatiles.
//
// MODELLED MOVE EFFECTS (decomp effect names, data/generated/moves.json `effect`):
//   damage: fixed-power moves at data power; LEVEL_DAMAGE_FLAT, 20/40_DAMAGE_FLAT, HALVE_HP;
//   variable power: Return/Frustration (TAI:3018-3026 formula), Low Kick/Grass Knot
//   (calcdamage.mjs WEIGHT_TO_POWER, speciesWeightHg), Hidden Power (TAI:2973-2993 formula),
//   Gyro Ball (TAI:2995-3003 formula on the decomp speeds); multi-hit (MULTI_HIT 2-5 hits with
//   3/8,3/8,1/8,1/8, HIT_TWICE, POISON_MULTI_HIT x2); Counter / Mirror Coat (2x the damage of that
//   class taken earlier in the turn); recoil 1/2, 1/3, 1/4 (subscript_recoil_1_*.s; Rock Head and
//   Magic Guard exempt); drain 1/2 (subscript_drain_half_damage_dealt.s); Life Orb 1/10; user
//   stat drops (USER_SP_ATK_DOWN_2, DEF_SPD_DOWN_HIT, LOWER_OWN_ATK_AND_DEF); RECHARGE_AFTER;
//   charge turns (Solar Beam outside sun, Fly/Dig/Dive/Bounce/Shadow Force, CHARGE_TURN_*);
//   Explosion / Self-Destruct (user faints); Sucker Punch fails unless the target attacks after it.
//   status: own stat raises (*_UP, *_UP_2, ATK_DEF_UP, ATK_SPD_UP, SP_ATK_SP_DEF_UP, DEF_SPD_UP,
//   EVA_UP*, Belly Drum), target stat drops (*_DOWN, *_DOWN_2), sleep / paralysis / poison /
//   toxic / burn (with type and ability immunities), Yawn, Rest, half-HP heals, Reflect,
//   Light Screen, Protect / Detect (moving first blocks the foe's move; 1/2 after a success).
//   held items: Sitrus Berry (effect_param % at <= 1/2 HP), Leftovers 1/16, Focus Sash, Life Orb.
//   residual: burn and poison 1/8 (subscript_burn_damage.s, subscript_poison_damage.s), toxic n/16,
//   sandstorm / hail 1/16.
//   Intimidate on a modelled switch-in.
//
// KNOWN GAPS (each a candidate divergence / limitation of the policy, not of the battle):
//   - Every other status move (weather, hazards, Taunt, Encore, Substitute, Baton Pass, Trick
//     Room, confusion, Leech Seed, ...) is modelled as having NO effect: scored conservatively,
//     so the policy only picks one when nothing else is better.
//   - Secondary effect chances of damaging moves (burn 10%, flinch, stat drops on the target,
//     confusion) are ignored. Confusion, infatuation, flinch are not modelled.
//   - Weather never changes inside the search (Sunny Day / Sandstorm / Sand Stream have no
//     modelled effect); weather turns do not expire.
//   - Entry hazards, Pursuit, U-turn's switch, Baton Pass, Roar are not modelled.
//   - Quick Claw / Custap / Lagging Tail are not triggered in the model (speedRand not drawn).
//   - Multi-hit moves use one roll and one crit roll for all hits. Variable-power moves other than
//     those listed (Eruption, Facade, Brine, Payback, Avalanche, Punishment, ...) use data power;
//     OHKO moves, Psywave, Magnitude, Present, Endeavor, Bide, Metal Burst, Future Sight score 0.
//   - Opponent ply-2 replies use K_PLY2 AI samples only; AI memory of the player's ability and
//     item is not updated inside the search (only the last move is).
//   - Abilities beyond those the damage port and the items above read are ignored (e.g. Clear
//     Body vs stat drops, Natural Cure on switch, Shed Skin, Synchronize, Static, Flame Body).
//   - Ply 2 does not search our switches; our post-KO replacement inside the search is a damage-
//     race heuristic, not a search.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { calcDamage, critChance, fromShowdown, DECOMP, ENUMS } from '../damage.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { AIRng, checkInvalidMoves, speedValuesNow, trainerAIMain } from '../ai/choose.mjs';
import { createAIState, processLog, stateFor } from '../ai/opponent.mjs';
import { replacementSlot } from '../ai/switch.mjs';
import { pickCommand } from '../ai/items.mjs';
import { compareBattlerSpeed } from '../ai/cmds/battler.mjs';
import { WEIGHT_TO_POWER, speciesWeightHg } from '../ai/calcdamage.mjs';

export const EXPECTIMAX2 = 'expectimax2-v1';
export const EXPECTIMAX2_V2 = 'expectimax2-v2';

// Per-version model options (see the header, VERSIONS). v1 = the recorded expectimax2-v1 behaviour.
//   koStop  a ply-1 branch in which an active member fainted is valued by the leaf at once (HORIZON)
//   wAlive  leaf value of being alive, per member (PARAMS.W_ALIVE when absent)
//   wFR     leaf value of one usable opponent Full Restore (PARAMS.W_FR when absent)
export const V1_OPTS = Object.freeze({ koStop: false });
export const V2_OPTS = Object.freeze({ koStop: true, wAlive: 0.25, wFR: 0.1 });

// Process-wide counters (diagnostics and benchmarks only; never read by the search).
export const STATS = { decisions: 0, aiCalls: 0, turns: 0, leaves: 0, ms: 0, aiMs: 0, viewMs: 0 };

// Search parameters (policy tuning).
export const PARAMS = {
  K_ROOT: 8, // AI samples for the opponent's reply at the root
  K_PLY2: 2, // AI samples at each hypothetical ply-2 state
  SWITCH_BEAM: 2, // switch targets searched at the root (best by the damage-race heuristic)
  W_ALIVE: 1.0,
  W_FR: 0.45,
  WIN: 100,
};

// ---------------------------------------------------------------------------------------------
// Decomp tables

// HitRateByStage (pokeplatinum/include/data/hit_rate_stages.h:4-18), used at
// battle_controller_player.c:2919-2920.
const HIT_RATE_BY_STAGE = (() => {
  const txt = readFileSync(join(DECOMP, 'include/data/hit_rate_stages.h'), 'utf8');
  const body = txt.slice(txt.indexOf('HitRateByStage[]'));
  const rows = [...body.matchAll(/\{\s*(\d+),\s*(\d+)\s*\}/g)].map((m) => [Number(m[1]), Number(m[2])]);
  if (rows.length !== 13) throw new Error(`expectimax2: HitRateByStage has ${rows.length} rows, expected 13`);
  return rows;
})();

// ---------------------------------------------------------------------------------------------
// Move classification from the decomp effect name

const SELF_BOOSTS = {
  ATK_UP: { atk: 1 }, ATK_UP_2: { atk: 2 }, DEF_UP: { def: 1 }, DEF_UP_2: { def: 2 },
  SP_ATK_UP: { spa: 1 }, SP_ATK_UP_2: { spa: 2 }, SP_DEF_UP_2: { spd: 2 }, SPEED_UP_2: { spe: 2 },
  ATK_DEF_UP: { atk: 1, def: 1 }, ATK_SPD_UP: { atk: 1, spe: 1 }, SP_ATK_SP_DEF_UP: { spa: 1, spd: 1 },
  DEF_SPD_UP: { def: 1, spd: 1 }, EVA_UP: { evasion: 1 }, EVA_UP_2_MINIMIZE: { evasion: 2 },
  DEF_UP_DOUBLE_ROLLOUT_POWER: { def: 1 }, SP_DEF_UP_DOUBLE_ELECTRIC_POWER: { spd: 1 },
};
const FOE_DROPS = {
  ATK_DOWN: { atk: -1 }, ATK_DOWN_2: { atk: -2 }, DEF_DOWN: { def: -1 }, DEF_DOWN_2: { def: -2 },
  SPEED_DOWN: { spe: -1 }, SPEED_DOWN_2: { spe: -2 }, SP_DEF_DOWN_2: { spd: -2 },
  ACC_DOWN: { accuracy: -1 }, EVA_DOWN: { evasion: -1 }, ATK_DEF_DOWN: { atk: -1, def: -1 },
};
const USER_DROPS_ON_HIT = {
  USER_SP_ATK_DOWN_2: { spa: -2 }, DEF_SPD_DOWN_HIT: { def: -1, spd: -1 }, LOWER_OWN_ATK_AND_DEF: { atk: -1, def: -1 },
};
const STATUS_OF = {
  STATUS_SLEEP: 'slp', STATUS_PARALYZE: 'par', STATUS_POISON: 'psn', STATUS_BADLY_POISON: 'tox', STATUS_BURN: 'brn',
};
const RECOIL = { RECOIL_HALF: 2, RECOIL_THIRD: 3, RECOIL_BURN_HIT: 3, RECOIL_PARALYZE_HIT: 3, RECOIL_QUARTER: 4 };
const CHARGE_EFFECTS = new Set(['SKIP_CHARGE_TURN_IN_SUN', 'FLY', 'DIG', 'DIVE', 'BOUNCE', 'SHADOW_FORCE',
  'CHARGE_TURN_DEF_UP', 'CHARGE_TURN_HIGH_CRIT', 'CHARGE_TURN_HIGH_CRIT_FLINCH']);
const HEAL_HALF = new Set(['RESTORE_HALF_HP', 'HEAL_HALF_MORE_IN_SUN', 'HEAL_HALF_REMOVE_FLYING_TYPE']);
const eff = (rec) => rec.effect.replace(/^BATTLE_EFFECT_/, '');

function moveInfo(gd, sdId) {
  const key = gd.fromSdMove.get(sdId);
  return key === undefined ? null : gd.moves[key];
}

// ---------------------------------------------------------------------------------------------
// Model state

const BOOST_KEYS = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion'];
const clampStage = (x) => Math.max(-6, Math.min(6, x));

function monFromReal(p, side, idx) {
  const v = p.volatiles || {};
  let charging = -1;
  if (v.twoturnmove) charging = p.moveSlots.findIndex((s) => s.id === v.twoturnmove.move);
  return {
    side, idx, ref: p,
    hp: p.hp, maxhp: p.maxhp,
    status: p.hp > 0 ? (p.status || '') : '',
    slp: p.status === 'slp' ? (p.statusState.time ?? 1) : 0,
    tox: p.status === 'tox' ? (p.statusState.stage ?? 0) : 0,
    boosts: p.isActive ? { ...p.boosts } : { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 },
    pp: p.moveSlots.map((s) => s.pp),
    item: p.item || '',
    fresh: false, // volatiles come from the live Pokemon
    recharge: !!v.mustrecharge,
    charging,
    yawn: v.yawn ? 1 : 0,
    protectOk: v.stall ? 0.5 : 1,
    protecting: false,
    lastMoveId: p.lastMove ? p.lastMove.id : null,
    lastMoveOk: p.moveLastTurnResult !== false,
    activeTurns: p.activeTurns,
  };
}

function cloneMon(m) {
  return { ...m, boosts: { ...m.boosts }, pp: m.pp.slice() };
}
function cloneState(S) {
  return {
    turn: S.turn, weather: S.weather,
    sides: S.sides.map((s) => ({ active: s.active, sc: { ...s.sc }, mons: s.mons.map(cloneMon) })),
    items: { ...S.items, trainerItems: S.items.trainerItems.slice() },
    moveHit: S.moveHit.slice(), moveHitBattler: S.moveHitBattler.slice(),
    taken: [{ phys: 0, spec: 0 }, { phys: 0, spec: 0 }],
  };
}
const activeOf = (S, side) => (S.sides[side].active >= 0 ? S.sides[side].mons[S.sides[side].active] : null);
const aliveCount = (S, side) => S.sides[side].mons.reduce((n, m) => n + (m.hp > 0 ? 1 : 0), 0);

function signature(S) {
  let s = `${S.turn}`;
  for (const side of S.sides) {
    s += `|${side.active}:${side.sc.reflect ?? 0},${side.sc.lightscreen ?? 0}`;
    for (const m of side.mons) {
      s += `;${m.hp},${m.status},${m.slp},${m.tox},${m.item},${m.recharge ? 1 : 0},${m.charging},${m.yawn}`;
      if (m.idx === side.active) s += `,${BOOST_KEYS.map((k) => m.boosts[k]).join('.')},${m.lastMoveId}`;
    }
  }
  s += `|${S.items.trainerItems.join('.')}|${S.moveHit.join('.')}`;
  return s;
}

const WEATHER = { sunnyday: 'sun', raindance: 'rain', sandstorm: 'sand', hail: 'hail' };

// ---------------------------------------------------------------------------------------------
// Decision context (one per decision; caches)

function cheapHash(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return h >>> 0;
}

const battleStates = new WeakMap();

function mirrorFor(battle, trainer, name) {
  let per = battleStates.get(battle);
  if (!per) { per = new Map(); battleStates.set(battle, per); }
  let st = per.get(name);
  if (!st) {
    // A private mirror of the AI's memory, rebuilt from the public log by the same processLog the
    // real AI uses. Its RNG is a throwaway stream (only its 4 initial speedRand draws use it).
    const mirror = createAIState(battle, { trainer, aiSide: 'p2', rng: new AIRng(0) });
    const seedBase = parseInt(createHash('sha256').update(`${Array.isArray(battle.prngSeed) ? battle.prngSeed.join(',') : String(battle.prngSeed)}|${name}`).digest('hex').slice(0, 8), 16) >>> 0;
    st = { mirror, seedBase };
    per.set(name, st);
  }
  return st;
}

function staticInfo(X, m) {
  let s = X.static.get(m.ref);
  if (!s) {
    const moves = m.ref.moveSlots.map((slot) => ({ id: slot.id, rec: moveInfo(X.gd, slot.id) }));
    const types = m.ref.getTypes();
    const ability = ENUMS.abilities[m.ref.getAbility().num] ?? 'ABILITY_NONE';
    let bestPhysical = 0, bestSpecial = 0;
    for (const mv of moves) {
      if (!mv.rec || mv.rec.power <= 1) continue;
      if (mv.rec.category === 'CLASS_PHYSICAL') bestPhysical = Math.max(bestPhysical, mv.rec.power);
      if (mv.rec.category === 'CLASS_SPECIAL') bestSpecial = Math.max(bestSpecial, mv.rec.power);
    }
    s = { moves, types, ability, physical: bestPhysical > bestSpecial };
    X.static.set(m.ref, s);
  }
  return s;
}
const itemConst = (X, sdItem) => {
  if (!sdItem) return 'ITEM_NONE';
  const it = X.battle.dex.items.get(sdItem);
  return ENUMS.items[it.num] ?? 'ITEM_NONE';
};
const holdEffect = (X, sdItem) => (sdItem ? X.gd.itemByConst.get(itemConst(X, sdItem))?.hold_effect ?? '' : '');
const itemParam = (X, sdItem) => (sdItem ? X.gd.itemByConst.get(itemConst(X, sdItem))?.effect_param ?? 0 : 0);

// ---------------------------------------------------------------------------------------------
// Shadow battle (hypothetical state materialised over the live objects; never writes to them)

function shadowBattle(X, S) {
  const real = X.battle;
  const b = Object.create(real);
  const sides = [0, 1].map((i) => Object.create(real.sides[i]));
  sides.forEach((sh, i) => {
    const ss = S.sides[i];
    const mons = ss.mons.map((m) => {
      const p = Object.create(m.ref);
      const active = ss.active === m.idx;
      p.side = sh;
      p.hp = m.hp;
      p.fainted = m.hp <= 0;
      p.status = m.status;
      p.statusState = { ...m.ref.statusState, time: m.slp, stage: m.tox };
      p.boosts = active ? { ...m.boosts } : { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 };
      const vol = active && !m.fresh ? { ...m.ref.volatiles } : {};
      if (!m.recharge) delete vol.mustrecharge; else vol.mustrecharge = vol.mustrecharge ?? { id: 'mustrecharge' };
      p.volatiles = vol;
      // Pokemon.getTypes() runs the 'Type' event; in gen 4 only Roost changes it (Showdown
      // data/mods/gen4 conditions). Without Roost the result is the stored types, so answer that
      // directly (a large share of the AI's cost on hypothetical states).
      if (!vol.roost) { const types = m.ref.types; p.getTypes = () => types.slice(); }
      p.isActive = active;
      p.position = 0;
      p.moveSlots = m.ref.moveSlots.map((s, j) => ({ ...s, pp: m.pp[j] ?? s.pp }));
      p.item = m.item;
      p.lastMove = m.lastMoveId ? real.dex.moves.get(m.lastMoveId) : null;
      p.moveLastTurnResult = m.lastMoveOk;
      p.activeTurns = m.activeTurns;
      return p;
    });
    sh.pokemon = mons;
    sh.active = [ss.active >= 0 ? mons[ss.active] : null];
    const sc = { ...real.sides[i].sideConditions };
    delete sc.reflect; delete sc.lightscreen;
    if (ss.sc.reflect) sc.reflect = { id: 'reflect', duration: ss.sc.reflect };
    if (ss.sc.lightscreen) sc.lightscreen = { id: 'lightscreen', duration: ss.sc.lightscreen };
    sh.sideConditions = sc;
    sh.pokemonLeft = mons.filter((x) => x.hp > 0).length;
  });
  sides[0].foe = sides[1];
  sides[1].foe = sides[0];
  b.sides = sides; // Battle.p1 / p2 are getters over this.sides
  b.turn = S.turn;
  return b;
}

const partyOrderOf = (b) => {
  const order = (side) => {
    const mons = side.pokemon.slice();
    if (mons.every((p) => Number.isInteger(p.platsimSlot))) mons.sort((a, c) => a.platsimSlot - c.platsimSlot);
    return mons;
  };
  return { p1: order(b.p1), p2: order(b.p2) };
};

// A view = {battle, ai adapter} for a state: the live battle at the root, a shadow elsewhere.
function viewOf(X, S) {
  if (S === X.root) return X.rootView;
  const key = signature(S);
  let v = X.views.get(key);
  if (!v) {
    const b = shadowBattle(X, S);
    const ai = createAdapter(b, { aiSide: 'p2', partyOrder: partyOrderOf(b), speedRand: (i) => X.speedRand[i] });
    v = { battle: b, ai, key };
    X.views.set(key, v);
  }
  return v;
}

// ---------------------------------------------------------------------------------------------
// Speed / order

const FASTER = 0; // COMPARE_SPEED_FASTER, include/constants/battle.h:163
function speedInfo(X, S) {
  const v = viewOf(X, S);
  if (v.speed) return v.speed;
  const mem = { monSpeedValues: [0, 0, 0, 0] };
  let pFirst = 0.5;
  const a = activeOf(S, 0), o = activeOf(S, 1);
  if (a && o && a.hp > 0 && o.hp > 0) {
    const r = compareBattlerSpeed({ ai: v.ai, mem, rand: () => 0 }, 0, 1);
    pFirst = r === FASTER ? 1 : 0;
    if (mem.monSpeedValues[0] === mem.monSpeedValues[1]) pFirst = 0.5;
  }
  v.speed = { pFirst, speeds: mem.monSpeedValues };
  return v.speed;
}

// ---------------------------------------------------------------------------------------------
// Damage

function variablePower(X, S, u, t, rec, uRef, tRef) {
  const e = eff(rec);
  switch (e) {
    case 'POWER_BASED_ON_FRIENDSHIP': return Math.trunc((uRef.happiness ?? 0) * 10 / 25); // TAI:3018-3021
    case 'POWER_BASED_ON_LOW_FRIENDSHIP': return Math.trunc((255 - (uRef.happiness ?? 0)) * 10 / 25); // TAI:3023-3026
    case 'INCREASE_POWER_WITH_WEIGHT': { // TAI:3055-3072
      const weight = speciesWeightHg(ENUMS.species[tRef.species.num]);
      let i;
      for (i = 0; WEIGHT_TO_POWER[i][0] !== 0xFFFF; i++) if (WEIGHT_TO_POWER[i][0] >= weight) break;
      return WEIGHT_TO_POWER[i][0] !== 0xFFFF ? WEIGHT_TO_POWER[i][1] : 120;
    }
    case 'RANDOM_POWER_BASED_ON_IVS': { // TAI:2973-2993 (power part)
      const iv = uRef.set.ivs;
      const p = ((iv.hp & 2) >> 1) | ((iv.atk & 2) >> 0) | ((iv.def & 2) << 1) | ((iv.spe & 2) << 2) | ((iv.spa & 2) << 3) | ((iv.spd & 2) << 4);
      return Math.trunc(p * 40 / 63) + 30;
    }
    case 'POWER_BASED_ON_LOW_SPEED': { // TAI:2995-3003
      const { speeds } = speedInfo(X, S);
      const a = speeds[u.side === 0 ? 0 : 1], d = speeds[u.side === 0 ? 1 : 0];
      if (!a) return 0;
      return Math.min(150, 1 + Math.floor((25 * d) / a));
    }
    default: return undefined;
  }
}
function hiddenPowerType(uRef) { // TAI:2973-2993 (type part)
  const iv = uRef.set.ivs;
  let type = ((iv.hp & 1) >> 0) | ((iv.atk & 1) << 1) | ((iv.def & 1) << 2) | ((iv.spe & 1) << 3) | ((iv.spa & 1) << 4) | ((iv.spd & 1) << 5);
  type = Math.trunc(type * 15 / 63) + 1;
  const mystery = ENUMS.types.indexOf('TYPE_MYSTERY');
  if (type >= mystery) type++;
  return ENUMS.types[type];
}

// Damage table for u's move `slot` on t: {fixed} or {rolls, crolls, critP}; null if no damage.
function damageTable(X, S, u, t, rec) {
  const e = eff(rec);
  const sInfo = staticInfo(X, u);
  const tInfo = staticInfo(X, t);
  const pinch = u.hp * 3 <= u.maxhp ? 1 : 0;
  const key = `${u.side}${u.idx}>${t.side}${t.idx}:${rec.key}:${BOOST_KEYS.slice(0, 5).map((k) => u.boosts[k]).join('.')}/${BOOST_KEYS.slice(0, 5).map((k) => t.boosts[k]).join('.')}:${u.status}:${t.status}:${pinch}:${u.item}:${t.item}:${S.sides[t.side].sc.reflect ? 1 : 0}${S.sides[t.side].sc.lightscreen ? 1 : 0}:${u.fresh ? 1 : 0}${t.fresh ? 1 : 0}`;
  let d = X.dmg.get(key);
  if (d !== undefined) return d;
  d = null;
  const num = rec.id;
  let fixed;
  if (e === 'LEVEL_DAMAGE_FLAT') fixed = u.ref.level;
  else if (e === '40_DAMAGE_FLAT') fixed = 40;
  else if (e === '20_DAMAGE_FLAT') fixed = 20;
  else if (e === 'HALVE_HP') fixed = -1; // computed at use time from t.hp
  let power, type;
  if (fixed === undefined && rec.power <= 1) {
    power = variablePower(X, S, u, t, rec, u.ref, t.ref);
    if (power === undefined || power <= 0) { X.dmg.set(key, null); return null; }
    if (e === 'RANDOM_POWER_BASED_ON_IVS') type = hiddenPowerType(u.ref);
  }
  const base = fromShowdown(X.battle, u.ref, t.ref, num, { power, type, powerMul: 10 });
  const fix = (bt, m, info) => {
    bt.stages = { atk: m.boosts.atk, def: m.boosts.def, spa: m.boosts.spa, spd: m.boosts.spd };
    bt.hp = m.hp;
    bt.status = m.status;
    bt.item = itemConst(X, m.item);
    if (m.fresh) {
      bt.flashFire = false; bt.charge = false; bt.helpingHand = false; bt.metronomeTurns = 0; bt.foresight = false;
      bt.magnetRise = false; bt.ingrain = false; bt.roosting = false; bt.miracleEye = false; bt.focusEnergy = false;
      bt.abilitySuppressed = false; bt.embargo = false; bt.types = info.types.map((x) => `TYPE_${x.toUpperCase()}`);
      if (bt.types.length === 1) bt.types.push(bt.types[0]);
    }
  };
  fix(base.attacker, u, sInfo);
  fix(base.defender, t, tInfo);
  const sc = S.sides[t.side].sc;
  base.field.defenderSide = { ...base.field.defenderSide, reflect: !!sc.reflect, lightScreen: !!sc.lightscreen };
  const fieldAb = (bt) => (bt.abilitySuppressed ? 'ABILITY_NONE' : bt.ability);
  base.field.abilitiesOnField = [fieldAb(base.attacker), fieldAb(base.defender)].filter((x, i) => (i === 0 ? u.hp > 0 : t.hp > 0));
  base.field.attackerSideAbilities = [fieldAb(base.attacker)];
  base.field.defenderSideAbilities = [fieldAb(base.defender)];
  const nc = calcDamage(base);
  if (nc.immune) { X.dmg.set(key, null); return null; }
  if (fixed !== undefined) {
    d = { fixed };
  } else {
    const cr = calcDamage({ ...base, crit: true });
    const stage = /HIGH_CRITICAL/.test(e) ? 1 : 0;
    d = { rolls: nc.rolls, crolls: cr.rolls, critP: critChance(base, stage) };
  }
  X.dmg.set(key, d);
  return d;
}

const HITS = { MULTI_HIT: [[2, 3 / 8], [3, 3 / 8], [4, 1 / 8], [5, 1 / 8]], HIT_TWICE: [[2, 1]], POISON_MULTI_HIT: [[2, 1]] };

// Outcome buckets [{p, dmg}] of one hit of `rec` (given it hits) against t's current HP.
function damageOutcomes(X, S, u, t, rec) {
  const d = damageTable(X, S, u, t, rec);
  if (!d) return null;
  if (d.fixed !== undefined) {
    const dmg = d.fixed < 0 ? Math.max(1, Math.floor(t.hp / 2)) : d.fixed;
    return [{ p: 1, dmg }];
  }
  const hits = HITS[eff(rec)] ?? [[1, 1]];
  const ws = [];
  for (const [n, pn] of hits) {
    for (let i = 0; i < 16; i++) {
      ws.push([d.rolls[i] * n, (1 - d.critP) / 16 * pn]);
      if (d.critP > 0) ws.push([d.crolls[i] * n, d.critP / 16 * pn]);
    }
  }
  let pKO = 0;
  const non = [];
  for (const [dmg, w] of ws) {
    if (dmg >= t.hp) pKO += w; else non.push([dmg, w]);
  }
  const out = [];
  if (pKO > 0) out.push({ p: pKO, dmg: t.hp });
  if (non.length) {
    non.sort((a, b) => a[0] - b[0]);
    const tot = non.reduce((s, x) => s + x[1], 0);
    const lo = non[0][0], hi = non[non.length - 1][0];
    if (hi - lo <= Math.max(2, t.maxhp * 0.06)) {
      out.push({ p: tot, dmg: Math.round(non.reduce((s, x) => s + x[0] * x[1], 0) / tot) });
    } else {
      let acc = 0, s1 = 0, w1 = 0, s2 = 0, w2 = 0;
      for (const [dmg, w] of non) {
        if (acc + w / 2 <= tot / 2) { s1 += dmg * w; w1 += w; } else { s2 += dmg * w; w2 += w; }
        acc += w;
      }
      if (w1 > 0) out.push({ p: w1, dmg: Math.round(s1 / w1) });
      if (w2 > 0) out.push({ p: w2, dmg: Math.round(s2 / w2) });
    }
  }
  return out;
}

// battle_controller_player.c:2865-2960 BattleControllerPlayer_CheckMoveHitAccuracy, as P(hit).
function hitChance(X, S, u, t, rec) {
  if (rec.accuracy === 0) return 1; // :2900-2903
  const e = eff(rec);
  if (e === 'BYPASS_ACCURACY' || e === 'PRIORITY_NEG_1_BYPASS_ACCURACY') return 1;
  const ua = staticInfo(X, u).ability, ta = staticInfo(X, t).ability;
  const moldBreaker = ua === 'ABILITY_MOLD_BREAKER';
  let accStages = u.boosts.accuracy;
  let evaStages = -t.boosts.evasion;
  if (ua === 'ABILITY_SIMPLE') accStages *= 2;
  if (ta === 'ABILITY_SIMPLE' && !moldBreaker) evaStages *= 2;
  if (ta === 'ABILITY_UNAWARE' && !moldBreaker) accStages = 0;
  if (ua === 'ABILITY_UNAWARE') evaStages = 0;
  if (!t.fresh && t.ref.volatiles?.foresight && evaStages < 0) evaStages = 0;
  const sum = Math.max(0, Math.min(12, 6 + evaStages + accStages));
  let hitRate = rec.accuracy;
  const [num, den] = HIT_RATE_BY_STAGE[sum];
  hitRate = Math.floor((hitRate * num) / den);
  if (ua === 'ABILITY_COMPOUND_EYES') hitRate = Math.floor(hitRate * 130 / 100);
  const noCloudNine = ![ua, ta].some((a) => a === 'ABILITY_CLOUD_NINE' || a === 'ABILITY_AIR_LOCK');
  if (noCloudNine) {
    if (S.weather === 'sand' && ta === 'ABILITY_SAND_VEIL' && !moldBreaker) hitRate = Math.floor(hitRate * 80 / 100);
    if (S.weather === 'hail' && ta === 'ABILITY_SNOW_CLOAK' && !moldBreaker) hitRate = Math.floor(hitRate * 80 / 100);
  }
  if (ua === 'ABILITY_HUSTLE' && rec.category === 'CLASS_PHYSICAL') hitRate = Math.floor(hitRate * 80 / 100);
  if (holdEffect(X, t.item) === 'HOLD_EFFECT_ACC_REDUCE') hitRate = Math.floor(hitRate * (100 - itemParam(X, t.item)) / 100);
  if (holdEffect(X, u.item) === 'HOLD_EFFECT_ACCURACY_UP') hitRate = Math.floor(hitRate * (100 + itemParam(X, u.item)) / 100);
  return Math.min(100, hitRate) / 100; // miss iff (rand % 100) + 1 > hitRate (:2949)
}

// ---------------------------------------------------------------------------------------------
// Turn resolution

function addBoosts(m, b) {
  for (const k of Object.keys(b)) m.boosts[k] = clampStage(m.boosts[k] + b[k]);
}

function afterHpLoss(X, m) {
  if (m.hp > 0 && m.item && holdEffect(X, m.item) === 'HOLD_EFFECT_HP_PCT_RESTORE' && m.hp * 2 <= m.maxhp) {
    m.hp = Math.min(m.maxhp, m.hp + Math.floor(m.maxhp * itemParam(X, m.item) / 100));
    m.item = '';
  }
}

function doSwitch(X, S, side, idx) {
  const sd = S.sides[side];
  const old = activeOf(S, side);
  if (old) {
    old.boosts = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 };
    old.fresh = true; old.recharge = false; old.charging = -1; old.yawn = 0; old.protectOk = 1;
    if (old.status === 'tox') old.tox = 0;
    old.lastMoveId = null;
  }
  sd.active = idx;
  const m = sd.mons[idx];
  m.fresh = true; m.activeTurns = 0; m.lastMoveId = null; m.lastMoveOk = true;
  m.boosts = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 };
  S.moveHit[side === 0 ? 0 : 1] = 0;
  if (staticInfo(X, m).ability === 'ABILITY_INTIMIDATE') {
    const foe = activeOf(S, 1 - side);
    if (foe && foe.hp > 0) addBoosts(foe, { atk: -1 });
  }
}

const statusImmune = (X, t, status) => {
  const info = staticInfo(X, t);
  const types = info.types;
  const a = info.ability;
  if (status === 'slp') return a === 'ABILITY_INSOMNIA' || a === 'ABILITY_VITAL_SPIRIT';
  if (status === 'par') return a === 'ABILITY_LIMBER';
  if (status === 'psn' || status === 'tox') return a === 'ABILITY_IMMUNITY' || types.includes('Poison') || types.includes('Steel');
  if (status === 'brn') return a === 'ABILITY_WATER_VEIL' || types.includes('Fire');
  return false;
};

// One branch = {p, S}. Returns the branches after `side` uses `act`.
function doMove(X, br, side, act, foeAct, foeMovesLater) {
  const S = br.S;
  const u = activeOf(S, side), t = activeOf(S, 1 - side);
  if (!u || u.hp <= 0) return [br];
  if (u.recharge) { u.recharge = false; return [br]; }
  const rec = act.rec;
  if (!rec) return [br];
  // pre-move status checks
  const pre = [];
  if (u.status === 'slp') {
    u.slp -= staticInfo(X, u).ability === 'ABILITY_EARLY_BIRD' ? 2 : 1;
    if (u.slp > 0) { u.lastMoveOk = false; return [br]; }
    u.status = ''; u.slp = 0;
    pre.push(br);
  } else if (u.status === 'frz') {
    const thaw = { p: br.p * 0.2, S: cloneState(S) };
    activeOf(thaw.S, side).status = '';
    br.p *= 0.8;
    return [br, ...doMove(X, thaw, side, act, foeAct, foeMovesLater)];
  } else if (u.status === 'par') {
    const moves = { p: br.p * 0.75, S: cloneState(S) };
    br.p *= 0.25;
    u.lastMoveOk = false;
    pre.push(moves);
    return [br, ...pre.flatMap((b) => execMove(X, b, side, act, foeAct, foeMovesLater))];
  } else {
    pre.push(br);
  }
  return pre.flatMap((b) => execMove(X, b, side, act, foeAct, foeMovesLater));
}

function execMove(X, br, side, act, foeAct, foeMovesLater) {
  const S = br.S;
  const u = activeOf(S, side), t = activeOf(S, 1 - side);
  const rec = act.rec;
  const e = eff(rec);
  if (act.slot >= 0 && u.pp[act.slot] > 0) {
    const pressure = t && t.hp > 0 && staticInfo(X, t).ability === 'ABILITY_PRESSURE';
    u.pp[act.slot] = Math.max(0, u.pp[act.slot] - (pressure ? 2 : 1));
  }
  u.lastMoveId = act.id;
  u.lastMoveOk = true;
  const wasProtecting = u.protectOk;
  if (e !== 'PROTECT') u.protectOk = 1;
  // charge turn
  if (CHARGE_EFFECTS.has(e) && u.charging !== act.slot && !(e === 'SKIP_CHARGE_TURN_IN_SUN' && S.weather === 'sun')) {
    u.charging = act.slot;
    return [br];
  }
  u.charging = -1;
  if (rec.category === 'CLASS_STATUS') return statusMove(X, br, side, act, e, wasProtecting, foeMovesLater);
  if (!t || t.hp <= 0) { u.lastMoveOk = false; return [br]; }
  if (t.protecting && rec.flags.includes('MOVE_FLAG_CAN_PROTECT')) { u.lastMoveOk = false; return [br]; }
  if (e === 'HIT_FIRST_IF_TARGET_ATTACKING' && !(foeMovesLater && foeAct.kind === 'move' && foeAct.rec && foeAct.rec.category !== 'CLASS_STATUS')) {
    u.lastMoveOk = false; return [br];
  }
  let outcomes;
  if (e === 'COUNTER' || e === 'MIRROR_COAT') {
    const taken = S.taken[side][e === 'COUNTER' ? 'phys' : 'spec'];
    if (!taken) { u.lastMoveOk = false; return [br]; }
    outcomes = [{ p: 1, dmg: Math.min(t.hp, taken * 2) }];
  } else {
    outcomes = damageOutcomes(X, S, u, t, rec);
  }
  if (!outcomes) { u.lastMoveOk = false; return selfKO(X, br, side, e); }
  const hc = hitChance(X, S, u, t, rec);
  const out = [];
  if (hc < 1) {
    const miss = { p: br.p * (1 - hc), S: cloneState(S) };
    activeOf(miss.S, side).lastMoveOk = false;
    out.push(...selfKO(X, miss, side, e));
  }
  outcomes.forEach((o, i) => {
    const last = i === outcomes.length - 1;
    const b = last ? { p: br.p * hc * o.p, S } : { p: br.p * hc * o.p, S: cloneState(S) };
    applyHit(X, b.S, side, rec, e, o.dmg);
    out.push(...selfKO(X, b, side, e));
  });
  return out;
}

function selfKO(X, br, side, e) {
  if (e === 'HALVE_DEFENSE') { const u = activeOf(br.S, side); u.hp = 0; } // Explosion / Self-Destruct
  return [br];
}

function applyHit(X, S, side, rec, e, dmgIn) {
  const u = activeOf(S, side), t = activeOf(S, 1 - side);
  let dmg = Math.min(dmgIn, t.hp);
  if (dmg >= t.hp && t.hp === t.maxhp && t.item && itemConst(X, t.item) === 'ITEM_FOCUS_SASH') { dmg = t.hp - 1; t.item = ''; }
  t.hp -= dmg;
  S.taken[1 - side][rec.category === 'CLASS_PHYSICAL' ? 'phys' : 'spec'] += dmg;
  S.moveHit[1 - side] = rec.id; // battleCtx->moveHit[defender] (opponent.mjs processLog)
  S.moveHitBattler[1 - side] = side;
  S.moveHit[side] = 0;
  afterHpLoss(X, t);
  const ua = staticInfo(X, u).ability;
  if (RECOIL[e] && dmg > 0 && ua !== 'ABILITY_ROCK_HEAD' && ua !== 'ABILITY_MAGIC_GUARD') {
    u.hp = Math.max(0, u.hp - Math.max(1, Math.floor(dmg / RECOIL[e])));
  }
  if (e === 'RECOVER_HALF_DAMAGE_DEALT' && dmg > 0) u.hp = Math.min(u.maxhp, u.hp + Math.max(1, Math.floor(dmg / 2)));
  if (dmg > 0 && u.item && holdEffect(X, u.item) === 'HOLD_EFFECT_HP_DRAIN_ON_ATK' && ua !== 'ABILITY_MAGIC_GUARD') {
    u.hp = Math.max(0, u.hp - Math.max(1, Math.floor(u.maxhp / 10)));
  }
  if (USER_DROPS_ON_HIT[e]) addBoosts(u, USER_DROPS_ON_HIT[e]);
  if (e === 'RECHARGE_AFTER' && t.hp > 0) u.recharge = true;
  afterHpLoss(X, u);
}

function statusMove(X, br, side, act, e, protectOk, foeMovesLater) {
  const S = br.S;
  const u = activeOf(S, side), t = activeOf(S, 1 - side);
  const rec = act.rec;
  if (e === 'PROTECT') {
    if (!foeMovesLater) { u.protectOk = 1; u.lastMoveOk = false; return [br]; }
    const ok = { p: br.p * protectOk, S: cloneState(S) };
    const m = activeOf(ok.S, side);
    m.protecting = true; m.protectOk = protectOk * 0.5;
    br.p *= 1 - protectOk;
    u.protectOk = 1; u.lastMoveOk = false;
    return protectOk >= 1 ? [ok] : [ok, br];
  }
  if (SELF_BOOSTS[e]) { addBoosts(u, SELF_BOOSTS[e]); return [br]; }
  if (e === 'MAX_ATK_LOSE_HALF_MAX_HP') {
    if (u.hp > Math.floor(u.maxhp / 2)) { u.hp -= Math.floor(u.maxhp / 2); u.boosts.atk = 6; }
    return [br];
  }
  if (HEAL_HALF.has(e)) { u.hp = Math.min(u.maxhp, u.hp + Math.floor(u.maxhp / 2)); return [br]; }
  if (e === 'REST') {
    if (u.hp < u.maxhp && staticInfo(X, u).ability !== 'ABILITY_INSOMNIA') { u.hp = u.maxhp; u.status = 'slp'; u.slp = 3; u.tox = 0; }
    return [br];
  }
  if (e === 'SET_REFLECT') { if (!S.sides[side].sc.reflect) S.sides[side].sc.reflect = 5; return [br]; }
  if (e === 'SET_LIGHT_SCREEN') { if (!S.sides[side].sc.lightscreen) S.sides[side].sc.lightscreen = 5; return [br]; }
  const targeted = FOE_DROPS[e] || STATUS_OF[e] || e === 'STATUS_SLEEP_NEXT_TURN';
  if (!targeted) return [br]; // unmodelled status move: no effect (conservative)
  if (!t || t.hp <= 0) { u.lastMoveOk = false; return [br]; }
  if (t.protecting && rec.flags.includes('MOVE_FLAG_CAN_PROTECT')) { u.lastMoveOk = false; return [br]; }
  const status = STATUS_OF[e];
  if (status || e === 'STATUS_SLEEP_NEXT_TURN') {
    if (t.status || (status && statusImmune(X, t, status)) || (e === 'STATUS_SLEEP_NEXT_TURN' && (t.yawn || statusImmune(X, t, 'slp')))) {
      u.lastMoveOk = false; return [br];
    }
    // Thunder Wave and other Electric status moves do not affect Ground types (type chart).
    if (rec.type === 'TYPE_ELECTRIC' && staticInfo(X, t).types.includes('Ground')) { u.lastMoveOk = false; return [br]; }
  }
  const hc = hitChance(X, S, u, t, rec);
  const hitBr = hc < 1 ? { p: br.p * hc, S: cloneState(S) } : br;
  const tt = activeOf(hitBr.S, 1 - side);
  if (FOE_DROPS[e]) addBoosts(tt, FOE_DROPS[e]);
  else if (e === 'STATUS_SLEEP_NEXT_TURN') tt.yawn = 2;
  else {
    tt.status = status;
    if (status === 'slp') tt.slp = 3;
    if (status === 'tox') tt.tox = 0;
  }
  if (hc >= 1) return [hitBr];
  br.p *= 1 - hc;
  u.lastMoveOk = false;
  return [hitBr, br];
}

function endOfTurn(X, S) {
  for (const side of [0, 1]) {
    const m = activeOf(S, side);
    if (!m || m.hp <= 0) continue;
    const info = staticInfo(X, m);
    const magicGuard = info.ability === 'ABILITY_MAGIC_GUARD';
    if (!magicGuard) {
      if (S.weather === 'sand' && !info.types.some((x) => x === 'Rock' || x === 'Ground' || x === 'Steel') && info.ability !== 'ABILITY_SAND_VEIL') {
        m.hp = Math.max(0, m.hp - Math.max(1, Math.floor(m.maxhp / 16)));
      }
      if (S.weather === 'hail' && !info.types.includes('Ice') && info.ability !== 'ABILITY_ICE_BODY') {
        m.hp = Math.max(0, m.hp - Math.max(1, Math.floor(m.maxhp / 16)));
      }
    }
    if (m.hp > 0 && m.item && holdEffect(X, m.item) === 'HOLD_EFFECT_HP_RESTORE_GRADUAL') m.hp = Math.min(m.maxhp, m.hp + Math.max(1, Math.floor(m.maxhp / 16)));
    if (m.hp > 0 && !magicGuard) {
      if (m.status === 'brn') m.hp = Math.max(0, m.hp - Math.max(1, Math.floor(m.maxhp / (info.ability === 'ABILITY_HEATPROOF' ? 16 : 8))));
      else if (m.status === 'psn' && info.ability !== 'ABILITY_POISON_HEAL') m.hp = Math.max(0, m.hp - Math.max(1, Math.floor(m.maxhp / 8)));
      else if (m.status === 'tox' && info.ability !== 'ABILITY_POISON_HEAL') {
        m.tox = Math.min(15, m.tox + 1);
        m.hp = Math.max(0, m.hp - Math.max(1, Math.floor(m.maxhp * m.tox / 16)));
      }
    }
    afterHpLoss(X, m);
    if (m.yawn) {
      m.yawn--;
      if (m.yawn === 0 && !m.status && m.hp > 0) { m.status = 'slp'; m.slp = 3; }
    }
    m.protecting = false;
    m.activeTurns++;
  }
  for (const sd of S.sides) {
    if (sd.sc.reflect) sd.sc.reflect--;
    if (sd.sc.lightscreen) sd.sc.lightscreen--;
  }
  S.turn++;
  S.taken = [{ phys: 0, spec: 0 }, { phys: 0, spec: 0 }];
}

const priorityOf = (act) => (act.kind === 'move' && act.rec ? act.rec.priority : 0);

function resolveTurn(X, S, pa, oa) {
  STATS.turns++;
  const S0 = cloneState(S);
  if (pa.kind === 'switch') doSwitch(X, S0, 0, pa.idx);
  if (oa.kind === 'switch') doSwitch(X, S0, 1, oa.idx);
  if (oa.kind === 'item') {
    const m = activeOf(S0, 1);
    m.hp = m.maxhp; m.status = ''; m.slp = 0; m.tox = 0;
    S0.items = { ...oa.items, trainerItems: oa.items.trainerItems.slice() };
    S0.moveHit[1] = 0;
  }
  const movers = [];
  if (pa.kind === 'move') movers.push(0);
  if (oa.kind === 'move') movers.push(1);
  let orders;
  if (movers.length === 2) {
    const p0 = priorityOf(pa), p1 = priorityOf(oa);
    if (p0 !== p1) orders = [[p0 > p1 ? [0, 1] : [1, 0], 1]];
    else {
      const f = speedInfo(X, S).pFirst; // turn order is fixed at the start of the turn
      orders = f === 1 ? [[[0, 1], 1]] : f === 0 ? [[[1, 0], 1]] : [[[0, 1], 0.5], [[1, 0], 0.5]];
    }
  } else orders = [[movers, 1]];
  const out = [];
  orders.forEach(([ord, po], oi) => {
    let branches = [{ p: po, S: oi === orders.length - 1 ? S0 : cloneState(S0) }];
    ord.forEach((side, k) => {
      const act = side === 0 ? pa : oa;
      const foeAct = side === 0 ? oa : pa;
      const foeMovesLater = k === 0 && ord.length === 2;
      branches = branches.flatMap((b) => doMove(X, b, side, act, foeAct, foeMovesLater));
    });
    for (const b of branches) { endOfTurn(X, b.S); out.push(b); }
  });
  // merge identical end states
  const merged = new Map();
  for (const b of out) {
    if (b.p <= 0) continue;
    const k = signature(b.S);
    const m = merged.get(k);
    if (m) m.p += b.p; else merged.set(k, b);
  }
  return [...merged.values()];
}

// ---------------------------------------------------------------------------------------------
// Opponent prediction with the game's AI

// Returns [{p, act}] where act = {kind:'move', slot, id, rec} | {kind:'switch', idx} | {kind:'item', items} | {kind:'none'}.
function predictOpponent(X, S, depthTag, K) {
  const key = `${depthTag}|${signature(S)}`;
  const hit = X.pred.get(key);
  if (hit) return hit;
  const o = activeOf(S, 1);
  let res;
  if (!o) res = [{ p: 1, act: { kind: 'none' } }];
  else if (o.hp > 0 && o.recharge) res = [{ p: 1, act: { kind: 'none' } }];
  else if (o.hp > 0 && o.charging >= 0) res = [{ p: 1, act: moveAct(X, o, o.charging) }];
  else if (S === X.root && o.ref.getLockedMove && o.ref.getLockedMove()) {
    const id = o.ref.getLockedMove();
    const slot = o.ref.moveSlots.findIndex((s) => s.id === id);
    res = [{ p: 1, act: slot >= 0 ? moveAct(X, o, slot) : { kind: 'none' } }];
  } else {
    const tv = performance.now();
    const view = viewOf(X, S);
    STATS.viewMs += performance.now() - tv;
    const counts = new Map();
    const h = cheapHash(key);
    for (let k = 0; k < K; k++) {
      const seed = (X.seedBase ^ Math.imul(h, 0x9e3779b1) ^ Math.imul(k + 1, 0x85ebca6b)) >>> 0;
      const ta = performance.now();
      const act = aiDecide(X, S, view, new AIRng(seed));
      STATS.aiMs += performance.now() - ta;
      const ak = act.kind === 'move' ? `m${act.slot}` : act.kind === 'switch' ? `s${act.idx}` : act.kind;
      const c = counts.get(ak);
      if (c) c.n++; else counts.set(ak, { n: 1, act });
    }
    res = [...counts.values()].map((c) => ({ p: c.n / K, act: c.act }));
  }
  X.pred.set(key, res);
  return res;
}

function moveAct(X, m, slot) {
  const id = m.ref.moveSlots[slot]?.id;
  return { kind: 'move', slot, id, rec: id ? moveInfo(X.gd, id) : null };
}

function aiDecide(X, S, view, rng) {
  STATS.aiCalls++;
  const { ai, battle } = view;
  const mir = X.mirror;
  const st = {
    battle, aiSide: 'p2', prog: mir.prog, rng,
    knowledge: {
      battlerMoves: X.knowledge.battlerMoves.map((r) => r.slice()),
      battlerAbilities: X.knowledge.battlerAbilities.slice(),
      battlerHeldItems: X.knowledge.battlerHeldItems.slice(),
    },
    speedRand: X.speedRand.slice(),
    moveHit: S.moveHit.slice(), moveHitBattler: S.moveHitBattler.slice(),
    aiSwitchedPartySlot: [6, 6, 6, 6],
    items: { ...S.items, trainerItems: S.items.trainerItems.slice() },
    thinkingMask: mir.thinkingMask,
    ai,
  };
  const side = battle.p2;
  const o = activeOf(S, 1);
  const toIdx = (gameSlot) => {
    const mon = partyOrderOf(battle).p2[gameSlot];
    return side.pokemon.indexOf(mon);
  };
  if (o.hp <= 0) {
    const idx = toIdx(replacementSlot(st, 1));
    return idx >= 0 && S.sides[1].mons[idx].hp > 0 ? { kind: 'switch', idx } : { kind: 'none' };
  }
  st.monSpeedValues = speedValuesNow(ai);
  st.mem = { monSpeedValues: st.monSpeedValues };
  const cmd = pickCommand(st, 1);
  if (cmd.command === 'party') {
    const idx = toIdx(cmd.slot);
    const trapped = S === X.root ? !!X.oppTrapped : false;
    if (!trapped && idx >= 0 && idx !== S.sides[1].active && S.sides[1].mons[idx].hp > 0) return { kind: 'switch', idx };
  } else if (cmd.command === 'item') {
    return { kind: 'item', items: st.items };
  }
  const STRUGGLING_ALL = 0xf; // include/constants/battle.h:137
  if ((checkInvalidMoves(ai, 1, 0, ~0) & STRUGGLING_ALL) === STRUGGLING_ALL) return { kind: 'none' };
  const med = ai.moveEffectsData(1);
  if (med.encoredMove) {
    const slot = ai.moves(1).indexOf(med.encoredMove);
    return slot >= 0 ? moveAct(X, o, slot) : { kind: 'none' };
  }
  const r = trainerAIMain(st, 1);
  let slot = r.slot;
  if (!(o.pp[slot] > 0)) { // the live decide() substitutes the best enabled move
    let best = -1;
    for (let i = 0; i < 4; i++) if (o.pp[i] > 0 && (best < 0 || r.scores[i] > r.scores[best])) best = i;
    slot = best;
  }
  return slot >= 0 ? moveAct(X, o, slot) : { kind: 'none' };
}

// ---------------------------------------------------------------------------------------------
// Leaf evaluation

function frUsable(S) { // TAI:4092 slot rule, TAI:4099-4104 Full Restore only
  const alive = aliveCount(S, 1);
  const it = S.items;
  let n = 0;
  for (let i = 0; i < 4; i++) {
    if (!it.trainerItems[i]) continue;
    if (i === 0 || alive <= it.trainerItemCounts - i + 1) n++;
  }
  return n;
}

function statusPenalty(X, m) {
  switch (m.status) {
    case 'slp': return 0.25;
    case 'frz': return 0.40;
    case 'par': return 0.15;
    case 'brn': return staticInfo(X, m).physical ? 0.30 : 0.15;
    case 'psn': return 0.08;
    case 'tox': return 0.12;
    default: return 0;
  }
}
function boostValue(m) {
  const b = m.boosts;
  const v = 0.10 * Math.max(b.atk, b.spa) + 0.05 * b.spe + 0.04 * (b.def + b.spd) + 0.06 * b.evasion + 0.03 * b.accuracy;
  return v * (m.hp / m.maxhp);
}

export function leafValue(X, S) {
  STATS.leaves++;
  const P = PARAMS;
  const myAlive = aliveCount(S, 0), oppAlive = aliveCount(S, 1);
  let v = 0;
  if (oppAlive === 0) v += P.WIN;
  if (myAlive === 0) v -= P.WIN;
  let fr = oppAlive > 0 ? frUsable(S) : 0;
  const oa = activeOf(S, 1);
  const wAlive = X.opts.wAlive ?? P.W_ALIVE;
  for (const m of S.sides[0].mons) if (m.hp > 0) v += wAlive + m.hp / m.maxhp - statusPenalty(X, m);
  for (const m of S.sides[1].mons) {
    if (m.hp <= 0) continue;
    let frac = m.hp / m.maxhp;
    let pen = statusPenalty(X, m);
    if (m === oa && fr > 0 && m.hp < Math.trunc(m.maxhp / 4)) { frac = 1; pen = 0; fr--; }
    v -= wAlive + frac - pen;
  }
  v -= (X.opts.wFR ?? P.W_FR) * fr;
  const ma = activeOf(S, 0);
  if (ma && ma.hp > 0) { v += boostValue(ma); if (ma.recharge) v -= 0.1; }
  if (oa && oa.hp > 0) { v -= boostValue(oa); if (oa.recharge) v += 0.1; }
  v += 0.05 * ((S.sides[0].sc.reflect ?? 0) + (S.sides[0].sc.lightscreen ?? 0)) / 5;
  v -= 0.05 * ((S.sides[1].sc.reflect ?? 0) + (S.sides[1].sc.lightscreen ?? 0)) / 5;
  return v;
}

// ---------------------------------------------------------------------------------------------
// Search

function playerMoveActs(X, S) {
  const m = activeOf(S, 0);
  if (!m || m.hp <= 0) return [];
  if (m.recharge) return [{ kind: 'none' }];
  if (m.charging >= 0) return [moveAct(X, m, m.charging)];
  const acts = [];
  m.ref.moveSlots.forEach((s, i) => { if (m.pp[i] > 0 && i < 4) acts.push(moveAct(X, m, i)); });
  return acts.length ? acts : [{ kind: 'none' }];
}

// Best expected damage fraction race: used to pick our replacement inside the search.
function matchupScore(X, S, m) {
  const foe = activeOf(S, 1);
  if (!foe || foe.hp <= 0) return m.hp / m.maxhp;
  const T = cloneState(S);
  T.sides[0].active = m.idx;
  const mm = activeOf(T, 0);
  mm.fresh = true;
  mm.boosts = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 };
  const best = (u, t) => {
    let bst = 0;
    staticInfo(X, u).moves.forEach((mv, i) => {
      if (!mv.rec || !(u.pp[i] > 0)) return;
      const outs = mv.rec.category === 'CLASS_STATUS' ? null : damageOutcomes(X, T, u, t, mv.rec);
      if (!outs) return;
      const e = outs.reduce((s, o) => s + o.p * o.dmg, 0) * hitChance(X, T, u, t, mv.rec);
      bst = Math.max(bst, e / t.maxhp);
    });
    return bst;
  };
  const dealt = best(mm, foe);
  const taken = best(foe, mm);
  return dealt / Math.max(0.05, foe.hp / foe.maxhp) - taken / Math.max(0.05, mm.hp / mm.maxhp);
}

function replaceFainted(X, S) {
  // the opponent's replacement first (the AI's BattleAI_PostKOSwitchIn), then ours.
  const o = activeOf(S, 1);
  if (o && o.hp <= 0 && aliveCount(S, 1) > 0) {
    const pred = predictOpponent(X, S, 'repl', 1);
    const act = pred[0].act;
    if (act.kind === 'switch') doSwitch(X, S, 1, act.idx);
  }
  const m = activeOf(S, 0);
  if (m && m.hp <= 0 && aliveCount(S, 0) > 0) {
    let best = -1, bs = -Infinity;
    for (const c of S.sides[0].mons) {
      if (c.hp <= 0 || c.idx === m.idx) continue;
      const sc = matchupScore(X, S, c);
      if (sc > bs) { bs = sc; best = c.idx; }
    }
    if (best >= 0) doSwitch(X, S, 0, best);
  }
}

const terminal = (S) => aliveCount(S, 0) === 0 || aliveCount(S, 1) === 0;

// Value of a state at the start of a turn (ply 2): max over our moves of E[leaf].
function valuePly2(X, S) {
  if (terminal(S)) return leafValue(X, S);
  X.nodes++;
  replaceFainted(X, S);
  if (terminal(S)) return leafValue(X, S);
  const opp = predictOpponent(X, S, 'p2', PARAMS.K_PLY2);
  let best = -Infinity;
  for (const a of playerMoveActs(X, S)) {
    let q = 0;
    for (const { p, act } of opp) {
      for (const br of resolveTurn(X, S, a, act)) q += p * br.p * leafValue(X, br.S);
    }
    if (q > best) best = q;
  }
  return best;
}

// koStop (v2, HORIZON): a ply-1 branch in which an active member fainted ends the line there.
const activeFainted = (S) => { const a = activeOf(S, 0), o = activeOf(S, 1); return !a || a.hp <= 0 || !o || o.hp <= 0; };
function qValue(X, S, a, opp) {
  let q = 0;
  for (const { p, act } of opp) {
    for (const br of resolveTurn(X, S, a, act)) {
      q += p * br.p * (X.opts.koStop && activeFainted(br.S) ? leafValue(X, br.S) : valuePly2(X, br.S));
    }
  }
  return q;
}

function rootState(X) {
  const { battle } = X;
  const sides = battle.sides.map((side, si) => ({
    active: side.active[0] ? side.pokemon.indexOf(side.active[0]) : -1,
    sc: { reflect: side.sideConditions.reflect ? (side.sideConditions.reflect.duration ?? 5) : 0,
      lightscreen: side.sideConditions.lightscreen ? (side.sideConditions.lightscreen.duration ?? 5) : 0 },
    mons: side.pokemon.map((p, i) => monFromReal(p, si, i)),
  }));
  return {
    turn: battle.turn, weather: WEATHER[battle.field.weather] ?? '',
    sides,
    items: { ...X.items, trainerItems: X.items.trainerItems.slice() },
    moveHit: X.moveHit.slice(), moveHitBattler: X.moveHitBattler.slice(),
    taken: [{ phys: 0, spec: 0 }, { phys: 0, spec: 0 }],
  };
}

/** Builds the decision context. Reads the live battle; never writes it. */
export function makeContext({ gd, battle, side, trainer }, opts = V1_OPTS, name = EXPECTIMAX2) {
  if (side.id !== 'p1') throw new Error('expectimax2: the policy plays p1');
  const ms = mirrorFor(battle, trainer, name);
  const mirror = ms.mirror;
  // Catch the private mirror's AI memory up with the public log (same mapping as the real AI).
  processLog(mirror);
  const real = stateFor(battle);
  const items = real ? real.items : mirror.items; // remaining trainer items are public information
  const X = {
    gd, battle, trainer, mirror,
    seedBase: (ms.seedBase ^ Math.imul(battle.turn + 1, 0x27d4eb2d)) >>> 0,
    knowledge: mirror.knowledge,
    speedRand: (real ? real.speedRand : mirror.speedRand).slice(),
    moveHit: mirror.moveHit.slice(), moveHitBattler: mirror.moveHitBattler.slice(),
    items: { ...items, trainerItems: items.trainerItems.slice() },
    static: new Map(), dmg: new Map(), pred: new Map(), views: new Map(),
    nodes: 0, opts,
  };
  X.oppTrapped = !!battle.p2.activeRequest?.active?.[0]?.trapped; // the opponent's pending request (read only)
  X.root = rootState(X);
  X.rootView = { battle, ai: mirror.ai, key: 'root' };
  return X;
}

/** Scores of every legal action of `request` (exported for tests). */
export function scoreActions(ctx, opts = V1_OPTS, name = EXPECTIMAX2) {
  const { side, request } = ctx;
  const X = makeContext(ctx, opts, name);
  const S = X.root;
  const acts = [];
  if (request.forceSwitch) {
    side.pokemon.forEach((p, i) => { if (!p.isActive && !p.fainted && p.hp > 0) acts.push({ kind: 'switch', idx: i, choice: `switch ${i + 1}` }); });
    const scores = acts.map((a) => {
      const T = cloneState(S);
      doSwitch(X, T, 0, a.idx);
      return valuePly2(X, T);
    });
    return { X, acts, scores };
  }
  const active = request.active[0];
  const mon = side.active[0];
  const aligned = active.moves.length === mon.moveSlots.length;
  active.moves.forEach((m, i) => {
    if (m.disabled) return;
    if (!aligned) { acts.push({ kind: 'move', slot: -1, id: m.id, rec: moveInfo(X.gd, m.id), choice: `move ${i + 1}` }); return; }
    acts.push({ ...moveAct(X, activeOf(S, 0), i), choice: `move ${i + 1}` });
  });
  const switches = [];
  if (!active.trapped) {
    side.pokemon.forEach((p, i) => { if (!p.isActive && !p.fainted && p.hp > 0) switches.push({ kind: 'switch', idx: i, choice: `switch ${i + 1}` }); });
  }
  // Switch beam: only the PARAMS.SWITCH_BEAM best switch targets by the damage-race heuristic are
  // searched (the others are scored -Infinity). Ties keep party order.
  const ranked = switches.map((a) => ({ a, r: matchupScore(X, S, S.sides[0].mons[a.idx]) }))
    .sort((x, y) => y.r - x.r).slice(0, PARAMS.SWITCH_BEAM).map((x) => x.a);
  const searched = new Set(ranked);
  acts.push(...switches);
  if (acts.length <= 1) return { X, acts, scores: acts.map(() => 0) };
  const opp = X.battle.p2.requestState === 'move' ? predictOpponent(X, S, 'root', PARAMS.K_ROOT) : [{ p: 1, act: { kind: 'none' } }];
  const scores = acts.map((a) => (a.kind === 'switch' && !searched.has(a) ? -Infinity : qValue(X, S, a, opp)));
  return { X, acts, scores, opp };
}

// Internals exported for sim/test/expectimax2.test.mjs (read-only use).
export const _internal = { cloneState, viewOf, aiDecide, predictOpponent, resolveTurn, signature, shadowBattle };

/** A player policy object for one version: `name` also seeds its private AI sample streams. */
export function makeExpectimax2(name, opts) {
  return {
    name,
    choose(ctx) {
      const { request } = ctx;
      if (!request || request.wait || request.teamPreview) return 'default';
      if (!request.forceSwitch && !request.active?.[0]) return 'default';
      const t0 = performance.now();
      const { acts, scores } = scoreActions(ctx, opts, name);
      STATS.decisions++;
      STATS.ms += performance.now() - t0;
      if (!acts.length) return 'default';
      let bi = 0;
      for (let i = 1; i < scores.length; i++) if (scores[i] > scores[bi]) bi = i;
      return acts[bi].choice;
    },
  };
}

export const expectimax2 = makeExpectimax2(EXPECTIMAX2, V1_OPTS); // kept for recorded results
export const expectimax2v2 = makeExpectimax2(EXPECTIMAX2_V2, V2_OPTS); // the default strong player
