// T039 tests: sim/ai/adapter.mjs answers in decomp encodings, checked against Showdown's own state.
// Decomp values are copied from pokeplatinum/ files and cited (path:line). Enum values are the
// 0-based position in the generated/*.txt list (line - 1; none of the lists used here has `=`).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle, Dex } from '../showdown.mjs';
import { createAdapter, decompTables } from '../ai/adapter.mjs';
import { loadConstants } from '../ai/constants.mjs';

const C = loadConstants();
const K = (n) => C.get(n);
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });

function makeBattle() {
  return new Battle({
    formatid: 'gen4customgame',
    seed: [1, 2, 3, 4],
    p1: { name: 'Player', team: [
      mon('garchomp', ['swordsdance', 'stealthrock', 'raindance', 'earthquake'], { item: 'leftovers', ability: 'Sand Veil' }),
      mon('blissey', ['softboiled', 'toxic', 'seismictoss', 'protect'], { ability: 'Natural Cure' }),
    ] },
    p2: { name: 'AI', team: [
      mon('blissey', ['toxic', 'leechseed', 'softboiled', 'thunderwave'], { ability: 'Natural Cure' }),
      mon('garchomp', ['earthquake', 'dragonclaw', 'swordsdance', 'protect'], { ability: 'Sand Veil' }),
    ] },
  });
}

test('constants: generated enums number from 0 in file order (positive controls)', () => {
  assert.equal(K('SPECIES_GARCHOMP'), 445); // generated/species.txt:446
  assert.equal(K('MOVE_EARTHQUAKE'), 89); // generated/moves.txt:90
  assert.equal(K('TYPE_DRAGON'), 16); // generated/pokemon_types.txt:17
  assert.equal(K('ITEM_LEFTOVERS'), 234); // generated/items.txt:235
  assert.equal(K('HOLD_EFFECT_HP_RESTORE_GRADUAL'), 69); // generated/item_hold_effects.txt:70
  assert.equal(K('SIDE_CONDITION_STEALTH_ROCK'), 1 << 7); // constants/battle/condition.h:95
  assert.equal(K('VOLATILE_CONDITION_TORMENT'), (1 << 31) | 0); // condition.h:63, int32
  assert.equal(K('AI_BATTLER_ATTACKER_PARTNER'), 3); // constants/battle/trainer_ai.h:31-32 (1 ^ 2)
  assert.equal(K('DEFAULT_STAT_STAGE'), 6); // constants/battle/battle_script.h:5
});

test('decomp move/item/species tables', () => {
  const T = decompTables();
  // res/moves/earthquake/data.json:9-11
  assert.equal(T.moves[89].power, 100);
  assert.equal(T.moves[89].type, K('TYPE_GROUND'));
  assert.equal(T.moves[89].class, K('CLASS_PHYSICAL'));
  // res/items/data/leftovers.json:17,20
  assert.equal(T.items[234].holdEffect, 69);
  assert.equal(T.items[234].flingPower, 10);
  // res/pokemon/garchomp/data.json:10,30
  assert.deepEqual(T.species[445].types, [16, 4]);
  assert.deepEqual(T.species[445].abilities, [K('ABILITY_SAND_VEIL'), 0]);
});

