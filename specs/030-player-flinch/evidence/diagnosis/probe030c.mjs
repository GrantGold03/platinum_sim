// Floatzel (B2) against Cynthia's Milotic: scores with flinch off / on, and the flinched states against their HP-equal twins.
import { B, gd, leagueBattle, sendIn } from '/home/grant/Desktop/platinum_sim/sim/test/ai_fixtures.mjs';
import { _internal, scoreActions, makeContext, V4_OPTS, EXPECTIMAX2_V4 } from '/home/grant/Desktop/platinum_sim/sim/policy/expectimax2.mjs';
const team = [
  B('floatzel', 51, ['waterfall', 'ice_punch', 'crunch', 'focus_blast'], 'ABILITY_SWIFT_SWIM', 'sitrus_berry'),
  B('garchomp', 52, ['earthquake', 'dragon_claw', 'rock_slide', 'crunch'], 'ABILITY_SAND_VEIL', 'sitrus_berry'),
  B('infernape', 50, ['fire_blast', 'flamethrower', 'close_combat', 'grass_knot'], 'ABILITY_BLAZE', 'expert_belt'),
  B('staraptor', 50, ['return', 'aerial_ace', 'pluck', 'close_combat'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('rotom', 50, ['thunderbolt', 'shadow_ball', 'charge_beam', 'thunder_shock'], 'ABILITY_LEVITATE', 'wise_glasses'),
  B('weavile', 53, ['ice_punch', 'night_slash', 'aerial_ace', 'brick_break'], 'ABILITY_PRESSURE', 'icicle_plate'),
];
function pos() {
  const x = leagueBattle('champion_cynthia', team);
  const mil = x.p2.pokemon.find((p) => p.species.id === 'milotic');
  x.battle.actions.switchIn(mil, 0);
  x.battle.makeRequest();
  return { gd, battle: x.battle, side: x.p1, request: x.p1.activeRequest, trainer: x.trainer };
}
for (const [name, opts] of [['off', { ...V4_OPTS, flinch: false }], ['on', V4_OPTS], ['defend', { ...V4_OPTS, flinch: 'defend' }]]) {
  const r = scoreActions(pos(), opts, EXPECTIMAX2_V4);
  console.log(name.padEnd(7), r.acts.slice(0, 4).map((a, i) => `${a.id}:${r.scores[i].toFixed(4)}`).join('  '));
}
const c = pos();
const X = makeContext(c, V4_OPTS, EXPECTIMAX2_V4); const S = X.root;
const me = S.sides[0].mons[S.sides[0].active], foe = S.sides[1].mons[S.sides[1].active];
const opp = _internal.predictOpponent(X, S, 'root', 4);
console.log('Milotic predicted:', opp.map((o) => `${o.p} ${o.act.id ?? o.act.kind}`).join(', '), '| hp', me.hp, foe.hp);
const wf = _internal.moveAct(X, me, 0);
for (const o of opp) {
  const out = _internal.resolveTurn(X, S, wf, o.act);
  const fl = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].hp === me.hp && b.S.sides[1].mons[b.S.sides[1].active].hp < foe.hp);
  const hit = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].hp < me.hp && b.S.sides[1].mons[b.S.sides[1].active].hp < foe.hp);
  for (const f of fl.slice(0, 2)) {
    const fh = f.S.sides[1].mons[f.S.sides[1].active].hp;
    const twin = hit.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === fh); if (!twin) continue;
    const T = _internal.cloneState(twin.S); T.sides[0].mons[T.sides[0].active].hp = me.hp;
    console.log(`  vs ${o.act.id}: flinched ${_internal.valuePly2(X, f.S).toFixed(4)}  twin(hit, Floatzel hp ${twin.S.sides[0].mons[twin.S.sides[0].active].hp}) ${_internal.valuePly2(X, twin.S).toFixed(4)}  twin with hp restored ${_internal.valuePly2(X, T).toFixed(4)}`);
  }
}
