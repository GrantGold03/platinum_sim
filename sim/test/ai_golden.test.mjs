// T048 golden positions: hand-built League positions where the trainer AI's choice is walked through
// line by line in pokeplatinum/src/battle/trainer_ai/script.s (S below) and trainer_ai.c (TAI).
//
// Every fixture uses the scripted RNG `stubRng([], 255)`: every BattleSystem_RandNext returns 255,
// so in the script
//   IfRandomLessThan N   jumps iff 255 % 256 < N  -> never (N <= 255): the "chance" bonus/penalty
//                        that follows the test is always APPLIED;
//   damage rolls         100 - 255 % 16 = 85 (TAI:240) — only used by the varied-damage commands,
//                        none of which the League sections use (all USE_MAX_DAMAGE = roll 100);
//   tie break            slot = ties[255 % n] (TAI:334); coin flips 255 & 1 = 1; % 3 = 0; % 10 = 5.
// The first 4 draws of every battle are speedRand[0..3] (BL:2024; opponent.mjs), so "draws" below
// counts the decision's draws only.
//
// Section entry points (FlagTable, S:15-18): flag 0 Basic_Main (S:52), 1 EvalAttack_Main (S:6353),
// 2 Expert_Main (S:1623), 3 SetupFirstTurn_Main (S:6417). Score-changing lines that recur:
//   S:68   Basic: IfMoveEffectivenessEquals TYPE_MULTI_IMMUNE, ScoreMinus10 -> S:1592 (-10)
//   S:6358 EvalAttack: IfCurrentMoveKills USE_MAX_DAMAGE -> kill bonus S:6412 (+4)
//   S:6361-6362 EvalAttack: FlagMoveDamageScore; IfLoadedEqualTo AI_NOT_HIGHEST_DAMAGE -> S:1568 (-1)
// `dmg` is TrainerAI_CalcAllDamage at roll 100 for the AI's four moves (what S:6361 compares).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as calcdamage from '../ai/calcdamage.mjs';
import { afterTurn, decide, processLog } from '../ai/opponent.mjs';
import { postKOSwitchIn } from '../ai/switch.mjs';
import { aiProgram } from '../ai/choose.mjs';
import { B, leagueBattle, sendIn, setHP, stubRng } from './ai_fixtures.mjs';

const prog = aiProgram();
const K = (n) => prog.constants.get(n);
const GARCHOMP = B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL');

function maxDamage(st) {
  const ai = st.ai;
  const env = { ai, rand: () => 0, mem: { moveDamageRolls: [100, 100, 100, 100], monSpeedValues: st.monSpeedValues } };
  return calcdamage.calcAllDamage(env, { attacker: 1, moves: ai.moves(1), heldItem: ai.heldItem(1), ivs: ai.ivs(1),
    ability: ai.battlerAbility(1), embargoTurns: 0, varyDamage: 0 }).damageVals;
}
const compact = (trace) => trace.map((t) => [t.flagBit, t.slot, t.line, t.add]);

function runFixture(fx) {
  const x = leagueBattle(fx.trainer, fx.player, { rng: stubRng([], 255) });
  fx.setup?.(x);
  const before = x.st.rng.draws;
  const r = decide(x.st, x.p2, { trace: true });
  return { x, r, draws: x.st.rng.draws - before };
}

