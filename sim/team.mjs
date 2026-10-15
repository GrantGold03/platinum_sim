// Build JSON / trainers.json party -> Showdown PokemonSet, and the post-construction fix-ups that
// make a Showdown Battle match the cartridge for both sides (T034).
//
// - Player Build (data-model.md "Build"): species/moves/item keys from data/generated, ability
//   ABILITY_* (or its key), nature "Hardy" / NATURE_*, ivs/evs. Optional extras used by the
//   gauntlet: is_traded, foreign_language (FR-008a; derived from `source` when absent, see
//   tradeOrigin below), gender ("M"/"F"; otherwise Showdown picks
//   one from the battle PRNG, which is seeded and therefore reproducible).
// - Opponent (trainers.json, built by the TrainerData_BuildParty port in
//   src/platsim/decomp/trainers.py): IVs = mon.iv (30 for the League), EVs 0, nature and ability
//   from the computed personality, gender per SpeciesData_GetGenderOf (src/pokemon.c:2717-2733):
//   ratio MALE_ONLY/FEMALE_ONLY/NO_GENDER fixed, else female iff ratio > (personality & 0xff).
// - PP: Showdown gives every move 3 PP Ups (pokemon-showdown/sim/pokemon.ts:361). The game sets
//   max PP = MoveTable_CalcMaxPP(move, ppUps) (BoxPokemon_SetMoveSlot, src/pokemon.c:3925-3930;
//   src/move_table.c:25), with ppUps 0 for trainer mons (Pokemon_Init zeroes the data,
//   src/pokemon.c:292-294) and, by spec FR-008, for the player too. So every slot of both sides is
//   reset to the decomp base PP (moves.json `pp`), or to carried-over PP for the player.
// - Stats: after construction, both sides' stats are overwritten with the decomp formula
//   (sim/exp.mjs calcStats, port of Pokemon_CalcStats src/pokemon.c:564) so a Showdown/decomp
//   formula or base-stat difference cannot leak in. sim/test/team.test.mjs checks that
//   Showdown's own numbers already agree.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { Battle, Dex } from './showdown.mjs';
import { FORMAT, MOD, REPO_ROOT, itemRecord, keyOf, moveRecord, speciesRecord, toID } from './gamedata.mjs';
import { STAT_KEYS, calcStats, expAt } from './exp.mjs';

export const P1_NAME = 'Player';
export const P2_NAME = 'Opponent';

const statsOf = (o, dflt) => Object.fromEntries(STAT_KEYS.map((k) => [k, o?.[k] ?? dflt]));
const natureConst = (n) => (String(n).startsWith('NATURE_') ? String(n) : `NATURE_${String(n).toUpperCase()}`);
const abilityConst = (a) => (String(a).startsWith('ABILITY_') ? String(a) : `ABILITY_${String(a).toUpperCase()}`);

function sdNature(nc) {
  const n = Dex.mod(MOD).natures.get(toID(nc.slice('NATURE_'.length)));
  if (!n.exists) throw new Error(`nature ${nc} has no Showdown mapping`);
  return n.name;
}

class InvalidTeam extends Error {
  constructor(msg) { super(msg); this.kind = 'invalid_team'; }
}
export { InvalidTeam };

function need(map, key, what) {
  const v = map.get(key);
  if (v === undefined) throw new InvalidTeam(`${what} ${key} has no Showdown mapping`);
  return v;
}

// ---- In-game NPC trades: not OT (FR-008a) -----------------------------------------------------
// BattleScript_GetExpTask boosts exp when BattleSystem_PokemonIsOT is FALSE
// (pokeplatinum/src/battle/battle_script.c:9757-9765): x170/100 if MON_DATA_LANGUAGE !=
// gGameLanguage, else x150/100. BattleSystem_PokemonIsOT (src/battle/battle_lib.c:6286-6301)
// compares the player's trainer ID, gender and name with the mon's OT fields.
// NPCTrade_CreateMon (src/overlay006/npc_trade.c:117-149) gives the traded mon the NPC's otID,
// OT name and OT gender (so it is never the player's: assumed, the player cannot pick an ID) and
// MON_DATA_LANGUAGE = the FixedMon's `language` (res/npc_trades/<name>.json).
// gGameLanguage = GAME_LANGUAGE (src/game_version.c:4), set by meson.build
// (`-DGAME_LANGUAGE=LANGUAGE_ENGLISH` for the pinned US build).
// A Build's `source` is "npc_trade:SPECIES_X@MAP_HEADER_Y" (src/platsim/legality, ledger kind
// npc_trade). This is the single place the worker derives `traded` / `foreignLanguage`, so every
// caller (CLI, evaluate, tests) gets the boost from the team file alone.
const DECOMP_DIR = join(REPO_ROOT, 'pokeplatinum');
let npcTradeCache = null;
export function npcTradeData(dir = DECOMP_DIR) {
  if (npcTradeCache && npcTradeCache.dir === dir) return npcTradeCache;
  const tdir = join(dir, 'res', 'npc_trades');
  const trades = readdirSync(tdir).filter((f) => f.endsWith('.json')).sort()
    .map((f) => ({ file: `res/npc_trades/${f}`, ...JSON.parse(readFileSync(join(tdir, f), 'utf8')) }));
  const m = /-DGAME_LANGUAGE=(LANGUAGE_\w+)/.exec(readFileSync(join(dir, 'meson.build'), 'utf8'));
  if (!m) throw new Error('GAME_LANGUAGE not found in pokeplatinum/meson.build');
  npcTradeCache = { dir, trades, gameLanguage: m[1] };
  return npcTradeCache;
}

