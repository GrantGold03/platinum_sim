// 025 (spec FR-004a): the battle player's model resets every stat stage on a modelled switch, both for the member
// switching out and the one switching in, and on a modelled replacement after a faint. The game resets stat stages on
// any switch (Pokemon_InitBattleMon via SwitchAndUpdateMon; feature 023 pinned the engine); the optimizer's dominance rule
// counts a self stat drop (Close Combat, Overheat, ...) as a cost that lasts only until the user switches, which is only
// right if the model agrees. Test only: no sim/ code changes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, gd, leagueBattle } from './ai_fixtures.mjs';
import { _internal, makeContext } from '../policy/expectimax2.mjs';

const ZERO = { atk: 0, def: 0, spa: 0, spd: 0, spe: 0, accuracy: 0, evasion: 0 };
const activeOf = (S, side) => S.sides[side].mons[S.sides[side].active];

function context() {
  const x = leagueBattle('elite_four_flint', [
    B('infernape', 60, ['close_combat', 'flare_blitz', 'mach_punch', 'u_turn'], 'ABILITY_BLAZE'),
    B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL'),
  ]);
  return makeContext({ gd, battle: x.battle, side: x.p1, trainer: x.trainer });
}

test('a modelled switch clears the stages of the member switching out and the one switching in', () => {
  const X = context();
  const T = _internal.cloneState(X.root);
  const out = activeOf(T, 0);
  out.boosts = { ...ZERO, def: -1, spd: -1 }; // Close Combat's self drop
  T.sides[0].mons[1].boosts = { ...ZERO, atk: 2 }; // a stale stage on the bench member (never happens in the game)
  _internal.doSwitch(X, T, 0, 1);
  assert.deepEqual(out.boosts, ZERO, 'the switched-out member');
  assert.deepEqual(activeOf(T, 0).boosts, ZERO, 'the switched-in member');
  assert.equal(activeOf(T, 0).idx, 1);
});

test('a modelled replacement after a faint enters with zero stages', () => {
  const X = context();
  const T = _internal.cloneState(X.root);
  const out = activeOf(T, 0);
  out.boosts = { ...ZERO, def: -2, spd: -2 };
  out.hp = 0; // fainted; the replacement is chosen inside valuePly2 -> replaceFainted
  T.sides[0].mons[1].boosts = { ...ZERO, spe: 1 };
  _internal.valuePly2(X, T);
  const now = activeOf(T, 0);
  assert.notEqual(now.idx, out.idx, 'a replacement came in');
  assert.deepEqual(now.boosts, ZERO);
});

test('the opponent side resets stages on its modelled switch too', () => {
  const X = context();
  const T = _internal.cloneState(X.root);
  const foe = activeOf(T, 1);
  foe.boosts = { ...ZERO, atk: -1 };
  const target = T.sides[1].mons.findIndex((m, i) => i !== T.sides[1].active && m.hp > 0);
  _internal.doSwitch(X, T, 1, target);
  assert.deepEqual(foe.boosts, ZERO);
  assert.deepEqual(activeOf(T, 1).boosts, ZERO);
});
