// T039: read-only battle-state queries for the trainer-AI interpreter.
//
// The AI command handlers in pokeplatinum/src/battle/trainer_ai/trainer_ai.c read the game's
// BattleContext (include/battle/battle_context.h) and BattleMon (include/battle/battle_mon.h) in
// the game's own encodings: move/ability/item/type/species ids from generated/*.txt, status and
// condition bitmasks from include/constants/battle/condition.h and constants/battle/moves.h,
// stat stages 0..12 with 6 neutral (DEFAULT_STAT_STAGE, constants/battle/battle_script.h:5;
// set at battle_lib.c:99). This module answers the same questions over a live Showdown Battle and
// returns values in those encodings, so the command files (T040-T044) can be written as
// line-by-line ports of the C handlers.
//
// Nothing here mutates the Battle. Nothing here imports Showdown directly (sim/showdown.mjs is the
// only importer); the caller passes in the Battle object.
//
// Feature 015 (specs/015-exact-ai-speedups/contracts/adapter-api.md): `damageInput()` builds the
// damage-formula inputs that sim/damage.mjs `fromShowdown` builds, but caches the per-Pokemon battler
// struct and the per-side field struct for the current decision, so the K trainer-AI samples on one
// state (and every move and damage check inside each) share them. `beginDecision()` drops the cache;
// an owner that keeps an adapter across battle changes (the live AI in opponent.mjs, the policy's
// per-battle mirror in policy/expectimax2.mjs) calls it at the start of every decision. The returned
// structs are SHARED and read-only: callers must not write to them. With PLATSIM_AI_FREEZE=1 in the
// environment they are deep-frozen when built, so any write throws (test guard).
//
// Feature 016 (specs/016-exact-damage-speedups/contracts/adapter-api.md): the same decision cache also memoises,
// per (attacker struct, defender struct, move, power, type), the type-chart PLAN (damage.mjs typeChartPlan) and the
// trainer AI's PRE-VARIANCE damage (TrainerAI_CalcDamage before the sample's roll, TAI:3081-3103; the spec calls it
// the "base damage"). The K samples on one state share them; the samples' own rolls are applied by the caller.
// PLATSIM_AI_CHECK=1 recomputes every memo hit and throws on a difference (control mode, see CHECK_STATS).
//
// Feature 017 (specs/017-exact-dispatch-speedups/contracts/adapter-api.md): the player policy's own damage table now
// reads `damageInput()` too (the per-battle mirror adapter is the policy's root view) and copies the structs before
// its per-state adjustments, so the live conversions happen once per Pokemon per decision for both users. The
// control mode therefore also recomputes every battler-struct and field-struct hit (`cacheStats.structChecks`,
// `CHECK_STATS.structChecks`). `speedPair()` memoises the two battlers' speed facts for the decision
// (cmds/battler.mjs compareBattlerSpeed); same lifecycle, freeze guard and control mode.
//
// Battler ids follow the game: battler & 1 is the side (BattleSystem_GetBattlerSide,
// battle_system.c:360-363). BATTLER_PLAYER_1 = 0, BATTLER_ENEMY_1 = 1, BATTLER_PLAYER_2 = 2
// (constants/battle.h:95-97). In singles only 0 and 1 exist; 2 and 3 return an empty BattleMon
// (all zero), which is what battleMons[2..3] hold in a single battle.
//
// What the AI may "know" about the player (AI_CONTEXT.battlerMoves / battlerAbilities /
// battlerHeldItems, ai_context.h:27-29) is AI memory, not battle state. It is owned by the
// interpreter (T045), which fills it the way the game does (TrainerAI_RecordLastMove,
// trainer_ai.c:2705-2717; BattleAI_SetAbility / BattleAI_SetHeldItem, battle_script.c:12106-12122;
// cleared on switch, battle_lib.c:2151-2153). This adapter only exposes the raw inputs.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { DECOMP_ROOT, loadConstants } from './constants.mjs';
import { ENUMS, battlerFromShowdown, typeChartPlan, replayTypeChart, calcBaseDamage } from '../damage.mjs';

const FREEZE = process.env.PLATSIM_AI_FREEZE === '1';
// Feature 016 control mode: every memo hit in typeChartPlan() / preVariance() is recomputed and compared; a
// difference throws. CHECK_STATS aggregates the comparisons across all adapters in the process (tests read it).
const CHECK = process.env.PLATSIM_AI_CHECK === '1';
export const CHECK_STATS = { checks: 0, mismatches: 0, structChecks: 0 }; // structChecks: 017 battler/field comparisons
function deepFreeze(o) {
  if (o && typeof o === 'object' && !Object.isFrozen(o)) {
    Object.freeze(o);
    for (const k of Object.keys(o)) deepFreeze(o[k]);
  }
  return o;
}
const WEATHER = { sunnyday: 'sun', raindance: 'rain', sandstorm: 'sand', hail: 'hail' }; // = damage.mjs WEATHER

const toID = (s) => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');

// ---------- decomp tables (loaded once) ----------

let tables = null;

