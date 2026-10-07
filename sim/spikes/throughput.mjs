// T008: battles/s for one Node process, gen4customgame, both sides choosing `default`.
// Usage: node sim/spikes/throughput.mjs [battles=500] [seedOffset=0]
import { Battle } from '../showdown.mjs';
import { loadTrainerTeam, seedFor } from './common.mjs';

const N = Number(process.argv[2] ?? 500);
const offset = Number(process.argv[3] ?? 0);

const cynthia = loadTrainerTeam('champion_cynthia');
// p1: Cynthia's own species/moves at a flat level 60, 15 IVs / 85 EVs (spec FR-008 defaults).
const p1Team = cynthia.map((m) => ({
  ...m,
  level: 60,
  ivs: { hp: 15, atk: 15, def: 15, spa: 15, spd: 15, spe: 15 },
  evs: { hp: 85, atk: 85, def: 85, spa: 85, spd: 85, spe: 85 },
}));

let turns = 0;
let p1Wins = 0;
const t0 = process.hrtime.bigint();
for (let i = 0; i < N; i++) {
  const battle = new Battle({
    formatid: 'gen4customgame',
    seed: seedFor(offset + i),
    p1: { name: 'Player', team: p1Team },
    p2: { name: 'Cynthia', team: cynthia },
  });
  while (!battle.ended) battle.makeChoices('default', 'default');
  turns += battle.turn;
  if (battle.winner === 'Player') p1Wins++;
}
const secs = Number(process.hrtime.bigint() - t0) / 1e9;
console.log(JSON.stringify({
  battles: N, seconds: +secs.toFixed(3), battlesPerSec: +(N / secs).toFixed(2),
  meanTurns: +(turns / N).toFixed(2), p1Wins,
}));
