// 030: the battle player models flinch. Part 1: the battle engine against the game (spec FR-005; research R1, R3,
// R4). Part 2: the player's model (FR-001 to FR-004, FR-012). The game: subscript_flinch_mon.s (moved this turn,
// substitute, Inner Focus), battle_script.c:8369 (Serene Grace doubles the chance), battle_controller_player.c:2528
// (a flinched Pokemon loses its move), subscript_flinched.s (Steadfast +1 Speed), battle_lib.c:3558 (Fake Out).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, gd, leagueBattle, sendIn } from './ai_fixtures.mjs';
import { _internal, makeContext, V4_OPTS as V4_DEFAULT } from '../policy/expectimax2.mjs';
// The model's cases test both sides (`flinch: true`); v4's default is the foe's side only ('defend', tested below).
const V4_OPTS = { ...V4_DEFAULT, flinch: true };

const dedupe = (lines) => lines.filter((l, i, a) => l !== a[i - 1]);
const seedOf = (i) => 'sodium,' + i.toString(16).padStart(32, '0');
const slotOf = (mon, id) => { const s = mon.moveSlots.findIndex((m) => m.id === id); assert.ok(s >= 0, `${mon.name} knows ${id}`); return s + 1; };

function turn(x, p1, p2) {
  const before = x.battle.log.length;
  x.battle.choose('p1', p1);
  if (x.battle.p2.requestState === 'move') x.battle.choose('p2', p2);
  return dedupe(x.battle.log.slice(before));
}
const flinchedLine = (lines, who) => lines.some((l) => l.startsWith(`|cant|${who}`) && l.endsWith('|flinch'));

// ---- part 1: the engine ---------------------------------------------------------------------------------------
// Flint's lead Houndoom (Lv 52, base Speed 95) knows Dark Pulse (20% flinch).
const SLOW = (ability = 'ABILITY_LEVITATE') => B('bronzong', 60, ['flash_cannon', 'protect', 'rest', 'hypnosis'], ability);

test('engine: a faster Dark Pulse flinches a slower target on some seed; the target then does not move', () => {
  let found = 0;
  for (let i = 1; i <= 40 && !found; i++) {
    const x = leagueBattle('elite_four_flint', [SLOW()], { seed: seedOf(i) });
    const lines = turn(x, 'move 1', `move ${slotOf(x.p2.active[0], 'darkpulse')}`);
    if (flinchedLine(lines, 'p1a')) {
      found = i;
      assert.ok(!lines.some((l) => l.startsWith('|move|p1a')), lines.join('\n'));
    }
  }
  assert.ok(found, 'no flinch in 40 seeds at 20%');
});

test('engine: a slower flinch move never flinches (the target already moved)', () => {
  // Level-100 Crobat (base Speed 130) moves first; Houndoom's Dark Pulse comes second.
  for (let i = 1; i <= 30; i++) {
    const x = leagueBattle('elite_four_flint', [B('crobat', 100, ['roost', 'protect', 'haze', 'confuse_ray'], 'ABILITY_INNER_FOCUS')], { seed: seedOf(i) });
    const lines = turn(x, 'move 2', `move ${slotOf(x.p2.active[0], 'darkpulse')}`);
    assert.ok(!flinchedLine(lines, 'p1a'), lines.join('\n'));
  }
});

test('engine: Inner Focus blocks the flinch; Steadfast raises Speed one stage when flinched', () => {
  let steadfast = 0;
  for (let i = 1; i <= 40; i++) {
    const inner = leagueBattle('elite_four_flint', [B('lucario', 30, ['swords_dance', 'protect', 'quick_attack', 'endure'], 'ABILITY_INNER_FOCUS')], { seed: seedOf(i) });
    assert.ok(!flinchedLine(turn(inner, 'move 1', `move ${slotOf(inner.p2.active[0], 'darkpulse')}`), 'p1a'));
    const sf = leagueBattle('elite_four_flint', [B('lucario', 100, ['swords_dance', 'protect', 'quick_attack', 'endure'], 'ABILITY_STEADFAST', null, { level_override: undefined })], { seed: seedOf(i) });
    sf.p1.active[0].storedStats.spe = 1; // slower than Houndoom whatever the level
    const lines = turn(sf, 'move 1', `move ${slotOf(sf.p2.active[0], 'darkpulse')}`);
    if (flinchedLine(lines, 'p1a')) {
      steadfast++;
      assert.ok(lines.some((l) => l.startsWith('|-boost|p1a') && l.includes('|spe|1')), lines.join('\n'));
    }
  }
  assert.ok(steadfast > 0, 'no Steadfast flinch in 40 seeds');
});

