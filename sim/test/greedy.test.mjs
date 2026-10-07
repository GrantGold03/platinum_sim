// T049: `greedy-v1` player policy (sim/policy/greedy.mjs).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGameData, speciesRecord } from '../gamedata.mjs';
import { PLACEHOLDER, PLAYER_POLICIES, runGauntlet } from '../gauntlet.mjs';
import { GREEDY, expectedDamage, greedy, moveScores } from '../policy/greedy.mjs';
import { newBattle, playerMember } from '../team.mjs';

const gd = loadGameData();
const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];
const B = (species, level, moves, ability, held_item = null) => ({ species, start_level: level, moves, ability, held_item, nature: 'Hardy' });
// Opponent member in the shape of team.mjs opponentMembers(): IV 30, EV 0, given nature/ability.
const opp = (species, level, moves, ability, gender, slot = 0) => ({
  slot, rec: speciesRecord(gd, species), level, moves, ability, nature: 'NATURE_HARDY',
  ivs: Object.fromEntries(STATS.map((k) => [k, 30])), evs: Object.fromEntries(STATS.map((k) => [k, 0])),
  itemRec: null, gender, pp: moves.map((k) => gd.moves[k].pp),
});
const battleOf = (builds, opponent) => {
  const player = builds.map((b, i) => playerMember(gd, b, i));
  return newBattle(gd, { seed: 'sodium,' + 'c'.repeat(32), player, opponent });
};
const ctx = (battle) => ({ gd, battle, side: battle.sides[0], request: battle.sides[0].activeRequest });

test('greedy-v1 is registered next to placeholder-default', () => {
  assert.ok(PLAYER_POLICIES.has(GREEDY));
  assert.ok(PLAYER_POLICIES.has(PLACEHOLDER));
});

// Hand calculation (decomp formula, every step an integer op as in the C):
//   Gyarados L60, Hardy, IV 15, EV 85 (playerMember defaults, FR-008):
//     base SpA 60 (PP/res/pokemon/gyarados/data.json:7), types Water/Flying (:10)
//     SpA = (2*60 + 15 + 85/4) * 60/100 + 5 = 156*60/100 + 5 = 93 + 5 = 98   (PP/src/pokemon.c:564-645)
//   Togekiss L60, Hardy, IV 30, EV 0:
//     base SpD 115 (PP/res/pokemon/togekiss/data.json:8), types Normal/Flying (:10)
//     SpD = (2*115 + 30) * 60/100 + 5 = 260*60/100 + 5 = 156 + 5 = 161
//   level factor = 60*2/5 + 2 = 26                                          (battle_lib.c:6961/7007)
//   Hydro Pump: special, Water, power 120, accuracy 80 (PP/res/moves/hydro_pump/data.json:9-12)
//     base = 98*120*26/161/50 + 2 = 305760/161 = 1899 -> /50 = 37 -> +2 = 39
//     variance r = 39*(85..100)/100 = 33,33,33,34,34,35,35,35,36,36,37,37,37,38,38,39
//     STAB x*15/10 (Gyarados is Water) = 49,49,49,51,51,52,52,52,54,54,55,55,55,57,57,58
//     Water has no chart entry vs Normal or Flying (battle_lib.c:2410-2415) -> neutral
//     sum = 850, mean = 53.125, x 0.80 = 42.5
//   Surf: special, Water, power 95, accuracy 100 (PP/res/moves/surf/data.json:10-13)
//     base = 98*95*26/161/50 + 2 = 242060/161 = 1503 -> /50 = 30 -> +2 = 32
//     variance = 27,27,27,28,28,28,29,29,29,30,30,30,31,31,31,32
//     STAB = 40,40,40,42,42,42,43,43,43,45,45,45,46,46,46,48
//     sum = 696, mean = 43.5, x 1.00 = 43.5
//   Earthquake: Ground vs Flying is TYPE_MULTI_IMMUNE (battle_lib.c:2459) -> 0
//   Dragon Dance: CLASS_STATUS, power 0 (PP/res/moves/dragon_dance/data.json:10-12) -> 0
// So greedy picks Surf (43.5) over Hydro Pump (42.5), although the nominal power x accuracy
// (96 vs 95) favours Hydro Pump; Hydro Pump sits in slot 1 so slot order cannot explain the pick.
test('hand-computed position: Surf beats Hydro Pump on expected damage', () => {
  const battle = battleOf(
    [B('gyarados', 60, ['hydro_pump', 'earthquake', 'dragon_dance', 'surf'], 'ABILITY_INTIMIDATE')],
    [opp('togekiss', 60, ['tackle'], 'ABILITY_SERENE_GRACE', 'F')],
  );
  const c = ctx(battle);
  assert.equal(battle.sides[0].active[0].storedStats.spa, 98);
  assert.equal(battle.sides[1].active[0].storedStats.spd, 161);
  assert.deepEqual(moveScores(gd, battle, c.side, c.request), [42.5, 0, 0, 43.5]);
  assert.equal(greedy.choose(c), 'move 4');
});

