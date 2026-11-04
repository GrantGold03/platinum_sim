// 023 Shift battle style: the offer's gate and hand-walk (part 1) and the policies' answers (part 2).
// Positions are real League battles (ai_fixtures.mjs). The Set guard is sim/test/replay.test.mjs
// and determinism.test.mjs; here (c) checks the hook is never called under Set.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { B, gd, leagueBattle, setHP } from './ai_fixtures.mjs';
import { decide } from '../ai/opponent.mjs';
import { PLAYER_POLICIES, registerPlayerPolicy, runGauntlet, shiftOffer, shiftWanted } from '../gauntlet.mjs';
import { loadTeam } from '../bench.mjs';

const SCIZOR = B('scizor', 56, ['bullet_punch', 'protect', 'swords_dance', 'roost'], 'ABILITY_TECHNICIAN');
const BRONZONG = B('bronzong', 56, ['gyro_ball', 'protect', 'hypnosis', 'rest'], 'ABILITY_LEVITATE');
const GYARADOS = B('gyarados', 56, ['waterfall', 'protect', 'dragon_dance', 'ice_fang'], 'ABILITY_INTIMIDATE'); // poisonable (Scizor is Steel)

// A scripted player: switches to the first bench member with HP on every offer and counts calls.
function probe(name, { switches = true } = {}) {
  const calls = [];
  const p = {
    name,
    choose: (ctx) => (ctx.request.forceSwitch ? 'switch 2' : 'move 1'),
    shiftChoice(ctx, incoming) {
      calls.push(incoming.species.name);
      if (!switches) return { choice: null, reason: 'scripted stay' };
      const k = ctx.side.pokemon.findIndex((m) => !m.isActive && m.hp > 0);
      return { choice: `switch ${k + 1}`, reason: 'scripted switch' };
    },
  };
  return { p, calls };
}

const ctxFor = (x, side) => ({ gd: null, battle: x.battle, side, request: side.activeRequest, trainer: x.trainer, bag: [], members: [] });
const rec = () => ({ offers: 0, switches: 0, events: [] });
const movesBetween = (log, from) => log.slice(from).filter((l) => l.startsWith('|move|'));

test('hand-walk: Scizor KOs Flint\'s lead; the offer names Infernape; the switch costs no move and resets boosts', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR, BRONZONG]);
  x.p1.active[0].boosts.atk = 2; // a boost that must be gone after the switch out
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1'); // Bullet Punch (priority) KOs
  assert.equal(x.p2.requestState, 'switch');
  assert.equal(x.p1.requestState, '');
  assert.ok(shiftWanted(x.p1, x.p2));
  const r = decide(x.st, x.p2); // the trainer AI's choice, made before the offer
  assert.equal(r.kind, 'replacement');
  const { p, calls } = probe('shift-probe-switch');
  const sr = rec();
  const turn0 = x.battle.turn, len0 = x.battle.log.length;
  const c1 = shiftOffer(x.battle, p, ctxFor(x, x.p1), r.choice, x.trainer, sr);
  assert.deepEqual(calls, ['Infernape']); // the announced species is the AI's actual pick
  assert.equal(c1, 'switch 2');
  assert.deepEqual(sr, { offers: 1, switches: 1, events: [{ turn: turn0, incoming: 'Infernape', answer: 'Bronzong', reason: 'scripted switch' }] });
  assert.ok(x.battle.log.some((l) => l.startsWith('|-message|shift: ') && l.includes('about to send in Infernape') && l.includes('switches to Bronzong')));
  assert.equal(x.p1.requestState, 'switch', 'the engine now expects p1 to switch');
  x.battle.makeChoices(c1, r.choice);
  assert.equal(x.p1.active[0].species.name, 'Bronzong');
  assert.equal(x.p2.active[0].species.name, 'Infernape');
  assert.equal(x.p1.pokemon.find((m) => m.species.name === 'Scizor').boosts.atk, 0, 'boosts reset on the way out');
  assert.equal(x.battle.turn, turn0 + 1, 'the counter advances once, as for a normal replacement');
  assert.equal(movesBetween(x.battle.log, len0).length, 0, 'no move between the offer and the next command selection');
  assert.equal(x.p1.requestState, 'move');
  assert.equal(x.p2.requestState, 'move');
});

test('hand-walk: the foe faints from poison at the end of the turn; the offer still fires (any cause)', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR, BRONZONG]);
  const foe = x.p2.active[0];
  setHP(foe, 1);
  foe.setStatus('psn');
  x.battle.makeChoices('move 2', 'move 1'); // Protect; the residual poison KOs the foe
  assert.equal(foe.hp, 0);
  assert.ok(shiftWanted(x.p1, x.p2));
  const r = decide(x.st, x.p2);
  const { p, calls } = probe('shift-probe-psn', { switches: false });
  const sr = rec();
  const c1 = shiftOffer(x.battle, p, ctxFor(x, x.p1), r.choice, x.trainer, sr);
  assert.equal(calls.length, 1);
  assert.equal(c1, '', 'a stay is today\'s empty choice');
  assert.deepEqual([sr.offers, sr.switches, sr.events[0].answer], [1, 0, 'stay']);
  x.battle.makeChoices(c1, r.choice);
  assert.equal(x.p1.active[0].species.name, 'Scizor');
});

