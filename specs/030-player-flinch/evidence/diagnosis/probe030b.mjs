import { B, gd, leagueBattle } from '/home/grant/Desktop/platinum_sim/sim/test/ai_fixtures.mjs';
import { _internal, makeContext, V4_OPTS, EXPECTIMAX2_V4 } from '/home/grant/Desktop/platinum_sim/sim/policy/expectimax2.mjs';
const { battle, trainer, p1 } = leagueBattle('champion_cynthia', [
  B('garchomp', 52, ['earthquake', 'dragon_claw', 'rock_slide', 'crunch'], 'ABILITY_SAND_VEIL', 'sitrus_berry'),
  B('infernape', 50, ['fire_blast', 'flamethrower', 'close_combat', 'grass_knot'], 'ABILITY_BLAZE', 'expert_belt'),
  B('staraptor', 50, ['return', 'aerial_ace', 'pluck', 'close_combat'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('rotom', 50, ['thunderbolt', 'shadow_ball', 'charge_beam', 'thunder_shock'], 'ABILITY_LEVITATE', 'wise_glasses'),
  B('floatzel', 51, ['waterfall', 'ice_punch', 'crunch', 'focus_blast'], 'ABILITY_SWIFT_SWIM', 'sitrus_berry'),
  B('weavile', 53, ['ice_punch', 'night_slash', 'aerial_ace', 'brick_break'], 'ABILITY_PRESSURE', 'icicle_plate'),
]);
battle.makeRequest();
const X = makeContext({ gd, battle, side: p1, trainer }, V4_OPTS, EXPECTIMAX2_V4);
const S = X.root;
const me = S.sides[0].mons[S.sides[0].active], foe = S.sides[1].mons[S.sides[1].active];
const opp = _internal.predictOpponent(X, S, 'root', 4);
console.log('predicted foe actions', opp.map((o) => `${o.p} ${o.act.kind} ${o.act.id ?? ''}`));
const rs = _internal.moveAct(X, me, 2);
for (const o of opp) {
  const out = _internal.resolveTurn(X, S, rs, o.act);
  let tot = 0, flinchP = 0, flinchV = 0, restV = 0, restP = 0;
  for (const b of out) {
    const g = b.S.sides[0].mons[b.S.sides[0].active], f = b.S.sides[1].mons[b.S.sides[1].active];
    const v = _internal.valuePly2(X, b.S);
    const fl = g.hp === me.hp && f.hp < foe.hp; // Garchomp untouched, Spiritomb hit: the flinched branches
    if (fl) { flinchP += b.p; flinchV += b.p * v; } else { restP += b.p; restV += b.p * v; }
    tot += b.p;
  }
  console.log(`foe ${o.act.id}: branches ${out.length}, flinched mass ${flinchP.toFixed(3)} mean value ${(flinchV / flinchP).toFixed(4)}; rest mass ${restP.toFixed(3)} mean value ${(restV / restP).toFixed(4)}`);
}
console.log('Garchomp hp', me.hp, '/', me.maxhp, 'Spiritomb hp', foe.hp, '/', foe.maxhp);
// control: a hit-but-not-flinched branch with Garchomp's HP restored, against the flinched branch with the same Spiritomb HP
const out = _internal.resolveTurn(X, S, rs, opp[1].act);
const hitRest = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].hp < me.hp && b.S.sides[1].mons[b.S.sides[1].active].hp < foe.hp);
const flinched = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].hp === me.hp && b.S.sides[1].mons[b.S.sides[1].active].hp < foe.hp);
for (const f of flinched) {
  const fh = f.S.sides[1].mons[f.S.sides[1].active].hp;
  const twin = hitRest.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === fh);
  if (!twin) continue;
  const g = twin.S.sides[0].mons[twin.S.sides[0].active];
  const T2 = _internal.cloneState(twin.S); const g2 = T2.sides[0].mons[T2.sides[0].active]; g2.hp = me.hp;
  const diffKeys = (a, b) => Object.keys(a).filter((k) => typeof a[k] !== 'object' && a[k] !== b[k]);
  const fm = f.S.sides[0].mons[f.S.sides[0].active], tm = T2.sides[0].mons[T2.sides[0].active];
  const ff = f.S.sides[1].mons[f.S.sides[1].active], tf = T2.sides[1].mons[T2.sides[1].active];
  console.log(`Spiritomb hp ${fh}: flinched ${_internal.valuePly2(X, f.S).toFixed(4)}; hit twin (Garchomp hp ${g.hp}) ${_internal.valuePly2(X, twin.S).toFixed(4)}; twin with Garchomp hp restored ${_internal.valuePly2(X, T2).toFixed(4)}`);
  console.log('   my-side fields differing', diffKeys(fm, tm), 'foe fields differing', diffKeys(ff, tf), 'taken', JSON.stringify(f.S.taken), JSON.stringify(T2.taken), 'moveHit', JSON.stringify(f.S.moveHit), JSON.stringify(T2.moveHit));
}
{
  const f = flinched.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103);
  const twin = hitRest.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103);
  const mk = (lastOk, moveHitFrom) => { const T = _internal.cloneState(twin.S); T.sides[0].mons[T.sides[0].active].hp = me.hp;
    T.sides[1].mons[T.sides[1].active].lastMoveOk = lastOk; if (moveHitFrom) { T.moveHit = moveHitFrom.moveHit.slice(); T.moveHitBattler = moveHitFrom.moveHitBattler.slice(); } return T; };
  console.log('twin restored, lastMoveOk false only:', _internal.valuePly2(X, mk(false, null)).toFixed(4));
  console.log('twin restored, moveHit as flinched only:', _internal.valuePly2(X, mk(true, f.S)).toFixed(4));
  console.log('twin restored, both:', _internal.valuePly2(X, mk(false, f.S)).toFixed(4), '| flinched', _internal.valuePly2(X, f.S).toFixed(4));
  const pf = _internal.predictOpponent(X, f.S, 'p2', 4), pt = _internal.predictOpponent(X, mk(true, null), 'p2', 4);
  console.log('ply-2 AI prediction after flinch:', pf.map((o) => `${o.p} ${o.act.kind} ${o.act.id ?? o.act.idx ?? ''}`), '| after twin:', pt.map((o) => `${o.p} ${o.act.kind} ${o.act.id ?? o.act.idx ?? ''}`));
}
{
  const f = flinched.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103).S;
  const t = _internal.cloneState(hitRest.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103).S);
  t.sides[0].mons[t.sides[0].active].hp = me.hp;
  const seen = new WeakSet();
  const walk = (a, b, path) => {
    if (a === b) return;
    if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) { console.log('  diff', path, JSON.stringify(a)?.slice(0, 80), '|', JSON.stringify(b)?.slice(0, 80)); return; }
    if (seen.has(a)) return; seen.add(a);
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) { if (k === 'ref') continue; walk(a[k], b[k], path + '.' + k); }
  };
  walk(f, t, 'S');
}
{
  const base = hitRest.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103).S;
  const f = flinched.find((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === 103).S;
  const mk = (fn) => { const T = _internal.cloneState(base); T.sides[0].mons[T.sides[0].active].hp = me.hp; fn(T); return T; };
  const show = (name, T) => console.log(name.padEnd(28), _internal.valuePly2(X, T).toFixed(4), _internal.predictOpponent(X, T, 'p2x' + name, 4).map((o) => `${o.p} ${o.act.kind} ${o.act.id ?? o.act.idx ?? ''}`).join(', '));
  show('twin', mk(() => {}));
  show('lastMoveId null', mk((T) => { T.sides[1].mons[T.sides[1].active].lastMoveId = null; }));
  show('moveHit+battler as flinch', mk((T) => { T.moveHit = f.moveHit.slice(); T.moveHitBattler = f.moveHitBattler.slice(); }));
  show('pp as flinch', mk((T) => { T.sides[1].mons[T.sides[1].active].pp = f.sides[1].mons[f.sides[1].active].pp.slice(); }));
  show('all four', mk((T) => { const m = T.sides[1].mons[T.sides[1].active]; m.lastMoveId = null; m.lastMoveOk = false; m.pp = f.sides[1].mons[f.sides[1].active].pp.slice(); T.moveHit = f.moveHit.slice(); T.moveHitBattler = f.moveHitBattler.slice(); }));
}