/** {traded, foreignLanguage, trade} for a Build `source`; traded false if it is not an NPC trade. */
export function tradeOrigin(source) {
  const s = String(source ?? '');
  if (!s.startsWith('npc_trade:')) return { traded: false, foreignLanguage: false, trade: null };
  const species = s.slice('npc_trade:'.length).split('@')[0];
  const { trades, gameLanguage } = npcTradeData();
  const hits = trades.filter((t) => t.species === species);
  if (hits.length !== 1) throw new InvalidTeam(`source ${s}: ${hits.length} NPC trades give ${species} (res/npc_trades)`);
  return { traded: true, foreignLanguage: hits[0].language !== gameLanguage, trade: hits[0].file };
}

/**
 * Player party-state member from a Build (persisted across the gauntlet).
 * start: optional {level, exp, pp:[..], item} from a start_state.
 */
export function playerMember(gd, build, slot, start = {}) {
  let rec;
  try { rec = speciesRecord(gd, build.species); } catch (e) { throw new InvalidTeam(e.message); }
  const level = start.level ?? build.start_level;
  if (!Number.isInteger(level) || level < 1 || level > gd.exp.max_level) throw new InvalidTeam(`slot ${slot}: bad level ${level}`);
  // start.moves: moves carried from earlier battles (auto-learned level-up moves, sim/exp.mjs).
  const moves = (start.moves ?? build.moves ?? []).map((m) => { try { return moveRecord(gd, m).key; } catch (e) { throw new InvalidTeam(e.message); } });
  if (moves.length < 1 || moves.length > 4) throw new InvalidTeam(`slot ${slot}: ${moves.length} moves`);
  const itemKey = start.item !== undefined ? start.item : build.held_item;
  let itemRec;
  try { itemRec = itemRecord(gd, itemKey); } catch (e) { throw new InvalidTeam(e.message); }
  const exp = start.exp ?? expAt(gd, rec.exp_rate, level);
  const origin = tradeOrigin(build.source);
  return {
    slot, rec, level, exp, moves,
    ability: abilityConst(build.ability),
    nature: natureConst(build.nature ?? 'Hardy'),
    ivs: statsOf(build.ivs, 15), evs: statsOf(build.evs, 85), // FR-008 defaults
    itemRec,
    // Explicit Build fields win (tests, what-ifs); otherwise derived from `source` (FR-008a).
    traded: !!(build.is_traded ?? build.traded ?? origin.traded),
    foreignLanguage: !!(build.foreign_language ?? origin.foreignLanguage),
    gender: build.gender ?? undefined,
    pp: start.pp ? [...start.pp] : moves.map((k) => gd.moves[k].pp),
    // 007 FR-012: every player member is assumed to have maximum friendship (Return = 102,
    // effect_script_0121.s; trainer_ai.c:3019). Showdown's default is also 255; this makes it explicit.
    happiness: 255,
  };
}

export function memberSet(gd, m) {
  return {
    name: m.rec.name, species: need(gd.sdSpecies, m.rec.key, 'species'), level: m.level,
    moves: m.moves.map((k) => need(gd.sdMove, k, 'move')),
    ability: need(gd.sdAbility, m.ability, 'ability'),
    // Items Showdown does not know (Exp. Share, Lucky Egg, ...: no battle effect) are given to
    // Showdown as no item; exp.mjs reads the decomp item from the member instead.
    item: m.itemRec ? gd.sdItem.get(m.itemRec.key) ?? '' : '',
    nature: sdNature(m.nature), ivs: m.ivs, evs: m.evs, gender: m.gender,
    ...(m.happiness !== undefined ? { happiness: m.happiness } : {}),
  };
}

