// T048: sim/ai/switch.mjs — TrainerAI_ShouldSwitch (TAI:3894), BattleAI_PostKOSwitchIn (BL:7923-8089)
// with the u8 score overflow (pokeplatinum/docs/bugs_and_glitches.md:136-153), and the
// effectiveness helpers. TAI = src/battle/trainer_ai/trainer_ai.c, BL = src/battle/battle_lib.c.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle } from '../showdown.mjs';
import { TYPE_CHART, MOVE_STATUS } from '../damage.mjs';
import { calcEffectiveness, postKOSwitchIn, shouldSwitch, typeMatchupMultiplier } from '../ai/switch.mjs';
import { createAIState, decide, processLog } from '../ai/opponent.mjs';
import { aiProgram } from '../ai/choose.mjs';
import { B, leagueBattle, setHP, sendIn, stubRng } from './ai_fixtures.mjs';

const prog = aiProgram();
const K = (n) => prog.constants.get(n);
const row = (atk, def) => TYPE_CHART.entries.find((e) => e.atk === atk && e.def === def);

// A non-League battle for situations no League party produces (Wonder Guard, all-immune moves).
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, ability, extra = {}) => ({ species, moves, ability, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });
function customBattle(p1team, p2team, rng = stubRng([], 255)) {
  const battle = new Battle({ formatid: 'gen4customgame', seed: [1, 2, 3, 4], p1: { name: 'Player', team: p1team }, p2: { name: 'AI', team: p2team } });
  const st = createAIState(battle, { trainer: { ai_flags: ['AI_FLAG_BASIC', 'AI_FLAG_EVAL_ATTACK', 'AI_FLAG_EXPERT'], bag_items: [] }, rng });
  processLog(st);
  st.aiSwitchedPartySlot = [6, 6, 6, 6];
  return { battle, st, p1: battle.sides[0], p2: battle.sides[1] };
}

test('BattleSystem_TypeMatchupMultiplier (BL:3009-3029): 40 * mul / 10 per matching chart row', () => {
  // sTypeMatchupMultipliers rows (BL:2399+): Fighting>Rock x2, Fighting>Steel x2 -> 40*20/10*20/10 = 160
  assert.ok(row('TYPE_FIGHTING', 'TYPE_ROCK').mul === 20 && row('TYPE_FIGHTING', 'TYPE_STEEL').mul === 20);
  assert.equal(typeMatchupMultiplier(K('TYPE_FIGHTING'), K('TYPE_ROCK'), K('TYPE_STEEL')), 160);
  assert.equal(typeMatchupMultiplier(K('TYPE_FIRE'), K('TYPE_BUG'), K('TYPE_STEEL')), 160);
  assert.equal(typeMatchupMultiplier(K('TYPE_WATER'), K('TYPE_FIRE'), K('TYPE_FIRE')), 80); // mono-type defender counted once
  assert.equal(typeMatchupMultiplier(K('TYPE_ELECTRIC'), K('TYPE_GROUND'), K('TYPE_GROUND')), 0);
  // The 0xFE separator is not a type, so the Ghost immunities still apply (unlike Foresight):
  assert.equal(typeMatchupMultiplier(K('TYPE_NORMAL'), K('TYPE_GHOST'), K('TYPE_GHOST')), 0);
  assert.equal(typeMatchupMultiplier(K('TYPE_DARK'), K('TYPE_BUG'), K('TYPE_STEEL')), 20); // Dark>Steel x0.5
});

