// T050: expectimax2-v1 checks (1-2); expectimax2-v2 checks at the end.
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
import { expectimax2, makeContext, scoreActions, _internal, PARAMS, V1_OPTS, V2_OPTS } from '../policy/expectimax2.mjs';
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

// expectimax2-v2 (VERSIONS / HORIZON in sim/policy/expectimax2.mjs). The position is the start of
// the measured switch loop on the smoke-run finalist: Cynthia's Spiritomb (lead) at 65/143 HP vs our
// Infernape at 71/179; Flamethrower (Flame Plate) KOs Spiritomb in most rolls and Infernape moves
// first. v1 delays the KO (switches out: the replacement's turn would be inside its horizon); v2 takes
// the KO with a Fire move. The v1 half is the positive control that the position shows the bug.
function spiritombPosition() {
  const { battle, trainer, p1, p2 } = leagueBattle('champion_cynthia', [
    B('infernape', 59, ['fire_blast', 'flamethrower', 'close_combat', 'fire_punch'], 'ABILITY_BLAZE', 'flame_plate'),
    B('staraptor', 58, ['brave_bird', 'pluck', 'wing_attack', 'close_combat'], 'ABILITY_INTIMIDATE', 'sky_plate'),
    B('luxray', 58, ['thunderbolt', 'ice_fang', 'crunch', 'fire_fang'], 'ABILITY_RIVALRY', 'zap_plate'),
    B('garchomp', 59, ['earthquake', 'dragon_claw', 'stone_edge', 'aerial_ace'], 'ABILITY_SAND_VEIL', 'sitrus_berry'),
    B('gyarados', 58, ['aqua_tail', 'waterfall', 'ice_fang', 'strength'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
    B('gardevoir', 58, ['psychic', 'shadow_ball', 'magical_leaf', 'ice_punch'], 'ABILITY_SYNCHRONIZE', 'mind_plate'),
  ]);
  assert.equal(p2.active[0].species.id, 'spiritomb');
  p1.active[0].hp = 71;
  p2.active[0].hp = 65;
  battle.makeRequest();
  return { gd, battle, side: p1, request: p1.activeRequest, trainer };
}

test('v2 takes the KO that v1 delays by switching (horizon fix); v1 still switches (control)', () => {
  const v1 = PLAYER_POLICIES.get('expectimax2-v1');
  const v2 = PLAYER_POLICIES.get('expectimax2-v2');
  assert.ok(v1 && v2 && v1 !== v2);
  const c1 = v1.choose(spiritombPosition());
  const c2 = v2.choose(spiritombPosition());
  assert.match(c1, /^switch /, `v1 chose ${c1}`);
  const ctx = spiritombPosition();
  const fire = new Set(['fireblast', 'flamethrower', 'firepunch']);
  const slot = Number(c2.split(' ')[1]) - 1;
  assert.ok(c2.startsWith('move ') && fire.has(ctx.side.active[0].moveSlots[slot].id), `v2 chose ${c2}`);
});

test('v2 options: koStop and the fitted leaf weights; v1 options are the recorded ones', () => {
  assert.deepEqual({ ...V1_OPTS }, { koStop: false });
  assert.deepEqual({ ...V2_OPTS }, { koStop: true, wAlive: 0.25, wFR: 0.1 });
  assert.equal(PARAMS.W_ALIVE, 1.0); // v1's weight, used when an option is absent
  assert.equal(PARAMS.W_FR, 0.45);
});
