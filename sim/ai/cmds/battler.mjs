// Trainer-AI opcode handlers: battler group (see ../OPCODES.md column "File" and ../INTERFACE.md).
// Each handler: (ctx, ins) => void. Cite the trainer_ai.c handler line in a comment for each.
//
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c, BL = pokeplatinum/src/battle/battle_lib.c.
// Arguments are read by name; the names are the macro parameters in asm/macros/aicmd.inc, emitted
// in the same order as the handler's AIScript_Read calls.
//
// Integer widths (include/battle/battle_mon.h, battle_context.h, ai_context.h):
//   curHP s32 (:107), maxHP u32 (:108), statBoosts s8 (:75), level u8 (:102), gender u8:4 (:123),
//   heldItem u16 (:118), speed u16 (:61); calcTemp int (ai_context.h:16),
//   battlerAbilities u8 (ai_context.h:28), battlerHeldItems u16 (ai_context.h:29).

const K = (ctx, name) => ctx.ai.constants.get(name);

// AIScript_Battler (TAI:2765-2781). ctx.battler implements ATTACKER -> attacker and everything
// else -> defender; the partner values (ATTACKER_PARTNER -> attacker ^ 2, DEFENDER_PARTNER ->
// defender ^ 2) are not reachable from the League sections (OPCODES.md header), so they throw here
// rather than resolve to the wrong battler.
function battlerArg(ctx, ins) {
  const inBattler = ctx.arg(ins, 'battler');
  if (inBattler === K(ctx, 'AI_BATTLER_ATTACKER_PARTNER') || inBattler === K(ctx, 'AI_BATTLER_DEFENDER_PARTNER')) {
    throw new Error(`${ins.name} (script.s:${ins.line}): partner battler ${inBattler} is not supported (singles only)`);
  }
  return { inBattler, battler: ctx.battler(inBattler) };
}

// curHP * 100 / maxHP as the handlers compute it into a u32 (TAI:596). curHP (s32) * 100 is an
// int; dividing by the u32 maxHP converts it to unsigned.
function hpPercent(ctx, ins, battler) {
  const maxHP = ctx.ai.maxHP(battler) >>> 0;
  if (maxHP === 0) throw new Error(`${ins.name} (script.s:${ins.line}): battler ${battler} has maxHP 0 (division by zero in C)`);
  return Math.floor(((ctx.ai.curHP(battler) * 100) >>> 0) / maxHP) >>> 0;
}

// `u32 < int` / `>` / `==` / `!=` compare as unsigned (usual arithmetic conversions).
const u32 = (v) => v >>> 0;

// ---------- local helpers for battle_lib.c functions the adapter does not expose ----------

// BattleSystem_GetItemData(item, ITEM_PARAM_*) over the decomp item table (BL:7254-7260).
// ITEM_NONE reads data file 0 (Item_FileID returns 0 for ITEM_NONE, src/item.c:49-55), which is
// res/items/data/none.json: all zero.
function itemData(ctx, item) {
  const d = ctx.ai.itemData(item);
  if (!d) throw new Error(`battler.mjs: no decomp item data for item ${item}`);
  return d;
}

// Battler_HeldItem (BL:5352-5363): ITEM_NONE under Klutz or Embargo.
function battlerHeldItem(ctx, b) {
  if (ctx.ai.battlerAbility(b) === K(ctx, 'ABILITY_KLUTZ')) return K(ctx, 'ITEM_NONE');
  if (ctx.ai.moveEffectsData(b).embargoTurns) return K(ctx, 'ITEM_NONE');
  return ctx.ai.heldItem(b);
}
// Battler_HeldItemEffect (BL:5438-5442).
const battlerHeldItemEffect = (ctx, b) => itemData(ctx, battlerHeldItem(ctx, b)).holdEffect;
// Battler_HeldItemPower(battler, ITEM_POWER_CHECK_ALL) (BL:5444-5462): ITEM_PARAM_EFFECT_PARAM of
// Battler_HeldItem. Stored into a u8 by the caller (BL:1193-1194).
const battlerHeldItemPowerAll = (ctx, b) => itemData(ctx, battlerHeldItem(ctx, b)).holdEffectParam & 0xff;

// BattleSystem_CountAbility(COUNT_ALIVE_BATTLERS, 0, ability) (BL:2870, case at 2952).
function countAliveAbility(ctx, ability) {
  let n = 0;
  for (let i = 0; i < ctx.ai.maxBattlers; i++) {
    if (ctx.ai.battlerAbility(i) === ability && ctx.ai.curHP(i)) n++;
  }
  return n;
}

