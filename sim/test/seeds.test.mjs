// T033: derived seeds are well-formed and accepted by Showdown, and a Showdown battle with a
// derived seed is deterministic (same seed -> identical log; different seed -> different log).
// Teams come from Showdown's own gen4 random-team generator with a fixed seed, so no game data is
// involved; this checks the seed plumbing only, not game fidelity.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle, Teams, PRNG } from '../showdown.mjs';
import { deriveSeed } from '../seeds.mjs';

test('known vector and format', () => {
  // Expected = sha256("master|0|0")[:32], computed independently with
  // `printf 'master|0|0' | sha256sum` (see tests/unit/test_seeds.py for the same vector).
  assert.equal(deriveSeed('master', 0, 0), 'sodium,39d2367647c627c2d5276f07f486e388');
  assert.match(deriveSeed(12345, 7, 4), /^sodium,[0-9a-f]{32}$/);
});

const teamSeed = 'sodium,' + '0'.repeat(31) + '1';
const teams = [
  Teams.generate('gen4randombattle', { seed: PRNG.get(teamSeed) }),
  Teams.generate('gen4randombattle', { seed: PRNG.get('sodium,' + '0'.repeat(31) + '2') }),
];

function play(seed, turns = 10) {
  const battle = new Battle({
    formatid: 'gen4customgame',
    seed,
    p1: { name: 'A', team: teams[0] },
    p2: { name: 'B', team: teams[1] },
  });
  for (let i = 0; i < turns && !battle.ended; i++) battle.makeChoices('default', 'default');
  return { log: battle.log.join('\n'), startingSeed: battle.prng.startingSeed };
}

test('Showdown accepts a derived seed and replays identically', () => {
  const seed = deriveSeed('determinism', 1, 2);
  const a = play(seed);
  const b = play(seed);
  assert.equal(a.startingSeed, seed);
  assert.ok(a.log.includes('|turn|'), 'battle actually progressed');
  assert.equal(a.log, b.log);
  // Positive control: a different derived seed changes the log.
  const c = play(deriveSeed('determinism', 1, 3));
  assert.notEqual(a.log, c.log);
});
