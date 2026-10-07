// T036: exp arithmetic and participation, hand-computed from the decomp formulas
// (BtlCmd_CalcExpGain pokeplatinum/src/battle/battle_script.c:2187-2248,
//  BattleScript_GetExpTask :9685, SEQ_GET_EXP_START :9725-9778, Pokemon_ShouldLevelUp
//  src/pokemon.c:3501-3526). Rules recap: exp = u16(base*L/7); with Exp. Share:
// gained = (exp/2)/nGaining, shared = (exp/2)/nShare, else gained = exp/nGaining; each >= 1;
// per mon: total = gained(if in mask) + shared(if holder); *150/100 Lucky Egg; *150/100 trainer;
// *150/100 traded (170/100 foreign language). All integer divisions.
//
// Game values used (copied from the decomp, path:line):
//   Yanmega base_exp_reward 198      pokeplatinum/res/pokemon/yanmega/data.json:12
//   Spiritomb base_exp_reward 168    pokeplatinum/res/pokemon/spiritomb/data.json:12
//   Magikarp base_exp_reward 20      pokeplatinum/res/pokemon/magikarp/data.json:12
//   Aaron's Yanmega is level 49      pokeplatinum/res/trainers/data/elite_four_aaron.json:18
//   Cynthia's Spiritomb is level 58  pokeplatinum/res/trainers/data/champion_cynthia.json:20
//   exp_tables.csv (pokeplatinum/res/pokemon/.shared/exp_tables.csv), columns
//     level,medium_fast,erratic,fluctuating,medium_slow,...:
//     :12 "10,1000,1800,540,560,..."   :17 "15,3375,5737,1957,2035,..."
//     :18 "16,4096,6881,2457,2535,..." :19 "17,4913,8155,3046,3120,..."
//     :52 "50,125000,..." :53 "51,132651,..." :54 "52,140608,..." :55 "53,148877,..."
//     :102 "100,1000000,..."
//   Lucario exp_rate EXP_RATE_MEDIUM_SLOW pokeplatinum/res/pokemon/lucario/data.json:28
//   Extreme Speed priority 1, accuracy 100 pokeplatinum/res/moves/extreme_speed/data.json:20,:13
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadGameData } from '../gamedata.mjs';
import { addExp, baseExpYield, calcStats, expForFaint, ExpTracker } from '../exp.mjs';
import { newBattle, opponentMembers, playerMember } from '../team.mjs';

const gd = loadGameData();
const mon = (o = {}) => ({ alive: true, inMask: false, expShare: false, luckyEgg: false,
  traded: false, foreignLanguage: false, atMaxLevel: false, ...o });

test('data sanity: values the cases below rely on', () => {
  assert.equal(gd.species.yanmega.base_exp, 198);
  assert.equal(gd.species.spiritomb.base_exp, 168);
  assert.equal(gd.species.magikarp.base_exp, 20);
  assert.equal(gd.exp.tables.EXP_RATE_MEDIUM_FAST[51], 132651);
  assert.equal(gd.exp.tables.EXP_RATE_MEDIUM_SLOW[16], 2535);
});

test('case 1: one participant, trainer battle', () => {
  // exp = floor(198*49/7) = floor(9702/7) = 1386; gained = 1386/1 = 1386; trainer 1386*150/100 = 2079
  const r = expForFaint({ baseExp: 198, faintedLevel: 49, party: [mon({ inMask: true })] });
  assert.equal(r.exp, 1386);
  assert.deepEqual(r.totals, [2079]);
});

test('case 2: two participants split, a bystander gets nothing', () => {
  // gained = 1386/2 = 693; 693*150/100 = 1039.5 -> 1039
  const r = expForFaint({ baseExp: 198, faintedLevel: 49,
    party: [mon({ inMask: true }), mon({ inMask: true }), mon()] });
  assert.deepEqual(r.totals, [1039, 1039, 0]);
});

test('case 3: Exp. Share holder that did not participate', () => {
  // half = 1386/2 = 693; gained = 693/1 = 693; shared = 693/1 = 693; each *1.5 -> 1039
  const r = expForFaint({ baseExp: 198, faintedLevel: 49,
    party: [mon({ inMask: true }), mon({ expShare: true })] });
  assert.equal(r.gained, 693);
  assert.equal(r.shared, 693);
  assert.deepEqual(r.totals, [1039, 1039]);
});

test('case 4: participant that also holds Exp. Share gets both parts', () => {
  // nGaining = 2, nShare = 1: gained = 693/2 = 346; shared = 693/1 = 693
  // slot0: (346 + 693) = 1039 -> *150/100 = 1558.5 -> 1558; slot1: 346 -> 519
  const r = expForFaint({ baseExp: 198, faintedLevel: 49,
    party: [mon({ inMask: true, expShare: true }), mon({ inMask: true })] });
  assert.deepEqual(r.totals, [1558, 519]);
});

