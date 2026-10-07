// T048: sim/ai/items.mjs (TrainerAI_ShouldUseItem, TAI:4056-4199; PickCommand order, TAI:3989-4040)
// and the Full Restore pseudo-move patches (sim/ai/patches.mjs) inside live Showdown battles.
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Dex } from '../showdown.mjs';
import { initTrainerItems, shouldUseItem } from '../ai/items.mjs';
import { afterTurn, decide, processLog } from '../ai/opponent.mjs';
import { aiProgram } from '../ai/choose.mjs';
import { FULL_RESTORE_MOVE } from '../ai/patches.mjs';
import { B, gd, leagueBattle, sendIn, setHP, stubRng } from './ai_fixtures.mjs';

const prog = aiProgram();
const K = (n) => prog.constants.get(n);
const FR = K('ITEM_FULL_RESTORE');

test('InitAI compacts the bag into trainerItems, counts never decrement (battle_controller_player.c:4796-4817)', () => {
  const { st } = leagueBattle('champion_cynthia', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  const items = initTrainerItems(st.ai, ['ITEM_NONE', 'ITEM_FULL_RESTORE', 'ITEM_NONE', 'ITEM_FULL_RESTORE']);
  assert.deepEqual(items.trainerItems, [FR, FR, 0, 0]);
  assert.equal(items.trainerItemCounts, 2);
  // Cynthia: res/trainers/data/champion_cynthia.json -> 4 Full Restores
  assert.deepEqual(st.items.trainerItems, [FR, FR, FR, FR]);
  assert.equal(st.items.trainerItemCounts, 4);
});

test('Full Restore threshold: curHP < maxHP / 4 (integer) and curHP != 0 (TAI:4099-4104)', () => {
  // Milotic (Cynthia slot 4) maxhp 195 -> 195 / 4 = 48.
  const { battle, st, p2 } = leagueBattle('champion_cynthia', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  const milotic = sendIn(battle, p2, 4);
  assert.equal(milotic.maxhp, 195);
  const at = (hp) => {
    setHP(milotic, hp);
    const items = initTrainerItems(st.ai, ['ITEM_FULL_RESTORE']);
    return shouldUseItem(st.ai, items, 1).use;
  };
  assert.equal(at(46), true); // 23.6%
  assert.equal(at(47), true);
  assert.equal(at(48), false); // == maxHP / 4: not strictly less
  assert.equal(at(51), false); // 26.2%
  assert.equal(at(0), false); // fainted
  assert.equal(at(1), true);
});

test('slot rule and no-break double consumption (TAI:4091-4196)', () => {
  // Cynthia: trainerItemCounts = 4. Slot i (> 0) is examined only if aliveMons <= 4 - i + 1.
  const { battle, st, p2 } = leagueBattle('champion_cynthia', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  const lead = p2.active[0];
  setHP(lead, 10);
  // 6 alive: only slot 0 can be examined -> one Full Restore used.
  let r = shouldUseItem(st.ai, st.items, 1);
  assert.deepEqual([r.use, r.consumedSlots, r.aliveMons], [true, [0], 6]);
  assert.deepEqual(st.items.trainerItems, [0, FR, FR, FR]);
  // still 6 alive: slot 0 is NONE (continue), slot 1 needs aliveMons <= 4 -> nothing.
  r = shouldUseItem(st.ai, st.items, 1);
  assert.deepEqual([r.use, r.consumedSlots], [false, []]);
  // 2 alive: slot 1 (2 <= 4) uses; slot 2 (2 <= 3) and slot 3 (2 <= 2) are examined after
  // `result` is already TRUE, so both are zeroed too: three Full Restores gone in one use.
  for (const p of p2.pokemon) if (p !== lead && p.platsimSlot !== 5) p.hp = 0;
  r = shouldUseItem(st.ai, st.items, 1);
  assert.deepEqual([r.use, r.consumedSlots, r.aliveMons], [true, [1, 2, 3], 2]);
  assert.deepEqual(st.items.trainerItems, [0, 0, 0, 0]);
  // E4 (2 items): with 3+ alive only slot 0 is reachable (3 <= 2 - 1 + 1 is false).
  const e4 = leagueBattle('elite_four_aaron', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  setHP(e4.p2.active[0], 5);
  assert.deepEqual(shouldUseItem(e4.st.ai, e4.st.items, 1).consumedSlots, [0]);
  assert.deepEqual(shouldUseItem(e4.st.ai, e4.st.items, 1).consumedSlots, []);
  void battle;
});

test('Embargo blocks trainer items (TAI:4076-4078)', () => {
  const { st, p2 } = leagueBattle('champion_cynthia', [B('garchomp', 58, ['earthquake'], 'ABILITY_SAND_VEIL')]);
  setHP(p2.active[0], 10);
  p2.active[0].addVolatile('embargo');
  assert.equal(shouldUseItem(st.ai, st.items, 1).use, false);
  assert.deepEqual(st.items.trainerItems, [FR, FR, FR, FR]);
});

test('Dex patches are installed (positive control for the live tests below)', () => {
  const data = Dex.mod('gen4').data.Moves;
  assert.equal(typeof data[FULL_RESTORE_MOVE].beforeTurnCallback, 'function');
  assert.ok(gd.dexPatch.aiPatches.includes('taunt: trainerfullrestore exempt'));
  assert.throws(() => data[FULL_RESTORE_MOVE].onHit(), /ran as a move/);
});

// One live turn: AI decides (must be the item), both sides act, afterTurn. Returns this turn's log.
function itemTurn(x, p1choice) {
  const r = decide(x.st, x.p2);
  assert.equal(r.kind, 'item', `expected the item, got ${r.kind} ${r.choice}`);
  const from = x.battle.log.length;
  x.battle.makeChoices(p1choice, r.choice);
  afterTurn(x.st);
  return { r, lines: x.battle.log.slice(from) };
}
const roseradeVs = (playerBuild) => {
  const x = leagueBattle('champion_cynthia', [playerBuild], { rng: stubRng([], 255) });
  x.rose = sendIn(x.battle, x.p2, 1); // Roserade: Energy Ball, Sludge Bomb, Toxic, Extrasensory
  return x;
};

test('Taunt + Full Restore: the item is used under Taunt; Taunt still blocks real status moves', () => {
  const x = roseradeVs(B('gyarados', 56, ['taunt', 'dragon_dance', 'waterfall', 'ice_fang'], 'ABILITY_INTIMIDATE'));
  x.battle.makeChoices('move 1', 'move 1'); // Gyarados Taunts Roserade
  assert.ok(x.rose.volatiles.taunt);
  setHP(x.rose, 20);
  const { lines } = itemTurn(x, 'move 2'); // Gyarados Dragon Dance (no damage)
  assert.equal(x.rose.hp, x.rose.maxhp);
  assert.ok(lines.some((l) => l.startsWith('|-heal|p2a: ROSERADE|') && l.endsWith('[from] item: Full Restore')));
  assert.ok(!lines.some((l) => l.startsWith('|cant|p2a: ROSERADE|move: Taunt')));
  assert.equal(x.rose.moveSlots.length, 4, 'pseudo-move slot removed after the turn');
  // positive control: Taunt still disables Toxic in the next request
  assert.ok(x.rose.volatiles.taunt);
  assert.equal(x.rose.getMoveRequestData().moves[2].disabled, true);
  assert.deepEqual(x.st.items.trainerItems, [0, FR, FR, FR]);
});

test('Encore + Full Restore: no OverrideAction, the encore stays, the encored move is not used that turn', () => {
  const x = roseradeVs(B('wobbuffet', 56, ['encore', 'counter', 'mirror_coat', 'safeguard'], 'ABILITY_SHADOW_TAG'));
  x.battle.makeChoices('move 1', 'move 3'); // Roserade Toxic, then the slower Wobbuffet Encores it
  assert.ok(x.rose.volatiles.encore);
  setHP(x.rose, 20);
  const { lines } = itemTurn(x, 'move 4');
  assert.equal(x.rose.hp, x.rose.maxhp);
  assert.ok(!lines.some((l) => l.startsWith('|move|p2a: ROSERADE|')), 'no move executed by the item user');
  assert.ok(x.rose.volatiles.encore);
  assert.equal(x.rose.lastMove.id, 'toxic', 'lastMove (Encore/Disable/Mirror Move target) untouched');
});

test('sleep / paralysis / confusion cannot stop the item, and it cures them (subscript_use_full_restore.s)', () => {
  for (const setup of [(m) => m.setStatus('slp'), (m) => m.setStatus('par'), (m) => m.addVolatile('confusion')]) {
    const x = roseradeVs(B('gyarados', 56, ['dragon_dance', 'waterfall'], 'ABILITY_INTIMIDATE'));
    setup(x.rose);
    setHP(x.rose, 20);
    const { lines } = itemTurn(x, 'move 1');
    assert.equal(x.rose.hp, x.rose.maxhp);
    assert.equal(x.rose.status, '');
    assert.ok(!x.rose.volatiles.confusion);
    assert.ok(!lines.some((l) => l.startsWith('|cant|p2a: ROSERADE')));
    assert.ok(!lines.some((l) => l.includes('|[from] confusion')));
  }
});

test('Pressure: no PP is deducted from the item user; Heal Block does not stop the heal', () => {
  const x = roseradeVs(B('spiritomb', 56, ['heal_block', 'shadow_sneak'], 'ABILITY_PRESSURE'));
  x.battle.makeChoices('move 1', 'move 4'); // Roserade Extrasensory; Spiritomb uses Heal Block
  assert.ok(x.rose.volatiles.healblock);
  const pp = x.rose.moveSlots.map((s) => s.pp);
  setHP(x.rose, 20);
  itemTurn(x, 'move 1');
  assert.equal(x.rose.hp, x.rose.maxhp);
  assert.deepEqual(x.rose.moveSlots.map((s) => s.pp), pp);
});

test("Sucker Punch fails against the item user (Battler_SelectedMove is MOVE_NONE, battle_script.c:7385-7400)", () => {
  const x = roseradeVs(B('absol', 56, ['sucker_punch', 'swords_dance'], 'ABILITY_PRESSURE'));
  setHP(x.rose, 20);
  const { lines } = itemTurn(x, 'move 1');
  assert.equal(x.rose.hp, x.rose.maxhp, 'healed and not hit');
  assert.ok(lines.some((l) => l.startsWith('|-fail|p1a: ABSOL')) || lines.some((l) => l.includes('Sucker Punch') && l.includes('[still]')));
});

test('PickCommand order: switch before item before fight (TAI:3989-4040)', () => {
  // Same position as the absorb-switch test (ai_switch.test.mjs): Houndoom under 25% but switches.
  const x = leagueBattle('elite_four_flint', [B('camerupt', 56, ['flamethrower', 'earth_power', 'yawn', 'rock_slide'], 'ABILITY_SOLID_ROCK')], { rng: stubRng([], 255) });
  x.battle.makeChoices('move 1', 'move 4');
  processLog(x.st);
  assert.ok(x.p2.active[0].hp < Math.trunc(x.p2.active[0].maxhp / 4));
  assert.equal(decide(x.st, x.p2).kind, 'switch');
  assert.deepEqual(x.st.items.trainerItems, [FR, FR, 0, 0], 'ShouldUseItem never ran');
  // remove the absorber's reason to switch (no moveHit) -> the item is used instead
  const y = leagueBattle('elite_four_flint', [B('camerupt', 56, ['flamethrower', 'earth_power', 'yawn', 'rock_slide'], 'ABILITY_SOLID_ROCK')], { rng: stubRng([], 255) });
  setHP(y.p2.active[0], 20);
  assert.equal(decide(y.st, y.p2).kind, 'item');
});

test('negative control: run as an ordinary move, the pseudo-move does not heal (it throws), so the heals above came from beforeTurnCallback', () => {
  const x = roseradeVs(B('gyarados', 56, ['taunt', 'dragon_dance'], 'ABILITY_INTIMIDATE'));
  setHP(x.rose, 20);
  // Showdown's move path (runMove -> useMove -> onHit) is what the spike used and what Taunt,
  // sleep, paralysis, Pressure and lastMove act on. Here onHit is the patched thrower.
  const m = x.battle.dex.moves.get(FULL_RESTORE_MOVE);
  x.rose.moveSlots.push({ move: m.name, id: m.id, pp: m.pp, maxpp: m.pp, target: m.target, disabled: false, used: false, virtual: true });
  assert.throws(() => x.battle.actions.runMove(FULL_RESTORE_MOVE, x.rose, 0), /ran as a move/);
  assert.equal(x.rose.hp, 20);
});
