// T048: 200 full League gauntlets with the game's trainer AI (`decomp-ai`) as the opponent and
// `greedy-v1` as the player. Asserts that no `ai_unimplemented` (or any other error) is reached,
// that the same seed gives a byte-identical result, and (positive controls) that the AI really
// made decisions of every kind and that another seed changes the result. Prints throughput.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { runGauntlet } from '../gauntlet.mjs';
import { AGGREGATE, DECOMP_AI } from '../ai/opponent.mjs';
import { B, gd } from './ai_fixtures.mjs';

const TEAM = [
  B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL', 'lucky_egg'),
  B('lucario', 56, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST'),
  B('gyarados', 56, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('alakazam', 56, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE', 'exp_share'),
  B('magnezone', 56, ['thunderbolt', 'flash_cannon', 'tri_attack', 'thunder_wave'], 'ABILITY_MAGNET_PULL'),
  B('roserade', 56, ['energy_ball', 'sludge_bomb', 'shadow_ball', 'extrasensory'], 'ABILITY_NATURAL_CURE'),
];
const N = 200;
const req = (i) => ({ team: TEAM, seed: `ai-gauntlet-${i}`, player_policy: 'greedy-v1', opponent_policy: DECOMP_AI,
  stop_on_loss: false, log: 'summary' });
const digest = (r) => createHash('sha256').update(JSON.stringify(r)).digest('hex');

test(`${N} full gauntlets with decomp-ai: no ai_unimplemented, deterministic per seed`, (t) => {
  const before = { ...AGGREGATE };
  const t0 = process.hrtime.bigint();
  const first = [];
  let battles = 0;
  let cleared = 0;
  for (let i = 0; i < N; i++) {
    const r = runGauntlet(gd, req(i)); // any AIUnimplemented (kind 'ai_unimplemented') throws here
    assert.equal(r.opponent_policy, DECOMP_AI);
    assert.equal(r.battles.length, 5);
    battles += r.battles.length;
    cleared += r.cleared ? 1 : 0;
    first.push(digest(r));
  }
  const seconds = Number(process.hrtime.bigint() - t0) / 1e9;
  const delta = Object.fromEntries(Object.entries(AGGREGATE).map(([k, v]) => [k, v - (before[k] ?? 0)]));
  t.diagnostic(`throughput: ${N} gauntlets (${battles} battles) in ${seconds.toFixed(1)} s = ${(N / seconds).toFixed(2)} gauntlets/s, one process`);
  t.diagnostic(`cleared ${cleared}/${N}; AI decisions ${JSON.stringify(delta)}`);
  // positive controls: the AI made move choices, post-KO replacements and used Full Restores
  assert.ok(delta.moves > 1000 && delta.replacements > 100 && delta.items > 50, JSON.stringify(delta));
  // same seeds again -> byte-identical results
  for (let i = 0; i < N; i++) assert.equal(digest(runGauntlet(gd, req(i))), first[i], `seed ${i} not reproducible`);
  // positive control: a different seed changes the result
  assert.notEqual(digest(runGauntlet(gd, { ...req(0), seed: 'ai-gauntlet-other' })), first[0]);
});
