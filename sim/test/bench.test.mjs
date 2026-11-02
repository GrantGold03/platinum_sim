// Feature 015: the benchmark tool's request set, digests and recording wrappers (contracts/bench-tool.md).
// Fast: one Aaron battle with greedy-v1. The full replay of the fixed set is sim/test/replay.test.mjs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { benchRequests, digestFull, digestLogs, diffRecorded, fixtureRecord, logLine, runBench, runRecorded } from '../bench.mjs';
import { INTERP_STATS } from '../ai/interp.mjs';
import { runGauntlet } from '../gauntlet.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { gd } from './ai_fixtures.mjs';

test('benchRequests: the default set is the spec\'s fixed set (40 requests, prof-a seeds, stop_on_loss off)', () => {
  const reqs = benchRequests();
  assert.equal(reqs.length, 40);
  assert.deepEqual(reqs.slice(0, 20).map((r) => r.seed), Array.from({ length: 20 }, (_, i) => `prof-a-bench-${i}`));
  assert.deepEqual(reqs.slice(20).map((r) => r.seed), Array.from({ length: 20 }, (_, i) => `prof-a-ref-${i}`));
  for (const r of reqs) {
    assert.equal(r.stop_on_loss, false);
    assert.equal(r.opponent_policy, DECOMP_AI);
    assert.equal(r.player_policy, 'expectimax2-v2');
    assert.ok(Array.isArray(r.team) && r.team.length === 6);
    assert.equal(r.trainers, undefined); // all five trainers = the gauntlet default
  }
  assert.notDeepEqual(reqs[0].team, reqs[20].team); // two different fixture teams
  assert.equal(benchRequests({ n: 1, teams: ['bench'], trainers: ['aaron'], policy: 'greedy-v1' })[0].trainers[0], 'aaron');
  assert.throws(() => benchRequests({ teams: ['nope'] }), /unknown bench team/);
});

// One digest vector shared with tests/integration/test_bench.py (the Python half must agree).
const VECTOR = [{
  seed: 'prof-a-bench-0', cleared: true, final_levels: [50, 51, 52, 53, 54, 55],
  battles: [{ trainer: 'aaron', end: 'win', turns: 12, log_hash: 'sha256:aa' }, { trainer: 'bertha', end: 'loss', turns: 7, log_hash: 'sha256:bb' }],
}];
const VECTOR_LINE = 'prof-a-bench-0|1|50,51,52,53,54,55|aaron:win:12:sha256:aa;bertha:loss:7:sha256:bb\n';

test('digestLogs: contract line format; one changed log_hash changes the digest (positive control)', () => {
  assert.equal(logLine(VECTOR[0], 'prof-a-bench-0'), VECTOR_LINE);
  const expected = createHash('sha256').update(VECTOR_LINE, 'utf8').digest('hex');
  assert.equal(digestLogs(VECTOR, ['prof-a-bench-0']), expected);
  assert.match(expected, /^[0-9a-f]{64}$/);
  const changed = structuredClone(VECTOR);
  changed[0].battles[1].log_hash = 'sha256:bc';
  assert.notEqual(digestLogs(changed, ['prof-a-bench-0']), expected);
  assert.equal(digestFull(['{"a":1}', '{"b":2}']), createHash('sha256').update('{"a":1}{"b":2}').digest('hex'));
});

test('runRecorded: result byte-identical to a plain run; choices and per-decision draw counts recorded', () => {
  const [req] = benchRequests({ n: 1, teams: ['bench'], trainers: ['aaron'], policy: 'greedy-v1' });
  const plain = runGauntlet(gd, req);
  const rr = runRecorded(gd, req);
  assert.equal(rr.json, JSON.stringify(plain));
  assert.equal(rr.result.player_policy, 'greedy-v1'); // the wrapper keeps the registered name
  assert.equal(rr.result.opponent_policy, DECOMP_AI);
  assert.ok(rr.choices.length > 0);
  assert.ok(rr.choices.every((c) => /^(move [1-4]|switch [1-6])$/.test(c)), rr.choices.join());
  assert.equal(rr.policy_ai_draws.length, rr.choices.length);
  assert.ok(rr.policy_ai_draws.every((d) => d === 0), 'greedy-v1 never runs the trainer AI');
  assert.ok(rr.live_ai_draws.length >= rr.choices.length - 1, `${rr.live_ai_draws.length} opponent decisions vs ${rr.choices.length} player decisions`);
  assert.ok(rr.live_ai_draws.some((d) => d > 0), 'positive control: the live AI drew random numbers');
  assert.ok(rr.live_ai_draws.every((d) => Number.isInteger(d) && d >= 0));
  const rec = fixtureRecord(req, 'bench', rr);
  assert.equal(rec.seed, 'prof-a-bench-0');
  assert.equal(rec.battles.length, 1);
  assert.equal(rec.battles[0][0], 'aaron');
  assert.equal(rec.battles[0][3], plain.battles[0].log_hash);
});

test('diffRecorded: identical records give no differences; one altered choice or draw count is reported', () => {
  const [req] = benchRequests({ n: 1, teams: ['bench'], trainers: ['aaron'], policy: 'greedy-v1' });
  const rr = runRecorded(gd, req);
  const entry = { digest_full: digestFull([rr.json]), digest_logs: digestLogs([rr.result], [req.seed]), gauntlets: [fixtureRecord(req, 'bench', rr)] };
  assert.deepEqual(diffRecorded(entry, structuredClone(entry)), []);
  const c = structuredClone(entry);
  c.gauntlets[0].choices[0] = c.gauntlets[0].choices[0] === 'move 1' ? 'move 2' : 'move 1';
  const d1 = diffRecorded(entry, c);
  assert.ok(d1.some((m) => /choices differs at index 0/.test(m)), d1.join('\n'));
  const d = structuredClone(entry);
  d.gauntlets[0].live_ai_draws[0] += 1;
  const d2 = diffRecorded(entry, d);
  assert.ok(d2.some((m) => /live_ai_draws differs at index 0/.test(m)), d2.join('\n'));
  const e = structuredClone(entry);
  e.digest_full = 'x';
  assert.ok(diffRecorded(entry, e).some((m) => /digest_full/.test(m)));
});

// Feature 017 (contracts/policy-and-bench.md): the report carries the interpreter step counters as deltas.
test('017 interpreter steps in the report: runBench reports INTERP_STATS deltas (one Aaron battle, expectimax2-v2)', () => {
  const s0 = INTERP_STATS.steps;
  const r = runBench(gd, { policy: 'expectimax2-v2', n: 1, teams: ['bench'], trainers: ['aaron'] });
  assert.ok(Number.isInteger(r.interp_steps), `interp_steps ${r.interp_steps}`);
  assert.ok(r.interp_steps > 0, 'the trainer AI ran script instructions');
  assert.equal(r.interp_steps, INTERP_STATS.steps - s0, 'the report is the delta over the run');
  assert.ok(Number.isInteger(r.interp_dispatches) && r.interp_dispatches >= 0, `interp_dispatches ${r.interp_dispatches}`);
  assert.ok(INTERP_STATS.steps > s0, 'positive control: the counter grew across the run');
});
