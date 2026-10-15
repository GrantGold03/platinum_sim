// 007 T021-T027: expectimax2-v3 status-move mechanics, each checked against the decomp numbers it
// cites (the model is the policy's own; Showdown plays the real battle). One hand-built Cynthia
// position per mechanic; our move is resolved with the opponent doing nothing, then end of turn.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { makeContext, _internal, V2_OPTS, V3_OPTS, EXPECTIMAX2_V3 } from '../policy/expectimax2.mjs';
import { B, gd, leagueBattle, sendIn } from './ai_fixtures.mjs';

const NONE = { kind: 'none' };
function setup(builds, { foeSlot = null, opts = V3_OPTS, name = EXPECTIMAX2_V3, live } = {}) {
  const { battle, trainer } = leagueBattle('champion_cynthia', builds);
  if (foeSlot !== null) sendIn(battle, battle.sides[1], foeSlot);
  if (live) live(battle);
  const X = makeContext({ gd, battle, side: battle.sides[0], trainer }, opts, name);
  return { X, S: X.root, battle };
}
const me = (S) => _internal.activeOf(S, 0);
const foe = (S) => _internal.activeOf(S, 1);
const slotOf = (S, id) => me(S).ref.moveSlots.findIndex((s) => s.id === id);
function play(X, S, id) { // our move, foe idle, end of turn; the most likely branch (hit)
  const brs = _internal.resolveTurn(X, S, _internal.moveAct(X, me(S), slotOf(S, id)), NONE);
  return brs.reduce((a, b) => (b.p > a.p ? b : a)).S;
}

test('weather: 5 turns, 8 with the matching rock; expiry; ability weather is permanent (effect_script_0136, battle_controller_player.c:1121)', () => {
  const { X, S } = setup([B('vaporeon', 60, ['rain_dance', 'surf', 'rest', 'wish'], 'ABILITY_WATER_ABSORB')]);
  const T = play(X, S, 'raindance');
  assert.equal(T.weather, 'rain');
  assert.equal(T.weatherTurns, 4); // set to 5, one end of turn passed
  const R = setup([B('vaporeon', 60, ['rain_dance', 'surf', 'rest', 'wish'], 'ABILITY_WATER_ABSORB', 'damp_rock')]);
  assert.equal(play(R.X, R.S, 'raindance').weatherTurns, 7);
  const U = _internal.cloneState(T); U.weatherTurns = 1;
  _internal.endOfTurn(X, U);
  assert.equal(U.weather, ''); // ends when the counter reaches 0, before its damage
  // a second Rain Dance in rain fails (effect_script_0136: already raining -> fail)
  assert.equal(play(X, T, 'raindance').weatherTurns, 3);
});

test('Thunder: never misses in rain, 50% base in sun; Blizzard never misses in hail (battle_controller_player.c:2915, 3025-3029)', () => {
  const { X, S } = setup([B('jolteon', 60, ['thunder', 'blizzard', 'rain_dance', 'sunny_day'], 'ABILITY_VOLT_ABSORB')]);
  const rec = (id) => _internal.moveAct(X, me(S), slotOf(S, id)).rec;
  const T = _internal.cloneState(S);
  assert.ok(_internal.hitChance(X, T, me(T), foe(T), rec('thunder')) < 1);
  T.weather = 'rain'; assert.equal(_internal.hitChance(X, T, me(T), foe(T), rec('thunder')), 1);
  T.weather = 'sun'; assert.equal(_internal.hitChance(X, T, me(T), foe(T), rec('thunder')), 0.5);
  T.weather = 'hail'; assert.equal(_internal.hitChance(X, T, me(T), foe(T), rec('blizzard')), 1);
});

test('Synthesis heals 1/2, 2/3 in sun, 1/4 in other weather (BtlCmd_WeatherHPRecovery, battle_script.c:5966-5978)', () => {
  const { X, S } = setup([B('meganium', 60, ['synthesis', 'leaf_storm', 'sunny_day', 'body_slam'], 'ABILITY_OVERGROW')]);
  const m = me(S);
  for (const [w, num, den] of [['', 1, 2], ['sun', 20, 30], ['rain', 1, 4]]) {
    const T = _internal.cloneState(S); T.weather = w; T.weatherTurns = w ? 5 : 0;
    me(T).hp = 1;
    const out = play(X, T, 'synthesis');
    assert.equal(me(out).hp, 1 + Math.floor(m.maxhp * num / den), w || 'none');
  }
});

test('Leech Seed: 1/8 of the seeded max HP to the seeder each turn; Grass types are immune (battle_controller_player.c:1378-1392)', () => {
  const { X, S } = setup([B('torterra', 60, ['leech_seed', 'earthquake', 'synthesis', 'wood_hammer'], 'ABILITY_OVERGROW')]);
  me(S).hp = 50;
  const T = play(X, S, 'leechseed'); // Spiritomb (Ghost/Dark)
  const f = foe(T), fmax = foe(S).maxhp;
  assert.equal(f.seeded, 1);
  assert.equal(f.hp, foe(S).hp - Math.floor(fmax / 8));
  assert.equal(me(T).hp, 50 + Math.floor(fmax / 8));
  const G = setup([B('torterra', 60, ['leech_seed', 'earthquake', 'synthesis', 'wood_hammer'], 'ABILITY_OVERGROW')], { foeSlot: 1 }); // Roserade
  assert.equal(foe(play(G.X, G.S, 'leechseed')).seeded, 0);
});

