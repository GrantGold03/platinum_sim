// Game data for the Node side: data/generated/*.json (written by `platsim extract`, T019), the
// Showdown Dex patch layer (data/divergences.json, T053) and decomp <-> Showdown id mapping.
//
// Order matters (research R4): Showdown caches Dex.*.get() results, so every data patch and the
// trainerfullrestore pseudo-move are installed in prepareDex() BEFORE the first Dex lookup.
// loadGameData() does both and is a per-process singleton.
//
// Divergence patches. data/divergences.json does not exist until T053. Its entries follow
// data-model.md DivergenceEntry; an entry is applied here only when resolution === "corrected"
// and it carries a `patch` object:
//   {"table": "Pokedex" | "Moves" | "Items" | "Abilities" | "Learnsets",
//    "id": "<showdown id>", "path": ["baseStats", "hp"], "value": <json>}
// (`path` is the key path inside Dex.mod('gen4').data[table][id]). Corrected entries without a
// `patch` are mechanics corrected by the game layer (exp, Full Restore, ...) and are skipped.
// T053: emit `patch` in this shape (and optionally a top-level "version").
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Dex } from './showdown.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = join(here, '..');
export const GENERATED_DIR = join(REPO_ROOT, 'data', 'generated');
export const DIVERGENCES_PATH = join(REPO_ROOT, 'data', 'divergences.json');
export const SHOWDOWN_DIR = join(REPO_ROOT, 'pokemon-showdown');
export const MOD = 'gen4';
export const FORMAT = 'gen4customgame'; // research R4

export const toID = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
const strip = (s, prefix) => (String(s).startsWith(prefix) ? String(s).slice(prefix.length) : String(s));
// "ITEM_SITRUS_BERRY" | "sitrus_berry" -> "sitrus_berry" (data/generated key form)
export const keyOf = (s, prefix) => strip(s, prefix).toLowerCase();

// ---- Full Restore pseudo-move (T010, research R5 "Spike results") -----------------------------
// Game rule it stands in for: TrainerAI_ShouldUseItem (pokeplatinum/src/battle/trainer_ai/
// trainer_ai.c:4056) decides; item use resolves before moves, so priority 7. Effect of Full
// Restore: full HP, cure status and confusion. Taunt still blocks it in Showdown
// (pokemon-showdown/data/mods/gen4/moves.ts:1411-1418); T047 patches that, not this file.
export const FULL_RESTORE_MOVE = 'trainerfullrestore';
const fullRestoreData = {
  num: -1001, name: 'Trainer Full Restore', accuracy: true, basePower: 0, category: 'Status',
  pp: 64, noPPBoosts: true, priority: 7, flags: {}, target: 'self', type: '???',
  onHit(pokemon) {
    pokemon.sethp(pokemon.maxhp);
    pokemon.cureStatus();
    pokemon.removeVolatile('confusion');
    this.add('-heal', pokemon, pokemon.getHealth, '[from] item: Full Restore');
  },
};

// Adds the pseudo-move to the active mon's slots for this turn; returns the choice string.
// The caller removes it after the turn with removeFullRestore().
export function injectFullRestore(battle, side) {
  const mon = side.active[0];
  const move = battle.dex.moves.get(FULL_RESTORE_MOVE);
  mon.moveSlots.push({ move: move.name, id: move.id, pp: move.pp, maxpp: move.pp, target: move.target,
    disabled: false, used: false, virtual: true });
  return `move ${mon.moveSlots.length}`;
}
export function removeFullRestore(mon) {
  mon.moveSlots = mon.moveSlots.filter((s) => s.id !== FULL_RESTORE_MOVE);
}

// ---- Dex patch layer ---------------------------------------------------------------------------
let prepared = null;

function sha256(buf) { return createHash('sha256').update(buf).digest('hex'); }

