// T035: gauntlet op behaviour (contracts/worker-protocol.md ops 2 and 4) with the
// `placeholder-default` policies on both sides (NOT the game AI, NOT a player policy).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGameData } from '../gamedata.mjs';
import { PLACEHOLDER, runGauntlet, playerPolicyFor, RequestError } from '../gauntlet.mjs';
import { loadTeam } from '../bench.mjs';
import { V4_OPTS } from '../policy/expectimax2.mjs';

const gd = loadGameData();
const B = (species, level, moves, ability, held_item = null) => ({ species, start_level: level, moves, ability, held_item, nature: 'Hardy' });
const TEAM = [
  B('garchomp', 62, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL', 'lucky_egg'),
  B('lucario', 60, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST'),
  B('gyarados', 60, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('alakazam', 60, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE', 'exp_share'),
  B('magnezone', 60, ['thunderbolt', 'flash_cannon', 'tri_attack', 'thunder_wave'], 'ABILITY_MAGNET_PULL'),
  B('roserade', 60, ['energy_ball', 'sludge_bomb', 'shadow_ball', 'extrasensory'], 'ABILITY_NATURAL_CURE'),
];
const req = (o = {}) => ({ team: TEAM, seed: 'sodium,' + 'a'.repeat(32), log: 'summary', stop_on_loss: false, opponent_policy: PLACEHOLDER, ...o });

test('deterministic: same request -> byte-identical result; other seed differs (positive control)', () => {
  const a = JSON.stringify(runGauntlet(gd, req()));
  const b = JSON.stringify(runGauntlet(gd, req()));
  assert.equal(a, b);
  const c = JSON.stringify(runGauntlet(gd, req({ seed: 'sodium,' + 'b'.repeat(32) })));
  assert.notEqual(a, c);
});

test('result shape, placeholder policies named, levels/exp/PP carry over', () => {
  const r = runGauntlet(gd, req());
  assert.equal(r.player_policy, PLACEHOLDER);
  assert.equal(r.opponent_policy, PLACEHOLDER);
  assert.equal(r.battles.length, 5);
  assert.deepEqual(r.battles.map((x) => x.trainer), ['aaron', 'bertha', 'flint', 'lucian', 'cynthia']);
  assert.equal(r.pp_restore_between_battles, false);
  for (let i = 1; i < r.battles.length; i++) {
    const prev = r.battles[i - 1].state_before;
    const cur = r.battles[i].state_before;
    for (let s = 0; s < 6; s++) {
      assert.ok(cur.exp[s] >= prev.exp[s]);
      assert.ok(cur.levels[s] >= prev.levels[s]);
      cur.pp[s].forEach((pp, j) => assert.ok(pp <= prev.pp[s][j], 'PP never refills (FR-012)'));
    }
  }
  // PP was actually spent somewhere (positive control for the carry-over check above)
  const first = r.battles[0].state_before.pp.flat().reduce((a, b) => a + b);
  const last = r.final_state.pp.flat().reduce((a, b) => a + b);
  assert.ok(last < first);
  assert.ok(r.exp_events.length > 0);
  assert.equal(r.final_levels.length, 6);
});

test('start_state resumes from a recorded state (op 4)', () => {
  const full = runGauntlet(gd, req());
  const st = full.battles[4].state_before;
  const seed = full.battles[4].seed;
  const top = runGauntlet(gd, req({ trainers: ['cynthia'], start_state: st, seeds: [seed] }));
  assert.equal(top.battles.length, 1);
  assert.deepEqual(top.battles[0].state_before, st);
  // same state + same seed -> the same Cynthia battle as in the full run
  assert.equal(top.battles[0].log_hash, full.battles[4].log_hash);
  assert.equal(top.battles[0].won, full.battles[4].won);
});

test('stop_on_loss stops at the first loss; a turn limit counts as a loss', () => {
  const r = runGauntlet(gd, req({ stop_on_loss: true, turn_limit: 1 }));
  assert.equal(r.battles.length, 1);
  assert.equal(r.battles[0].end, 'turn_limit');
  assert.equal(r.battles[0].won, false);
  assert.equal(r.cleared, false);
});

test('pp_restore_between_battles from availability data restores PP', () => {
  const saved = gd.availability;
  try {
    gd.availability = { pp_restore_between_battles: true };
    const r = runGauntlet(gd, req());
    assert.equal(r.pp_restore_between_battles, true);
    const base = r.battles[0].state_before.pp;
    for (const b of r.battles) assert.deepEqual(b.state_before.pp, base);
  } finally {
    gd.availability = saved;
  }
});

test('invalid team and unknown policy are reported with the contract error kinds', () => {
  assert.throws(() => runGauntlet(gd, req({ team: [B('notamon', 50, ['tackle'], 'ABILITY_NONE')] })), (e) => e.kind === 'invalid_team');
  assert.throws(() => runGauntlet(gd, req({ player_policy: 'no-such-policy-v0' })), (e) => e.kind === 'internal' && /unknown player_policy/.test(e.message));
});

// Feature 018 (contracts/policy-api.md "playerPolicyFor"): candidate names carry their knobs and seed from the base name.
test('018 candidate policy names: resolve and cache, reject bad ones, and equal the plain name with the same knobs', () => {
  assert.equal(playerPolicyFor('expectimax2-v2').name, 'expectimax2-v2');
  const full = `expectimax2-v4?kRoot=${V4_OPTS.kRoot}&kPly2=${V4_OPTS.kPly2}&beam=${V4_OPTS.beam}&floor=${V4_OPTS.floor}`;
  const c1 = playerPolicyFor(full);
  assert.equal(c1.name, full);
  assert.equal(playerPolicyFor(full), c1, 'cached');
  const invalid = (e) => e instanceof RequestError && e.kind === 'invalid_policy';
  for (const bad of ['expectimax2-v4?', 'expectimax2-v4?bogus=1', 'expectimax2-v4?kRoot=0', 'expectimax2-v4?kRoot=33',
    'expectimax2-v4?beam=6', 'expectimax2-v4?floor=0.6', 'expectimax2-v4?floor=-0.1', 'expectimax2-v4?kPly2=1&kPly2=2', 'expectimax2-v4?kPly2=x']) {
    assert.throws(() => playerPolicyFor(bad), invalid, bad);
  }
  assert.throws(() => playerPolicyFor('nope'), (e) => e instanceof RequestError && /unknown player_policy/.test(e.message));
  const team = loadTeam('bench');
  const run = (pol, i) => runGauntlet(gd, { team, seed: `prof-a-bench-${i}`, player_policy: pol, opponent_policy: 'decomp-ai', stop_on_loss: false, trainers: ['aaron'] });
  const strip = (r) => { const { player_policy, ...rest } = r; return JSON.stringify(rest); };
  let differs = 0;
  for (const i of [0, 1]) {
    const plain = run('expectimax2-v4', i), cand = run(full, i);
    assert.equal(plain.player_policy, 'expectimax2-v4');
    assert.equal(cand.player_policy, full, 'the result names the full candidate');
    assert.equal(strip(cand), strip(plain), `seed ${i}: a candidate with V4_OPTS's knobs equals the plain name (shared seeding)`);
    const other = run(`expectimax2-v4?kRoot=${V4_OPTS.kRoot}&kPly2=${V4_OPTS.kPly2 + 1}&beam=${V4_OPTS.beam}&floor=${V4_OPTS.floor}`, i);
    if (strip(other) !== strip(plain)) differs++;
  }
  assert.ok(differs >= 1, 'positive control: a different knob changes at least one of the two gauntlets');
  assert.throws(() => run('expectimax2-v4?kRoot=0', 0), invalid, 'an invalid candidate is a request error, not a crash');
});