test('every decomp move/ability matches Showdown by num; every Showdown-known item too', () => {
  const T = decompTables();
  const dex = Dex.mod('gen4');
  const toID = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  const renamed = [];
  let moves = 0;
  for (const m of T.moves) {
    if (!m || m.id === 0) continue;
    moves++;
    const s = dex.moves.all().find((x) => x.num === m.id);
    assert.ok(s, `no Showdown move with num ${m.id} (${m.constant})`);
    if (toID(s.name) !== toID(m.name)) renamed.push(`${m.name}->${s.name}`);
  }
  assert.equal(moves, 467); // generated/moves.txt: MOVE_POUND (:2) .. MOVE_SHADOW_FORCE (:468)
  // Name differences are renames only (decomp names from res/moves/*/data.json "name").
  assert.deepEqual(renamed.sort(), ['Faint Attack->Feint Attack', 'Hi Jump Kick->High Jump Kick', 'SmellingSalt->Smelling Salts', 'ViceGrip->Vise Grip']);
  for (const e of C.lists.get('abilities')) {
    if (e.value === 0 || !e.name.startsWith('ABILITY_')) continue;
    const a = dex.abilities.all().find((x) => x.num === e.value);
    assert.ok(a && toID(a.name) === toID(e.name.slice(8)), e.name);
  }
  let items = 0;
  for (const it of T.items) {
    if (!it) continue;
    const s = dex.items.get(toID(it.name));
    if (!s.exists) continue; // non-battle items (potions, balls) are not in Showdown
    items++;
    assert.equal(s.num, it.id, it.constant);
  }
  assert.ok(items > 150, `items matched: ${items}`);
});