// sStatStageBoosts (BL:6550-6564): {numerator, denominator} for stages 0..12.
const STAT_STAGE_BOOSTS = [
  [10, 40], [10, 35], [10, 30], [10, 25], [10, 20], [10, 15], [10, 10],
  [15, 10], [20, 10], [25, 10], [30, 10], [35, 10], [40, 10],
];
// sSpeedHalvingItemEffects (BL:1160-1169).
const SPEED_HALVING_ITEM_EFFECTS = [
  'HOLD_EFFECT_EVS_UP_SPEED_DOWN', 'HOLD_EFFECT_SPEED_DOWN_GROUNDED', 'HOLD_EFFECT_LVLUP_HP_EV_UP',
  'HOLD_EFFECT_LVLUP_ATK_EV_UP', 'HOLD_EFFECT_LVLUP_DEF_EV_UP', 'HOLD_EFFECT_LVLUP_SPEED_EV_UP',
  'HOLD_EFFECT_LVLUP_SPATK_EV_UP', 'HOLD_EFFECT_LVLUP_SPDEF_EV_UP',
];

// CompareSpeed_ApplySimple (BL:1171-1186).
function applySimple(ctx, b, stage) {
  if (ctx.ai.battlerAbility(b) === K(ctx, 'ABILITY_SIMPLE')) {
    stage = K(ctx, 'DEFAULT_STAT_STAGE') + ((stage - K(ctx, 'DEFAULT_STAT_STAGE')) * 2);
    if (stage > K(ctx, 'MAX_STAT_STAGE')) stage = K(ctx, 'MAX_STAT_STAGE');
    if (stage < K(ctx, 'MIN_STAT_STAGE')) stage = K(ctx, 'MIN_STAT_STAGE');
  }
  return stage;
}

// Per-battler part of BattleSystem_CompareBattlerSpeed: BL:1225-1226 (stage), 1228-1238 (weather,
// gated by NO_CLOUD_NINE, battle/common.h:63-64), then BL:1240-1304 for battler1 (BL:1306-1370
// is the same code for battler2). ignoreQuickClaw is TRUE here, so the quickClaw / custapBerry
// writes (BL:1282-1284, 1295-1297) never happen.
function battlerSpeed(ctx, b, noCloudNine) {
  const ai = ctx.ai;
  const ability = ai.battlerAbility(b); // Battler_Ability (BL:1214-1215)
  const itemEffect = battlerHeldItemEffect(ctx, b); // BL:1216, 1218 (u8)
  let itemParam = battlerHeldItemPowerAll(ctx, b); // BL:1217, 1219 (u8)
  const stage = applySimple(ctx, b, ai.statBoost(b, K(ctx, 'BATTLE_STAT_SPEED')));
  const [num, den] = STAT_STAGE_BOOSTS[stage];
  let speed = Math.floor((ai.stat(b, K(ctx, 'BATTLE_STAT_SPEED')) * num) / den) >>> 0; // u32 (BL:1190)

  if (noCloudNine) {
    const fc = ai.fieldConditionsMask();
    if ((ability === K(ctx, 'ABILITY_SWIFT_SWIM') && (fc & K(ctx, 'FIELD_CONDITION_RAINING')))
      || (ability === K(ctx, 'ABILITY_CHLOROPHYLL') && (fc & K(ctx, 'FIELD_CONDITION_SUNNY')))) {
      speed = (speed * 2) >>> 0;
    }
  }
  // Speed-halving items read the raw heldItem, not Battler_HeldItem (BL:1240-1246).
  const rawEffect = itemData(ctx, ai.heldItem(b)).holdEffect;
  if (SPEED_HALVING_ITEM_EFFECTS.some((n) => K(ctx, n) === rawEffect)) speed = Math.floor(speed / 2);

  if (itemEffect === K(ctx, 'HOLD_EFFECT_CHOICE_SPEED')) speed = Math.floor((speed * 15) / 10) >>> 0; // BL:1248-1250
  if (itemEffect === K(ctx, 'HOLD_EFFECT_DITTO_SPEED_UP') && ai.species(b) === K(ctx, 'SPECIES_DITTO')) speed = (speed * 2) >>> 0; // BL:1252-1255

  const status = ai.status(b);
  if (ability === K(ctx, 'ABILITY_QUICK_FEET') && (status & K(ctx, 'MON_CONDITION_ANY'))) { // BL:1257-1261
    speed = Math.floor((speed * 15) / 10) >>> 0;
  } else if (status & K(ctx, 'MON_CONDITION_PARALYSIS')) {
    speed = Math.floor(speed / 4);
  }
  const med = ai.moveEffectsData(b);
  // totalTurns (int, battle_context.h:202) - slowStartTurnNumber (int, battle_mon.h:41): signed.
  if (ability === K(ctx, 'ABILITY_SLOW_START') && ai.totalTurns() - med.slowStartTurnNumber < 5) speed = Math.floor(speed / 2); // BL:1263-1266
  if (ability === K(ctx, 'ABILITY_UNBURDEN') && med.canUnburden && ai.heldItem(b) === K(ctx, 'ITEM_NONE')) speed = (speed * 2) >>> 0; // BL:1268-1272
  if (ai.sideConditionsMask(ai.side(b)) & K(ctx, 'SIDE_CONDITION_TAILWIND')) speed = (speed * 2) >>> 0; // BL:1274-1276

  let quickClaw = 0;
  if (itemEffect === K(ctx, 'HOLD_EFFECT_SOMETIMES_PRIORITY')) { // BL:1278-1286
    const speedRand = ai.speedRand(b);
    if (speedRand === undefined) {
      throw new Error(`IfSpeedCompareEqualTo: battler ${b} holds a Quick Claw effect item but speedRand[${b}] (battle_context.h:293) was not supplied to the adapter`);
    }
    if ((speedRand & 0xffff) % Math.floor(100 / itemParam) === 0) quickClaw = 1;
  }
  if (itemEffect === K(ctx, 'HOLD_EFFECT_PINCH_PRIORITY')) { // BL:1288-1299
    if (ai.battlerAbility(b) === K(ctx, 'ABILITY_GLUTTONY')) itemParam = Math.floor(itemParam / 2);
    if ((ai.curHP(b) >>> 0) <= Math.floor((ai.maxHP(b) >>> 0) / itemParam)) quickClaw = 1;
  }
  const laggingTail = itemEffect === K(ctx, 'HOLD_EFFECT_PRIORITY_DOWN') ? 1 : 0; // BL:1301-1303
  return { speed, ability, quickClaw, laggingTail };
}

