// 007 T019: expectimax2-v3 state plumbing (weather, volatiles, side conditions) and the MODELLED table.
//  1. Round trip on a hand-set League position: weather, Leech Seed, a substitute, Taunt, Encore,
//     confusion, Spikes, Toxic Spikes, Stealth Rock, Safeguard and Wish set on the live battle are read
//     into the v3 root state and come back out of the shadow battle the AI reads, unchanged.
//     The live battle is not touched. Showdown's own fields are set directly (the same fields
//     sim/ai/adapter.mjs reads), not through Showdown's setters, so the test does not depend on a
//     setter's side effects.
//  2. During real gauntlets, the AI run on a v3 SHADOW of the current state chooses exactly what it
//     chooses on the live battle (same seeds). Positive control: setting rain in the shadow changes
//     the AI adapter's field-condition mask, so the shadow's weather is what the AI reads.
//  3. v1 / v2 states carry no v3 fields (their signature is unchanged; the golden test pins behaviour).
//  4. MODELLED lists exactly the effects statusMove handles for v1 / v2 (SELF_BOOSTS, FOE_DROPS,
//     STATUS_OF, HEAL_HALF, Protect, Rest, screens, Belly Drum, Yawn).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runGauntlet, PLAYER_POLICIES, registerPlayerPolicy } from '../gauntlet.mjs';
import { AIRng } from '../ai/choose.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { makeContext, _internal, MODELLED, V2_OPTS, V3_OPTS, EXPECTIMAX2_V3 } from '../policy/expectimax2.mjs';
import { gd, leagueBattle } from './ai_fixtures.mjs';

const REF = JSON.parse(readFileSync(new URL('../../tests/fixtures/reference_team.json', import.meta.url), 'utf8')).builds;
const TEAM = JSON.parse(readFileSync(new URL('../../tests/fixtures/policy_benchmark_team.json', import.meta.url), 'utf8')).team;
const key = (a) => `${a.kind}${a.slot ?? ''}${a.idx ?? ''}`;

function handSet() {
  const { battle, trainer } = leagueBattle('champion_cynthia', REF);
  const me = battle.sides[0].active[0], foe = battle.sides[1].active[0];
  battle.field.weather = 'raindance';
  battle.field.weatherState = { id: 'raindance', duration: 3 };
  me.volatiles.substitute = { id: 'substitute', hp: 41 };
  me.volatiles.encore = { id: 'encore', move: me.moveSlots[0].id, duration: 2 };
  foe.volatiles.leechseed = { id: 'leechseed', source: me };
  foe.volatiles.taunt = { id: 'taunt', duration: 2 };
  foe.volatiles.confusion = { id: 'confusion', time: 3, duration: 3 };
  battle.sides[1].sideConditions.spikes = { id: 'spikes', layers: 2 };
  battle.sides[1].sideConditions.toxicspikes = { id: 'toxicspikes', layers: 1 };
  battle.sides[1].sideConditions.stealthrock = { id: 'stealthrock' };
  battle.sides[0].sideConditions.safeguard = { id: 'safeguard', duration: 4 };
  battle.sides[0].slotConditions = [{ wish: { id: 'wish', duration: 1, hp: 120 } }];
  return { battle, trainer, me, foe };
}

test('v3 state: hand-set conditions round-trip through the root state and the shadow battle', () => {
  const { battle, trainer, me, foe } = handSet();
  const liveBefore = JSON.stringify([battle.field.weather, Object.keys(me.volatiles), Object.keys(foe.volatiles)]);
  const X = makeContext({ gd, battle, side: battle.sides[0], trainer }, V3_OPTS, EXPECTIMAX2_V3);
  const S = X.root;
  assert.equal(S.v3, true);
  assert.equal(S.weather, 'rain');
  assert.equal(S.weatherTurns, 3);
  const a = S.sides[0].mons[S.sides[0].active], o = S.sides[1].mons[S.sides[1].active];
  assert.deepEqual([a.subHp, a.encoreMove, a.encoreTurns], [41, me.moveSlots[0].id, 2]);
  assert.deepEqual([o.seeded, o.taunt, o.confusion], [1, 2, 3]);
  assert.deepEqual([S.sides[1].sc.spikes, S.sides[1].sc.tspikes, S.sides[1].sc.rocks], [2, 1, 1]);
  assert.deepEqual([S.sides[0].sc.safeguard, S.sides[0].sc.wish, S.sides[0].sc.wishHp], [4, 1, 120]);
  const sh = _internal.shadowBattle(X, _internal.cloneState(S));
  assert.equal(sh.field.weather, 'raindance');
  assert.equal(sh.field.weatherState.duration, 3);
  const sme = sh.sides[0].active[0], sfoe = sh.sides[1].active[0];
  assert.equal(sme.volatiles.substitute.hp, 41);
  assert.equal(sme.volatiles.encore.move, me.moveSlots[0].id);
  assert.equal(sfoe.volatiles.leechseed.source, sme); // the seeder is the shadow's own active mon
  assert.equal(sfoe.volatiles.taunt.duration, 2);
  assert.equal(sfoe.volatiles.confusion.duration, 3);
  assert.equal(sh.sides[1].sideConditions.spikes.layers, 2);
  assert.equal(sh.sides[1].sideConditions.toxicspikes.layers, 1);
  assert.ok(sh.sides[1].sideConditions.stealthrock);
  assert.equal(sh.sides[0].sideConditions.safeguard.duration, 4);
  assert.equal(sh.sides[0].slotConditions[0].wish.hp, 120);
  // the AI adapter sees the same masks on the shadow as on the live battle
  const live = createAdapter(battle, { aiSide: 'p2' }), shad = createAdapter(sh, { aiSide: 'p2' });
  assert.equal(shad.fieldConditionsMask(), live.fieldConditionsMask());
  assert.equal(shad.sideConditionsMask(0), live.sideConditionsMask(0));
  assert.equal(shad.sideConditionsMask(1), live.sideConditionsMask(1));
  // a changed model state shows up in the shadow (positive control)
  const T = _internal.cloneState(S);
  T.weather = ''; T.sides[1].sc.spikes = 0; T.sides[1].mons[T.sides[1].active].taunt = 0;
  const sh2 = _internal.shadowBattle(X, T);
  assert.equal(sh2.field.weather, '');
  assert.equal(sh2.sides[1].sideConditions.spikes, undefined);
  assert.equal(sh2.sides[1].active[0].volatiles.taunt, undefined);
  assert.notEqual(createAdapter(sh2, { aiSide: 'p2' }).fieldConditionsMask(), live.fieldConditionsMask());
  assert.notEqual(_internal.signature(T), _internal.signature(S));
  // the live battle was not written
  assert.equal(JSON.stringify([battle.field.weather, Object.keys(me.volatiles), Object.keys(foe.volatiles)]), liveBefore);
});

