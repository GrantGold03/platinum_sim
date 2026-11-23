// 029 (H4, resist berries). Part 1: the battle engine against the game (spec FR-004; research R1, R4). The game halves the HP
// change of the first super-effective hit of the berry's type (Chilan: any Normal hit) after the final damage and removes the
// berry (res/battle/scripts/subscripts/subscript_type_resist_berry.s, from subscript_update_hp.s:10). Showdown applies a 0.5
// modifier in onSourceModifyDamage (data/items.ts occaberry and the others). Part 2: the battle player's model (FR-001, FR-002).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, gd, leagueBattle } from './ai_fixtures.mjs';
import { _internal, makeContext, V4_OPTS } from '../policy/expectimax2.mjs';

const activeOf = (S, side) => S.sides[side].mons[S.sides[side].active];
const dedupe = (lines) => lines.filter((l, i, a) => l !== a[i - 1]);

// One turn where the opponent's lead attacks our holder with a chosen move slot; returns the deduped log of the turn.
function foeHits(x, p2move) {
  const before = x.battle.log.length;
  x.battle.choose('p1', 'move 1');
  if (x.battle.p2.requestState === 'move') x.battle.choose('p2', `move ${p2move}`);
  return dedupe(x.battle.log.slice(before));
}

// ---- part 1: the engine -------------------------------------------------------------------------------------------
// Flint's lead Houndoom knows Flamethrower (Fire) and Dark Pulse; Bronzong (Steel/Psychic) takes both at 2x and survives them
// at level 100, so the HP lost is comparable with and without the berry on the same seed.
const SCIZOR = (item) => B('bronzong', 100, ['calm_mind', 'protect', 'rest', 'hypnosis'], 'ABILITY_LEVITATE', item);

function houndoomMoveSlot(x, id) {
  const slot = x.p2.active[0].moveSlots.findIndex((m) => m.id === id);
  assert.ok(slot >= 0, `Houndoom knows ${id}`);
  return slot + 1;
}

test('engine: a super-effective hit of the berry type is weakened and the berry eaten; the plain holder takes more', () => {
  const lost = {};
  for (const item of ['occa_berry', null]) {
    const x = leagueBattle('elite_four_flint', [SCIZOR(item)]);
    const me = x.p1.active[0];
    const before = me.hp;
    const lines = foeHits(x, houndoomMoveSlot(x, 'flamethrower'));
    lost[item ?? 'none'] = before - me.hp;
    if (item) {
      assert.ok(lines.some((l) => l.startsWith('|-enditem|p1a') && l.includes('Occa Berry') && l.includes('[weaken]')), lines.join('\n'));
      assert.equal(me.item, '', 'the berry is gone');
    }
  }
  console.log(`# super-effective: HP lost with berry ${lost.occa_berry}, without ${lost.none} (same seed)`);
  assert.ok(lost.occa_berry > 0 && lost.occa_berry < lost.none);
  assert.ok(Math.abs(lost.occa_berry - Math.floor(lost.none / 2)) <= 1, `about half: ${lost.occa_berry} vs ${lost.none}`);
});

test('engine: a neutral hit leaves the berry in place', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR('passho_berry')]); // Water berry; Flamethrower is Fire
  const lines = foeHits(x, houndoomMoveSlot(x, 'flamethrower'));
  assert.ok(!lines.some((l) => l.startsWith('|-enditem|p1a')), lines.join('\n'));
  assert.equal(x.p1.active[0].item, 'passhoberry');
});

// ---- part 2: the player's model -------------------------------------------------------------------------------------
function playerState(item, opts = V4_OPTS) {
  const x = leagueBattle('elite_four_flint', [SCIZOR(item)]);
  const X = makeContext({ gd, battle: x.battle, side: x.p1, trainer: x.trainer }, opts);
  return { X, T: _internal.cloneState(X.root) };
}
const FLAMETHROWER = () => gd.moves[gd.fromSdMove.get('flamethrower')];
const DARK_PULSE = () => gd.moves[gd.fromSdMove.get('darkpulse')];

function outcomes(item, rec, opts) {
  const { X, T } = playerState(item, opts);
  const foe = activeOf(T, 1), me = activeOf(T, 0);
  me.hp = me.maxhp; // the full outcome list, with no knockout bucket when the halved hit leaves HP
  return { X, T, out: _internal.damageOutcomes(X, T, foe, me, rec), me };
}

test('player: a super-effective hit of the berry type is halved and the berry consumed when it lands', () => {
  const plain = outcomes(null, FLAMETHROWER()).out;
  const { X, T, out, me } = outcomes('occa_berry', FLAMETHROWER());
  const meanPlain = plain.reduce((s, o) => s + o.p * o.dmg, 0), meanBerry = out.reduce((s, o) => s + o.p * o.dmg, 0);
  assert.ok(out.every((o) => o.berry === true), 'flagged');
  assert.ok(Math.abs(meanBerry - meanPlain / 2) <= 2, `halved: ${meanBerry} vs ${meanPlain}`);
  _internal.applyHit(X, T, 1, FLAMETHROWER(), 'BURN_HIT', out[0].dmg, out[0].berry);
  assert.equal(me.item, '', 'consumed');
});

test('player: a hit of another type is not halved and the berry stays', () => {
  const { out } = outcomes('occa_berry', DARK_PULSE());
  const plain = outcomes(null, DARK_PULSE()).out;
  assert.ok(out.every((o) => !o.berry));
  assert.deepEqual(out.map((o) => o.dmg), plain.map((o) => o.dmg));
});

test('player: after the berry is used, the next super-effective hit is not halved', () => {
  const { X, T, me } = outcomes('occa_berry', FLAMETHROWER());
  const foe = activeOf(T, 1);
  const first = _internal.damageOutcomes(X, T, foe, me, FLAMETHROWER());
  _internal.applyHit(X, T, 1, FLAMETHROWER(), 'BURN_HIT', 1, first[0].berry);
  me.hp = me.maxhp;
  const second = _internal.damageOutcomes(X, T, foe, me, FLAMETHROWER());
  assert.ok(second.every((o) => !o.berry));
});

test('player: Chilan halves a Normal hit at any effectiveness; the knob off halves nothing', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR('chilan_berry')]);
  const X = makeContext({ gd, battle: x.battle, side: x.p1, trainer: x.trainer }, V4_OPTS);
  const T = _internal.cloneState(X.root);
  const normal = gd.moves[gd.fromSdMove.get('return')];
  const d = _internal.damageOutcomes(X, T, activeOf(T, 1), activeOf(T, 0), normal);
  if (d) assert.ok(d.every((o) => o.berry === true), 'Chilan on a resisted Normal hit');
  const off = outcomes('occa_berry', FLAMETHROWER(), { ...V4_OPTS, resistBerries: false }).out;
  assert.ok(off.every((o) => !o.berry));
});
