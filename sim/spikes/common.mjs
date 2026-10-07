// Shared helpers for the Phase 2a spikes (T008–T010). Spike code only, not the real worker.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
export const DECOMP = join(here, '../../pokeplatinum');

// "SPECIES_DRAGON_RUSH" -> "dragonrush" (Showdown id). Spike-grade mapping only.
const toId = (constant) => constant.replace(/^(SPECIES|MOVE|ITEM)_/, '').toLowerCase().replace(/[^a-z0-9]/g, '');

// Reads a first-run trainer party from pokeplatinum/res/trainers/data/<key>.json.
// IVs = iv_scale*31/255 (pokeplatinum/src/trainer_data.c), EVs 0. Nature/ability left at
// Showdown defaults here; the real converter (T034) computes them from personality.
export function loadTrainerTeam(key) {
  const data = JSON.parse(readFileSync(join(DECOMP, 'res/trainers/data', `${key}.json`), 'utf8'));
  return data.party.map((mon) => {
    const iv = Math.floor((mon.iv_scale * 31) / 255);
    return {
      species: toId(mon.species),
      level: mon.level,
      item: mon.item === 'ITEM_NONE' ? '' : toId(mon.item),
      moves: mon.moves.filter((m) => m !== 'MOVE_NONE').map(toId),
      ability: '0',
      nature: 'Serious',
      ivs: { hp: iv, atk: iv, def: iv, spa: iv, spd: iv, spe: iv },
      evs: { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    };
  });
}

export const seedFor = (n) => `sodium,${n.toString(16).padStart(32, '0')}`;