test('case 5: Lucky Egg then trainer bonus', () => {
  // Spiritomb L58: 168*58/7 = 9744/7 = 1392; Lucky Egg 1392*150/100 = 2088; trainer 2088*150/100 = 3132
  const r = expForFaint({ baseExp: 168, faintedLevel: 58, party: [mon({ inMask: true, luckyEgg: true })] });
  assert.equal(r.exp, 1392);
  assert.deepEqual(r.totals, [3132]);
});

test('case 6: traded Lucky Egg holder (same language)', () => {
  // 1392 -> egg 2088 -> trainer 3132 -> traded 3132*150/100 = 4698
  const r = expForFaint({ baseExp: 168, faintedLevel: 58,
    party: [mon({ inMask: true, luckyEgg: true, traded: true })] });
  assert.deepEqual(r.totals, [4698]);
});

test('case 7: traded, different language: x1.7', () => {
  // 1392 -> trainer 2088 -> 2088*170/100 = 3549.6 -> 3549
  const r = expForFaint({ baseExp: 168, faintedLevel: 58,
    party: [mon({ inMask: true, traded: true, foreignLanguage: true })] });
  assert.deepEqual(r.totals, [3549]);
});

test('case 8: fainted participant is not counted and gets nothing', () => {
  // only slot1 alive in the mask: nGaining = 1, gained = 1386 -> 2079
  const r = expForFaint({ baseExp: 198, faintedLevel: 49,
    party: [mon({ inMask: true, alive: false }), mon({ inMask: true })] });
  assert.equal(r.nGaining, 1);
  assert.deepEqual(r.totals, [0, 2079]);
});

test('case 9: minimum 1 for gained and shared', () => {
  // Magikarp L1: 20*1/7 = 2. With a share holder: half = 1; gained = 1/3 = 0 -> 1; shared = 1/1 = 1.
  // trainer: 1*150/100 = 1 (integer). Share-only holder: 1 -> 1.
  const r = expForFaint({ baseExp: 20, faintedLevel: 1,
    party: [mon({ inMask: true }), mon({ inMask: true }), mon({ inMask: true }), mon({ expShare: true })] });
  assert.equal(r.exp, 2);
  assert.equal(r.gained, 1);
  assert.equal(r.shared, 1);
  assert.deepEqual(r.totals, [1, 1, 1, 1]);
  // No share: gained = 2/3 = 0 -> 1
  const r2 = expForFaint({ baseExp: 20, faintedLevel: 1, party: [mon({ inMask: true }), mon({ inMask: true }), mon({ inMask: true })] });
  assert.equal(r2.gained, 1);
});

test('case 10: a max-level participant still counts in the split but gains nothing', () => {
  // count uses species && HP only (battle_script.c:2204); the level check is in GetExpTask (:9740)
  // gained = 1386/2 = 693 -> 1039 for the other one
  const r = expForFaint({ baseExp: 198, faintedLevel: 49,
    party: [mon({ inMask: true, atMaxLevel: true }), mon({ inMask: true })] });
  assert.deepEqual(r.totals, [0, 1039]);
});

test('case 11: u16 truncation of base*level/7', () => {
  // Not reachable with real data (base_exp_reward <= 255), arithmetic only:
  // 4000*200/7 = 114285 (floor); u16: 114285 - 65536 = 48749
  assert.equal(baseExpYield(4000, 200), 48749);
  assert.equal(baseExpYield(198, 49), 1386);
});

test('case 12: multi-level gain and max-exp cap', () => {
  // medium fast: L50 at 125000; +16000 = 141000 >= 132651 (L51) and >= 140608 (L52), < 148877 (L53)
  const m = { rec: gd.species.yanmega, level: 50, exp: 125000 };
  assert.deepEqual(addExp(gd, m, 16000), [51, 52]);
  assert.equal(m.level, 52);
  assert.equal(m.exp, 141000);
  // cap: exp > table[100] = 1000000 is clamped (pokemon.c:3509-3512)
  const top = { rec: gd.species.yanmega, level: 99, exp: 990000 };
  assert.deepEqual(addExp(gd, top, 50000), [100]);
  assert.equal(top.exp, 1000000);
});

// Battle integration: participation, mid-battle level-up with stat recompute and HP raise.
const build = (species, level, moves, ability, item = null) => ({
  species, start_level: level, moves, ability, held_item: item, nature: 'Hardy' });
const yanmegaOnly = () => opponentMembers(gd, gd.trainers[0]).slice(0, 1); // Aaron's lead, L49