// BattleSystem_CompareBattlerSpeed(battleSys, battleCtx, battler1, battler2, ignoreQuickClaw = TRUE)
// (BL:1188-1454). Draws ctx.rand() exactly where the C calls BattleSystem_RandNext. Side effect:
// battleCtx->monSpeedValues[b] (BL:1372-1373, battle_context.h:259), later read by Gyro Ball in
// TrainerAI_CalcDamage; kept in ctx.mem.monSpeedValues because ctx.ai is read-only.
export function compareBattlerSpeed(ctx, battler1, battler2) {
  const ai = ctx.ai;
  const FASTER = K(ctx, 'COMPARE_SPEED_FASTER');
  const SLOWER = K(ctx, 'COMPARE_SPEED_SLOWER');
  const TIE = K(ctx, 'COMPARE_SPEED_TIE');
  let result = FASTER;

  // BL:1204-1210: these return the literals 1 and 0.
  if (ai.curHP(battler1) === 0 && ai.curHP(battler2)) return 1;
  if (ai.curHP(battler1) && ai.curHP(battler2) === 0) return 0;

  const noCloudNine = countAliveAbility(ctx, K(ctx, 'ABILITY_CLOUD_NINE')) === 0
    && countAliveAbility(ctx, K(ctx, 'ABILITY_AIR_LOCK')) === 0;
  const b1 = battlerSpeed(ctx, battler1, noCloudNine);
  const b2 = battlerSpeed(ctx, battler2, noCloudNine);

  if (!ctx.mem.monSpeedValues) ctx.mem.monSpeedValues = [0, 0, 0, 0];
  ctx.mem.monSpeedValues[battler1] = b1.speed;
  ctx.mem.monSpeedValues[battler2] = b2.speed;

  // ignoreQuickClaw == TRUE: both priorities stay 0 (BL:1196, 1375-1398), so the
  // `battler1Priority == battler2Priority` branch (BL:1401) is always taken.
  const s1 = b1.speed;
  const s2 = b2.speed;
  const coin = () => (ctx.rand() & 1) !== 0;
  const STALL = K(ctx, 'ABILITY_STALL');
  if (b1.quickClaw && b2.quickClaw) { // BL:1402-1407
    if (s1 < s2) result = SLOWER;
    else if (s1 === s2 && coin()) result = TIE;
  } else if (b1.quickClaw === 0 && b2.quickClaw) { // BL:1408-1409
    result = SLOWER;
  } else if (b1.quickClaw && b2.quickClaw === 0) { // BL:1410-1411
    result = FASTER;
  } else if (b1.laggingTail && b2.laggingTail) { // BL:1412-1417
    if (s1 > s2) result = SLOWER;
    else if (s1 === s2 && coin()) result = TIE;
  } else if (b1.laggingTail && b2.laggingTail === 0) { // BL:1418-1419
    result = SLOWER;
  } else if (b1.laggingTail === 0 && b2.laggingTail) { // BL:1420-1421
    result = FASTER;
  } else if (b1.ability === STALL && b2.ability === STALL) { // BL:1422-1427
    if (s1 > s2) result = SLOWER;
    else if (s1 === s2 && coin()) result = TIE;
  } else if (b1.ability === STALL && b2.ability !== STALL) { // BL:1428-1429
    result = SLOWER;
  } else if (b1.ability !== STALL && b2.ability === STALL) { // BL:1430-1431
    result = FASTER;
  } else if (ai.fieldConditionsMask() & K(ctx, 'FIELD_CONDITION_TRICK_ROOM')) { // BL:1432-1439
    if (s1 > s2) result = SLOWER;
    if (s1 === s2 && coin()) result = TIE;
  } else { // BL:1440-1447
    if (s1 < s2) result = SLOWER;
    if (s1 === s2 && coin()) result = TIE;
  }
  return result;
}