test('engine: Fake Out flinches on its user\'s first turn out and fails on the second', () => {
  const x = leagueBattle('elite_four_flint', [B('infernape', 60, ['fake_out', 'protect', 'nasty_plot', 'calm_mind'], 'ABILITY_BLAZE')]);
  const t1 = turn(x, 'move 1', `move ${slotOf(x.p2.active[0], 'darkpulse')}`);
  assert.ok(flinchedLine(t1, 'p2a'), t1.join('\n'));
  const t2 = turn(x, 'move 1', `move ${slotOf(x.p2.active[0], 'darkpulse')}`);
  assert.ok(t2.some((l) => l.startsWith('|-fail|p1a')) || t2.some((l) => l.startsWith('|-fail|')), t2.join('\n'));
  assert.ok(!flinchedLine(t2, 'p2a'));
});

// ---- part 2: the player's model -------------------------------------------------------------------------------
function ctx(build, opts = V4_OPTS, setup) {
  const x = leagueBattle('elite_four_flint', [build]);
  if (setup) setup(x);
  const X = makeContext({ gd, battle: x.battle, side: x.p1, trainer: x.trainer }, opts);
  const T = _internal.cloneState(X.root);
  const me = T.sides[0].mons[T.sides[0].active], foe = T.sides[1].mons[T.sides[1].active];
  return { x, X, T, me, foe };
}
const act = (X, m, id) => _internal.moveAct(X, m, m.ref.moveSlots.findIndex((s) => s.id === id));
// The probability mass where `who` ends the turn with full HP (its attacker's move did not happen or missed).
const untouched = (branches, side, hp) => branches.reduce((s, b) => s + (b.S.sides[side].mons[b.S.sides[side].active].hp === hp ? b.p : 0), 0);

test('player: a faster foe\'s Dark Pulse flinches the slower member with p 0.20; off, never', () => {
  const on = ctx(SLOW());
  const off = ctx(SLOW(), { ...V4_OPTS, flinch: false });
  const run = (c) => _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'flashcannon'), act(c.X, c.foe, 'darkpulse'));
  const pOn = untouched(run(on), 1, on.foe.hp), pOff = untouched(run(off), 1, off.foe.hp);
  assert.ok(Math.abs((pOn - pOff) - 0.20) < 1e-9, `flinch mass ${pOn - pOff}`);
});

test('player: the member\'s faster Air Slash flinches the foe with p 0.30 x hit chance', () => {
  const crobat = B('crobat', 60, ['air_slash', 'protect', 'haze', 'roost'], 'ABILITY_INNER_FOCUS'); // faster, no knockout
  const on = ctx(crobat), off = ctx(crobat, { ...V4_OPTS, flinch: false });
  const run = (c) => _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'airslash'), act(c.X, c.foe, 'darkpulse'));
  const pOn = untouched(run(on), 0, on.me.hp), pOff = untouched(run(off), 0, off.me.hp);
  assert.ok(Math.abs((pOn - pOff) - 0.30 * 0.95) < 1e-9, `flinch mass ${pOn - pOff}`);
});

test('player: no flinch chance at all when the flinch move\'s user moves second (owner\'s rule, FR-012)', () => {
  const crobat = B('crobat', 100, ['roost', 'protect', 'haze', 'air_slash'], 'ABILITY_INNER_FOCUS');
  const on = ctx(crobat), off = ctx(crobat, { ...V4_OPTS, flinch: false });
  const run = (c) => _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'haze'), act(c.X, c.foe, 'darkpulse'));
  const a = run(on), b = run(off);
  assert.equal(a.length, b.length, 'no extra branch');
  assert.deepEqual(a.map((r) => r.p), b.map((r) => r.p));
  assert.equal(_internal.flinchChance(on.X, on.T, 1, gd.moves[gd.fromSdMove.get('darkpulse')], 'FLINCH_HIT', false), 0);
});