test('case 13: KO in battle -> exp, mid-battle level-up, HP raised by the max-HP gain', () => {
  const party = [playerMember(gd, build('lucario', 10, ['extreme_speed'], 'ABILITY_STEADFAST'), 0)];
  const battle = newBattle(gd, { seed: 'sodium,' + '0'.repeat(31) + '5', player: party, opponent: yanmegaOnly() });
  const events = [];
  new ExpTracker(gd, battle, party, { events });
  const luc = battle.p1.active[0];
  const yan = battle.p2.active[0];
  yan.sethp(1);
  luc.sethp(5);
  const oldMax = luc.maxhp;
  battle.makeChoices('move 1', 'move 1'); // Extreme Speed (+1) KOs Yanmega first
  assert.equal(yan.fainted, true);
  // exp: 198*49/7 = 1386 -> trainer 2079; 560 (L10 medium slow) + 2079 = 2639:
  // >= 2535 (L16), < 3120 (L17) -> level 16
  assert.equal(events.length, 1);
  assert.deepEqual(events[0].gains, [{ slot: 0, exp: 2079, total_exp: 2639, level: 16, from_level: 10,
    ...(events[0].gains[0].declined_moves ? { declined_moves: events[0].gains[0].declined_moves, auto_learn_in_game: true } : {}) }]);
  assert.equal(party[0].level, 16);
  assert.equal(luc.level, 16);
  const s16 = calcStats(gd, gd.species.lucario, party[0].ivs, party[0].evs, 16, 'NATURE_HARDY');
  assert.equal(luc.maxhp, s16.hp);
  assert.equal(luc.storedStats.atk, s16.atk);
  assert.equal(luc.storedStats.spe, s16.spe);
  assert.equal(luc.hp, 5 + (s16.hp - oldMax)); // pokemon.c:639
  assert.equal(battle.ended, true);
});

test('case 14: Exp. Share holder in the back levels up off-field; participation mask', () => {
  const party = [
    playerMember(gd, build('lucario', 10, ['extreme_speed'], 'ABILITY_STEADFAST'), 0),
    playerMember(gd, build('lucario', 10, ['extreme_speed'], 'ABILITY_STEADFAST', 'exp_share'), 1),
  ];
  const battle = newBattle(gd, { seed: 'sodium,' + '0'.repeat(31) + '6', player: party, opponent: yanmegaOnly() });
  const events = [];
  new ExpTracker(gd, battle, party, { events });
  battle.p2.active[0].sethp(1);
  battle.makeChoices('move 1', 'move 1');
  // half = 693; gained 693/1 -> 1039; shared 693/1 -> 1039. 560 + 1039 = 1599:
  // medium slow L13 = 1261 (csv :15), L14 = 1612 (csv :16) -> level 13 for both
  assert.deepEqual(events[0].participants, [0]);
  assert.deepEqual(events[0].gains.map((g) => [g.slot, g.exp, g.level]), [[0, 1039, 13], [1, 1039, 13]]);
  const back = battle.p1.pokemon.find((p) => p.platsimSlot === 1);
  assert.equal(back.level, 13);
  assert.equal(back.maxhp, calcStats(gd, gd.species.lucario, party[1].ivs, party[1].evs, 13, 'NATURE_HARDY').hp);
  assert.equal(back.hp, back.maxhp); // full HP raised by the gain
});

test('case 15: a mon switched in while the foe is up joins the mask (battle_lib.c:1461-1479)', () => {
  const party = [
    playerMember(gd, build('lucario', 60, ['extreme_speed'], 'ABILITY_STEADFAST'), 0),
    playerMember(gd, build('lucario', 60, ['extreme_speed'], 'ABILITY_STEADFAST'), 1),
  ];
  const battle = newBattle(gd, { seed: 'sodium,' + '0'.repeat(31) + '7', player: party, opponent: yanmegaOnly() });
  const events = [];
  new ExpTracker(gd, battle, party, { events });
  battle.makeChoices('switch 2', 'move 4'); // Yanmega uses Double Team (aaron.json:24): no damage
  assert.equal(battle.p1.active[0].platsimSlot, 1);
  battle.p2.active[0].sethp(1);
  battle.makeChoices('move 1', 'move 4');
  if (!battle.p2.active[0].fainted && !battle.ended) battle.makeChoices('move 1', 'move 4'); // in case of an evasion miss
  assert.equal(events.length, 1);
  // mask {0, 1}, both alive: gained = 1386/2 = 693 -> *150/100 = 1039 each
  assert.deepEqual(events[0].participants, [0, 1]);
  assert.deepEqual(events[0].gains.map((g) => [g.slot, g.exp]), [[0, 1039], [1, 1039]]);
});
