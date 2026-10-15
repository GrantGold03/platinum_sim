// 007 T004: golden battle logs for the existing player policies (Constitution IV: earlier results
// must reproduce). expectimax2-v3 is added in the same file as v1/v2 (sim/policy/expectimax2.mjs),
// so every v3 change must leave v1, v2 and greedy-v1 byte-identical. The per-battle log hashes were
// recorded on the 007 branch before any sim/ edit (code equal to main f88cdd0).
//
// Re-record (only when a change to v1/v2 behaviour is intended and approved):
//   GOLDEN_RECORD=1 node --test sim/test/golden_v1_v2.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { runGauntlet } from '../gauntlet.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { gd } from './ai_fixtures.mjs';

const FIXTURE = new URL('./fixtures/golden_v1_v2.json', import.meta.url);
const TEAMS = {
  policy_benchmark: JSON.parse(readFileSync(new URL('../../tests/fixtures/policy_benchmark_team.json', import.meta.url), 'utf8')).team,
  reference_b1: JSON.parse(readFileSync(new URL('../../tests/fixtures/reference_team.json', import.meta.url), 'utf8')).builds,
};
const POLICIES = ['greedy-v1', 'expectimax2-v1', 'expectimax2-v2'];
const SEEDS = Array.from({ length: 20 }, (_, i) => `golden-007|${i}`);

export function goldenRun(team, pol, seed) {
  const r = runGauntlet(gd, { team, seed, player_policy: pol, opponent_policy: DECOMP_AI, stop_on_loss: false });
  return { cleared: r.cleared, battles: r.battles.map((b) => [b.trainer, b.won, b.turns, b.log_hash]) };
}

function recordAll() {
  const out = {};
  for (const [tk, team] of Object.entries(TEAMS)) for (const pol of POLICIES) for (const s of SEEDS) {
    out[`${tk}|${pol}|${s}`] = goldenRun(team, pol, s);
  }
  return out;
}

if (process.env.GOLDEN_RECORD === '1') {
  writeFileSync(FIXTURE, JSON.stringify(recordAll(), null, 1) + '\n');
}

test('golden: greedy-v1, expectimax2-v1 and -v2 battle logs are unchanged', () => {
  assert.ok(existsSync(FIXTURE), 'golden fixture missing: record it with GOLDEN_RECORD=1');
  const golden = JSON.parse(readFileSync(FIXTURE, 'utf8'));
  assert.equal(Object.keys(golden).length, Object.keys(TEAMS).length * POLICIES.length * SEEDS.length);
  for (const [k, want] of Object.entries(golden)) {
    const [tk, pol, ...seed] = k.split('|');
    assert.deepEqual(goldenRun(TEAMS[tk], pol, seed.join('|')), want, `golden mismatch for ${k}`);
  }
});