test('forced switch goes to the living bench member with the best expected damage', () => {
  // Lead Magikarp L2 (Splash) is KO'd by the foe's Waterfall; bench: Roserade (Energy Ball,
  // Grass vs Water/Flying = neutral), Magnezone and Jolteon (Thunderbolt, Electric vs
  // Water/Flying = 4x, battle_lib.c type chart).
  const builds = [
    B('magikarp', 2, ['splash'], 'ABILITY_SWIFT_SWIM'),
    B('roserade', 60, ['energy_ball'], 'ABILITY_NATURAL_CURE'),
    B('magnezone', 60, ['thunderbolt'], 'ABILITY_MAGNET_PULL'),
    B('jolteon', 50, ['thunderbolt'], 'ABILITY_VOLT_ABSORB'),
  ];
  const run = (faintMagnezone) => {
    const battle = battleOf(builds, [opp('gyarados', 60, ['waterfall'], 'ABILITY_INTIMIDATE', 'M')]);
    const side = battle.sides[0];
    if (faintMagnezone) { side.pokemon[2].hp = 0; side.pokemon[2].fainted = true; }
    battle.makeChoices('move 1', 'move 1');
    assert.equal(side.requestState, 'switch', 'Magikarp fainted -> forced switch');
    const foe = battle.sides[1].active[0];
    const score = (i) => Math.max(...side.pokemon[i].moveSlots.map((s) => expectedDamage(gd, battle, side.pokemon[i], foe, s.id)));
    return { choice: greedy.choose(ctx(battle)), scores: [1, 2, 3].map(score) };
  };
  const a = run(false);
  // Positive control: Magnezone is the overall best, and the choice is not Showdown's default
  // (first legal switch = slot 2).
  assert.ok(a.scores[1] > a.scores[2] && a.scores[2] > a.scores[0], JSON.stringify(a.scores));
  assert.equal(a.choice, 'switch 3');
  const b = run(true);
  assert.equal(b.choice, 'switch 4', 'fainted Magnezone is skipped; Jolteon is next best');
});

const SMOKE = [
  B('garchomp', 62, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL', 'lucky_egg'),
  B('lucario', 60, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST'),
  B('gyarados', 60, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
  B('alakazam', 60, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE', 'exp_share'),
  B('magnezone', 60, ['thunderbolt', 'flash_cannon', 'tri_attack', 'thunder_wave'], 'ABILITY_MAGNET_PULL'),
  B('roserade', 60, ['energy_ball', 'sludge_bomb', 'shadow_ball', 'extrasensory'], 'ABILITY_NATURAL_CURE'),
];

test('full gauntlet end-to-end with greedy-v1 (opponents placeholder-default)', () => {
  const req = { team: SMOKE, seed: 'sodium,' + 'd'.repeat(32), player_policy: GREEDY, opponent_policy: PLACEHOLDER, stop_on_loss: false, log: 'summary' };
  const r = runGauntlet(gd, req);
  assert.equal(r.player_policy, GREEDY);
  assert.equal(r.opponent_policy, PLACEHOLDER);
  assert.equal(r.battles.length, 5);
  assert.ok(r.battles.every((b) => ['win', 'loss', 'tie', 'turn_limit'].includes(b.end)));
  // deterministic
  assert.equal(JSON.stringify(runGauntlet(gd, req)), JSON.stringify(r));
  // Positive control: the policy actually changes play vs placeholder-default on the same seed.
  const p = runGauntlet(gd, { ...req, player_policy: PLACEHOLDER });
  assert.notDeepEqual(p.battles.map((b) => b.log_hash), r.battles.map((b) => b.log_hash));
});
