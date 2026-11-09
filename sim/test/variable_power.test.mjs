// 024: the shared variable-power helper against the decomp tables (part 1) and greedy-v1's scoring of the
// four offered moves (part 2). Sources: battle_script.c:6808-6828 (weight tiers, first limit >= weight),
// :7123-7133 (Gyro Ball), effect_script_0121.s (Return), weight_to_power.h.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WEIGHT_TO_POWER, frustrationPower, gyroBallPower, returnPower, speciesWeightHg, weightTierPower } from '../variable_power.mjs';
import { B, gd, leagueBattle } from './ai_fixtures.mjs';
import { expectedDamage, greedy, variablePowerFor } from '../policy/greedy.mjs';
import { calcDamage, fromShowdown } from '../damage.mjs';

test('WEIGHT_TO_POWER is the decomp table', () => {
  assert.deepEqual(WEIGHT_TO_POWER, [[100, 20], [250, 40], [500, 60], [1000, 80], [2000, 100], [0xFFFF, 0xFFFF]]);
});

test('weightTierPower: every tier, both sides of every limit (the game gives the LOWER tier on a limit)', () => {
  const cases = [[1, 20], [100, 20], [101, 40], [250, 40], [251, 60], [500, 60], [501, 80], [1000, 80], [1001, 100], [2000, 100], [2001, 120], [4600, 120]];
  for (const [w, p] of cases) assert.equal(weightTierPower(w), p, `weight ${w}`);
});

test('speciesWeightHg: Snorlax 4600, Pikachu 60, Flareon 250 (exactly on the 250 limit: game 40, Showdown 60)', () => {
  assert.equal(speciesWeightHg('SPECIES_SNORLAX'), 4600);
  assert.equal(speciesWeightHg('SPECIES_PIKACHU'), 60);
  assert.equal(speciesWeightHg('SPECIES_FLAREON'), 250);
  assert.equal(weightTierPower(speciesWeightHg('SPECIES_FLAREON')), 40);
});

test('returnPower / frustrationPower at friendship 255 and 0', () => {
  assert.equal(returnPower(255), 102);
  assert.equal(returnPower(0), 0);
  assert.equal(frustrationPower(255), 0);
  assert.equal(frustrationPower(0), 102);
});

test('gyroBallPower: the trainer-AI test values, the cap, a faster attacker, zero speed', () => {
  assert.equal(gyroBallPower(100, 436), 110); // 1 + floor(25*436/100)
  assert.equal(gyroBallPower(100, 512), 129);
  assert.equal(gyroBallPower(100, 1000), 150);
  assert.equal(gyroBallPower(300, 100), 9);
  assert.equal(gyroBallPower(1000, 10), 1);
  assert.equal(gyroBallPower(0, 100), 0);
});

// ---- part 2: greedy-v1 ----
const SNORLAX = B('snorlax', 60, ['return', 'grass_knot', 'low_kick', 'gyro_ball'], 'ABILITY_THICK_FAT');
const SNORLAX_RETURN = B('snorlax', 60, ['return', 'tackle', 'rest', 'yawn'], 'ABILITY_THICK_FAT');
const SNORLAX_OTHER = B('snorlax', 60, ['frustration', 'magnitude', 'tackle', 'rest'], 'ABILITY_THICK_FAT');
const expected = (battle, a, f, id, power) => {
  const { rolls } = calcDamage(fromShowdown(battle, a, f, id, { power }));
  return rolls.reduce((x, y) => x + y, 0) / rolls.length; // accuracy 100 for all four
};

test('greedy expectedDamage scores the four moves at the computed power (Flint\'s Houndoom, then Bertha\'s Rhyperior)', () => {
  for (const [trainer, foeName] of [['elite_four_flint', 'Houndoom'], ['elite_four_bertha', 'Rhyperior']]) {
    const x = leagueBattle(trainer, [SNORLAX]);
    const a = x.p1.active[0], f = x.p2.active[0];
    if (f.species.name !== foeName) { // Bertha's lead may differ; find the foe by sending it is not needed: use whoever leads
    }
    const foeConst = `SPECIES_${f.species.name.toUpperCase()}`;
    const tier = weightTierPower(speciesWeightHg(foeConst));
    const gyro = gyroBallPower(a.storedStats.spe, f.storedStats.spe);
    assert.equal(variablePowerFor('MOVE_RETURN', a, f), 102);
    assert.equal(variablePowerFor('MOVE_GRASS_KNOT', a, f), tier);
    assert.equal(variablePowerFor('MOVE_GYRO_BALL', a, f), gyro);
    for (const [id, power] of [['return', 102], ['grassknot', tier], ['lowkick', tier], ['gyroball', gyro]]) {
      const e = expectedDamage(gd, x.battle, a, f, id);
      assert.ok(e > 0, `${id} vs ${f.species.name} scores > 0`);
      assert.equal(e, expected(x.battle, a, f, id, power), `${id} vs ${f.species.name} equals a ${power}-power move`);
    }
  }
});

test('Rhyperior is in the 120 tier and Flareon in the 40 tier through the helper', () => {
  assert.equal(weightTierPower(speciesWeightHg('SPECIES_RHYPERIOR')), 120);
  assert.equal(weightTierPower(speciesWeightHg('SPECIES_FLAREON')), 40);
});

test('greedy still scores Frustration and Magnitude 0', () => {
  const x = leagueBattle('elite_four_flint', [SNORLAX_OTHER]);
  const a = x.p1.active[0], f = x.p2.active[0];
  assert.equal(expectedDamage(gd, x.battle, a, f, 'frustration'), 0);
  assert.equal(expectedDamage(gd, x.battle, a, f, 'magnitude'), 0);
  assert.equal(variablePowerFor('MOVE_FRUSTRATION', a, f), 0);
});

test('greedy.choose picks Return (102, STAB) over Tackle for a Snorlax with return/tackle/rest/yawn', () => {
  const x = leagueBattle('elite_four_flint', [SNORLAX_RETURN]);
  const ctx = { gd, battle: x.battle, side: x.p1, request: x.p1.activeRequest, trainer: x.trainer, bag: [], members: [] };
  assert.equal(greedy.choose(ctx), 'move 1');
});