test('BattleSystem_CalcEffectiveness (BL:2681-2743): Levitate, chart order, Wonder Guard', () => {
  const { st } = leagueBattle('elite_four_aaron', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  const ai = st.ai;
  const base = { attackerAbility: K('ABILITY_NONE'), defenderItemEffect: 0 };
  const eff = (move, d1, d2, defAb = 'ABILITY_NONE') => calcEffectiveness(ai, { ...base, move: K(move), inType: 0, defenderAbility: K(defAb), defenderType1: K(d1), defenderType2: K(d2) });
  assert.equal(eff('MOVE_EARTHQUAKE', 'TYPE_STEEL', 'TYPE_PSYCHIC', 'ABILITY_LEVITATE'), MOVE_STATUS.INEFFECTIVE);
  assert.equal(eff('MOVE_STONE_EDGE', 'TYPE_WATER', 'TYPE_FLYING'), MOVE_STATUS.SUPER_EFFECTIVE); // Rock>Water has no row
  assert.equal(eff('MOVE_FLAMETHROWER', 'TYPE_FIRE', 'TYPE_STEEL'), 0); // NVE then SE cancel (BL:2790-2804)
  assert.equal(eff('MOVE_SURF', 'TYPE_GRASS', 'TYPE_DRAGON'), MOVE_STATUS.NOT_VERY_EFFECTIVE); // two NVE rows keep NVE
  assert.equal(eff('MOVE_TACKLE', 'TYPE_BUG', 'TYPE_GHOST', 'ABILITY_WONDER_GUARD') & MOVE_STATUS.INEFFECTIVE, MOVE_STATUS.INEFFECTIVE);
  assert.equal(eff('MOVE_FLAMETHROWER', 'TYPE_BUG', 'TYPE_GHOST', 'ABILITY_WONDER_GUARD'), MOVE_STATUS.SUPER_EFFECTIVE);
});

test('PostKOSwitchIn stage 1 keeps the u8 overflow bug: 320 becomes 64 (Flint vs Scizor)', () => {
  // Flint's party (res/trainers/data/elite_four_flint.json): 0 Houndoom (Dark/Fire), 1 Flareon (Fire),
  // 2 Rapidash (Fire), 3 Infernape (Fire/Fighting), 4 Magmortar (Fire). The player's Scizor
  // (Bug/Steel) KOs Houndoom with Bullet Punch. Stage 1 (BL:7958-7990), defender types Bug/Steel:
  //   Flareon:   TM(Fire)+TM(Fire) = 160 + 160 = 320 -> u8 64
  //   Rapidash:  64 (same)          Magmortar: 64 (same)
  //   Infernape: TM(Fire) 160 + TM(Fighting: Bug x0.5, Steel x2 -> 40*5/10*20/10 = 40) = 200
  // `maxScore < score` strictly, in party order -> Infernape (slot 3), and Flare Blitz is
  // super-effective (BL:7996-8021) -> return 3. With u32 scores (the documented fix) Flareon's
  // 320 would win and slot 1 would be returned.
  const { battle, st, p2 } = leagueBattle('elite_four_flint', [B('scizor', 56, ['bullet_punch', 'x_scissor', 'swords_dance', 'roost'], 'ABILITY_TECHNICIAN')], { rng: stubRng([], 255) });
  setHP(p2.active[0], 1);
  battle.makeChoices('move 1', 'move 1');
  assert.equal(p2.requestState, 'switch');
  const trace = [];
  st.aiSwitchedPartySlot = [6, 6, 6, 6];
  const slot = postKOSwitchIn(st, 1, trace);
  assert.deepEqual(trace.filter((t) => t.stage === 1).map((t) => [t.slot, t.score]), [[1, 64], [2, 64], [3, 200], [4, 64]]);
  assert.equal(slot, 3);
  // positive control: the unbugged sum for Flareon is 320 > 200
  assert.equal(typeMatchupMultiplier(K('TYPE_FIRE'), K('TYPE_BUG'), K('TYPE_STEEL')) * 2, 320);
  // the live decision sends Infernape (no RNG used by PostKOSwitchIn)
  const draws = st.rng.draws;
  const r = decide(st, p2);
  assert.equal(r.kind, 'replacement');
  assert.equal(p2.pokemon[Number(r.choice.split(' ')[1]) - 1].species.name, 'Infernape');
  assert.equal(st.rng.draws, draws);
});

test('PostKOSwitchIn stage 2: no stage-1 candidate has a super-effective move -> highest u8 damage (Cynthia vs Spiritomb)', () => {
  // Spiritomb (Ghost/Dark) has no weakness in Gen 4, so every stage-1 pick is disregarded
  // (BL:8015-8018) and stage 2 (BL:8032-8086) scores each move by
  // u8(CalcMoveDamage(attacker = the fainted Spiritomb's battle slot)) through ApplyTypeChart.
  const { battle, st, p2 } = leagueBattle('champion_cynthia', [B('spiritomb', 56, ['shadow_sneak', 'dark_pulse', 'will_o_wisp', 'sucker_punch'], 'ABILITY_PRESSURE')], { rng: stubRng([], 255) });
  setHP(p2.active[0], 1);
  battle.makeChoices('move 1', 'move 1');
  st.aiSwitchedPartySlot = [6, 6, 6, 6];
  const trace = [];
  const slot = postKOSwitchIn(st, 1, trace);
  const stage2 = trace.filter((t) => t.stage === 2);
  assert.ok(stage2.length > 0, 'stage 2 ran');
  const best = Math.max(...stage2.map((t) => t.score));
  assert.equal(stage2.find((t) => t.score === best).slot, slot); // first slot reaching the max (strict <)
  // Immune moves score 0 (BL:8072-8074): Lucario's Aura Sphere (Fighting) vs Ghost
  assert.equal(stage2.find((t) => t.slot === 3 && t.move === K('MOVE_AURA_SPHERE')).score, 0);
  assert.equal(slot, 3); // Lucario, Shadow Ball
});

test('ShouldSwitch: Flash Fire absorber on the bench after a Fire hit (AI_HasAbsorbAbilityInParty, TAI:3640-3714)', () => {
  // Turn 1: Flint's Houndoom uses Sunny Day; the slower player Camerupt hits it with Flamethrower,
  // so at the next decision battleCtx->moveHit[1] = Flamethrower (UpdateFlagsWhenHit,
  // battle_controller_player.c:4495-4502), rebuilt from the log line |move|p1a|Flamethrower|p2a.
  //   TrainerAI_ShouldSwitch: not trapped; 4 bench mons alive; PerishSong no; Wonder Guard no;
  //   OnlyIneffectiveMoves: Flamethrower is not immune vs Fire/Ground -> FALSE.
  //   HasAbsorbAbilityInParty: AI_HasSuperEffectiveMove(TRUE) is FALSE (Fire/Poison/Dark vs
  //   Fire/Ground), so no %3 draw; moveHit power 90 Fire -> Flash Fire; Houndoom's ability is
  //   Early Bird; slot 1 Flareon has Flash Fire and RandNext & 1 = 255 & 1 = 1 -> switch to slot 1.
  // Houndoom is under 25% HP, but PickCommand checks switching before items (TAI:4000-4033).
  const { battle, st, p2 } = leagueBattle('elite_four_flint', [B('camerupt', 56, ['flamethrower', 'earth_power', 'yawn', 'rock_slide'], 'ABILITY_SOLID_ROCK')], { rng: stubRng([], 255) });
  battle.makeChoices('move 1', 'move 4');
  processLog(st);
  assert.equal(st.moveHit[1], K('MOVE_FLAMETHROWER'));
  assert.equal(st.moveHitBattler[1], 0);
  assert.ok(p2.active[0].hp < p2.active[0].maxhp / 4);
  const draws = st.rng.draws;
  const r = decide(st, p2);
  assert.equal(r.kind, 'switch');
  assert.equal(r.detail.slot, 1);
  assert.equal(p2.pokemon[Number(r.choice.split(' ')[1]) - 1].species.name, 'Flareon');
  assert.equal(st.rng.draws - draws, 1);
});

test('ShouldSwitch: trapped (Mean Look) never switches (TAI:3906-3913)', () => {
  const { battle, st, p2 } = leagueBattle('elite_four_flint', [B('camerupt', 56, ['flamethrower', 'earth_power', 'yawn', 'rock_slide'], 'ABILITY_SOLID_ROCK')], { rng: stubRng([], 255) });
  battle.makeChoices('move 1', 'move 4');
  processLog(st);
  p2.active[0].addVolatile('trapped', battle.p1.active[0]);
  st.aiSwitchedPartySlot = [6, 6, 6, 6];
  assert.ok(st.ai.statusVolatile(1) & K('VOLATILE_CONDITION_TRAPPED'));
  assert.equal(shouldSwitch(st, 1), false);
});

test('ShouldSwitch: only ineffective moves -> bench member with a super-effective move (TAI:3361-3546)', () => {
  // AI Snorlax (Body Slam, Return: both Normal, both immune vs Ghost) faces Gengar.
  // numMoves = 2 (>= 2, TAI:3413). Bench slot 1 Gengar's Shadow Ball is SE vs Gengar:
  // RandNext % 3 = 255 % 3 = 0 < 2 -> switch to slot 1.
  const { st, p2 } = customBattle([mon('gengar', ['shadowball'], 'Levitate')],
    [mon('snorlax', ['bodyslam', 'return'], 'Thick Fat'), mon('gengar', ['shadowball'], 'Levitate')]);
  assert.equal(shouldSwitch(st, 1), true);
  assert.equal(st.aiSwitchedPartySlot[1], 1);
  void p2;
});

test('ShouldSwitch: Wonder Guard with no super-effective move -> bench member that has one (TAI:3286-3350)', () => {
  // Player Shedinja (Bug/Ghost, Wonder Guard). AI Snorlax: Body Slam (immune), Earthquake (Ground
  // vs Bug NVE) -> no SE. Bench Arcanine's Flamethrower is SE -> 255 % 3 = 0 < 2 -> slot 1.
  const { st } = customBattle([mon('shedinja', ['shadowsneak'], 'Wonder Guard')],
    [mon('snorlax', ['bodyslam', 'earthquake'], 'Thick Fat'), mon('arcanine', ['flamethrower'], 'Intimidate')]);
  assert.equal(shouldSwitch(st, 1), true);
  assert.equal(st.aiSwitchedPartySlot[1], 1);
});

test('ShouldSwitch: AI_IsHeavilyStatBoosted (+4 or more) blocks the resist-switch (TAI:3967-3970)', () => {
  // Player Machamp hits AI Snorlax with Close Combat (moveHit). Bench Gengar is immune to it and
  // has Psychic (SE vs Machamp). Snorlax has no SE move vs Machamp, so without boosts
  // AI_HasPartyMemberWithSuperEffectiveMove(INEFFECTIVE, 2) would switch on RandNext % 2 == 0.
  const make = () => {
    const x = customBattle([mon('machamp', ['closecombat'], 'Guts')],
      [mon('snorlax', ['bodyslam', 'return'], 'Thick Fat'), mon('gengar', ['psychic'], 'Levitate')], stubRng([], 0));
    x.st.moveHit[1] = K('MOVE_CLOSE_COMBAT');
    x.st.moveHitBattler[1] = 0;
    return x;
  };
  const a = make();
  assert.equal(shouldSwitch(a.st, 1), true); // positive control: 0 % 2 == 0 -> switch to Gengar
  assert.equal(a.st.aiSwitchedPartySlot[1], 1);
  const b = make();
  b.p2.active[0].boosts.atk = 2;
  b.p2.active[0].boosts.def = 2; // (8-6) + (8-6) = 4 -> heavily boosted
  assert.equal(shouldSwitch(b.st, 1), false);
});

test('ShouldSwitch: asleep Natural Cure above half HP, nothing hit it yet -> post-KO style switch (TAI:3817-3859)', () => {
  // Cynthia's Roserade (Natural Cure) asleep at full HP, moveHit NONE: RandNext & 1 = 1 ->
  // aiSwitchedPartySlot = 6 -> TrainerAI_PickCommand runs BattleAI_PostKOSwitchIn (TAI:4004-4027).
  const { battle, st, p2 } = leagueBattle('champion_cynthia', [B('garchomp', 58, ['earthquake', 'dragon_claw', 'crunch', 'fire_fang'], 'ABILITY_SAND_VEIL')], { rng: stubRng([], 255) });
  const rose = sendIn(battle, p2, 1);
  rose.setStatus('slp');
  const r = decide(st, p2);
  assert.equal(r.kind, 'switch');
  // PostKOSwitchIn vs Garchomp (Dragon/Ground): Togekiss/Milotic... first stage-1 pick with an SE move
  const picked = p2.pokemon[Number(r.choice.split(' ')[1]) - 1];
  assert.notEqual(picked, rose);
  assert.ok(!picked.fainted);
});