export function prepareDex(divergencesPath = DIVERGENCES_PATH) {
  if (prepared) {
    if (prepared.path !== divergencesPath) throw new Error('prepareDex: already prepared with another ledger');
    return prepared;
  }
  const data = Dex.mod(MOD).data;
  const result = { path: divergencesPath, version: 'none', applied: [], skipped_mechanics: 0 };
  if (existsSync(divergencesPath)) {
    const raw = readFileSync(divergencesPath);
    const ledger = JSON.parse(raw.toString('utf8'));
    const entries = Array.isArray(ledger) ? ledger : ledger.entries ?? [];
    result.version = (!Array.isArray(ledger) && ledger.version) || `sha256:${sha256(raw).slice(0, 16)}`;
    for (const e of entries) {
      if (e.resolution !== 'corrected') continue;
      if (!e.patch) { result.skipped_mechanics++; continue; }
      const { table, id, path, value } = e.patch;
      if (!data[table]?.[id]) throw new Error(`divergence ${e.id}: no ${table}.${id} in Showdown ${MOD} data`);
      let obj = data[table][id];
      for (const k of path.slice(0, -1)) obj = obj[k] ??= {};
      obj[path[path.length - 1]] = value;
      result.applied.push(e.id);
    }
  }
  data.Moves[FULL_RESTORE_MOVE] = fullRestoreData;
  prepared = result;
  return result;
}

// ---- Showdown commit (provenance for `hello`) -----------------------------------------------
export function showdownCommit(dir = SHOWDOWN_DIR) {
  const gitDir = join(dir, '.git');
  let head = readFileSync(join(gitDir, 'HEAD'), 'utf8').trim();
  if (!head.startsWith('ref: ')) return head;
  const ref = head.slice(5);
  if (existsSync(join(gitDir, ref))) return readFileSync(join(gitDir, ref), 'utf8').trim();
  const packed = readFileSync(join(gitDir, 'packed-refs'), 'utf8');
  const line = packed.split('\n').find((l) => l.endsWith(` ${ref}`));
  if (!line) throw new Error(`cannot resolve ${ref} in ${gitDir}`);
  return line.split(' ')[0];
}

// ---- Id mapping --------------------------------------------------------------------------------
// Species: base forms map by national dex number (decomp id = species.txt index =
// Showdown `num`), forms by "<base><form>" id; moves by number (MOVE_* index = Showdown `num`);
// items and abilities by name, number checked. Every failure is reported, never guessed.
function mapSpecies(gd, dex) {
  const byNum = new Map();
  for (const s of dex.species.all()) if (!s.forme && s.num > 0) byNum.set(s.num, s);
  for (const rec of Object.values(gd.species)) {
    let sd = null;
    if (rec.form === null) {
      sd = byNum.get(rec.id) ?? null;
    } else {
      const base = gd.species[rec.base_species];
      const cand = dex.species.get(toID(rec.base_species) + toID(rec.form));
      if (cand.exists && cand.num === base.id) sd = cand;
    }
    if (sd) { gd.sdSpecies.set(rec.key, sd.name); gd.fromSdSpecies.set(sd.id, rec.key); } else gd.unmapped.species.push(rec.key);
  }
}

function mapMoves(gd, dex) {
  const byNum = new Map(); // several Showdown entries can share a num (hiddenpowerbug, ...)
  for (const m of dex.moves.all()) if (m.num > 0) byNum.set(m.num, [...(byNum.get(m.num) ?? []), m]);
  for (const rec of Object.values(gd.moves)) {
    const cands = byNum.get(rec.id) ?? [];
    const m = cands.find((c) => c.id === toID(rec.name)) ?? (cands.length === 1 ? cands[0] : null);
    if (!m) { gd.unmapped.moves.push(rec.key); continue; }
    if (toID(m.name) !== toID(rec.name) && toID(m.name) !== toID(rec.key)) gd.renamed.moves.push([rec.key, m.id]);
    gd.sdMove.set(rec.key, m.id); gd.fromSdMove.set(m.id, rec.key);
  }
}