// Shared body of the IfHPPercent* handlers (TAI:588-646).
function ifHPPercent(cmp) {
  return (ctx, ins) => {
    const { battler } = battlerArg(ctx, ins);
    const target = u32(ctx.arg(ins, 'i'));
    if (cmp(hpPercent(ctx, ins, battler), target)) ctx.jump(ins);
  };
}

// Shared body of the IfStatStage* handlers (TAI:1465-1523): statBoosts[stat] (s8) vs val (int).
function ifStatStage(cmp) {
  return (ctx, ins) => {
    const { battler } = battlerArg(ctx, ins);
    const stat = ctx.arg(ins, 'stat');
    const val = ctx.arg(ins, 'i');
    if (cmp(ctx.ai.statBoost(battler, stat), val)) ctx.jump(ins);
  };
}

// Shared body of the mask tests IfStatus .. IfNotMoveEffect (TAI:648-730).
function ifMask(argName, read, negate) {
  return (ctx, ins) => {
    const { battler } = battlerArg(ctx, ins);
    const mask = ctx.arg(ins, argName);
    const set = (read(ctx.ai, battler) & mask) !== 0;
    if (negate ? !set : set) ctx.jump(ins);
  };
}

// Species abilities for the coin flip / guess (TAI:1191-1192, 1236-1237):
// SpeciesData_GetSpeciesValue(species, SPECIES_DATA_ABILITY_1 / _2).
function speciesAbilityPair(ctx, battler) {
  const ab = ctx.ai.speciesAbilities(ctx.ai.species(battler));
  return [ab[0] ?? 0, ab[1] ?? 0];
}

