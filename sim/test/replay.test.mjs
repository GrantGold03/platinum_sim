// Feature 015 (FR-001, FR-002, FR-003, SC-001, SC-005): replay of the fixed set against the recorded fixture.
//
// For every policy in sim/test/replay_prof_a.json (expectimax2-v2 and expectimax2-v1), the 40 gauntlets of
// the fixed set (prof-a seeds, policy_benchmark_team and reference_team, all five trainers, stop_on_loss off)
// are run again and compared with the fixture: the full-result digest (the one recorded on `main`
// c751fb2 by the profiling harness, db6d20cf... for v2), the cross-language log digest, every player choice,
// and the trainer-AI draw count inside every decision (the policy's predictions and the live opponent AI).
// The 80 gauntlets run in worker threads (this file re-imports itself as the worker), like the determinism
// test. The fixture is re-recorded only when a decision change is intended: `node sim/bench.mjs --policy
// <name> --record sim/test/replay_prof_a.json`. A positive-control test shows the comparison catches a
// single altered choice or draw count.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cpus } from 'node:os';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { benchRequests, diffRecorded, digestFull, digestLogs, fixtureRecord, runRecorded } from '../bench.mjs';

const FIXTURE_URL = new URL('./replay_prof_a.json', import.meta.url);
const fixture = JSON.parse(readFileSync(FIXTURE_URL, 'utf8'));

function jobsFor(policy) {
  const set = fixture.set;
  const reqs = benchRequests({ block: set.block, n: set.n, teams: set.teams, trainers: set.trainers, policy });
  return reqs.map((req, i) => ({ policy, i, req, team: req.seed.split('-')[2] }));
}

function runJobs(jobs) {
  // Game data is loaded once per worker (the test fixture module does it on import).
  return import('./ai_fixtures.mjs').then(({ gd: data }) => jobs.map((j) => {
    const rr = runRecorded(data, j.req);
    const r = rr.result;
    return { policy: j.policy, i: j.i, json: rr.json, record: fixtureRecord(j.req, j.team, rr),
      logInput: { cleared: r.cleared, final_levels: r.final_levels, battles: r.battles.map((b) => ({ trainer: b.trainer, end: b.end, turns: b.turns, log_hash: b.log_hash })) },
      decisions: rr.choices.length };
  }));
}

if (!isMainThread && workerData?.replayWorker) {
  runJobs(workerData.jobs).then((out) => parentPort.postMessage(out));
} else {
  const policies = Object.keys(fixture.policies);

  test('fixture: both policies, the fixed set, the main digest for expectimax2-v2', () => {
    assert.deepEqual(policies.sort(), ['expectimax2-v1', 'expectimax2-v2', 'expectimax2-v4']); // 018: v4 entry added
    assert.equal(fixture.set.n, 20);
    assert.deepEqual(fixture.set.teams, ['bench', 'ref']);
    assert.equal(fixture.set.stop_on_loss, false);
    assert.equal(fixture.policies['expectimax2-v2'].digest_full, 'db6d20cf59008d32640358a6a143eb94d5102b46ebcc0d116f39c2856fd504d3');
    for (const p of policies) assert.equal(fixture.policies[p].gauntlets.length, 40);
  });

  test('positive control: an altered choice, draw count or digest is reported by the comparison', () => {
    const e = fixture.policies['expectimax2-v2'];
    const same = structuredClone(e);
    assert.deepEqual(diffRecorded(e, same), []);
    const a = structuredClone(e);
    a.gauntlets[3].choices[5] = a.gauntlets[3].choices[5] === 'move 1' ? 'move 2' : 'move 1';
    assert.ok(diffRecorded(e, a).some((m) => /prof-a-bench-3 choices differs at index 5/.test(m)));
    const b = structuredClone(e);
    b.gauntlets[25].policy_ai_draws[0] += 1;
    assert.ok(diffRecorded(e, b).some((m) => /prof-a-ref-5 policy_ai_draws differs at index 0/.test(m)));
    const c = structuredClone(e);
    c.gauntlets[0].live_ai_draws[2] -= 1;
    assert.ok(diffRecorded(e, c).some((m) => /live_ai_draws differs at index 2/.test(m)));
  });

  test(`replay: ${policies.length} policies x 40 gauntlets reproduce the fixture (digests, choices, AI draws per decision)`, async (t) => {
    const jobs = policies.flatMap(jobsFor);
    const W = Math.max(1, Math.min(16, cpus().length));
    const chunks = Array.from({ length: W }, (_, w) => jobs.filter((_, k) => k % W === w)).filter((c) => c.length);
    const t0 = process.hrtime.bigint();
    const parts = await Promise.all(chunks.map((c) => new Promise((resolve, reject) => {
      const wk = new Worker(new URL(import.meta.url), { workerData: { replayWorker: true, jobs: c } });
      wk.once('message', resolve);
      wk.once('error', reject);
    })));
    const sec = Number(process.hrtime.bigint() - t0) / 1e9;
    const outs = parts.flat();
    let decisions = 0;
    const failures = [];
    for (const policy of policies) {
      const mine = outs.filter((o) => o.policy === policy).sort((x, y) => x.i - y.i);
      assert.equal(mine.length, 40, `${policy}: ${mine.length} gauntlets came back`);
      decisions += mine.reduce((s, o) => s + o.decisions, 0);
      const actual = {
        digest_full: digestFull(mine.map((o) => o.json)),
        digest_logs: digestLogs(mine.map((o) => o.logInput), mine.map((o) => o.record.seed)),
        gauntlets: mine.map((o) => o.record),
      };
      for (const m of diffRecorded(fixture.policies[policy], actual)) failures.push(`${policy}: ${m}`);
    }
    t.diagnostic(`replay: ${outs.length} gauntlets, ${decisions} player decisions, ${W} workers, ${sec.toFixed(1)} s`);
    assert.ok(decisions > 5000, 'positive control: the recorders saw the decisions');
    assert.deepEqual(failures, []);
  });
}
