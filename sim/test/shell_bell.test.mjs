// 028 (H4, Shell Bell). Part 1: the battle engine against the game (spec FR-003; research R1, R2). The game heals a Shell
// Bell holder after a move that hit by BattleSystem_Divide(damage dealt, 8) (at least 1), when the holder is below max HP
// and above 0, damage to a substitute counting (pokeplatinum battle_controller_player.c:3361-3430, :4738; battle_lib.c:3599,
// :7345 for U-turn). Showdown heals move.totalDamage / 8 truncated, at least 1, unless a forced switch is pending
// (data/items.ts shellbell; sim/battle.ts heal). These tests drive the vendored engine on constructed battles and record
// what it does. Part 2: the battle player's model of the heal (spec FR-001; contract player-and-items.md).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, gd, leagueBattle } from './ai_fixtures.mjs';
import { _internal, makeContext, V4_OPTS } from '../policy/expectimax2.mjs';

const activeOf = (S, side) => S.sides[side].mons[S.sides[side].active];

function engine(builds, trainer = 'elite_four_flint') {
  const x = leagueBattle(trainer, builds);
  return x;
}
const heals = (battle, from) => battle.log.filter((l) => l.startsWith('|-heal|') && l.includes('Shell Bell') && (!from || l.includes(from)));

function turn(x, p1choice) {
  const before = x.battle.log.length;
  x.battle.choose('p1', p1choice);
  if (x.battle.p2.requestState === 'move') x.battle.choose('p2', 'move 1');
  // Showdown writes split lines twice (private and public copies): keep one of each consecutive duplicate
  return x.battle.log.slice(before).filter((l, i, a) => l !== a[i - 1]);
}
const shellHeals = (lines) => lines.filter((l) => l.startsWith('|-heal|p1a') && l.includes('Shell Bell'));

// ---- part 1: the engine -------------------------------------------------------------------------------------------
test('engine: a hurt holder heals floor(damage / 8) after a damaging hit', () => {
  const x = engine([B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL', 'shell_bell')]);
  const me = x.p1.active[0], foe = x.p2.active[0];
  me.hp = Math.floor(me.maxhp / 2);
  const foeBefore = foe.hp;
  const lines = turn(x, 'move 1');
  const dealt = foeBefore - foe.hp;
  const h = shellHeals(lines);
  assert.ok(dealt > 0, 'the hit landed');
  assert.equal(h.length, 1, lines.join('\n'));
  const hpAfterHeal = +h[0].split('|')[3].split('/')[0];
  // the holder takes no damage before its own heal when it moves first (it outspeeds the lead here): heal = after - half
  assert.equal(hpAfterHeal - Math.floor(me.maxhp / 2), Math.max(1, Math.floor(dealt / 8)), lines.join('\n'));
});

test('engine: a holder at full HP does not heal', () => {
  const x = engine([B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL', 'shell_bell')]);
  const lines = turn(x, 'move 1');
  assert.equal(shellHeals(lines).length, 0);
});

test('engine: damage to a substitute (records whether the engine heals from it)', () => {
  const x = engine([B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL', 'shell_bell')]);
  const me = x.p1.active[0], foe = x.p2.active[0];
  me.hp = Math.floor(me.maxhp / 2);
  foe.addVolatile('substitute');
  const lines = turn(x, 'move 2');
  const subHit = lines.some((l) => (l.startsWith('|-activate|p2a') || l.startsWith('|-end|p2a')) && l.includes('Substitute'));
  const healed = shellHeals(lines).length > 0;
  console.log(`# substitute: hit the substitute ${subHit}; engine healed ${healed} (game: heals, battle_controller_player.c:3361)`);
  assert.ok(subHit, lines.join('\n'));
  // 028 divergence (ledger mech-shell-bell-substitute): the engine counts no damage to a substitute, the game does
  assert.equal(healed, false, 'the engine behaviour this ledger entry records');
});

test('engine: U-turn heals (records it; the game heals on the pivot path)', () => {
  const x = engine([B('infernape', 60, ['u_turn', 'close_combat', 'flare_blitz', 'mach_punch'], 'ABILITY_BLAZE', 'shell_bell'),
                    B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL')]);
  const me = x.p1.active[0];
  me.hp = Math.floor(me.maxhp / 2);
  const lines = turn(x, 'move 1');
  const healed = shellHeals(lines).length > 0;
  console.log(`# u-turn: engine healed ${healed} (game: heals, battle_lib.c:7345)`);
  assert.equal(healed, true, 'engine and game agree: U-turn heals');
});

test('engine: a holder knocked out by its own recoil does not heal', () => {
  const x = engine([B('infernape', 60, ['flare_blitz', 'close_combat', 'u_turn', 'mach_punch'], 'ABILITY_BLAZE', 'shell_bell'),
                    B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL')]);
  const me = x.p1.active[0];
  me.hp = 1;
  const lines = turn(x, 'move 1');
  assert.equal(shellHeals(lines).length, 0, lines.join('\n'));
});

// ---- part 2: the player's model ------------------------------------------------------------------------------------
function playerState(item, opts = V4_OPTS) {
  const x = leagueBattle('elite_four_flint', [B('garchomp', 60, ['earthquake', 'dragon_claw', 'stone_edge', 'fire_fang'], 'ABILITY_SAND_VEIL', item)]);
  const X = makeContext({ gd, battle: x.battle, side: x.p1, trainer: x.trainer }, opts);
  return { X, T: _internal.cloneState(X.root) };
}
const EQ = { id: 'earthquake', category: 'CLASS_PHYSICAL' };

function hitFor(hp, dmg, { item = 'shell_bell', opts, foeHp } = {}) {
  const { X, T } = playerState(item, opts);
  const u = activeOf(T, 0), t = activeOf(T, 1);
  u.hp = hp === 'max' ? u.maxhp : hp === 'half' ? Math.floor(u.maxhp / 2) : hp;
  if (foeHp !== undefined) t.hp = foeHp;
  const before = u.hp;
  _internal.applyHit(X, T, 0, EQ, 'HIT', dmg);
  return { before, after: u.hp, max: u.maxhp };
}

test('player: a holder at half HP dealing 80 damage heals 10', () => {
  const r = hitFor('half', 80, { foeHp: 500 });
  assert.equal(r.after - r.before, 10);
});

test('player: a holder at full HP heals 0', () => {
  const r = hitFor('max', 80, { foeHp: 500 });
  assert.equal(r.after, r.max);
});

test('player: a 7-damage hit heals 1', () => {
  const r = hitFor('half', 7, { foeHp: 500 });
  assert.equal(r.after - r.before, 1);
});

test('player: the heal uses the HP the target lost, not the raw damage', () => {
  const r = hitFor('half', 80, { foeHp: 16 });
  assert.equal(r.after - r.before, 2);
});

test('player: a holder fainted by recoil heals 0', () => {
  const { X, T } = playerState('shell_bell');
  const u = activeOf(T, 0), t = activeOf(T, 1);
  u.hp = 1; t.hp = 500;
  _internal.applyHit(X, T, 0, { id: 'flareblitz', category: 'CLASS_PHYSICAL' }, 'RECOIL_BURN_HIT', 90);
  assert.equal(u.hp, 0);
});

test('player: no Shell Bell, no heal; the knob off, no heal', () => {
  const none = hitFor('half', 80, { item: 'expert_belt', foeHp: 500 });
  assert.equal(none.after - none.before, 0);
  const r = hitFor('half', 80, { foeHp: 500, opts: { ...V4_OPTS, shellBell: false } });
  assert.equal(r.after - r.before, 0);
});