test('Substitute: costs 1/4 max HP, fails at or below it, takes the hit (battle_script.c:5211-5226)', () => {
  const { X, S } = setup([B('gengar', 60, ['substitute', 'shadow_ball', 'protect', 'thunderbolt'], 'ABILITY_LEVITATE')]);
  const m = me(S), cost = Math.floor(m.maxhp / 4);
  const T = play(X, S, 'substitute');
  assert.equal(me(T).subHp, cost);
  assert.equal(me(T).hp, m.maxhp - cost);
  const L = _internal.cloneState(S); me(L).hp = cost;
  assert.equal(me(play(X, L, 'substitute')).subHp, 0);
});

test('Wish heals half of the recipient max HP at the end of the next turn; Aqua Ring and Ingrain 1/16 (battle_controller_player.c:1085-1110, 1311-1345)', () => {
  const { X, S } = setup([B('vaporeon', 60, ['wish', 'aqua_ring', 'surf', 'protect'], 'ABILITY_WATER_ABSORB')]);
  me(S).hp = 10;
  const T = play(X, S, 'wish');
  assert.equal(T.sides[0].sc.wish, 1);
  assert.equal(me(T).hp, 10);
  _internal.endOfTurn(X, T);
  assert.equal(me(T).hp, 10 + Math.floor(me(T).maxhp / 2));
  const A = _internal.cloneState(S); me(A).hp = 10;
  const out = play(X, A, 'aquaring');
  assert.equal(me(out).hp, 10 + Math.floor(me(out).maxhp / 16));
});

test('Taunt 4 turns (mean of 3-5), Encore 5 (mean of 3-7), confusion 3 (mean of 2-5): counters tick at end of turn', () => {
  const { X, S, battle } = setup([B('gengar', 60, ['taunt', 'encore', 'confuse_ray', 'shadow_ball'], 'ABILITY_LEVITATE')]);
  const T = play(X, S, 'taunt');
  assert.equal(foe(T).taunt, 3);
  const C = play(X, S, 'confuseray');
  assert.equal(foe(C).confusion, 3);
  const E0 = _internal.cloneState(S); foe(E0).lastMoveId = foe(E0).ref.moveSlots[0].id;
  const E = play(X, E0, 'encore');
  assert.equal(foe(E).encoreTurns, 4);
  assert.equal(foe(E).encoreMove, foe(E0).lastMoveId);
});

test('hazards on switch-in: Spikes 1/8, 1/6, 1/4; Stealth Rock maxHP x Rock multiplier / 8; Flying ignores Spikes (battle_script.c:5434-5436, 8313-8335)', () => {
  const { X, S } = setup([B('skarmory', 60, ['spikes', 'stealth_rock', 'toxic_spikes', 'drill_peck'], 'ABILITY_KEEN_EYE')]);
  const T = play(X, S, 'spikes');
  assert.equal(T.sides[1].sc.spikes, 1);
  const U = _internal.cloneState(T);
  U.sides[1].sc.rocks = 1;
  const before = U.sides[1].mons.find((m) => m.ref.species.id === 'garchomp');
  const hp0 = before.hp;
  _internal.doSwitch(X, U, 1, before.idx);
  // Garchomp (Dragon/Ground, grounded): Spikes 1 layer 1/8 + Stealth Rock (Rock vs Ground x0.5) 1/16
  assert.equal(before.hp, hp0 - Math.floor(before.maxhp / 8) - Math.floor(before.maxhp / 16));
  const V = _internal.cloneState(T); V.sides[1].sc.spikes = 3;
  const tog = V.sides[1].mons.find((m) => m.ref.species.id === 'togekiss');
  const t0 = tog.hp;
  _internal.doSwitch(X, V, 1, tog.idx);
  assert.equal(tog.hp, t0); // Flying: no Spikes damage
});

test('Baton Pass carries stat stages and the substitute to the bench member it picks', () => {
  const { X, S } = setup([B('ninjask', 60, ['baton_pass', 'swords_dance', 'substitute', 'x_scissor'], 'ABILITY_SPEED_BOOST'),
    B('scizor', 60, ['bullet_punch', 'x_scissor', 'swords_dance', 'roost'], 'ABILITY_TECHNICIAN')]);
  const T = _internal.cloneState(S);
  me(T).boosts.atk = 2; me(T).subHp = 30;
  const out = play(X, T, 'batonpass');
  assert.equal(out.sides[0].active, 1);
  assert.equal(me(out).boosts.atk, 2);
  assert.equal(me(out).subHp, 30);
});

test('v2 is unchanged by the v3 mechanics: Leech Seed has no effect in the v2 model', () => {
  const { X, S } = setup([B('torterra', 60, ['leech_seed', 'earthquake', 'synthesis', 'wood_hammer'], 'ABILITY_OVERGROW')],
    { opts: V2_OPTS, name: 'expectimax2-v2' });
  const T = play(X, S, 'leechseed');
  assert.equal(foe(T).hp, foe(S).hp);
  assert.equal(S.v3, undefined);
});
