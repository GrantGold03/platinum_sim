// T047: the trainer AI's item use and command order.
//
// Ports (TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c @ c248fb3f):
//   battle_controller_player.c:4796-4817 BattleControllerPlayer_InitAI -> initTrainerItems()
//   TAI:4056-4199 TrainerAI_ShouldUseItem -> shouldUseItem()
//   TAI:3989-4040 TrainerAI_PickCommand   -> pickCommand() (switch -> item -> fight)
//
// Item state (include/battle/ai_context.h:31, 36): trainerItems u16[2][4], trainerItemCounts
// u8[2], indexed by battler >> 1. InitAI compacts the trainer's non-NONE items into slots 0..n-1
// and sets trainerItemCounts = n; NOTHING ever decrements trainerItemCounts (the only writes are
// battle_controller_player.c:4808-4809). Using an item zeroes its slot (TAI:4193).
//
// Slot rule (TAI:4092): slot i is examined only if `i == 0 || aliveMons <= trainerItemCounts - i + 1`
// (u8 aliveMons vs int; aliveMons counts every party member with HP, the active one included).
// No break (TAI:4091-4196): once `result` is TRUE, every later examined non-NONE slot is ALSO
// zeroed and becomes usedItem, whatever its own condition — the "double consumption" behaviour.
//
// Only ITEM_FULL_RESTORE is supported: it is the only item in any League bag
// (data/generated/trainers.json bag_items, from res/trainers/data/*.json). The other
// branches (TAI:4105-4189) need item parameters and Showdown actions this project does not
// model; reaching one throws, so it can never be silently mis-simulated.
import { shouldSwitch, pickSwitchSlot } from './switch.mjs';

const K = (ai, n) => ai.constants.get(n);
export const MAX_TRAINER_ITEMS = 4; // include/constants/battle.h:69

// BattleControllerPlayer_InitAI (battle_controller_player.c:4796-4817) for the AI side.
// `bagItems`: ITEM_* constant names in trainer-data order.
export function initTrainerItems(ai, bagItems) {
  const trainerItems = [0, 0, 0, 0];
  let count = 0;
  for (let i = 0; i < MAX_TRAINER_ITEMS; i++) {
    const name = bagItems[i] ?? 'ITEM_NONE';
    const item = K(ai, name);
    if (item !== K(ai, 'ITEM_NONE')) {
      trainerItems[count] = item;
      count = (count + 1) & 0xff;
    }
  }
  return { trainerItems, trainerItemCounts: count, usedItem: 0, usedItemType: 0 };
}

/**
 * TrainerAI_ShouldUseItem(battler) (TAI:4056-4199). Mutates items.trainerItems (and usedItem).
 * Returns { use: bool, item, consumedSlots: [...], aliveMons }.
 */
export function shouldUseItem(ai, items, battler = 1) {
  const consumedSlots = [];
  let result = false;
  // TAI:4069-4073: TRAINER_WITH_AI_PARTNER only; not a League battle.
  if (ai.moveEffectsMask(battler) & K(ai, 'MOVE_EFFECT_EMBARGO')) return { use: false, consumedSlots, aliveMons: null }; // TAI:4076-4078
  let aliveMons = 0; // u8
  const party = ai.party(battler);
  for (let i = 0; i < party.length; i++) { // Party_GetCurrentCount
    const p = party[i];
    if (p.hp !== 0 && p.species !== K(ai, 'SPECIES_NONE') && p.species !== K(ai, 'SPECIES_EGG')) aliveMons = (aliveMons + 1) & 0xff;
  }
  const curHP = ai.curHP(battler);
  const maxHP = ai.maxHP(battler);
  for (let i = 0; i < MAX_TRAINER_ITEMS; i++) {
    if (i === 0 || aliveMons <= items.trainerItemCounts - i + 1) { // TAI:4092
      const item = items.trainerItems[i];
      if (item === K(ai, 'ITEM_NONE')) continue;
      if (item === K(ai, 'ITEM_FULL_RESTORE')) {
        // TAI:4099-4104: curHP < maxHP / 4 (u16 / int, truncating) and curHP != 0
        if (curHP < Math.trunc(maxHP / 4) && curHP) {
          items.usedItemType = K(ai, 'ITEM_AI_CATEGORY_FULL_RESTORE');
          result = true;
        }
      } else {
        throw new Error(`items: trainer item ${item} is not ITEM_FULL_RESTORE; TrainerAI_ShouldUseItem branches TAI:4105-4189 are not ported`);
      }
      if (result === true) { // TAI:4191-4194
        items.usedItem = item;
        items.trainerItems[i] = 0;
        consumedSlots.push(i);
      }
    }
  }
  return { use: result, item: items.usedItem, consumedSlots, aliveMons };
}

/**
 * TrainerAI_PickCommand (TAI:3989-4040): PLAYER_INPUT_PARTY / ITEM / FIGHT.
 * `st` needs { ai, rng, items, aiSwitchedPartySlot, moveHit, moveHitBattler }.
 * Returns { command: 'party' | 'item' | 'fight', slot?, itemUse? }.
 */
export function pickCommand(st, battler = 1) {
  const { ai } = st;
  // TAI:4000: BATTLE_TYPE_TRAINER is set for a League battle
  if (shouldSwitch(st, battler)) {
    const slot = pickSwitchSlot(st, battler);
    return { command: 'party', slot };
  }
  const itemUse = shouldUseItem(ai, st.items, battler);
  if (itemUse.use) return { command: 'item', itemUse };
  return { command: 'fight' };
}