test('battler ids, BattleMon fields and turn counters track Showdown', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const [P, A] = [0, 1];
  assert.equal(ai.pokemon(P), battle.p1.active[0]);
  assert.equal(ai.pokemon(A), battle.p2.active[0]);
  assert.equal(ai.pokemon(2), null);
  assert.equal(ai.exists(3), false);
  assert.equal(ai.side(P), 0);
  assert.equal(ai.side(A), 1);
  assert.equal(ai.species(P), 445);
  assert.deepEqual(ai.types(P), [16, 4]); // same as res/pokemon/garchomp/data.json:10
  assert.deepEqual(ai.types(A), [0, 0]); // res/pokemon/blissey/data.json:10
  assert.deepEqual(ai.moves(P), [K('MOVE_SWORDS_DANCE'), K('MOVE_STEALTH_ROCK'), K('MOVE_RAIN_DANCE'), 89]);
  assert.equal(ai.heldItem(P), 234);
  assert.equal(ai.itemHoldEffect(ai.heldItem(P)), 69);
  assert.equal(ai.ability(P), K('ABILITY_SAND_VEIL')); // Showdown slot 0 ability
  assert.equal(ai.curHP(A), battle.p2.active[0].hp);
  assert.equal(ai.stat(P, K('BATTLE_STAT_SPEED')), battle.p1.active[0].storedStats.spe);
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6);
  assert.equal(ai.ppCur(P, 0), battle.p1.active[0].moveSlots[0].pp);
  // First decision: totalTurns 0, leads have fakeOutTurnNumber 0.
  assert.equal(battle.turn, 1);
  assert.equal(ai.totalTurns(), 0);
  assert.equal(ai.moveEffectsData(A).fakeOutTurnNumber, 0);
  assert.equal(ai.movePrevByBattler(P), 0);

  battle.makeChoices('move swordsdance', 'move toxic');
  assert.equal(ai.totalTurns(), 1);
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6 + battle.p1.active[0].boosts.atk);
  assert.equal(battle.p1.active[0].boosts.atk, 2, 'positive control: Swords Dance applied');
  assert.equal(ai.movePrevByBattler(P), K('MOVE_SWORDS_DANCE'));
  // Toxic: Showdown status 'tox' -> MON_CONDITION_TOXIC (condition.h:14).
  // With this seed Toxic hits (positive control); after one residual the counter is 1
  // (MON_CONDITION_TOXIC_COUNTER_0 = 1 << 8, condition.h:15).
  assert.equal(battle.p1.active[0].status, 'tox');
  assert.equal(ai.status(P), K('MON_CONDITION_TOXIC') | K('MON_CONDITION_TOXIC_COUNTER_0'));

  battle.makeChoices('move stealthrock', 'move leechseed');
  assert.ok(battle.p2.sideConditions.stealthrock, 'positive control: Stealth Rock set on p2');
  assert.ok(ai.sideConditionsMask(1) & K('SIDE_CONDITION_STEALTH_ROCK'));
  assert.equal(ai.sideConditionsMask(0) & K('SIDE_CONDITION_STEALTH_ROCK'), 0);
  // Leech Seed hits with this seed; the bit is on the seeded mon (subscript_leech_seed_start.s:15)
  // and LEECH_SEED_RECIPIENT (moves.h:8-9) holds the seeder's battler id, 1.
  assert.ok(battle.p1.active[0].volatiles.leechseed, 'positive control: seeded');
  assert.equal(ai.moveEffectsMask(P), K('MOVE_EFFECT_LEECH_SEED') | 1);
  assert.equal(ai.moveEffectsMask(A), 0);

  battle.makeChoices('move raindance', 'move softboiled');
  assert.equal(battle.field.weather, 'raindance');
  assert.ok(ai.fieldConditionsMask() & K('FIELD_CONDITION_RAINING_TEMP')); // move weather has a duration
  assert.equal(ai.fieldConditionsMask() & K('FIELD_CONDITION_RAINING_PERM'), 0);
  // Soft-Boiled at full HP fails in Showdown -> movePrevByBattler MOVE_NONE (game clears it when
  // the move did not succeed, battle_controller_player.c:3944-3948).
  assert.equal(battle.p2.active[0].lastMove.id, 'softboiled');
  assert.equal(battle.p2.active[0].moveLastTurnResult, false);
  assert.equal(ai.movePrevByBattler(A), 0);
  assert.equal(ai.movePrevByBattler(P), K('MOVE_RAIN_DANCE'));
  assert.equal(ai.totalTurns(), 3);

  // Switch: party order stays in game order; the incoming mon's fakeOutTurnNumber is
  // totalTurns + 1 at the switch (battle_lib.c:2117) = 4 here.
  battle.makeChoices('switch 2', 'move toxic');
  assert.equal(battle.p1.active[0].species.id, 'blissey');
  assert.equal(ai.selectedPartySlot(P), 1);
  assert.equal(ai.party(P)[0].species, 445);
  assert.equal(ai.party(P)[1].species, 242); // generated/species.txt:243
  assert.equal(ai.moveEffectsData(P).fakeOutTurnNumber, 4);
  assert.equal(ai.totalTurns(), 4);
  // => AICmd_LoadIsFirstTurnInBattle (trainer_ai.c:2480-2492): fakeOut < totalTurns is false -> TRUE.
  assert.equal(ai.moveEffectsData(P).fakeOutTurnNumber < ai.totalTurns(), false);
  // The AI's own lead has been in since turn 0: not its first turn.
  assert.equal(ai.moveEffectsData(A).fakeOutTurnNumber < ai.totalTurns(), true);
  // Stat stages reset for the new mon.
  assert.equal(ai.statBoost(P, K('BATTLE_STAT_ATTACK')), 6);
});

test('Showdown status and volatiles map to condition.h bits', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const p = battle.p1.active[0];
  // Set states directly (read-only adapter: this only checks the encoding).
  p.setStatus('par');
  assert.equal(ai.status(0), K('MON_CONDITION_PARALYSIS'));
  p.addVolatile('substitute');
  p.addVolatile('focusenergy');
  const v = ai.statusVolatile(0);
  assert.ok(v & K('VOLATILE_CONDITION_SUBSTITUTE'));
  assert.ok(v & K('VOLATILE_CONDITION_FOCUS_ENERGY'));
  assert.equal(v & K('VOLATILE_CONDITION_CONFUSION'), 0);
  battle.p2.addSideCondition('reflect', battle.p2.active[0]);
  assert.ok(ai.sideConditionsMask(1) & K('SIDE_CONDITION_REFLECT'));
  battle.field.addPseudoWeather('trickroom', battle.p2.active[0]);
  assert.ok(ai.fieldConditionsMask() & K('FIELD_CONDITION_TRICK_ROOM'));
  assert.equal(ai.fieldConditionsMask() & K('FIELD_CONDITION_GRAVITY'), 0);
});