export const handlers = {
  // AICmd_IfHPPercentLessThan (TAI:588-601).
  IfHPPercentLessThan: ifHPPercent((p, t) => p < t),
  // AICmd_IfHPPercentGreaterThan (TAI:603-616).
  IfHPPercentGreaterThan: ifHPPercent((p, t) => p > t),
  // AICmd_IfHPPercentEqualTo (TAI:618-631).
  IfHPPercentEqualTo: ifHPPercent((p, t) => p === t),
  // AICmd_IfHPPercentNotEqualTo (TAI:633-646).
  IfHPPercentNotEqualTo: ifHPPercent((p, t) => p !== t),

  // AICmd_IfStatus (TAI:648-660): battleMons[battler].status & mask.
  IfStatus: ifMask('status', (ai, b) => ai.status(b), false),
  // AICmd_IfNotStatus (TAI:662-674).
  IfNotStatus: ifMask('status', (ai, b) => ai.status(b), true),
  // AICmd_IfVolatileStatus (TAI:676-688): statusVolatile & mask.
  IfVolatileStatus: ifMask('volatile_status', (ai, b) => ai.statusVolatile(b), false),
  // AICmd_IfNotVolatileStatus (TAI:690-702).
  IfNotVolatileStatus: ifMask('volatile_status', (ai, b) => ai.statusVolatile(b), true),
  // AICmd_IfMoveEffect (TAI:704-716): moveEffectsMask & mask.
  IfMoveEffect: ifMask('move_effects', (ai, b) => ai.moveEffectsMask(b), false),
  // AICmd_IfNotMoveEffect (TAI:718-730).
  IfNotMoveEffect: ifMask('move_effects', (ai, b) => ai.moveEffectsMask(b), true),

  // AICmd_LoadTypeFrom (TAI:937-987).
  LoadTypeFrom(ctx, ins) {
    const ai = ctx.ai;
    const param = ctx.arg(ins, 'load_type_target');
    // BattleSystem_GetPartner (battle_system.c:394-411) returns the battler itself outside doubles.
    const partner = (b) => {
      if (ai.battleType() & K(ctx, 'BATTLE_TYPE_DOUBLES')) throw new Error(`LoadTypeFrom (script.s:${ins.line}): partner types need doubles support`);
      return b;
    };
    switch (param) {
      case K(ctx, 'LOAD_ATTACKER_TYPE_1'): ctx.mem.calcTemp = ai.types(ai.attacker)[0]; break;
      case K(ctx, 'LOAD_DEFENDER_TYPE_1'): ctx.mem.calcTemp = ai.types(ai.defender)[0]; break;
      case K(ctx, 'LOAD_ATTACKER_TYPE_2'): ctx.mem.calcTemp = ai.types(ai.attacker)[1]; break;
      case K(ctx, 'LOAD_DEFENDER_TYPE_2'): ctx.mem.calcTemp = ai.types(ai.defender)[1]; break;
      // MOVE_DATA(AI_CONTEXT.move).type: the table type (TAI:961-963).
      case K(ctx, 'LOAD_MOVE_TYPE'): ctx.mem.calcTemp = ai.moveData(ctx.mem.move).type; break;
      case K(ctx, 'LOAD_ATTACKER_PARTNER_TYPE_1'): ctx.mem.calcTemp = ai.types(partner(ai.attacker))[0]; break;
      case K(ctx, 'LOAD_DEFENDER_PARTNER_TYPE_1'): ctx.mem.calcTemp = ai.types(partner(ai.defender))[0]; break;
      case K(ctx, 'LOAD_ATTACKER_PARTNER_TYPE_2'): ctx.mem.calcTemp = ai.types(partner(ai.attacker))[1]; break;
      // TAI:980-983: the C reads BATTLEMON_TYPE_1 here (decomp bug, ported as written).
      case K(ctx, 'LOAD_DEFENDER_PARTNER_TYPE_2'): ctx.mem.calcTemp = ai.types(partner(ai.defender))[0]; break;
      default: throw new Error(`LoadTypeFrom (script.s:${ins.line}): GF_ASSERT(FALSE) on param ${param} (TAI:985-987)`);
    }
  },

  // AICmd_IfSpeedCompareEqualTo (TAI:1102-1113).
  IfSpeedCompareEqualTo(ctx, ins) {
    const val = ctx.arg(ins, 'cmp');
    if (compareBattlerSpeed(ctx, ctx.ai.attacker, ctx.ai.defender) === val) ctx.jump(ins);
  },

  // AICmd_LoadBattlerAbility (TAI:1170-1210).
  LoadBattlerAbility(ctx, ins) {
    const ai = ctx.ai;
    const { inBattler, battler } = battlerArg(ctx, ins);
    if (ai.moveEffectsMask(battler) & K(ctx, 'MOVE_EFFECT_ABILITY_SUPPRESSED')) {
      ctx.mem.calcTemp = K(ctx, 'ABILITY_NONE');
    } else if (ai.attacker !== battler && inBattler !== K(ctx, 'AI_BATTLER_ATTACKER_PARTNER')) {
      if (ctx.mem.battlerAbilities[battler]) {
        ctx.mem.calcTemp = ctx.mem.battlerAbilities[battler] & 0xff; // u8 (ai_context.h:28)
      } else {
        const real = ai.ability(battler); // battleMons[battler].ability, not Battler_Ability
        if (real === K(ctx, 'ABILITY_SHADOW_TAG') || real === K(ctx, 'ABILITY_MAGNET_PULL') || real === K(ctx, 'ABILITY_ARENA_TRAP')) {
          ctx.mem.calcTemp = real;
        } else {
          const [ability1, ability2] = speciesAbilityPair(ctx, battler);
          if (ability1 && ability2) {
            ctx.mem.calcTemp = (ctx.rand() & 1) ? ability1 : ability2; // TAI:1195-1199
          } else if (ability1) {
            ctx.mem.calcTemp = ability1;
          } else {
            ctx.mem.calcTemp = ability2;
          }
        }
      }
    } else {
      ctx.mem.calcTemp = ai.ability(battler); // TAI:1207-1209: raw ability
    }
  },

  // AICmd_CheckBattlerAbility (TAI:1212-1266).
  CheckBattlerAbility(ctx, ins) {
    const ai = ctx.ai;
    const { inBattler, battler } = battlerArg(ctx, ins);
    const expected = ctx.arg(ins, 'ability');
    const NONE = K(ctx, 'ABILITY_NONE');
    let tmpAbility;
    if (ai.moveEffectsMask(battler) & K(ctx, 'MOVE_EFFECT_ABILITY_SUPPRESSED')) {
      tmpAbility = NONE;
    } else if (inBattler === K(ctx, 'AI_BATTLER_DEFENDER') || inBattler === K(ctx, 'AI_BATTLER_DEFENDER_PARTNER')) {
      if (ctx.mem.battlerAbilities[battler]) {
        tmpAbility = ctx.mem.battlerAbilities[battler] & 0xff;
        ctx.mem.calcTemp = tmpAbility; // TAI:1227 (overwritten below)
      } else {
        const real = ai.ability(battler);
        if (real === K(ctx, 'ABILITY_SHADOW_TAG') || real === K(ctx, 'ABILITY_MAGNET_PULL') || real === K(ctx, 'ABILITY_ARENA_TRAP')) {
          tmpAbility = real;
        } else {
          const [ability1, ability2] = speciesAbilityPair(ctx, battler);
          if (ability1 && ability2) {
            tmpAbility = (ability1 !== expected && ability2 !== expected) ? ability1 : NONE; // TAI:1240-1248
          } else if (ability1) {
            tmpAbility = ability1;
          } else {
            tmpAbility = ability2;
          }
        }
      }
    } else {
      tmpAbility = ai.ability(battler); // TAI:1255-1257
    }
    if (tmpAbility === NONE) ctx.mem.calcTemp = K(ctx, 'AI_UNKNOWN');
    else if (tmpAbility === expected) ctx.mem.calcTemp = K(ctx, 'AI_HAVE');
    else ctx.mem.calcTemp = K(ctx, 'AI_NOT_HAVE');
  },

  // AICmd_IfStatStageLessThan (TAI:1465-1478).
  IfStatStageLessThan: ifStatStage((s, v) => s < v),
  // AICmd_IfStatStageGreaterThan (TAI:1480-1493).
  IfStatStageGreaterThan: ifStatStage((s, v) => s > v),
  // AICmd_IfStatStageEqualTo (TAI:1495-1508).
  IfStatStageEqualTo: ifStatStage((s, v) => s === v),
  // AICmd_IfStatStageNotEqualTo (TAI:1510-1523).
  IfStatStageNotEqualTo: ifStatStage((s, v) => s !== v),

  // AICmd_IfBattlerUnderEffect (TAI:1823-1848).
  IfBattlerUnderEffect(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    const check = ctx.arg(ins, 'check_effect');
    const med = ctx.ai.moveEffectsData(battler);
    if (check === K(ctx, 'CHECK_DISABLE')) {
      if (med.disabledTurns) ctx.jump(ins);
    } else if (check === K(ctx, 'CHECK_ENCORE')) {
      if (med.encoredTurns) ctx.jump(ins);
    } // default: nothing (TAI:1845-1846)
  },

  // AICmd_LoadHeldItem (TAI:1891-1899): the real item, even for the player.
  LoadHeldItem(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    ctx.mem.calcTemp = ctx.ai.heldItem(battler);
  },

  // AICmd_LoadHeldItemEffect (TAI:1901-1913): AI memory for anyone but the attacker.
  LoadHeldItemEffect(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    const item = ctx.ai.attacker !== battler ? (ctx.mem.battlerHeldItems[battler] & 0xffff) : ctx.ai.heldItem(battler);
    ctx.mem.calcTemp = itemData(ctx, item).holdEffect; // BattleSystem_GetItemData(ITEM_PARAM_HOLD_EFFECT)
  },

  // AICmd_IfHeldItemEqualTo (TAI:1915-1934): own side reads the real item, the other side AI memory.
  IfHeldItemEqualTo(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    const expected = ctx.arg(ins, 'item');
    const heldItem = (battler & 1) === (ctx.ai.attacker & 1)
      ? ctx.ai.heldItem(battler) & 0xffff
      : ctx.mem.battlerHeldItems[battler] & 0xffff; // u16 heldItem (TAI:1923)
    if (heldItem === expected) ctx.jump(ins);
  },

  // AICmd_LoadFlingPower (TAI:2014-2022) -> Battler_ItemFlingPower (BL:5491-5498).
  LoadFlingPower(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    if (ctx.ai.moveEffectsData(battler).embargoTurns) {
      ctx.mem.calcTemp = 0;
    } else {
      ctx.mem.calcTemp = itemData(ctx, ctx.ai.heldItem(battler)).flingPower;
    }
  },

  // AICmd_SumPositiveStatStages (TAI:2243-2257): BATTLE_STAT_HP .. BATTLE_STAT_MAX-1.
  SumPositiveStatStages(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    ctx.mem.calcTemp = 0;
    for (let stat = K(ctx, 'BATTLE_STAT_HP'); stat < K(ctx, 'BATTLE_STAT_MAX'); stat++) {
      const s = ctx.ai.statBoost(battler, stat);
      if (s > 6) ctx.mem.calcTemp += s - 6;
    }
  },

  // AICmd_DiffStatStages (TAI:2259-2268).
  DiffStatStages(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    const stat = ctx.arg(ins, 'battle_stat');
    ctx.mem.calcTemp = ctx.ai.statBoost(battler, stat) - ctx.ai.statBoost(ctx.ai.attacker, stat);
  },

  // AICmd_LoadGender (TAI:2470-2478).
  LoadGender(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    ctx.mem.calcTemp = ctx.ai.gender(battler);
  },

  // AICmd_LoadStockpileCount (TAI:2494-2502).
  LoadStockpileCount(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    ctx.mem.calcTemp = ctx.ai.moveEffectsData(battler).stockpileCount;
  },

  // AICmd_LoadRecycleItem (TAI:2510-2518).
  LoadRecycleItem(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    ctx.mem.calcTemp = ctx.ai.recycleItem(battler);
  },

  // AICmd_LoadProtectChain (TAI:2538-2552). protectSuccessTurns is 2 for both 2 and 3 successes
  // (adapter, OPCODES.md trap 10).
  LoadProtectChain(ctx, ins) {
    const { battler } = battlerArg(ctx, ins);
    const mp = ctx.ai.moveProtect(battler);
    if (mp !== K(ctx, 'MOVE_PROTECT') && mp !== K(ctx, 'MOVE_DETECT') && mp !== K(ctx, 'MOVE_ENDURE')) {
      ctx.mem.calcTemp = 0;
    } else {
      ctx.mem.calcTemp = ctx.ai.moveEffectsData(battler).protectSuccessTurns;
    }
  },

  // AICmd_IfLevel (TAI:2579-2608).
  IfLevel(ctx, ins) {
    const op = ctx.arg(ins, 'check_level');
    const a = ctx.ai.level(ctx.ai.attacker);
    const d = ctx.ai.level(ctx.ai.defender);
    if (op === K(ctx, 'CHECK_HIGHER_THAN_TARGET')) { if (a > d) ctx.jump(ins); }
    else if (op === K(ctx, 'CHECK_LOWER_THAN_TARGET')) { if (a < d) ctx.jump(ins); }
    else if (op === K(ctx, 'CHECK_EQUAL_TO_TARGET')) { if (a === d) ctx.jump(ins); }
    // default: nothing (TAI:2605-2606)
  },

  // AICmd_IfTargetIsNotTaunted (TAI:2620-2628).
  IfTargetIsNotTaunted(ctx, ins) {
    if (ctx.ai.moveEffectsData(ctx.ai.defender).tauntedTurns === 0) ctx.jump(ins);
  },
};