function mapItems(gd, dex) {
  for (const rec of Object.values(gd.items)) {
    if (rec.key === 'none') continue;
    let it = dex.items.get(toID(rec.name));
    if (!it.exists) it = dex.items.get(toID(rec.key));
    if (!it.exists) { gd.unmapped.items.push(rec.key); continue; }
    if (it.num !== rec.id) gd.numMismatch.items.push([rec.key, rec.id, it.id, it.num]);
    gd.sdItem.set(rec.key, it.id); gd.fromSdItem.set(it.id, rec.key);
  }
}

function mapAbilities(gd, dex) {
  for (const [constName, num] of Object.entries(gd.constants.abilities)) {
    if (constName === 'ABILITY_NONE' || !constName.startsWith('ABILITY_')) continue;
    const a = dex.abilities.get(toID(strip(constName, 'ABILITY_')));
    if (!a.exists) { gd.unmapped.abilities.push(constName); continue; }
    if (a.num !== num) gd.numMismatch.abilities.push([constName, num, a.id, a.num]);
    gd.sdAbility.set(constName, a.id);
  }
}

let cached = null;

export function loadGameData({ dir = GENERATED_DIR, divergencesPath = DIVERGENCES_PATH } = {}) {
  if (cached) return cached;
  const dexPatch = prepareDex(divergencesPath);
  const read = (n) => JSON.parse(readFileSync(join(dir, `${n}.json`), 'utf8'));
  const manifestRaw = readFileSync(join(dir, 'manifest.json'));
  const manifest = JSON.parse(manifestRaw.toString('utf8'));
  const gd = {
    dir, manifest, dexPatch,
    decompDataHash: `sha256:${sha256(manifestRaw)}`,
    species: read('species').species,
    moves: read('moves').moves,
    items: read('items').items,
    trainers: read('trainers').trainers,
    exp: read('exp'),
    constants: read('constants'),
    // Optional tables (added by later tasks).
    availability: existsSync(join(dir, 'availability.json')) ? read('availability') : null,
    sdSpecies: new Map(), fromSdSpecies: new Map(), sdMove: new Map(), fromSdMove: new Map(),
    sdItem: new Map(), fromSdItem: new Map(), sdAbility: new Map(),
    unmapped: { species: [], moves: [], items: [], abilities: [] },
    renamed: { moves: [] },
    numMismatch: { items: [], abilities: [] },
  };
  gd.itemByConst = new Map(Object.values(gd.items).map((r) => [r.const, r]));
  gd.moveByConst = new Map(Object.values(gd.moves).map((r) => [r.const, r]));
  const dex = Dex.mod(MOD);
  mapSpecies(gd, dex); mapMoves(gd, dex); mapItems(gd, dex); mapAbilities(gd, dex);
  cached = gd;
  return gd;
}

// Species record for a Build species key or a SPECIES_* constant (+ form index for trainers).
export function speciesRecord(gd, s, form = 0) {
  let key = keyOf(s, 'SPECIES_');
  if (form) {
    const f = Object.values(gd.species).find((r) => r.base_species === key && r.form_index === form);
    if (!f) throw new Error(`no data form ${form} for ${s}`);
    key = f.key;
  }
  const rec = gd.species[key];
  if (!rec) throw new Error(`unknown species ${s}`);
  return rec;
}
export function moveRecord(gd, m) {
  const rec = gd.moves[keyOf(typeof m === 'object' ? m.move : m, 'MOVE_')];
  if (!rec) throw new Error(`unknown move ${JSON.stringify(m)}`);
  return rec;
}
export function itemRecord(gd, it) {
  if (it === null || it === undefined || it === '' || it === 'ITEM_NONE' || it === 'none') return null;
  const rec = gd.items[keyOf(it, 'ITEM_')];
  if (!rec) throw new Error(`unknown item ${it}`);
  return rec;
}