test('player: substitute, Inner Focus (not against Mold Breaker) and Serene Grace', () => {
  const dp = gd.moves[gd.fromSdMove.get('darkpulse')];
  const inner = ctx(B('lucario', 100, ['swords_dance', 'protect', 'quick_attack', 'endure'], 'ABILITY_INNER_FOCUS'));
  assert.equal(_internal.flinchChance(inner.X, inner.T, 1, dp, 'FLINCH_HIT', true), 0);
  const plain = ctx(SLOW());
  assert.equal(_internal.flinchChance(plain.X, plain.T, 1, dp, 'FLINCH_HIT', true), 0.2);
  const sub = ctx(SLOW(), V4_OPTS, (x) => { x.p1.active[0].volatiles.substitute = { id: 'substitute', hp: 50 }; });
  assert.equal(_internal.flinchChance(sub.X, sub.T, 1, dp, 'FLINCH_HIT', true), 0);
  const sg = ctx(B('togekiss', 100, ['air_slash', 'protect', 'roost', 'nasty_plot'], 'ABILITY_SERENE_GRACE'));
  assert.equal(_internal.flinchChance(sg.X, sg.T, 0, gd.moves[gd.fromSdMove.get('airslash')], 'FLINCH_HIT', true), 0.6);
});

test('player: Steadfast gains +1 Speed when flinched; the mark is gone at the end of the turn', () => {
  const sf = B('lucario', 100, ['swords_dance', 'protect', 'quick_attack', 'endure'], 'ABILITY_STEADFAST');
  const c = ctx(sf, V4_OPTS, (x) => { x.p1.active[0].storedStats.spe = 1; });
  const out = _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'swordsdance'), act(c.X, c.foe, 'darkpulse'));
  const flinched = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].boosts.spe === 1);
  assert.ok(Math.abs(flinched.reduce((s, b) => s + b.p, 0) - 0.2) < 1e-9);
  assert.ok(out.every((b) => !b.S.sides[0].mons[b.S.sides[0].active].flinched));
});

test('player: Fake Out flinches on the first turn out and fails afterwards', () => {
  const ape = B('infernape', 60, ['fake_out', 'protect', 'nasty_plot', 'calm_mind'], 'ABILITY_BLAZE');
  const c = ctx(ape);
  const first = _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'fakeout'), act(c.X, c.foe, 'darkpulse'));
  assert.ok(Math.abs(untouched(first, 0, c.me.hp) - 1) < 1e-9, 'the foe never moves');
  const c2 = ctx(ape);
  c2.me.activeTurns = 2; // a second turn out (the engine reads 1 at a lead's first decision)
  const later = _internal.resolveTurn(c2.X, c2.T, act(c2.X, c2.me, 'fakeout'), act(c2.X, c2.foe, 'darkpulse'));
  assert.ok(later.every((b) => b.S.sides[1].mons[b.S.sides[1].active].hp === c2.foe.hp), 'Fake Out fails');
});

test('player: a flinched Pokemon\'s move-hit record is cleared, as the game\'s ClearFlags does (030 diagnosis)', () => {
  const crobat = B('crobat', 60, ['air_slash', 'protect', 'haze', 'roost'], 'ABILITY_INNER_FOCUS');
  const c = ctx(crobat);
  const out = _internal.resolveTurn(c.X, c.T, act(c.X, c.me, 'airslash'), act(c.X, c.foe, 'darkpulse'));
  const flinched = out.filter((b) => b.S.sides[0].mons[b.S.sides[0].active].hp === c.me.hp && b.S.sides[1].mons[b.S.sides[1].active].hp < c.foe.hp);
  assert.ok(flinched.length > 0);
  assert.ok(flinched.every((b) => b.S.moveHit[1] === 0), 'the foe\'s record of being hit is cleared when its turn is lost');
});

test('player: v4\'s default models the foe\'s flinches only (owner\'s decision, 030)', () => {
  assert.equal(V4_DEFAULT.flinch, 'defend');
  const crobat = B('crobat', 60, ['air_slash', 'protect', 'haze', 'roost'], 'ABILITY_INNER_FOCUS');
  const d = ctx(crobat, V4_DEFAULT);
  assert.equal(_internal.flinchChance(d.X, d.T, 0, gd.moves[gd.fromSdMove.get('airslash')], 'FLINCH_HIT', true), 0, 'own flinch odds not valued');
  const s = ctx(SLOW(), V4_DEFAULT);
  assert.equal(_internal.flinchChance(s.X, s.T, 1, gd.moves[gd.fromSdMove.get('darkpulse')], 'FLINCH_HIT', true), 0.2, 'the foe\'s flinch is');
});
