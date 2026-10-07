// T053: dump Showdown's gen4 data (species, moves, battle-effect items) as JSON on stdout, for
// src/platsim/divergence/compare.py to diff against data/generated/.
//
// The dump is Showdown's OWN data: no divergence patch is applied. It reuses the exact id mapping
// of sim/gamedata.mjs (loadGameData: species/moves by number, items by name) by preparing the Dex
// with a ledger path that does not exist, so every dumped entry carries the decomp key it maps to.
// Values are read through Dex.mod('gen4') after the mod chain (gen4 <- gen5 <- ... <- base) merges.
//
// Usage: node sim/dump_dex.mjs [--generated DIR] > dump.json
import { join } from 'node:path';
import { FULL_RESTORE_MOVE, MOD, REPO_ROOT, GENERATED_DIR, loadGameData } from './gamedata.mjs';
import { Dex } from './showdown.mjs';

const argv = process.argv.slice(2);
const gi = argv.indexOf('--generated');
const dir = gi >= 0 ? argv[gi + 1] : GENERATED_DIR;
// A path that never exists: no patches are applied, so the dump shows unpatched Showdown data.
const NO_LEDGER = join(REPO_ROOT, 'data', '.no-ledger-for-dump_dex');

const gd = loadGameData({ dir, divergencesPath: NO_LEDGER });
if (gd.dexPatch.applied.length) throw new Error('dump_dex: patches were applied; dump would not be raw Showdown data');
const dex = Dex.mod(MOD);

const species = [];
for (const [key, name] of gd.sdSpecies) {
  const s = dex.species.get(name);
  species.push({
    decomp_key: key, id: s.id, name: s.name, num: s.num,
    baseStats: { ...s.baseStats }, types: [...s.types],
    abilities: [s.abilities['0'] ?? null, s.abilities['1'] ?? null],
  });
}

const moves = [];
for (const [key, id] of gd.sdMove) {
  if (id === FULL_RESTORE_MOVE) continue;
  const m = dex.moves.get(id);
  moves.push({
    decomp_key: key, id: m.id, name: m.name, num: m.num,
    basePower: m.basePower, accuracy: m.accuracy, pp: m.pp, priority: m.priority,
    type: m.type, category: m.category, target: m.target,
    flags: Object.keys(m.flags).filter((f) => m.flags[f]).sort(),
    secondaryChances: (m.secondaries ?? []).map((x) => x.chance ?? null),
    // How Showdown sets power at run time when basePower is 0 (variable-power/fixed-damage moves).
    powerHooks: ['basePowerCallback', 'damageCallback', 'damage', 'ohko', 'beforeMoveCallback',
      'onModifyMove', 'onPrepareHit'].filter((k) => m[k]),
    multihit: m.multihit ?? null,
  });
}

// Items with a battle effect: any event handler, Fling power, Natural Gift data, or a berry.
const items = [];
for (const [key, id] of gd.sdItem) {
  const it = dex.items.get(id);
  const handlers = Object.keys(it).filter((k) => /^on[A-Z]/.test(k) && typeof it[k] === 'function').sort();
  if (!handlers.length && !it.fling && !it.naturalGift && !it.isBerry) continue;
  items.push({
    decomp_key: key, id: it.id, name: it.name, num: it.num,
    flingPower: it.fling?.basePower ?? null,
    naturalGift: it.naturalGift ? { basePower: it.naturalGift.basePower, type: it.naturalGift.type } : null,
    isBerry: Boolean(it.isBerry), handlers,
  });
}

const out = {
  mod: MOD,
  generated_dir: dir,
  mapping: {
    unmapped: gd.unmapped, renamed: gd.renamed, num_mismatch: gd.numMismatch,
  },
  species, moves, items,
};
process.stdout.write(JSON.stringify(out) + '\n');
