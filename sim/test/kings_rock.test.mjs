// 031: King's Rock / Razor Fang in the battle engine against the game (spec FR-001; research R1). The game: after each
// damaging hit of a move with MOVE_FLAG_TRIGGERS_KINGS_ROCK, 10% to flinch a target that took damage, has HP and has not
// moved (battle_controller_player.c CheckExtraFlinch :4630, also after every hit of a multi-hit move); not through a
// substitute, Inner Focus or Shield Dust (subscript_flinch_mon.s). The engine (Gen 4 mod items.ts kingsrock) adds a 10%
// flinch secondary to the same moves, applied per hit.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, leagueBattle } from './ai_fixtures.mjs';

const dedupe = (lines) => lines.filter((l, i, a) => l !== a[i - 1]);
const seedOf = (i) => 'sodium,' + (0x31000 + i).toString(16).padStart(32, '0');
const N = 400;

// Level-80 Crobat (faster than Flint's lead Houndoom) holding the item; Houndoom answers with Sunny Day (no damage).
const HOLDER = (item = 'kings_rock', level = 80) => B('crobat', level, ['tackle', 'double_kick', 'air_slash', 'protect'], 'ABILITY_INNER_FOCUS', item);

function rate(build, p1, n, setup) {
  let flinched = 0, hit = 0;
  for (let i = 1; i <= n; i++) {
    const x = leagueBattle('elite_four_flint', [build], { seed: seedOf(i) });
    const foe = x.p2.active[0];
    if (setup) setup(x, foe);
    const sunny = foe.moveSlots.findIndex((m) => m.id === 'sunnyday') + 1;
    const before = x.battle.log.length;
    x.battle.choose('p1', p1);
    if (x.battle.p2.requestState === 'move') x.battle.choose('p2', `move ${sunny}`);
    const lines = dedupe(x.battle.log.slice(before));
    // a use counts when it damaged the target and the target survived (a fainted target cannot flinch)
    if (!lines.some((l) => l.startsWith('|-damage|p2a'))) continue;
    if (lines.some((l) => l.startsWith('|faint|p2a'))) continue;
    hit++;
    if (lines.some((l) => l.startsWith('|cant|p2a') && l.endsWith('|flinch'))) flinched++;
  }
  return { flinched, hit, n };
}
// 99% interval for a binomial rate (normal approximation)
const within = (k, n, p) => Math.abs(k / n - p) <= 2.576 * Math.sqrt(p * (1 - p) / n);

test('engine: a single-hit affected move (Tackle) flinches at 10% per hit with the item, never without', () => {
  const r = rate(HOLDER(), 'move 1', N);
  console.log(`# Tackle + King's Rock: ${r.flinched}/${r.hit} hits flinched`);
  assert.ok(within(r.flinched, r.hit, 0.10), `${r.flinched}/${r.hit}`);
  const c = rate(HOLDER(null), 'move 1', 100);
  assert.equal(c.flinched, 0, 'no item: no flinch (control)');
});

test('engine: a two-hit move (Double Kick) rolls after each hit: about 19%', () => {
  const r = rate(HOLDER('kings_rock', 45), 'move 2', N); // Lv 45: still faster than Houndoom, no knockout
  console.log(`# Double Kick + King's Rock: ${r.flinched}/${r.hit} uses flinched`);
  assert.ok(within(r.flinched, r.hit, 0.19), `${r.flinched}/${r.hit}`);
  assert.ok(r.flinched / r.hit > 0.10 + 2.576 * Math.sqrt(0.09 / r.hit), 'more than one roll per use');
});

test('engine: the item\'s roll is separate from a flinch move\'s own (Air Slash 30%): about 37% per hit', () => {
  const r = rate(HOLDER(), 'move 3', N);
  console.log(`# Air Slash + King's Rock: ${r.flinched}/${r.hit} hits flinched`);
  assert.ok(within(r.flinched, r.hit, 1 - 0.7 * 0.9), `${r.flinched}/${r.hit}`);
});

test('engine: never through Shield Dust, Inner Focus or a substitute, nor from a slower holder', () => {
  const shield = rate(HOLDER(), 'move 1', 100, (x, foe) => foe.setAbility('shielddust'));
  const inner = rate(HOLDER(), 'move 1', 100, (x, foe) => foe.setAbility('innerfocus'));
  const sub = rate(HOLDER(), 'move 1', 100, (x, foe) => { foe.addVolatile('substitute'); });
  const slow = rate(B('bronzong', 60, ['gyro_ball', 'protect', 'rest', 'hypnosis'], 'ABILITY_LEVITATE', 'kings_rock'), 'move 1', 100);
  console.log(`# blockers: shield dust ${shield.flinched}, inner focus ${inner.flinched}, substitute ${sub.flinched}, slower holder ${slow.flinched}`);
  assert.deepEqual([shield.flinched, inner.flinched, sub.flinched, slow.flinched], [0, 0, 0, 0]);
  assert.ok(shield.hit > 0 && inner.hit > 0 && slow.hit > 0, 'the hits landed');
});
