// sim/version.mjs: the code fingerprint reported as `sim_code_hash` in the worker hello.
// (Change detection on a modified copy of the tree is tested from Python: tests/unit/test_version.py.)
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { simCodeFiles, simCodeHash } from '../version.mjs';

test('sim code file set: *.mjs + package.json, no tests or spikes', () => {
  const rels = simCodeFiles().map(([r]) => r);
  for (const r of ['sim/worker.mjs', 'sim/version.mjs', 'sim/package.json', 'sim/ai/interp.mjs', 'sim/policy/greedy.mjs']) {
    assert.ok(rels.includes(r), r);
  }
  assert.ok(rels.every((r) => (r.endsWith('.mjs') || r.endsWith('/package.json'))
    && !r.startsWith('sim/test/') && !r.startsWith('sim/spikes/')));
  assert.deepEqual(rels, [...rels].sort());
});

test('sim code hash is stable and well formed', () => {
  const a = simCodeHash();
  assert.match(a, /^sha256:[0-9a-f]{64}$/);
  assert.equal(simCodeHash(), a);
});
