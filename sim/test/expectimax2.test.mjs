// T050: expectimax2-v1 checks.
//  1. Hypothetical-state model vs live battle: at real p1 decision points the game AI run on a
//     SHADOW copy of the current state (the path ply 2 uses) chooses exactly what it chooses on
//     the live battle through the live adapter, for the same RNG seeds. Positive control: on a
//     shadow whose opponent active is at 1 HP the AI's choice changes (Full Restore / switch), so
//     the shadow's modelled fields are really what the AI reads.
//  2. Plumbing on a hand-built position: every legal action gets a finite score and the policy
//     picks the super-effective KO move.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runGauntlet, PLAYER_POLICIES, registerPlayerPolicy } from '../gauntlet.mjs';
import { AIRng } from '../ai/choose.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { expectimax2, makeContext, scoreActions, _internal } from '../policy/expectimax2.mjs';
import { B, gd, leagueBattle } from './ai_fixtures.mjs';

const TEAM = JSON.parse(readFileSync(new URL('../../tests/fixtures/policy_benchmark_team.json', import.meta.url), 'utf8')).team;
const key = (a) => `${a.kind}${a.slot ?? ''}${a.idx ?? ''}`;

test('AI on a shadow of the current state == AI on the live battle (same seeds)', (t) => {
  const inner = PLAYER_POLICIES.get('expectimax2-v1');
  let n = 0, agree = 0, changed = 0, controls = 0;
  const disagreements = [];
  registerPlayerPolicy({ name: 'shadow-probe', choose(ctx) {
    if (ctx.request?.active && !ctx.request.forceSwitch && ctx.battle.p2.requestState === 'move') {
      const X = makeContext(ctx);
      const T = _internal.cloneState(X.root);
      const vSh = _internal.viewOf(X, T);
      for (let k = 0; k < 4; k++) {
        const a = _internal.aiDecide(X, X.root, X.rootView, new AIRng(77 + k));
        const b = _internal.aiDecide(X, T, vSh, new AIRng(77 + k));
        n++;
        if (key(a) === key(b)) agree++; else disagreements.push([ctx.battle.turn, key(a), key(b)]);
      }
      // positive control: opponent active at 1 HP in the shadow
      const L = _internal.cloneState(X.root);
      const o = L.sides[1].mons[L.sides[1].active];
      if (o.hp > 1 && L.items.trainerItems.some((x) => x)) {
        controls++;
        o.hp = 1;
        const c = _internal.aiDecide(X, L, _internal.viewOf(X, L), new AIRng(77));
        const r = _internal.aiDecide(X, X.root, X.rootView, new AIRng(77));
        if (key(c) !== key(r)) changed++;
      }
    }
    return inner.choose(ctx);
  } });
  for (let i = 0; i < 2; i++) runGauntlet(gd, { team: TEAM, seed: `shadow-${i}`, player_policy: 'shadow-probe', opponent_policy: DECOMP_AI, stop_on_loss: false });
  t.diagnostic(`shadow==live ${agree}/${n}; 1-HP control changed the AI choice in ${changed}/${controls} positions`);
  assert.ok(n > 100, `only ${n} comparisons`);
  assert.deepEqual(disagreements, []);
  assert.equal(agree, n);
  assert.ok(controls > 10 && changed > controls / 2, `control changed ${changed}/${controls}`);
});

test('hand position: finite scores for every action; the super-effective move is chosen', () => {
  // Aaron's lead is Yanmega (Bug/Flying, res/trainers/data/elite_four_aaron.json:16).
  const { battle, trainer, p1 } = leagueBattle('elite_four_aaron', [
    B('infernape', 60, ['close_combat', 'flame_wheel', 'mach_punch', 'taunt'], 'ABILITY_BLAZE'),
    B('luxray', 60, ['thunder_fang', 'crunch', 'spark', 'scary_face'], 'ABILITY_INTIMIDATE'),
  ]);
  const ctx = { gd, battle, side: p1, request: p1.activeRequest, trainer };
  const { acts, scores, opp } = scoreActions(ctx);
  assert.deepEqual(acts.map((a) => a.choice), ['move 1', 'move 2', 'move 3', 'move 4', 'switch 2']);
  assert.ok(scores.every(Number.isFinite), JSON.stringify(scores));
  assert.ok(opp.length >= 1 && Math.abs(opp.reduce((s, x) => s + x.p, 0) - 1) < 1e-9);
  // Flame Wheel (Fire) is 2x on Bug/Flying; Close Combat and Mach Punch (Fighting) are 0.25x.
  assert.equal(expectimax2.choose(ctx), 'move 2');
  assert.ok(scores[1] > scores[0] && scores[1] > scores[2], JSON.stringify(scores));
});