// MOVE_DATA(move) = battleCtx->aiContext.moveTable[move] (battle/common.h:25). The table is built
// from res/moves/<name>/data.json (res/moves/meson.build:40-45 maps MOVE_X -> x/).
// Item hold effects / fling power come from res/items/data/<name>.json (holdEffect, flingPower,
// effectParam), the source of BattleSystem_GetItemData (ITEM_PARAM_HOLD_EFFECT etc.).
// Species abilities/types from res/pokemon/<name>/data.json (SpeciesData_GetSpeciesValue,
// SPECIES_DATA_ABILITY_1/2 used at trainer_ai.c:1187-1188).
export function decompTables(root = DECOMP_ROOT) {
  if (tables && tables.root === root) return tables;
  const C = loadConstants(root);
  const moves = [];
  for (const e of C.lists.get('moves')) {
    if (!e.name.startsWith('MOVE_')) continue;
    const path = join(root, 'res/moves', e.name.slice(5).toLowerCase(), 'data.json');
    if (!existsSync(path)) { if (e.value !== 0) throw new Error(`adapter: missing ${path}`); continue; }
    const d = JSON.parse(readFileSync(path, 'utf8'));
    moves[e.value] = {
      id: e.value, constant: e.name, name: d.name,
      effect: C.get(d.effect.type), effectChance: d.effect.chance,
      power: d.power, type: C.get(d.type), class: C.get(d.class),
      accuracy: d.accuracy, pp: d.pp, priority: d.priority, range: d.range, flags: d.flags,
      src: `res/moves/${e.name.slice(5).toLowerCase()}/data.json`,
    };
  }
  const items = [];
  for (const e of C.lists.get('items')) {
    if (!e.name.startsWith('ITEM_')) continue;
    const path = join(root, 'res/items/data', `${e.name.slice(5).toLowerCase()}.json`);
    if (!existsSync(path)) continue; // e.g. ITEM_UNUSED_113..: no data file
    const d = JSON.parse(readFileSync(path, 'utf8'));
    items[e.value] = {
      id: e.value, constant: e.name, name: d.name,
      holdEffect: d.holdEffect ? C.get(d.holdEffect) : 0, holdEffectParam: d.effectParam ?? 0,
      flingPower: d.flingPower ?? 0, naturalGiftPower: d.naturalGiftPower ?? 0,
      naturalGiftType: d.naturalGiftType ? C.get(d.naturalGiftType) : undefined,
      src: `res/items/data/${e.name.slice(5).toLowerCase()}.json`,
    };
  }
  const species = [];
  for (const e of C.lists.get('species')) {
    if (!e.name.startsWith('SPECIES_')) continue;
    const path = join(root, 'res/pokemon', e.name.slice(8).toLowerCase(), 'data.json');
    if (!existsSync(path)) continue;
    const d = JSON.parse(readFileSync(path, 'utf8'));
    species[e.value] = {
      id: e.value, constant: e.name,
      abilities: d.abilities.map((a) => C.get(a)), types: d.types.map((t) => C.get(t)),
      src: `res/pokemon/${e.name.slice(8).toLowerCase()}/data.json`,
    };
  }
  tables = { root, C, moves, items, species };
  return tables;
}

// ---------- Showdown id <-> decomp id ----------
// Moves, abilities, items and species are matched by Showdown's `num`, which for Gen <= 4 entries
// equals the decomp index. Checked over every decomp move/ability/item in
// sim/test/ai_adapter.test.mjs (moves differ only by four renames, e.g. MOVE_VICE_GRIP vs
// "Vise Grip"; every Showdown-known item has num == decomp id).

//
// Feature 016 (specs/016-exact-damage-speedups/contracts/adapter-api.md): the mappers are pure functions of the
// engine's dex and the decomp tables, both process-wide singletons, so one mapper set per (dex, tables) is built and
// shared by every adapter (`mappersFor`) instead of a cold cache per adapter (tens of thousands of shadow-view
// adapters per run). Each kind has its own Map keyed by its natural id; a miss resolves and validates as before.
// `makeMappers` (exported for the equivalence test) builds an unshared set.
export function makeMappers(dex, T) {
  const C = T.C;
  const caches = { move: new Map(), ability: new Map(), item: new Map(), species: new Map(), type: new Map() };
  const memo = (cache, k, f) => {
    let v = cache.get(k);
    if (v === undefined) { v = f(); cache.set(k, v); }
    return v;
  };
  return {
    caches, // diagnostics (tests)
    move(id) {
      if (!id) return 0;
      return memo(caches.move, id, () => {
        const m = dex.moves.get(id);
        if (!m.exists || !T.moves[m.num]) throw new Error(`adapter: no decomp move for Showdown move ${id}`);
        return m.num;
      });
    },
    ability(id) {
      if (!id) return 0;
      return memo(caches.ability, id, () => {
        const a = dex.abilities.get(id);
        if (!a.exists || !C.nameOf('abilities', a.num)) throw new Error(`adapter: no decomp ability for ${id}`);
        return a.num;
      });
    },
    item(id) {
      if (!id) return 0; // ITEM_NONE
      return memo(caches.item, id, () => {
        const it = dex.items.get(id);
        if (!it.exists || !T.items[it.num] || toID(T.items[it.num].name) !== it.id) {
          throw new Error(`adapter: no decomp item for Showdown item ${id}`);
        }
        return it.num;
      });
    },
    species(sp) {
      return memo(caches.species, sp.id, () => {
        if (!T.species[sp.num]) throw new Error(`adapter: no decomp species for ${sp.id}`);
        return sp.num;
      });
    },
    type(name) {
      // TYPE_X constants are generated/pokemon_types.txt; Showdown type names are 'Fire' etc.
      return memo(caches.type, name, () => {
        const constName = name === '???' ? 'TYPE_MYSTERY' : `TYPE_${name.toUpperCase()}`;
        if (!C.has(constName)) throw new Error(`adapter: no decomp type for ${name}`);
        return C.get(constName);
      });
    },
  };
}
const MAPPERS = new WeakMap(); // dex -> { T, api }
function mappersFor(dex, T) {
  const hit = MAPPERS.get(dex);
  if (hit && hit.T === T) return hit.api;
  const api = makeMappers(dex, T);
  MAPPERS.set(dex, { T, api });
  return api;
}

// ---------- the adapter ----------

/**
 * @param battle   a Showdown Battle (singles, gen4 format)
 * @param opts.aiSide   'p2' (default): the AI's side. Battler ids: the player's side is even
 *                      (BATTLER_PLAYER_1 = 0), the AI's side odd (BATTLER_ENEMY_1 = 1).
 * @param opts.partyOrder  {p1: Pokemon[], p2: Pokemon[]} in game party order. Showdown reorders
 *                      side.pokemon on every switch (sim/battle-actions.ts switchIn), the game does
 *                      not (selectedPartySlot indexes the fixed party). Default: side.pokemon as it
 *                      is when the adapter is created, so create the adapter before turn 1.
 * @param opts.battleType  BATTLE_TYPE_* mask (constants/battle.h:26-48). Default
 *                      BATTLE_TYPE_TRAINER: a League battle is a single trainer battle.
 */