test('v1 / v2 root states carry no v3 fields', () => {
  const { battle, trainer } = handSet();
  const X = makeContext({ gd, battle, side: battle.sides[0], trainer }, V2_OPTS, 'expectimax2-v2');
  assert.equal(X.root.v3, undefined);
  assert.equal(X.root.weatherTurns, undefined);
  assert.equal(X.root.sides[1].sc.spikes, undefined);
  assert.ok(!_internal.signature(X.root).includes('|w'));
});

test('AI on a v3 shadow of the current state == AI on the live battle (same seeds)', (t) => {
  const inner = PLAYER_POLICIES.get('expectimax2-v2');
  let n = 0, agree = 0, controls = 0, changed = 0;
  const disagreements = [];
  registerPlayerPolicy({ name: 'shadow-probe-v3', choose(ctx) {
    if (ctx.request?.active && !ctx.request.forceSwitch && ctx.battle.p2.requestState === 'move') {
      const X = makeContext(ctx, V3_OPTS, EXPECTIMAX2_V3);
      const T = _internal.cloneState(X.root);
      const vSh = _internal.viewOf(X, T);
      for (let k = 0; k < 3; k++) {
        const a = _internal.aiDecide(X, X.root, X.rootView, new AIRng(91 + k));
        const b = _internal.aiDecide(X, T, vSh, new AIRng(91 + k));
        n++;
        if (key(a) === key(b)) agree++; else disagreements.push([ctx.battle.turn, key(a), key(b)]);
      }
      const R = _internal.cloneState(X.root);
      if (R.weather !== 'rain') {
        controls++;
        R.weather = 'rain'; R.weatherTurns = 5;
        if (_internal.viewOf(X, R).ai.fieldConditionsMask() !== X.rootView.ai.fieldConditionsMask()) changed++;
      }
    }
    return inner.choose(ctx);
  } });
  for (let i = 0; i < 2; i++) runGauntlet(gd, { team: TEAM, seed: `shadow-v3-${i}`, player_policy: 'shadow-probe-v3', opponent_policy: DECOMP_AI, stop_on_loss: false });
  t.diagnostic(`v3 shadow==live ${agree}/${n}; rain control changed the AI field mask in ${changed}/${controls}`);
  assert.ok(n > 100, `only ${n} comparisons`);
  assert.deepEqual(disagreements, []);
  assert.ok(controls > 10 && changed === controls, `control ${changed}/${controls}`);
});

test('MODELLED v1/v2 lists exactly the status effects statusMove handles', () => {
  const src = readFileSync(new URL('../policy/expectimax2.mjs', import.meta.url), 'utf8');
  const table = (name) => {
    const body = src.slice(src.indexOf(`const ${name} = {`));
    return [...body.slice(body.indexOf('{') + 1, body.indexOf('};')).matchAll(/(\w+): [{']/g)].map((m) => m[1]);
  };
  const heal = [...src.match(/const HEAL_HALF = new Set\(\[([^\]]*)\]\)/)[1].matchAll(/'(\w+)'/g)].map((m) => m[1]);
  const want = new Set([...table('SELF_BOOSTS'), ...table('FOE_DROPS'), ...table('STATUS_OF'), ...heal,
    'PROTECT', 'REST', 'SET_REFLECT', 'SET_LIGHT_SCREEN', 'MAX_ATK_LOSE_HALF_MAX_HP', 'STATUS_SLEEP_NEXT_TURN']);
  const got = new Set(MODELLED['expectimax2-v1'].effects);
  assert.deepEqual([...got].sort(), [...want].sort());
  assert.equal(MODELLED['expectimax2-v2'].extends, 'expectimax2-v1');
});