const FIXTURES = [
  {
    // A1. Aaron's Yanmega (Air Slash, Bug Buzz, U-turn, Double Team) vs Alakazam, turn 1.
    //  dmg [60, 140, 114, 0]: Bug Buzz is the max -> Air Slash and U-turn get S:6362 -> S:1568 (-1).
    //  Expert U-turn (S:5100-5145): Bug Buzz is SE vs Psychic (IfHasSuperEffectiveMove) ->
    //    S:5114 IfRandomLessThan 64 falls through -> S:5115 -2; IfPartyMemberDealsMoreDamage jumps
    //    (a bench member out-damages Yanmega) -> target HP > 70% -> S:5130 IfRandomLessThan 64 falls ->
    //    S:5131 +1; S:5134 IfRandomLessThan 128 falls -> S:5135 +1; speed/coin -> S:5142 +1.
    //  Expert Double Team = Expert_StatusEvasionUp (S:2184): HP >= 90%, S:2204 IfRandomLessThan 100
    //    falls -> S:2205 +3; evasion stage 6 < 9 and no other condition adds.
    //  Scores [99, 100, 100-1-2+1+1+1 = 100, 103] -> Double Team (slot 3).
    name: 'A1 Aaron Yanmega turn 1 -> Double Team', trainer: 'elite_four_aaron',
    player: [B('alakazam', 56, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE')],
    dmg: [60, 140, 114, 0], scores: [99, 100, 100, 103], choice: 'move 4', draws: 20,
    trace: [[1, 0, 1568, -1], [1, 2, 1568, -1], [2, 2, 5115, -2], [2, 2, 5131, 1], [2, 2, 5135, 1], [2, 2, 5142, 1], [2, 3, 2205, 3]],
  },
  {
    // A2. Aaron's Drapion (X-Scissor, Cross Poison, Ice Fang, Aerial Ace) vs Gengar (Ghost/Poison).
    //  dmg [12, 15, 39, 36]: X-Scissor (Bug: NVE vs Ghost and vs Poison), Cross Poison (NVE vs
    //  Poison and Ghost) and Aerial Ace fall short of Ice Fang -> each S:1568 -1. No Expert change.
    //  Scores [99, 99, 100, 99] -> Ice Fang.
    name: 'A2 Aaron Drapion vs Gengar -> Ice Fang', trainer: 'elite_four_aaron',
    player: [B('gengar', 56, ['shadow_ball', 'focus_blast', 'thunderbolt', 'hypnosis'], 'ABILITY_LEVITATE')],
    setup: (x) => sendIn(x.battle, x.p2, 4),
    dmg: [12, 15, 39, 36], scores: [99, 99, 100, 99], choice: 'move 3', draws: 5,
    trace: [[1, 0, 1568, -1], [1, 1, 1568, -1], [1, 3, 1568, -1]],
  },
  {
    // B1. Bertha's Whiscash (Earth Power, Aqua Tail, Zen Headbutt, Sandstorm) vs Gyarados.
    //  Earth Power: Ground vs Flying is immune -> S:68 -> S:1592 -10; EvalAttack then sees 0 < 22 ->
    //  S:1568 -1. Aqua Tail 18 < 22 -> -1. Sandstorm: no Basic/Expert change here.
    //  Scores [89, 99, 100, 100], ties [2, 3] -> 255 % 2 = 1 -> slot 3 (Sandstorm).
    name: 'B1 Bertha Whiscash vs Gyarados -> tie broken to Sandstorm', trainer: 'elite_four_bertha',
    player: [B('gyarados', 56, ['waterfall', 'ice_fang', 'earthquake', 'dragon_dance'], 'ABILITY_INTIMIDATE')],
    dmg: [0, 18, 22, 0], scores: [89, 99, 100, 100], choice: 'move 4', draws: 5,
    trace: [[0, 0, 1592, -10], [1, 0, 1568, -1], [1, 1, 1568, -1]],
  },
  {
    // B2. Bertha's Rhyperior (Earthquake, Rock Wrecker, Megahorn, Avalanche) vs Empoleon 180 HP.
    //  Earthquake max 228 >= 180 -> S:6358 jumps to EvalAttack_ApplyKillBonuses; effect is not a
    //  +1-priority one -> GoTo EvalAttack_ScorePlus4 -> S:6412 +4.
    //  Rock Wrecker: recharge effect (sNoDamageCalcMoveEffects, TAI:31) -> no comparison; Expert
    //    recharge turn routine -> S:3070 -1 (HP > 40% / not slower branch).
    //  Megahorn 45 and Avalanche 11 < 228 -> -1 each; Avalanche = Expert_Revenge (S:4542): target not
    //    asleep/attracted/confused, S:4549 IfRandomLessThan 180 falls -> S:4550 +2.
    //  Scores [104, 99, 99, 101] -> Earthquake.
    name: 'B2 Bertha Rhyperior KO bonus -> Earthquake', trainer: 'elite_four_bertha',
    player: [B('empoleon', 56, ['surf', 'ice_beam', 'grass_knot', 'agility'], 'ABILITY_TORRENT')],
    setup: (x) => sendIn(x.battle, x.p2, 4),
    dmg: [228, 0, 45, 11], scores: [104, 99, 99, 101], choice: 'move 1', draws: 8,
    trace: [[1, 0, 6412, 4], [1, 2, 1568, -1], [1, 3, 1568, -1], [2, 1, 3070, -1], [2, 3, 4550, 2]],
  },
  {
    // F1. Flint's Houndoom (Flamethrower, Sludge Bomb, Dark Pulse, Sunny Day) vs Vaporeon.
    //  dmg [33, 42, 57, 0] -> Flamethrower and Sludge Bomb -1. Sunny Day: Basic_CheckSunnyDay (S:803):
    //  Early Bird is none of S:807-809; Vaporeon is not Hydration (S:814) -> S:819-820 sun not up -> no
    //  change. Expert (S:3782-3789): HP not < 40%, no weather, Early Bird is not Flower Gift and not
    //  Leaf Guard -> Expert_SunnyDay_End, no change.
    //  Scores [99, 99, 100, 100], ties [2, 3] -> 255 % 2 = 1 -> Sunny Day.
    name: 'F1 Flint Houndoom vs Vaporeon -> tie broken to Sunny Day', trainer: 'elite_four_flint',
    player: [B('vaporeon', 56, ['surf', 'ice_beam', 'wish', 'protect'], 'ABILITY_WATER_ABSORB')],
    dmg: [33, 42, 57, 0], scores: [99, 99, 100, 100], choice: 'move 4', draws: 13,
    trace: [[1, 0, 1568, -1], [1, 1, 1568, -1]],
  },
  {
    // F2. Flint's Flareon (Overheat, Giga Impact, Quick Attack, Will-O-Wisp) vs Heatran.
    //  Heatran's only ability is Flash Fire, so LoadBattlerAbility DEFENDER needs no coin flip:
    //  Overheat: S:75 IfLoadedEqualTo ABILITY_FLASH_FIRE -> Basic_CheckFireAbsorption (S:91) ->
    //  move type Fire -> ScoreMinus12 (S:1596) -12.
    //  Will-O-Wisp: Basic_CheckCannotBurn (S:879): defender type 1 is Fire (S:885-886) -> S:1592 -10.
    //  Quick Attack 12 < Overheat 90 -> -1. Giga Impact (recharge) -> Expert S:3070 -1.
    //  Scores [88, 99, 99, 90], ties [1, 2] -> 255 % 2 = 1 -> Quick Attack.
    name: 'F2 Flint Flareon vs Flash Fire Heatran -> Quick Attack', trainer: 'elite_four_flint',
    player: [B('heatran', 56, ['flamethrower', 'earth_power', 'dragon_pulse', 'stealth_rock'], 'ABILITY_FLASH_FIRE')],
    setup: (x) => sendIn(x.battle, x.p2, 1),
    dmg: [90, 0, 12, 0], scores: [88, 99, 99, 90], choice: 'move 3', draws: 5,
    trace: [[0, 0, 1596, -12], [0, 3, 1592, -10], [1, 2, 1568, -1], [2, 1, 3070, -1]],
  },
  {
    // L1. Lucian (SETUP_FIRST_TURN) Mr. Mime (Psychic, Thunderbolt, Reflect, Light Screen) vs
    //  Garchomp, turn 1 (totalTurns 0).
    //  Thunderbolt: Electric vs Ground immune -> S:68 -> -10, then EvalAttack 0 < 66 -> -1.
    //  Expert_Reflect (S:2893): HP >= 90%, S:2901 IfRandomLessThan 128 falls -> S:2902 +1; then
    //    LoadDefenderLastUsedMoveClass reads MOVE_NONE's class, which is CLASS_PHYSICAL
    //    (res/moves/none/data.json:9) -> S:2907 IfRandomLessThan 64 falls -> S:2908 +1.
    //  Expert_LightScreen: S:2718 falls -> S:2719 +1; MOVE_NONE is not CLASS_SPECIAL -> no more.
    //  SetupFirstTurn_Main: LoadTurnCount = 0 (S:6421-6422); Reflect (SET_REFLECT) and Light Screen
    //    (SET_LIGHT_SCREEN) are in SetupFirstTurn_SetupEffects; S:6429 IfRandomLessThan 80 falls ->
    //    S:6430 +2 each. Psychic (BATTLE_EFFECT_SP_DEF_DOWN_HIT) is not in the table.
    //  Scores [100, 89, 104, 103] -> Reflect.
    name: 'L1 Lucian Mr. Mime turn 1: SETUP_FIRST_TURN -> Reflect', trainer: 'elite_four_lucian', player: [GARCHOMP],
    dmg: [66, 0, 0, 0], scores: [100, 89, 104, 103], choice: 'move 3', draws: 10,
    trace: [[0, 1, 1592, -10], [1, 1, 1568, -1], [2, 2, 2902, 1], [2, 2, 2908, 1], [2, 3, 2719, 1], [3, 2, 6430, 2], [3, 3, 6430, 2]],
  },
  {
    // L2. Same position on turn 2 (battle.turn 2 -> totalTurns 1): S:6422 IfLoadedNotEqualTo 0 ->
    //  SetupFirstTurn_Terminate, so the two +2 are gone and their two draws are not made.
    //  Scores [100, 89, 102, 101] -> still Reflect.
    name: 'L2 Lucian Mr. Mime turn 2: no first-turn bonus', trainer: 'elite_four_lucian', player: [GARCHOMP],
    setup: (x) => { x.battle.turn = 2; },
    dmg: [66, 0, 0, 0], scores: [100, 89, 102, 101], choice: 'move 3', draws: 8,
    trace: [[0, 1, 1592, -10], [1, 1, 1568, -1], [2, 2, 2902, 1], [2, 2, 2908, 1], [2, 3, 2719, 1]],
  },
  {
    // L3. Lucian's Bronzong (Psychic, Gyro Ball, Earthquake, Calm Mind) vs Infernape, turn 1.
    //  dmg [132, 24, 106, 0] -> Gyro Ball and Earthquake -1.
    //  Calm Mind (SP_ATK_SP_DEF_UP) in Expert: SpDef stage 6 < 9 -> CheckUserAtMaxHP: HP 100%,
    //    S:2132 IfRandomLessThan 128 falls -> S:2133 +2; HP >= 70%: S:2137 IfRandomLessThan 200 falls;
    //    LoadBattlerPreviousMove (MOVE_NONE) power 0 -> UserAtLowHP: S:2149 IfRandomLessThan 60 falls
    //    -> S:2152 -2. SetupFirstTurn: in the table -> S:6430 +2.
    //  Scores [100, 99, 99, 102] -> Calm Mind.
    name: 'L3 Lucian Bronzong turn 1 -> Calm Mind', trainer: 'elite_four_lucian',
    player: [B('infernape', 56, ['flamethrower', 'close_combat', 'grass_knot', 'nasty_plot'], 'ABILITY_BLAZE')],
    setup: (x) => sendIn(x.battle, x.p2, 2),
    dmg: [132, 24, 106, 0], scores: [100, 99, 99, 102], choice: 'move 4', draws: 11,
    trace: [[1, 1, 1568, -1], [1, 2, 1568, -1], [2, 3, 2133, 2], [2, 3, 2152, -2], [3, 3, 6430, 2]],
  },
  {
    // C1. Cynthia's Spiritomb (Dark Pulse, Psychic, Silver Wind, Shadow Ball) vs Lucario.
    //  dmg [19, 58, 9, 39]: Psychic is the max; the other three -1. Scores [99, 100, 99, 99].
    name: 'C1 Cynthia Spiritomb vs Lucario -> Psychic', trainer: 'champion_cynthia',
    player: [B('lucario', 56, ['aura_sphere', 'dark_pulse', 'dragon_pulse', 'extreme_speed'], 'ABILITY_STEADFAST')],
    dmg: [19, 58, 9, 39], scores: [99, 100, 99, 99], choice: 'move 2', draws: 13,
    trace: [[1, 0, 1568, -1], [1, 2, 1568, -1], [1, 3, 1568, -1]],
  },
  {
    // C2. Cynthia's Garchomp (Dragon Rush, Earthquake, Flamethrower, Giga Impact) vs Dragonite at 40 HP.
    //  Dragon Rush max 228 >= 40 -> S:6412 +4. Earthquake immune (Flying) -> -10 and -1.
    //  Flamethrower 23 -> -1. Giga Impact: recharge, no damage comparison, Expert S:3070 -1.
    //  Scores [104, 89, 99, 99] -> Dragon Rush.
    name: 'C2 Cynthia Garchomp KO bonus -> Dragon Rush', trainer: 'champion_cynthia',
    player: [B('dragonite', 55, ['outrage', 'fire_punch', 'thunder_punch', 'roost'], 'ABILITY_INNER_FOCUS')],
    setup: (x) => { sendIn(x.battle, x.p2, 5); setHP(x.p1.active[0], 40); },
    dmg: [228, 0, 23, 0], scores: [104, 89, 99, 99], choice: 'move 1', draws: 7,
    trace: [[0, 1, 1592, -10], [1, 0, 6412, 4], [1, 1, 1568, -1], [1, 2, 1568, -1], [2, 3, 3070, -1]],
  },
  {
    // C3. Full Restore at 24%: Cynthia's Milotic at 46/195 (195 / 4 = 48) vs Garchomp.
    //  TrainerAI_PickCommand: ShouldSwitch -> HasAbsorbAbilityInParty: Ice Beam is SE so
    //  AI_HasSuperEffectiveMove(TRUE) is TRUE and 255 % 3 = 0 (not != 0) -> continue; moveHit NONE ->
    //  FALSE (1 draw). AI_HasSuperEffectiveMove(FALSE): Surf is not SE, Ice Beam is: 255 % 10 = 5
    //  != 0 -> TRUE -> do not switch (1 draw). ShouldUseItem: 6 alive, slot 0 Full Restore,
    //  46 < 48 and 46 != 0 -> use; slots 1-3 not examined (6 <= 4 - i + 1 is false).
    name: 'C3 Cynthia Milotic at 24% -> Full Restore', trainer: 'champion_cynthia', player: [GARCHOMP],
    setup: (x) => { const m = sendIn(x.battle, x.p2, 4); setHP(m, 46); },
    kind: 'item', choice: 'move 5', draws: 2,
  },
  {
    // C4. Same at 26% (51/195): 51 >= 48 -> no item -> FIGHT -> TrainerAI_Main.
    //  Ice Beam max damage kills Garchomp (4x) -> S:6412 +4; Surf and Dragon Pulse -1;
    //  Mirror Coat in Expert (S:3852): HP 26% <= 30%: S:3873 IfRandomLessThan 10 falls -> S:3874 -1;
    //  HP <= 50%: S:3878 IfRandomLessThan 100 falls -> S:3879 -1. Scores [99, 104, 98, 99] -> Ice Beam.
    name: 'C4 Cynthia Milotic at 26% -> no item, Ice Beam', trainer: 'champion_cynthia', player: [GARCHOMP],
    setup: (x) => { const m = sendIn(x.battle, x.p2, 4); setHP(m, 51); },
    scores: [99, 104, 98, 99], choice: 'move 2', draws: 2 + 4 + 2 + 1,
    trace: [[1, 0, 1568, -1], [1, 1, 6412, 4], [1, 3, 1568, -1], [2, 2, 3874, -1], [2, 2, 3879, -1]],
  },
];

for (const fx of FIXTURES) {
  test(`golden ${fx.name}`, () => {
    const { x, r, draws } = runFixture(fx);
    if (fx.dmg) assert.deepEqual(maxDamage(x.st), fx.dmg, 'AI damage estimates (roll 100)');
    assert.equal(r.kind, fx.kind ?? 'move');
    assert.equal(r.choice, fx.choice);
    if (fx.scores) assert.deepEqual(r.detail.scores, fx.scores);
    if (fx.trace) assert.deepEqual(compact(r.detail.trace), fx.trace);
    assert.equal(draws, fx.draws, 'RNG draws in this decision');
  });
}

test('golden P1 post-KO switch-in (Flint vs Scizor, u8 overflow) -> Infernape', () => {
  // Walkthrough in ai_switch.test.mjs ("stage 1 keeps the u8 overflow bug"): stage-1 scores
  // Flareon 64, Rapidash 64, Infernape 200, Magmortar 64; Infernape's Flare Blitz is SE -> slot 3.
  const x = leagueBattle('elite_four_flint', [B('scizor', 56, ['bullet_punch', 'x_scissor', 'swords_dance', 'roost'], 'ABILITY_TECHNICIAN')], { rng: stubRng([], 255) });
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1');
  const r = decide(x.st, x.p2);
  assert.equal(r.kind, 'replacement');
  assert.equal(r.detail.slot, 3);
  x.battle.makeChoices('', r.choice);
  assert.equal(x.p2.active[0].species.name, 'Infernape');
});

test('golden P2 post-KO stage 2 (Cynthia vs Spiritomb) -> Lucario by u8 damage', () => {
  // No stage-1 pick has a SE move vs Ghost/Dark; stage 2's best u8 score is Lucario's Shadow Ball.
  const x = leagueBattle('champion_cynthia', [B('spiritomb', 56, ['shadow_sneak', 'dark_pulse', 'will_o_wisp', 'sucker_punch'], 'ABILITY_PRESSURE')], { rng: stubRng([], 255) });
  setHP(x.p2.active[0], 1);
  x.battle.makeChoices('move 1', 'move 1');
  const trace = [];
  x.st.aiSwitchedPartySlot = [6, 6, 6, 6];
  assert.equal(postKOSwitchIn(x.st, 1, trace), 3);
  const best = trace.filter((t) => t.stage === 2 && t.slot === 3 && t.move === K('MOVE_SHADOW_BALL'))[0];
  assert.equal(best.score, Math.max(...trace.filter((t) => t.stage === 2).map((t) => t.score)));
});

test('golden S1 Flint Houndoom hit by Fire switches to Flash Fire Flareon (switch before item)', () => {
  // Walkthrough in ai_switch.test.mjs (AI_HasAbsorbAbilityInParty). One draw: RandNext & 1 = 1.
  const x = leagueBattle('elite_four_flint', [B('camerupt', 56, ['flamethrower', 'earth_power', 'yawn', 'rock_slide'], 'ABILITY_SOLID_ROCK')], { rng: stubRng([], 255) });
  x.battle.makeChoices('move 1', 'move 4');
  const before = x.st.rng.draws;
  const r = decide(x.st, x.p2);
  assert.deepEqual([r.kind, r.detail.slot, x.st.rng.draws - before], ['switch', 1, 1]);
});

test('golden T1 Taunt + Full Restore (Cynthia Roserade taunted at 20 HP) -> item, healed in battle', () => {
  // ShouldSwitch: Roserade vs Gyarados has no SE move (Energy Ball: Grass SE vs Water, NVE vs Flying
  // -> cancel); moveHit is NONE or Taunt (power 0), so the absorb / party checks return FALSE;
  // HasSuperEffectiveMove(FALSE) FALSE; not boosted -> no switch. ShouldUseItem: 20 < 155 / 4 = 38 -> Full Restore. Taunt does not apply to
  // bag items in the game; the pseudo-move runs in beforeTurnCallback (sim/ai/patches.mjs).
  const x = leagueBattle('champion_cynthia', [B('gyarados', 56, ['taunt', 'dragon_dance'], 'ABILITY_INTIMIDATE')], { rng: stubRng([], 255) });
  const rose = sendIn(x.battle, x.p2, 1);
  x.battle.makeChoices('move 1', 'move 1');
  processLog(x.st);
  assert.ok(rose.volatiles.taunt);
  setHP(rose, 20);
  const r = decide(x.st, x.p2);
  assert.equal(r.kind, 'item');
  x.battle.makeChoices('move 2', r.choice);
  afterTurn(x.st);
  assert.equal(rose.hp, rose.maxhp);
});

test('golden E1 Encore: FIGHT under Encore uses the encored move without running TrainerAI_Main', () => {
  // battle_controller_player.c:430-438: encoredMove set -> moveSelected = encoredMove; no AI move
  // choice, so no Init rolls and no script draws. Wobbuffet's Shadow Tag traps Roserade
  // (ShouldSwitch FALSE at TAI:3906-3913 before any draw); HP full -> no item.
  const x = leagueBattle('champion_cynthia', [B('wobbuffet', 56, ['encore', 'counter', 'mirror_coat', 'safeguard'], 'ABILITY_SHADOW_TAG')], { rng: stubRng([], 255) });
  const rose = sendIn(x.battle, x.p2, 1);
  x.battle.makeChoices('move 1', 'move 3'); // Roserade Toxic, Wobbuffet Encore
  assert.ok(rose.volatiles.encore);
  const before = x.st.rng.draws;
  const r = decide(x.st, x.p2);
  assert.deepEqual([r.kind, r.choice, x.st.rng.draws - before], ['encore', 'move 3', 0]);
});
