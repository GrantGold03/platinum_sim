// Feature 010 T007: greedy-v2 equals greedy-v1 except that it scores the offered variable-power attacks
// (Return, Grass Knot, Low Kick, Gyro Ball) at their real power. On a team without them the two players
// must play byte-identical gauntlets; on a team with Return they must differ (positive control).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { runGauntlet } from '../gauntlet.mjs';
import { DECOMP_AI } from '../ai/opponent.mjs';
import { B, gd } from './ai_fixtures.mjs';

const TEAM = [ // sim/test/ai_gauntlet.test.mjs: no variable-power attack
  B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL', 'lucky_egg'),
  B('lucario', 56, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST'),
  B('gyarados', 56, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('alakazam', 56, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE', 'exp_share'),
  B('magnezone', 56, ['thunderbolt', 'flash_cannon', 'tri_attack', 'thunder_wave'], 'ABILITY_MAGNET_PULL'),
  B('roserade', 56, ['energy_ball', 'sludge_bomb', 'shadow_ball', 'extrasensory'], 'ABILITY_NATURAL_CURE'),
];
// Same team with Return (Garchomp) and Grass Knot (Roserade) in place of a weaker move.
const VP_TEAM = TEAM.map((b, i) => (i === 0 ? B('garchomp', 58, ['earthquake', 'dragon_claw', 'return', 'fire_fang'], 'ABILITY_SAND_VEIL', 'lucky_egg')
  : i === 5 ? B('roserade', 56, ['grass_knot', 'sludge_bomb', 'shadow_ball', 'extrasensory'], 'ABILITY_NATURAL_CURE') : b));
const N = 30;
const req = (team, policy, i) => ({ team, seed: `greedy-v2-${i}`, player_policy: policy, opponent_policy: DECOMP_AI,
  stop_on_loss: false, log: 'summary' });
const digest = (r) => { const { player_policy, ...rest } = r; return createHash('sha256').update(JSON.stringify(rest)).digest('hex'); };

test('greedy-v2 plays exactly like greedy-v1 on a team without variable-power attacks', () => {
  for (let i = 0; i < N; i++) {
    const a = runGauntlet(gd, req(TEAM, 'greedy-v1', i));
    const b = runGauntlet(gd, req(TEAM, 'greedy-v2', i));
    assert.equal(a.player_policy, 'greedy-v1');
    assert.equal(b.player_policy, 'greedy-v2');
    assert.equal(digest(b), digest(a), `seed ${i}`);
  }
});

test('greedy-v2 uses Return and Grass Knot where greedy-v1 scores them 0 (positive control)', () => {
  let differ = 0;
  for (let i = 0; i < N; i++) {
    if (digest(runGauntlet(gd, req(VP_TEAM, 'greedy-v1', i))) !== digest(runGauntlet(gd, req(VP_TEAM, 'greedy-v2', i)))) differ++;
  }
  assert.ok(differ > N / 2, `only ${differ}/${N} gauntlets differ`);
});
