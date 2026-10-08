// T051: determinism of the gauntlet for both player policies (Constitution IV) and FR-011.
//
//  1. The same gauntlet request run twice gives byte-identical output (JSON of the full result,
//     including the full Showdown logs), for `greedy-v1` and for `expectimax2-v1`; a different
//     seed changes the output (positive control).
//  2. Over 200 gauntlets per policy, every p1 choice is `move N` or `switch N`, never an item or
//     anything else (FR-011: no bag items).
//  3. The policy's look-ahead never touches the live battle: around every p1 choose() call the
//     battle PRNG seed, the real AI's RNG stream (state and draw count), the log length and every
//     Pokemon's hp / status / boosts / item / PP / volatiles are unchanged. A deliberately bad
//     policy that draws one number from the battle PRNG is caught by the same check (positive
//     control).
// The 200 expectimax2-v1 gauntlets run in worker threads (this file re-imports itself as the
// worker) so the test takes minutes, not tens of minutes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { cpus } from 'node:os';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { runGauntlet, PLAYER_POLICIES, registerPlayerPolicy } from '../gauntlet.mjs';
import { stateFor } from '../ai/opponent.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { gd } from './ai_fixtures.mjs';
import { readFileSync } from 'node:fs';

const FIXTURE = new URL('../../tests/fixtures/policy_benchmark_team.json', import.meta.url);
const TEAM = JSON.parse(readFileSync(FIXTURE, 'utf8')).team;
const POLICIES = ['greedy-v1', 'expectimax2-v1'];
const N = 200;
const digest = (r) => createHash('sha256').update(JSON.stringify(r)).digest('hex');
const req = (pol, seed, extra = {}) => ({ team: TEAM, seed, player_policy: pol, opponent_policy: DECOMP_AI, ...extra });

// Everything a policy could disturb in the live battle.
function fingerprint(battle) {
  const ai = stateFor(battle);
  return JSON.stringify({
    prng: battle.prng.getSeed(),
    ai: ai ? [ai.rng.state, ai.rng.draws, ai.speedRand, ai.logIndex] : null,
    log: battle.log.length,
    turn: battle.turn,
    mons: battle.sides.map((s) => s.pokemon.map((p) => [p.hp, p.status, p.statusState?.time, p.statusState?.stage, p.boosts, p.item,
      p.moveSlots.map((m) => m.pp), Object.keys(p.volatiles), p.isActive, p.lastMove?.id ?? null])),
    sc: battle.sides.map((s) => Object.keys(s.sideConditions)),
    weather: battle.field.weather,
  });
}

// Wraps a registered policy: records every choice and checks the fingerprint around choose().
function instrument(name) {
  const inner = PLAYER_POLICIES.get(name);
  const rec = { choices: 0, bad: [], disturbed: [] };
  const wrapped = {
    name: `${name}+probe`,
    choose(ctx) {
      const before = fingerprint(ctx.battle);
      const c = inner.choose(ctx);
      const after = fingerprint(ctx.battle);
      rec.choices++;
      if (!/^(move [1-4]|switch [1-6])$/.test(c)) rec.bad.push(c);
      if (before !== after) rec.disturbed.push({ turn: ctx.battle.turn, before, after });
      return c;
    },
    afterTurn: inner.afterTurn,
  };
  registerPlayerPolicy(wrapped);
  return { wrapped, rec };
}

function runChunk(pol, seeds) {
  const { wrapped, rec } = instrument(pol);
  let cleared = 0;
  for (const s of seeds) cleared += runGauntlet(gd, req(wrapped.name, s)).cleared ? 1 : 0;
  return { ...rec, cleared, gauntlets: seeds.length };
}

if (!isMainThread && workerData?.determinismWorker) {
  parentPort.postMessage(runChunk(workerData.pol, workerData.seeds));
} else {
  for (const pol of POLICIES) {
    test(`${pol}: same request twice is byte-identical; another seed differs`, () => {
      const r1 = runGauntlet(gd, req(pol, 'det-a', { stop_on_loss: false, log: 'full' }));
      const r2 = runGauntlet(gd, req(pol, 'det-a', { stop_on_loss: false, log: 'full' }));
      assert.equal(r1.player_policy, pol);
      assert.equal(JSON.stringify(r1), JSON.stringify(r2));
      const r3 = runGauntlet(gd, req(pol, 'det-b', { stop_on_loss: false, log: 'full' }));
      assert.notEqual(digest(r3), digest(r1)); // positive control
    });
  }

  test('positive control: a policy that draws from the battle PRNG is caught by the fingerprint', () => {
    const inner = PLAYER_POLICIES.get('greedy-v1');
    registerPlayerPolicy({ name: 'prng-thief', choose(ctx) { ctx.battle.prng.random(); return inner.choose(ctx); } });
    const { wrapped, rec } = instrument('prng-thief');
    runGauntlet(gd, req(wrapped.name, 'det-thief', { trainers: ['aaron'] }));
    assert.ok(rec.choices > 0 && rec.disturbed.length === rec.choices, `${rec.disturbed.length}/${rec.choices}`);
  });

  for (const pol of POLICIES) {
    test(`${pol}: ${N} gauntlets, every p1 choice is move/switch and the live battle is untouched`, async (t) => {
      const seeds = Array.from({ length: N }, (_, i) => `det-fr011-${i}`);
      const t0 = process.hrtime.bigint();
      let parts;
      if (pol === 'greedy-v1') {
        parts = [runChunk(pol, seeds)];
      } else {
        const W = Math.max(1, Math.min(16, cpus().length));
        const chunks = Array.from({ length: W }, (_, w) => seeds.filter((_, i) => i % W === w));
        parts = await Promise.all(chunks.map((c) => new Promise((resolve, reject) => {
          const wk = new Worker(new URL(import.meta.url), { workerData: { determinismWorker: true, pol, seeds: c } });
          wk.once('message', resolve);
          wk.once('error', reject);
        })));
      }
      const sec = Number(process.hrtime.bigint() - t0) / 1e9;
      const sum = (k) => parts.reduce((s, p) => s + (Array.isArray(p[k]) ? p[k].length : p[k]), 0);
      t.diagnostic(`${pol}: ${sum('gauntlets')} gauntlets, ${sum('choices')} p1 choices, cleared ${sum('cleared')}, ${sec.toFixed(1)} s`);
      assert.equal(sum('gauntlets'), N);
      assert.ok(sum('choices') > N * 5, 'positive control: the probe saw the choices');
      assert.deepEqual(parts.flatMap((p) => p.bad), []);
      assert.deepEqual(parts.flatMap((p) => p.disturbed), []);
    });
  }
}