// SpeciesData_GetGenderOf (src/pokemon.c:2717-2733)
export function genderOf(gd, rec, personality) {
  const r = gd.constants.gender_ratios;
  const ratio = r[rec.gender_ratio];
  if (ratio === r.GENDER_RATIO_MALE_ONLY) return 'M';
  if (ratio === r.GENDER_RATIO_FEMALE_ONLY) return 'F';
  if (ratio === r.GENDER_RATIO_NO_GENDER) return 'N';
  return ratio > (personality & 0xff) ? 'F' : 'M';
}

/** Opponent members for one trainers.json entry. */
export function opponentMembers(gd, trainer) {
  return trainer.party.map((mon, slot) => {
    const rec = speciesRecord(gd, mon.species, mon.form);
    const moves = mon.moves.filter((m) => m !== 'MOVE_NONE').map((m) => moveRecord(gd, m).key);
    const iv = mon.iv;
    return {
      slot, rec, level: mon.level, moves,
      ability: mon.ability, nature: mon.nature,
      ivs: statsOf(null, iv), evs: statsOf(null, 0),
      itemRec: itemRecord(gd, mon.held_item),
      gender: genderOf(gd, rec, mon.personality),
      pp: moves.map((k) => gd.moves[k].pp),
    };
  });
}

/** Overwrite stats with the decomp formula and set PP; tags each Pokemon with platsim fields. */
export function fixupSide(gd, side, members) {
  side.pokemon.forEach((pokemon, i) => {
    const m = members[i];
    pokemon.platsimSlot = m.slot;
    pokemon.platsimRec = m.rec;
    const stats = calcStats(gd, m.rec, m.ivs, m.evs, m.level, m.nature);
    pokemon.platsimShowdownStats = { hp: pokemon.maxhp, ...pokemon.baseStoredStats };
    const full = pokemon.hp === pokemon.maxhp;
    pokemon.baseStoredStats = { ...stats };
    for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) pokemon.storedStats[k] = stats[k];
    pokemon.baseMaxhp = stats.hp;
    pokemon.maxhp = stats.hp;
    if (full) pokemon.hp = stats.hp;
    // PP: base (decomp) max PP, current = carried PP. ppUps 0 (FR-008).
    pokemon.baseMoveSlots.forEach((s, j) => {
      const key = gd.fromSdMove.get(s.id);
      s.maxpp = gd.moves[key].pp;
      s.pp = Math.min(m.pp[j], s.maxpp);
    });
    pokemon.moveSlots = pokemon.baseMoveSlots.slice(); // same objects, as Pokemon.clearVolatile does
    pokemon.ppUps = pokemon.baseMoveSlots.map(() => 0);
  });
}

/** New Battle with both sides fixed up. */
export function newBattle(gd, { seed, player, opponent }) {
  const p1team = player.map((m) => memberSet(gd, m));
  const p2team = opponent.map((m) => memberSet(gd, m));
  const battle = new Battle({
    formatid: FORMAT, seed,
    p1: { name: P1_NAME, team: p1team }, p2: { name: P2_NAME, team: p2team },
  });
  fixupSide(gd, battle.sides[0], player);
  fixupSide(gd, battle.sides[1], opponent);
  return battle;
}

/** Id-mapping coverage of every League mon and every generated species/move/item. */
export function mappingReport(gd) {
  const league = [];
  for (const t of gd.trainers) {
    for (const mon of t.party) {
      const rec = speciesRecord(gd, mon.species, mon.form);
      const problems = [];
      if (!gd.sdSpecies.has(rec.key)) problems.push(`species ${rec.key}`);
      for (const mv of mon.moves) if (mv !== 'MOVE_NONE' && !gd.sdMove.has(keyOf(mv, 'MOVE_'))) problems.push(`move ${mv}`);
      if (mon.held_item !== 'ITEM_NONE' && !gd.sdItem.has(keyOf(mon.held_item, 'ITEM_'))) problems.push(`item ${mon.held_item}`);
      if (!gd.sdAbility.has(mon.ability)) problems.push(`ability ${mon.ability}`);
      if (problems.length) league.push({ trainer: t.key, species: mon.species, problems });
    }
  }
  const heldUnmapped = gd.unmapped.items.filter((k) => gd.items[k].hold_effect !== 'HOLD_EFFECT_NONE')
    .map((k) => `${k}:${gd.items[k].hold_effect}`);
  return {
    league_unmapped: league,
    unmapped: gd.unmapped,
    unmapped_items_with_hold_effect: heldUnmapped,
    renamed_moves: gd.renamed.moves,
    num_mismatch: gd.numMismatch,
  };
}