export function createAdapter(battle, opts = {}) {
  const T = decompTables(opts.root);
  const C = T.C;
  const dex = battle.dex;
  const map = mappersFor(dex, T); // 016: shared per (dex, tables)
  const aiSide = opts.aiSide || 'p2';
  const playerSide = aiSide === 'p2' ? 'p1' : 'p2';
  const sideOfBattler = (b) => ((b & 1) === 1 ? battle[aiSide] : battle[playerSide]);
  const partyOrder = opts.partyOrder || { p1: battle.p1.pokemon.slice(), p2: battle.p2.pokemon.slice() };
  const battleType = opts.battleType ?? C.get('BATTLE_TYPE_TRAINER');
  const K = (n) => C.get(n);
  const STAT = {
    [K('BATTLE_STAT_ATTACK')]: 'atk', [K('BATTLE_STAT_DEFENSE')]: 'def', [K('BATTLE_STAT_SPEED')]: 'spe',
    [K('BATTLE_STAT_SP_ATTACK')]: 'spa', [K('BATTLE_STAT_SP_DEFENSE')]: 'spd',
    [K('BATTLE_STAT_ACCURACY')]: 'accuracy', [K('BATTLE_STAT_EVASION')]: 'evasion',
  };
  const DEFAULT_STAT_STAGE = K('DEFAULT_STAT_STAGE');

  // Battler id -> active Showdown Pokemon, or null for an empty slot (2/3 in singles).
  function pokemon(b) {
    if (b >> 1) return null; // singles: slot index b>>1 must be 0
    return sideOfBattler(b).active[0] || null;
  }
  const must = (b) => {
    const p = pokemon(b);
    if (!p) throw new Error(`adapter: battler ${b} has no active Pokemon (singles has battlers 0 and 1)`);
    return p;
  };
  const vol = (p, id) => (p ? p.volatiles[id] : undefined);
  // Remaining turns of a Showdown effect, clamped to a game bit-field width.
  const turns = (state, max) => Math.max(1, Math.min(max, state && state.duration ? state.duration : 1));

  // 015 decision cache (see damageInput below); declared before `api`, which exposes cacheStats.
  const battlers = new Map(); // Showdown Pokemon -> battlerFromShowdown(p)
  const fields = new Map(); // defender Side -> field members that do not depend on the pair
  const plans = new Map(); // 016: attacker struct -> defender struct -> key -> type-chart plan
  const pre = new Map(); // 016: attacker struct -> defender struct -> key -> { damage, moveStatusMask }
  const cacheStats = { builds: 0, hits: 0, decisions: 0, plans: 0, planHits: 0, preVariance: 0, preVarianceHits: 0, checks: 0,
    fieldBuilds: 0, structChecks: 0, speedPairs: 0, speedPairHits: 0 }; // 017: the last four

  const api = {
    battle,
    constants: C,
    tables: T,
    map,
    mappers: map, // 016: the shared mapper set (contracts/adapter-api.md)
    // AI_CONTEXT.attacker / defender in singles: TrainerAI_Main sets attacker = the AI battler and
    // defender = BattleSystem_RandomOpponent (trainer_ai.c:264-265), the only opposing battler.
    attacker: 1,
    defender: 0,
    maxBattlers: 2, // BattleSystem_GetMaxBattlers in singles
    exists: (b) => pokemon(b) !== null,
    pokemon,
    // BattleSystem_GetBattlerSide (battle_system.c:360-363): battler & 1.
    side: (b) => b & 1,
    // battleSys->battleType (AICmd_LoadBattleType, trainer_ai.c:2504-2508).
    battleType: () => battleType,

    // ----- BattleContext fields -----

    // battleCtx->totalTurns (battle_context.h:202): 0 during the first turn's decisions,
    // incremented at end of turn (battle_controller_player.c:1852). Showdown's battle.turn is 1 when
    // the first turn's choices are requested (sim/battle.ts:1628, endTurn), so totalTurns = turn-1.
    totalTurns: () => Math.max(0, battle.turn - 1),

    // battleCtx->fieldConditionsMask (battle_context.h:210), bits from condition.h
    // (FIELD_CONDITION_*). Weather: *_PERM when Showdown's weather has no duration (ability
    // weather in Gen 4), *_TEMP otherwise. Trick Room / Gravity hold their remaining turns in their
    // bit fields (FIELD_CONDITION_TRICK_ROOM_SHIFT 16, GRAVITY_SHIFT 12). DEEP_FOG never occurs in
    // a Showdown battle. Uproar bits are not reconstructed (no reachable League command reads them).
    fieldConditionsMask() {
      let m = 0;
      const w = battle.field.weather;
      const perm = !battle.field.weatherState || !battle.field.weatherState.duration;
      const pick = (temp, p) => K(perm ? p : temp);
      if (w === 'raindance') m |= pick('FIELD_CONDITION_RAINING_TEMP', 'FIELD_CONDITION_RAINING_PERM');
      if (w === 'sandstorm') m |= pick('FIELD_CONDITION_SANDSTORM_TEMP', 'FIELD_CONDITION_SANDSTORM_PERM');
      if (w === 'sunnyday') m |= pick('FIELD_CONDITION_SUNNY_TEMP', 'FIELD_CONDITION_SUNNY_PERM');
      if (w === 'hail') m |= pick('FIELD_CONDITION_HAILING_TEMP', 'FIELD_CONDITION_HAILING_PERM');
      const pw = battle.field.pseudoWeather;
      if (pw.trickroom) m |= (turns(pw.trickroom, 7) << K('FIELD_CONDITION_TRICK_ROOM_SHIFT')) & K('FIELD_CONDITION_TRICK_ROOM');
      if (pw.gravity) m |= (turns(pw.gravity, 7) << K('FIELD_CONDITION_GRAVITY_SHIFT')) & K('FIELD_CONDITION_GRAVITY');
      return m;
    },

    // battleCtx->sideConditionsMask[side] (battle_context.h:213), SIDE_CONDITION_* (condition.h).
    // FUTURE_SIGHT and WISH are Showdown slot conditions (futuremove / wish) on that side.
    sideConditionsMask(side) {
      const s = side === 1 ? battle[aiSide] : battle[playerSide];
      const sc = s.sideConditions;
      let m = 0;
      if (sc.reflect) m |= K('SIDE_CONDITION_REFLECT');
      if (sc.lightscreen) m |= K('SIDE_CONDITION_LIGHT_SCREEN');
      if (sc.spikes) m |= K('SIDE_CONDITION_SPIKES');
      if (sc.safeguard) m |= K('SIDE_CONDITION_SAFEGUARD');
      if (sc.mist) m |= K('SIDE_CONDITION_MIST');
      if (sc.stealthrock) m |= K('SIDE_CONDITION_STEALTH_ROCK');
      if (sc.toxicspikes) m |= K('SIDE_CONDITION_TOXIC_SPIKES');
      if (sc.tailwind) m |= (turns(sc.tailwind, 3) << 8) & K('SIDE_CONDITION_TAILWIND'); // TAILWIND_0 = 1<<8
      if (sc.luckychant) m |= (turns(sc.luckychant, 7) << 12) & K('SIDE_CONDITION_LUCKY_CHANT'); // LUCKY_CHANT_0 = 1<<12
      for (const slot of s.slotConditions || []) {
        if (slot.futuremove) m |= K('SIDE_CONDITION_FUTURE_SIGHT');
        if (slot.wish) m |= K('SIDE_CONDITION_WISH');
      }
      return m;
    },
    // battleCtx->sideConditions[side].spikesLayers / toxicSpikesLayers (battle_context.h:52-53).
    spikesLayers: (side) => (side === 1 ? battle[aiSide] : battle[playerSide]).sideConditions.spikes?.layers ?? 0,
    toxicSpikesLayers: (side) => (side === 1 ? battle[aiSide] : battle[playerSide]).sideConditions.toxicspikes?.layers ?? 0,

    // battleCtx->movePrevByBattler[b] (battle_context.h:275): the battler's last move, MOVE_NONE
    // if it did not succeed (battle_controller_player.c:3944-3948) and after switching in
    // (battle_lib.c:2124, 2202). Showdown: pokemon.lastMove (cleared on switch-in); a move whose
    // result last turn was false maps to MOVE_NONE. UNVERIFIED: Showdown's "false" result vs the
    // game's SYSCTL_MOVE_SUCCEEDED for every move (misses, protect-blocked, immunities).
    movePrevByBattler(b) {
      const p = pokemon(b);
      if (!p || !p.lastMove) return 0;
      if (p.moveLastTurnResult === false) return 0;
      return map.move(p.lastMove.id);
    },
    // battleCtx->moveProtect[b] (battle_context.h:271): set to the move used when its attack
    // message was shown (battle_controller_player.c:3937-3942). Approximated by lastMove.
    moveProtect(b) {
      const p = pokemon(b);
      return p && p.lastMove ? map.move(p.lastMove.id) : 0;
    },
    // battleCtx->recycleItem[b] (battle_context.h:307). Showdown keeps the consumed item in
    // pokemon.lastItem and, in Gen <= 4, hands it to the replacement on switch
    // (sim/battle-actions.ts switchIn), i.e. it is per battler slot like the game's array.
    recycleItem: (b) => { const p = pokemon(b); return p ? map.item(p.lastItem) : 0; },
    // battleCtx->selectedPartySlot[b] (battle_context.h:252): game-order party index of the active mon.
    selectedPartySlot(b) {
      const p = pokemon(b);
      return p ? partyOrder[p.side.id].indexOf(p) : -1;
    },

    // ----- BattleMon fields (battle_mon.h:57-130) -----

    species: (b) => { const p = pokemon(b); return p ? map.species(p.species) : 0; },
    level: (b) => pokemon(b)?.level ?? 0,
    // curHP / maxHP (battle_mon.h:107-108).
    curHP: (b) => pokemon(b)?.hp ?? 0,
    maxHP: (b) => pokemon(b)?.maxhp ?? 0,
    // attack/defense/speed/spAttack/spDefense (battle_mon.h:59-63): stats without stages.
    // `stat` is a BATTLE_STAT_* id; BATTLE_STAT_HP returns curHP, as TrainerAI_GetStats does
    // (trainer_ai.c:2330-2367).
    stat(b, stat) {
      const p = pokemon(b);
      if (!p) return 0;
      if (stat === K('BATTLE_STAT_HP')) return p.hp;
      const key = STAT[stat];
      if (!key || key === 'accuracy' || key === 'evasion') throw new Error(`adapter: no raw stat for BATTLE_STAT ${stat}`);
      return p.storedStats[key];
    },
    // statBoosts[stat] (battle_mon.h:75): 0..12, DEFAULT_STAT_STAGE = 6 neutral. Index 0 (HP) is
    // always 6. Showdown boosts are -6..+6.
    statBoost(b, stat) {
      const p = pokemon(b);
      if (!p) return 0; // empty BattleMon
      if (stat === K('BATTLE_STAT_HP')) return DEFAULT_STAT_STAGE;
      const key = STAT[stat];
      if (!key) throw new Error(`adapter: unknown BATTLE_STAT ${stat}`);
      return DEFAULT_STAT_STAGE + p.boosts[key];
    },
    // type1 / type2 (battle_mon.h:79-80); a single-typed mon has type2 == type1.
    types(b) {
      const p = pokemon(b);
      if (!p) return [0, 0];
      const t = p.types.map((x) => map.type(x));
      return [t[0], t[1] ?? t[0]];
    },
    // ability (battle_mon.h:84): the raw current ability (no suppression applied).
    ability: (b) => { const p = pokemon(b); return p ? map.ability(p.ability) : 0; },
    // Battler_Ability (battle_lib.c:3088-3106): ABILITY_NONE under Gastro Acid (except
    // Multitype), or Levitate under Gravity or Ingrain.
    battlerAbility(b) {
      const a = api.ability(b);
      const mask = api.moveEffectsMask(b);
      if ((mask & K('MOVE_EFFECT_ABILITY_SUPPRESSED')) && a !== K('ABILITY_MULTITYPE')) return K('ABILITY_NONE');
      if ((api.fieldConditionsMask() & K('FIELD_CONDITION_GRAVITY')) && a === K('ABILITY_LEVITATE')) return K('ABILITY_NONE');
      if ((mask & K('MOVE_EFFECT_INGRAIN')) && a === K('ABILITY_LEVITATE')) return K('ABILITY_NONE');
      return a;
    },
    heldItem: (b) => { const p = pokemon(b); return p ? map.item(p.item) : 0; },
    // gender (battle_mon.h:123): GENDER_MALE/FEMALE/NONE (generated/genders.txt).
    gender(b) {
      const p = pokemon(b);
      if (!p) return 0;
      return K(p.gender === 'M' ? 'GENDER_MALE' : p.gender === 'F' ? 'GENDER_FEMALE' : 'GENDER_NONE');
    },
    // moves[4] / ppCur[4] (battle_mon.h:64, 99). Showdown moveSlots (Mimic/Transform included).
    moves(b) {
      const p = pokemon(b);
      const out = [0, 0, 0, 0];
      if (p) p.moveSlots.slice(0, 4).forEach((s, i) => { out[i] = map.move(s.id); });
      return out;
    },
    ppCur(b, slot) { const p = pokemon(b); return p && p.moveSlots[slot] ? p.moveSlots[slot].pp : 0; },
    // friendship (battle_mon.h:103), read by TrainerAI_CalcDamage for Return/Frustration
    // (trainer_ai.c:3018-3026). Showdown: pokemon.happiness (set.happiness, default 255). The
    // trainer-party value must be set by the team converter (T034).
    friendship: (b) => pokemon(b)?.happiness ?? 0,
    // weight, from Pokedex_HeightWeightData_Weight (battle_lib.c:150); unit is hectograms, as the
    // Low Kick / Grass Knot table thresholds show (include/data/battle/weight_to_power.h:1-8).
    // Showdown: pokemon.getWeight() in hectograms. UNVERIFIED per species against the decomp's
    // Pokedex weight data.
    weight: (b) => { const p = pokemon(b); return p ? p.getWeight() : 0; },
    // battleCtx->speedRand[b] (battle_context.h:293): a per-turn random number drawn by the game
    // (battle_controller_player.c:855, battle_lib.c:2024) and used for Quick Claw in
    // BattleSystem_CompareBattlerSpeed (battle_lib.c:1279). Showdown has no equivalent; the caller
    // must supply it (opts.speedRand(b)) or the speed-compare command must decide how to draw it.
    speedRand: (b) => (opts.speedRand ? opts.speedRand(b) : undefined),
    // IVs, as read with BattleMon_Get(BATTLEMON_HP_IV + i) (trainer_ai.c:1037-1039), in STAT_*
    // order HP, Atk, Def, Speed, SpAtk, SpDef (BATTLE_STAT order, generated/battle_stats.txt).
    ivs(b) {
      const p = pokemon(b);
      if (!p) return [0, 0, 0, 0, 0, 0];
      const iv = p.set.ivs;
      return [iv.hp, iv.atk, iv.def, iv.spe, iv.spa, iv.spd];
    },

    // status (battle_mon.h:114): MON_CONDITION_* (condition.h). Sleep stores the remaining turns in
    // bits 0-2; toxic stores its counter in bits 8-11.
    status(b) { return statusMask(pokemon(b)); },

    // statusVolatile (battle_mon.h:115): VOLATILE_CONDITION_* (condition.h).
    statusVolatile(b) {
      const p = pokemon(b);
      if (!p) return 0;
      const v = p.volatiles;
      let m = 0;
      if (v.confusion) m |= turns(v.confusion, 7) << K('VOLATILE_CONDITION_CONFUSION_SHIFT');
      if (v.flinch) m |= K('VOLATILE_CONDITION_FLINCH');
      if (v.uproar) m |= turns(v.uproar, 7) << K('VOLATILE_CONDITION_UPROAR_SHIFT');
      if (v.bide) m |= turns(v.bide, 3) << K('VOLATILE_CONDITION_BIDE_SHIFT');
      if (v.lockedmove) m |= (turns(v.lockedmove, 3) << K('VOLATILE_CONDITION_THRASH_SHIFT')) | K('VOLATILE_CONDITION_MOVE_LOCKED');
      // Charge turn of a two-turn move (Solar Beam, Bounce, ...): the game locks the move choice
      // (Battler_LockMoveChoice, battle_lib.c:1828-1832; tested by effect_script_0151.s:9, cleared
      // by subscript_charge_move_cleanup.s:6). Showdown: the 'twoturnmove' volatile. (T046)
      if (v.twoturnmove) m |= K('VOLATILE_CONDITION_MOVE_LOCKED');
      if (v.partiallytrapped) m |= turns(v.partiallytrapped, 7) << K('VOLATILE_CONDITION_BIND_SHIFT');
      if (v.attract) {
        // ATTRACT_0 << (battler that caused it) (VOLATILE_CONDITION_ATTRACT_SHIFT 16).
        const src = v.attract.source;
        const sb = src ? api.battlerOf(src) : 0;
        m |= 1 << (K('VOLATILE_CONDITION_ATTRACT_SHIFT') + (sb < 0 ? 0 : sb));
      }
      if (v.focusenergy) m |= K('VOLATILE_CONDITION_FOCUS_ENERGY');
      if (p.transformed) m |= K('VOLATILE_CONDITION_TRANSFORM');
      if (v.mustrecharge) m |= K('VOLATILE_CONDITION_RECHARGING');
      if (v.rage) m |= K('VOLATILE_CONDITION_RAGE');
      if (v.substitute) m |= K('VOLATILE_CONDITION_SUBSTITUTE');
      if (v.destinybond) m |= K('VOLATILE_CONDITION_DESTINY_BOND');
      if (v.trapped) m |= K('VOLATILE_CONDITION_MEAN_LOOK'); // Mean Look / Block
      if (v.nightmare) m |= K('VOLATILE_CONDITION_NIGHTMARE');
      if (v.curse) m |= K('VOLATILE_CONDITION_CURSE');
      if (v.foresight) m |= K('VOLATILE_CONDITION_FORESIGHT');
      if (v.defensecurl) m |= K('VOLATILE_CONDITION_DEFENSE_CURL');
      if (v.torment) m |= K('VOLATILE_CONDITION_TORMENT');
      return m | 0;
    },

    // moveEffectsMask (battle_mon.h:127): MOVE_EFFECT_* (constants/battle/moves.h:7-38).
    // Game placement differs from Showdown's for some effects:
    //  - LEECH_SEED is on the seeded mon (subscript_leech_seed_start.s:15) = Showdown 'leechseed'
    //    volatile on the target; LEECH_SEED_RECIPIENT (bits 0-1) = battler that receives the HP.
    //  - LOCK_ON is set on the *target* (subscript_lock_on.s:7-8); Showdown puts 'lockon' on the
    //    user with effectState.source = target.
    //  - IMPRISON on the user, IMPRISONED on its opponents (battle_script.c:6689-6724).
    moveEffectsMask(b) {
      const p = pokemon(b);
      if (!p) return 0;
      const v = p.volatiles;
      let m = 0;
      if (v.leechseed) {
        const src = v.leechseed.source;
        m |= K('MOVE_EFFECT_LEECH_SEED') | ((src ? Math.max(0, api.battlerOf(src)) : 0) & K('MOVE_EFFECT_LEECH_SEED_RECIPIENT'));
      }
      for (const foe of p.side.foe.active) {
        if (foe && foe.volatiles.lockon && foe.volatiles.lockon.source === p) m |= K('MOVE_EFFECT_LOCK_ON');
        if (foe && foe.volatiles.imprison) m |= K('MOVE_EFFECT_IMPRISONED');
      }
      if (v.perishsong) m |= K('MOVE_EFFECT_PERISH_SONG');
      if (v.twoturnmove) {
        const mv = v.twoturnmove.move;
        if (mv === 'fly' || mv === 'bounce') m |= K('MOVE_EFFECT_AIRBORNE');
        if (mv === 'dig') m |= K('MOVE_EFFECT_UNDERGROUND');
        if (mv === 'dive') m |= K('MOVE_EFFECT_UNDERWATER');
        if (mv === 'shadowforce') m |= K('MOVE_EFFECT_SHADOW_FORCE');
      }
      if (v.minimize) m |= K('MOVE_EFFECT_MINIMIZE');
      if (v.charge) m |= K('MOVE_EFFECT_CHARGE');
      if (v.ingrain) m |= K('MOVE_EFFECT_INGRAIN');
      if (v.yawn) m |= K('MOVE_EFFECT_YAWN');
      if (v.imprison) m |= K('MOVE_EFFECT_IMPRISON');
      if (v.grudge) m |= K('MOVE_EFFECT_GRUDGE');
      if (v.mudsport || battle.field.pseudoWeather.mudsport) m |= K('MOVE_EFFECT_MUD_SPORT');
      if (v.watersport || battle.field.pseudoWeather.watersport) m |= K('MOVE_EFFECT_WATER_SPORT');
      if (v.gastroacid) m |= K('MOVE_EFFECT_ABILITY_SUPPRESSED');
      if (v.miracleeye) m |= K('MOVE_EFFECT_MIRACLE_EYE');
      if (v.powertrick) m |= K('MOVE_EFFECT_POWER_TRICK');
      if (v.aquaring) m |= K('MOVE_EFFECT_AQUA_RING');
      if (v.healblock) m |= K('MOVE_EFFECT_HEAL_BLOCK');
      if (v.embargo) m |= K('MOVE_EFFECT_EMBARGO');
      if (v.magnetrise) m |= K('MOVE_EFFECT_MAGNET_RISE');
      // MOVE_EFFECT_CAMOUFLAGE: Showdown keeps no marker for having used Camouflage. Never set.
      return m | 0;
    },

    // moveEffectsData (battle_mon.h:8-55). Only nonzero-ness matters to the reachable League
    // commands for the *Turns counters (IfBattlerUnderEffect :1823, IfTargetIsNotTaunted :2620).
    moveEffectsData(b) {
      const p = pokemon(b);
      if (!p) return EMPTY_MED;
      const v = p.volatiles;
      const usedSlots = p.moveSlots.filter((s) => s.used).length;
      return {
        disabledTurns: v.disable ? turns(v.disable, 7) : 0,
        disabledMove: v.disable ? map.move(v.disable.move) : 0,
        encoredTurns: v.encore ? turns(v.encore, 7) : 0,
        encoredMove: v.encore ? map.move(v.encore.move) : 0,
        tauntedTurns: v.taunt ? turns(v.taunt, 7) : 0,
        // stockpileCount (battle_mon.h:17); Showdown 'stockpile' volatile layers.
        stockpileCount: v.stockpile ? v.stockpile.layers : 0,
        flashFire: v.flashfire ? 1 : 0,
        embargoTurns: v.embargo ? turns(v.embargo, 7) : 0,
        // lastResortCount (battle_mon.h:27): distinct moves used since entering. Showdown marks
        // moveSlots[].used, reset on switch-in.
        lastResortCount: usedSlots,
        // fakeOutTurnNumber (battle_mon.h:40) = totalTurns + 1 at switch-in (battle_lib.c:2117,
        // 2195); 0 for the leads (never set before turn 1). Showdown: activeTurns is 0 at
        // switch-in and +1 at each endTurn, so the switch happened at battle.turn - activeTurns,
        // which equals the game's value in both cases.
        fakeOutTurnNumber: battle.turn - p.activeTurns,
        // protectSuccessTurns (battle_mon.h:13): consecutive successes, capped at 3. Showdown's
        // 'stall' volatile counter is 3 after one success and 9 (capped, gen4 counterMax 8,
        // data/mods/gen4/conditions.ts:142-147) after more, so 2 and 3 are indistinguishable;
        // returns 2 for both. The reachable League uses compare it with > 1 and == 0 only
        // (script.s:3546, 3576).
        protectSuccessTurns: v.stall ? (v.stall.counter >= 9 ? 2 : 1) : 0,
        // slowStartTurnNumber is set together with fakeOutTurnNumber (battle_lib.c:2117-2118).
        slowStartTurnNumber: battle.turn - p.activeTurns,
        // magnetRiseTurns (battle_mon.h:28), read by BattleSystem_ApplyTypeChart (battle_lib.c:2604).
        magnetRiseTurns: v.magnetrise ? turns(v.magnetrise, 7) : 0,
        // canUnburden (battle_mon.h:31), read by BattleSystem_CompareBattlerSpeed (battle_lib.c:1269).
        canUnburden: v.unburden ? 1 : 0,
        // choiceLockedMove (battle_mon.h:51): Showdown 'choicelock' volatile.
        choiceLockedMove: v.choicelock ? map.move(v.choicelock.move) : 0,
      };
    },

    // battleCtx->battlersSwitchingMask (battle_context.h:289). Not reachable from League sections
    // (IfBattlerFainted is doubles-only); provided for completeness.
    battlersSwitchingMask: () => 0,

    // ----- party (Pokemon_GetValue over BattleSystem_GetParty) -----

    // Party in game order. Each entry mirrors the MON_DATA_* values the handlers read:
    // HP/MAX_HP (:1146, :1977), SPECIES_OR_EGG (:1147), STATUS (:1371), MOVE1..4 / PP / MAX_PP
    // (:2001, :2139), HELD_ITEM, ABILITY (:2152-2154), IVs (:2142).
    party(b) {
      const s = sideOfBattler(b);
      return partyOrder[s.id].map((p, i) => ({
        slot: i,
        pokemon: p,
        species: map.species(p.species),
        level: p.level,
        hp: p.hp,
        maxHP: p.maxhp,
        status: statusMask(p),
        moves: p.moveSlots.slice(0, 4).map((m) => map.move(m.id)),
        pp: p.moveSlots.slice(0, 4).map((m) => m.pp),
        maxPP: p.moveSlots.slice(0, 4).map((m) => m.maxpp),
        heldItem: map.item(p.item),
        ability: map.ability(p.ability),
        ivs: [p.set.ivs.hp, p.set.ivs.atk, p.set.ivs.def, p.set.ivs.spe, p.set.ivs.spa, p.set.ivs.spd],
      }));
    },
    // BattleSystem_GetPartyCount.
    partyCount: (b) => partyOrder[sideOfBattler(b).id].length,

    // ----- static data -----

    // MOVE_DATA(move) (battle/common.h:25). moveData(0) is MOVE_NONE's row.
    moveData(move) {
      const m = T.moves[move];
      if (!m) throw new Error(`adapter: no move data for id ${move}`);
      return m;
    },
    // BattleSystem_GetItemData(item, ITEM_PARAM_HOLD_EFFECT). ITEM_NONE -> HOLD_EFFECT_NONE (0).
    itemHoldEffect: (item) => (item ? (T.items[item]?.holdEffect ?? 0) : 0),
    itemData: (item) => T.items[item],
    // SpeciesData_GetSpeciesValue(species, SPECIES_DATA_ABILITY_1 / _2).
    speciesAbilities: (sp) => T.species[sp].abilities,

    // Showdown Pokemon -> battler id (-1 if not active).
    battlerOf(p) {
      if (!p || !p.isActive) return -1;
      const base = p.side.id === aiSide ? 1 : 0;
      return base + 2 * p.position;
    },

    // ---------- 015: per-decision cache of damage-formula inputs (contracts/adapter-api.md) ----------
    cacheStats,
    beginDecision() {
      battlers.clear();
      fields.clear();
      plans.clear();
      pre.clear();
      cacheStats.decisions++;
    },
    damageInput,
    // ---------- 016: per-decision memo of the type-chart plan and the pre-variance damage ----------
    typeChartPlan: typeChartPlanMemo,
    preVariance,
  };

  // Damage-formula inputs, identical to damage.mjs fromShowdown(battle, att, def, move, opts) for the
  // current battle state, with the battler structs cached per Pokemon object and the field struct per
  // defender side until beginDecision(). Reads only battle state, like fromShowdown.
  function battler(p) {
    let b = battlers.get(p);
    if (b) {
      cacheStats.hits++;
      if (CHECK) { cacheStats.structChecks++; CHECK_STATS.structChecks++; checkSame('battler', `${p.species.id}#${p.side.id}${p.position}`, b, battlerFromShowdown(p)); }
      return b;
    }
    b = battlerFromShowdown(p);
    if (FREEZE) deepFreeze(b);
    battlers.set(p, b);
    cacheStats.builds++;
    return b;
  }
  const abilityOf = (b) => (b.abilitySuppressed ? 'ABILITY_NONE' : b.ability);
  function buildField(defenderPoke) {
    const active = battle.getAllActive();
    const ds = defenderPoke.side.sideConditions;
    const anyVol = (id) => active.some((p) => p.volatiles[id]) || !!battle.field.pseudoWeather[id];
    return {
      weather: WEATHER[battle.field.weather] ?? '',
      abilitiesOnField: active.filter((p) => p.hp > 0).map((p) => abilityOf(battler(p))),
      defenderSide: { reflect: !!ds.reflect, lightScreen: !!ds.lightscreen, luckyChant: !!ds.luckychant },
      gravity: !!battle.field.pseudoWeather.gravity,
      mudSport: anyVol('mudsport'),
      waterSport: anyVol('watersport'),
    };
  }
  function fieldFor(defenderPoke) {
    let f = fields.get(defenderPoke.side);
    if (f) {
      if (CHECK) { cacheStats.structChecks++; CHECK_STATS.structChecks++; checkSame('field', defenderPoke.side.id, f, buildField(defenderPoke)); }
      return f;
    }
    f = buildField(defenderPoke);
    if (FREEZE) deepFreeze(f);
    fields.set(defenderPoke.side, f);
    cacheStats.fieldBuilds++;
    return f;
  }
  function damageInput(attackerPoke, defenderPoke, moveIdOrNum, { power, type, powerMul } = {}) {
    if (battle.gameType !== 'singles') throw new Error('damage.mjs adapter: only singles is covered');
    const num = typeof moveIdOrNum === 'number' ? moveIdOrNum : battle.dex.moves.get(moveIdOrNum).num;
    const moveConst = ENUMS.moves[num];
    if (!moveConst) throw new Error(`damage.mjs adapter: no decomp move for num ${num}`);
    const attacker = battler(attackerPoke);
    const defender = battler(defenderPoke);
    const base = fieldFor(defenderPoke);
    const field = {
      weather: base.weather,
      abilitiesOnField: base.abilitiesOnField,
      attackerSideAbilities: [abilityOf(attacker)],
      defenderSideAbilities: [abilityOf(defender)],
      defenderSide: base.defenderSide,
      gravity: base.gravity,
      mudSport: base.mudSport,
      waterSport: base.waterSport,
    };
    const input = { attacker, defender, move: { id: moveConst, power, type, powerMul }, field, crit: false };
    return FREEZE ? deepFreeze(input) : input;
  }

  // 016 memos (contracts/adapter-api.md). Keyed on the cached attacker and defender structs (identity-stable within
  // a decision) and the per-call move facts. Everything that varies per sample is in the key (power, type, fixed
  // damage come from the sample's inputs and RNG draws) or applied after (the variance step), and the shared part
  // draws no random numbers, so the K samples read identical values whether recomputed or memoised.
  const memoKey = (mv, ignore, fixed) => `${mv.id}|${mv.power}|${mv.type}|${ignore ? 1 : 0}|${fixed}`;
  function slotFor(map, att, def) {
    let byDef = map.get(att);
    if (!byDef) { byDef = new Map(); map.set(att, byDef); }
    let slot = byDef.get(def);
    if (!slot) { slot = new Map(); byDef.set(def, slot); }
    return slot;
  }
  function checkSame(kind, key, memo, fresh) {
    cacheStats.checks++;
    CHECK_STATS.checks++;
    const a = JSON.stringify(memo), b = JSON.stringify(fresh);
    if (a !== b) {
      CHECK_STATS.mismatches++;
      throw new Error(`adapter: CHECK mismatch ${kind} ${key}: memo=${a} fresh=${b}`);
    }
  }
  function planFor(input, ignoreTypeChecks) {
    const key = memoKey(input.move, ignoreTypeChecks, '');
    const slot = slotFor(plans, input.attacker, input.defender);
    let plan = slot.get(key);
    if (plan) {
      cacheStats.planHits++;
      if (CHECK) checkSame('typeChartPlan', key, plan, typeChartPlan(input, { ignoreTypeChecks, moveStatusMask: 0 }));
      return plan;
    }
    plan = typeChartPlan(input, { ignoreTypeChecks, moveStatusMask: 0 });
    if (FREEZE) deepFreeze(plan);
    slot.set(key, plan);
    cacheStats.plans++;
    return plan;
  }
  function typeChartPlanMemo(attackerPoke, defenderPoke, moveIdOrNum, opts = {}, { ignoreTypeChecks = false } = {}) {
    return planFor(damageInput(attackerPoke, defenderPoke, moveIdOrNum, opts), ignoreTypeChecks);
  }
  // TrainerAI_CalcDamage, TAI:3081-3103: BattleSystem_CalcMoveDamage(..., criticalMul 1) when there is no fixed
  // damage, then BattleSystem_ApplyTypeChart with SYSCTL_IGNORE_TYPE_CHECKS set for fixed damage (TAI:3093). The
  // immune check and the variance step (TAI:3106-3109) are the caller's, per sample.
  function computePreVariance(input, fixedDamage, plan) {
    const damage = fixedDamage === 0 ? calcBaseDamage({ ...input, critMul: 1 }) : fixedDamage;
    const r = replayTypeChart(plan, damage);
    return { damage: r.damage, moveStatusMask: r.moveStatusMask };
  }
  function preVariance(attackerPoke, defenderPoke, moveIdOrNum, opts = {}, fixedDamage = 0) {
    const input = damageInput(attackerPoke, defenderPoke, moveIdOrNum, opts);
    const ignore = fixedDamage !== 0;
    const key = memoKey(input.move, ignore, fixedDamage);
    const slot = slotFor(pre, input.attacker, input.defender);
    let entry = slot.get(key);
    if (entry) {
      cacheStats.preVarianceHits++;
      // The fresh value uses a fresh plan too, so a corrupted plan memo cannot hide behind a matching entry.
      if (CHECK) checkSame('preVariance', key, entry, computePreVariance(input, fixedDamage, typeChartPlan(input, { ignoreTypeChecks: ignore, moveStatusMask: 0 })));
      return entry;
    }
    entry = computePreVariance(input, fixedDamage, planFor(input, ignore));
    if (FREEZE) deepFreeze(entry);
    slot.set(key, entry);
    cacheStats.preVariance++;
    return entry;
  }

  function statusMask(p) {
    if (!p) return 0;
    switch (p.status) {
      case 'slp': return Math.max(1, Math.min(7, p.statusState.time ?? 1)) & K('MON_CONDITION_SLEEP');
      case 'psn': return K('MON_CONDITION_POISON');
      case 'brn': return K('MON_CONDITION_BURN');
      case 'frz': return K('MON_CONDITION_FREEZE');
      case 'par': return K('MON_CONDITION_PARALYSIS');
      case 'tox': return K('MON_CONDITION_TOXIC') | ((Math.min(15, p.statusState.stage ?? 0) << 8) & K('MON_CONDITION_TOXIC_COUNTER'));
      default: return 0;
    }
  }

  return api;
}

const EMPTY_MED = Object.freeze({
  disabledTurns: 0, disabledMove: 0, encoredTurns: 0, encoredMove: 0, tauntedTurns: 0,
  stockpileCount: 0, flashFire: 0, embargoTurns: 0, lastResortCount: 0, fakeOutTurnNumber: 0,
  protectSuccessTurns: 0, slowStartTurnNumber: 0, magnetRiseTurns: 0, canUnburden: 0, choiceLockedMove: 0,
});