test('exclusion: both actives faint in the same turn -> both replace, no offer', () => {
  const x = leagueBattle('elite_four_flint', [GYARADOS, BRONZONG]);
  setHP(x.p2.active[0], 1); assert.ok(x.p2.active[0].setStatus('psn'));
  setHP(x.p1.active[0], 1); assert.ok(x.p1.active[0].setStatus('psn'));
  x.battle.makeChoices('move 2', 'move 1'); // Protect blocks the hit; poison KOs both at the end of the turn
  assert.equal(x.p1.requestState, 'switch');
  assert.equal(x.p2.requestState, 'switch');
  assert.equal(shiftWanted(x.p1, x.p2), false);
});

test('exclusion: only the player\'s active faints -> forced replacement, no offer', () => {
  const x = leagueBattle('elite_four_flint', [GYARADOS, BRONZONG]);
  setHP(x.p1.active[0], 1); assert.ok(x.p1.active[0].setStatus('psn'));
  x.battle.makeChoices('move 2', 'move 1');
  assert.equal(x.p1.requestState, 'switch');
  assert.equal(shiftWanted(x.p1, x.p2), false);
});

test('exclusion: the player has no bench member with HP -> no offer, no log line', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR]);
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1');
  assert.ok(shiftWanted(x.p1, x.p2));
  const r = decide(x.st, x.p2);
  const { p, calls } = probe('shift-probe-nobench');
  const sr = rec();
  const len0 = x.battle.log.length;
  const c1 = shiftOffer(x.battle, p, ctxFor(x, x.p1), r.choice, x.trainer, sr);
  assert.equal(c1, '');
  assert.equal(calls.length, 0);
  assert.deepEqual(sr, { offers: 0, switches: 0, events: [] });
  assert.equal(x.battle.log.length, len0);
});

test('exclusion: the trainer\'s last Pokemon faints -> the battle is over, no request, no offer', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR, BRONZONG]);
  for (const m of x.p2.pokemon) if (!m.isActive) { m.hp = 0; m.fainted = true; x.p2.pokemonLeft -= 1; }
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1');
  assert.ok(x.battle.ended);
  assert.equal(shiftWanted(x.p1, x.p2), false);
});

test('illegal answers are refused: the active member, a fainted member, a bad string', () => {
  const x = leagueBattle('elite_four_flint', [SCIZOR, BRONZONG]);
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1');
  const r = decide(x.st, x.p2);
  for (const bad of ['switch 1', 'switch 9', 'move 1']) {
    const p = { name: 'bad', choose: () => 'move 1', shiftChoice: () => ({ choice: bad, reason: 'x' }) };
    assert.throws(() => shiftOffer(x.battle, p, ctxFor(x, x.p1), r.choice, x.trainer, rec()), /illegal answer/);
  }
});

test('through runGauntlet: Set never calls the hook and matches a hookless run; Shift calls it and records the mix', () => {
  const greedy = PLAYER_POLICIES.get('greedy-v1');
  const calls = [];
  registerPlayerPolicy({ name: 'greedy+shiftprobe', choose: (ctx) => greedy.choose(ctx),
    shiftChoice(ctx, incoming) { calls.push(incoming.species.name); const k = ctx.side.pokemon.findIndex((m) => !m.isActive && m.hp > 0); return { choice: `switch ${k + 1}`, reason: 'probe' }; } });
  const req = (pol, style) => ({ team: loadTeam('bench'), seed: 'shift-test-0', player_policy: pol, opponent_policy: 'decomp-ai',
    stop_on_loss: false, trainers: ['aaron', 'bertha'], log: 'summary', ...(style ? { battle_style: style } : {}) });
  const plain = runGauntlet(gd, req('greedy-v1'));
  const set = runGauntlet(gd, req('greedy+shiftprobe', 'set'));
  assert.equal(calls.length, 0, 'never called under Set');
  assert.deepEqual(set.battles.map((b) => [b.trainer, b.won, b.log_hash]), plain.battles.map((b) => [b.trainer, b.won, b.log_hash]));
  assert.equal('battle_style' in set, false, 'no echo under Set');
  assert.equal(set.battles.every((b) => !('shift' in b)), true);
  const shift = runGauntlet(gd, req('greedy+shiftprobe', 'shift'));
  assert.equal(shift.battle_style, 'shift');
  const offers = shift.battles.reduce((n, b) => n + b.shift.offers, 0);
  assert.ok(offers >= 1 && calls.length === offers, `offers ${offers}, calls ${calls.length}`);
  assert.ok(shift.battles.some((b) => b.shift.events.some((e) => e.answer !== 'stay' && e.reason === 'probe')));
  assert.throws(() => runGauntlet(gd, req('greedy-v1', 'shuffle')), /unknown battle_style/);
});
