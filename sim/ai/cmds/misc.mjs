// Trainer-AI opcode handlers: misc group (see ../OPCODES.md column "File" and ../INTERFACE.md).
// Each handler: (ctx, ins) => void. Cite the trainer_ai.c handler line in a comment for each.
//
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c. Every C handler starts with
// AIScript_Iter(battleCtx, 1) and reads its arguments in order; parse.mjs has already decoded them
// into `ins.args`, so a handler only needs the branch logic. A taken jump is AIScript_Iter(jump),
// which ctx.jump() maps to the parsed target instruction.
//
// Integer widths used below:
//   AI_CONTEXT.calcTemp is `int` (ai_context.h:16)            -> `| 0`
//   battleCtx->totalTurns is `int` (battle_context.h:202)
//   moveEffectsData.fakeOutTurnNumber is `int` (battle_mon.h:40)
//   battleCtx->selectedPartySlot[] is `u8` (battle_context.h:252)  -> `& 0xFF`
//   AIScript_Battler() result is stored in `u8` (TAI:741 etc.); its values are 0..3 already.
//   BattleSystem_RandNext returns u16 (battle_system.c:1308-1312).

// ---- local helpers (no adapter query covers these exactly) ----

const K = (ctx, name) => ctx.ai.constants.get(name);

// BattleSystem_GetPartner (battle_system.c:394-412): the battler itself unless BATTLE_TYPE_DOUBLES,
// else the first other battler id on the same side.
function partnerOf(ctx, battler) {
  const ai = ctx.ai;
  if ((ai.battleType() & K(ctx, 'BATTLE_TYPE_DOUBLES')) === 0) return battler;
  let i;
  for (i = 0; i < ai.maxBattlers; i++) {
    if (i !== battler && ai.side(i) === ai.side(battler)) break;
  }
  return i;
}

// battleCtx->selectedPartySlot[b] as the game's u8 (battle_context.h:252). The adapter returns -1
// for an empty battler slot; as a u8 that is 255, which never equals a party index.
const selectedSlot = (ctx, b) => ctx.ai.selectedPartySlot(b) & 0xFF;

// The (slot1, slot2) pair TAI:1137-1142 and TAI:1358-1363 compute: both the battler's own slot
// unless doubles, where slot2 is the partner's.
function activeSlots(ctx, battler) {
  if (ctx.ai.battleType() & K(ctx, 'BATTLE_TYPE_DOUBLES')) {
    return [selectedSlot(ctx, battler), selectedSlot(ctx, partnerOf(ctx, battler))];
  }
  const s = selectedSlot(ctx, battler);
  return [s, s];
}

// Pokemon_GetValue(mon, MON_DATA_SPECIES_OR_EGG) != SPECIES_NONE && != SPECIES_EGG.
// The adapter's party entry has `species` (MON_DATA_SPECIES); a Showdown party never contains an
// egg, so SPECIES_OR_EGG equals SPECIES here.
function isRealSpecies(ctx, entry) {
  return entry.species !== K(ctx, 'SPECIES_NONE') && entry.species !== K(ctx, 'SPECIES_EGG');
}

export const handlers = {
  // AICmd_IfRandomLessThan, TAI:528-538. One RandNext() per execution, before the comparison.
  // `val` is an int; the u16 draw % 256 is 0..255.
  IfRandomLessThan(ctx, ins) {
    const val = ctx.arg(ins, 'i') | 0;
    const r = ctx.rand() & 0xFFFF;
    if ((r % 256) < val) ctx.jump(ins);
  },

  // AICmd_IfSideCondition, TAI:732-745: sideConditionsMask[BattleSystem_GetBattlerSide(battler)] & mask.
  IfSideCondition(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const mask = ctx.arg(ins, 'side_conditions') >>> 0;
    const side = ctx.ai.side(battler);
    if ((ctx.ai.sideConditionsMask(side) & mask) !== 0) ctx.jump(ins);
  },

  // AICmd_LoadTurnCount, TAI:931-935: calcTemp = battleCtx->totalTurns.
  LoadTurnCount(ctx) {
    ctx.mem.calcTemp = ctx.ai.totalTurns() | 0;
  },

  // AICmd_CountAlivePartyBattlers, TAI:1126-1156. calcTemp is zeroed first, then counts party
  // slots that are not an active slot, have HP != 0 and a species that is not NONE/EGG.
  CountAlivePartyBattlers(ctx, ins) {
    ctx.mem.calcTemp = 0;
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const [battlerSlot, partnerSlot] = activeSlots(ctx, battler);
    const party = ctx.ai.party(battler);
    const count = ctx.ai.partyCount(battler);
    for (let i = 0; i < count; i++) {
      const mon = party[i];
      if (i !== battlerSlot && i !== partnerSlot && mon.hp !== 0 && isRealSpecies(ctx, mon)) {
        ctx.mem.calcTemp = (ctx.mem.calcTemp + 1) | 0;
      }
    }
  },

  // AICmd_IfPartyMemberStatus, TAI:1348-1378: jump on the first non-active, alive, non-egg party
  // member with (MON_DATA_STATUS & statusMask) != 0.
  IfPartyMemberStatus(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const statusMask = ctx.arg(ins, 'pokemon_status') >>> 0;
    const [slot1, slot2] = activeSlots(ctx, battler);
    const party = ctx.ai.party(battler);
    const count = ctx.ai.partyCount(battler);
    for (let i = 0; i < count; i++) {
      const mon = party[i];
      if (i !== slot1 && i !== slot2 && mon.hp !== 0 && isRealSpecies(ctx, mon) && (mon.status & statusMask) !== 0) {
        ctx.jump(ins);
        return;
      }
    }
  },

  // AICmd_LoadCurrentWeather, TAI:1414-1439. Each later test overwrites the earlier one
  // (rain < sand < sun < hail < fog). WEATHER_IS_* are mask tests on fieldConditionsMask
  // (battle/common.h:68-72).
  LoadCurrentWeather(ctx) {
    const f = ctx.ai.fieldConditionsMask() >>> 0;
    let t = K(ctx, 'AI_WEATHER_CLEAR');
    if (f & K(ctx, 'FIELD_CONDITION_RAINING')) t = K(ctx, 'AI_WEATHER_RAINING');
    if (f & K(ctx, 'FIELD_CONDITION_SANDSTORM')) t = K(ctx, 'AI_WEATHER_SANDSTORM');
    if (f & K(ctx, 'FIELD_CONDITION_SUNNY')) t = K(ctx, 'AI_WEATHER_SUNNY');
    if (f & K(ctx, 'FIELD_CONDITION_HAILING')) t = K(ctx, 'AI_WEATHER_HAILING');
    if (f & K(ctx, 'FIELD_CONDITION_DEEP_FOG')) t = K(ctx, 'AI_WEATHER_DEEP_FOG');
    ctx.mem.calcTemp = t;
  },

  // AICmd_LoadIsFirstTurnInBattle, TAI:2480-2492:
  // calcTemp = (fakeOutTurnNumber < totalTurns) ? FALSE : TRUE (both int).
  LoadIsFirstTurnInBattle(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const fakeOut = ctx.ai.moveEffectsData(battler).fakeOutTurnNumber | 0;
    ctx.mem.calcTemp = fakeOut < (ctx.ai.totalTurns() | 0) ? 0 : 1;
  },

  // AICmd_LoadBattleType, TAI:2504-2508: calcTemp = battleSys->battleType (u32 into int).
  LoadBattleType(ctx) {
    ctx.mem.calcTemp = ctx.ai.battleType() | 0;
  },

  // AICmd_IfTargetIsPartner, TAI:2630-2639: jump if attacker and defender are on the same side.
  // Uses AI_CONTEXT.attacker/defender directly, not AIScript_Battler.
  IfTargetIsPartner(ctx, ins) {
    if ((ctx.ai.attacker & 1) === (ctx.ai.defender & 1)) ctx.jump(ins);
  },

  // AICmd_IfFieldConditionsMask, TAI:1936-1946: fieldConditionsMask & mask.
  IfFieldConditionsMask(ctx, ins) {
    const mask = ctx.arg(ins, 'field_conditions') >>> 0;
    if ((ctx.ai.fieldConditionsMask() & mask) !== 0) ctx.jump(ins);
  },

  // AICmd_LoadSpikesLayers, TAI:1948-1966. Only SIDE_CONDITION_SPIKES / _TOXIC_SPIKES load a value;
  // any other argument leaves calcTemp unchanged (the switch has no default).
  LoadSpikesLayers(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const sideCondition = ctx.arg(ins, 'side_conditions') >>> 0;
    const side = ctx.ai.side(battler);
    if (sideCondition === K(ctx, 'SIDE_CONDITION_SPIKES')) {
      ctx.mem.calcTemp = ctx.ai.spikesLayers(side) | 0;
    } else if (sideCondition === K(ctx, 'SIDE_CONDITION_TOXIC_SPIKES')) {
      ctx.mem.calcTemp = ctx.ai.toxicSpikesLayers(side) | 0;
    }
  },

  // AICmd_IfAnyPartyMemberIsWounded, TAI:1968-1985: any slot other than selectedPartySlot[battler]
  // with HP != MAX_HP. No alive / species check, so a fainted member (HP 0) counts. No doubles
  // partner exclusion either.
  IfAnyPartyMemberIsWounded(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const sel = selectedSlot(ctx, battler);
    const party = ctx.ai.party(battler);
    const count = ctx.ai.partyCount(battler);
    for (let i = 0; i < count; i++) {
      if (i !== sel && party[i].hp !== party[i].maxHP) {
        ctx.jump(ins);
        break;
      }
    }
  },

  // AICmd_IfAnyPartyMemberUsedPP, TAI:1987-2012: any slot other than selectedPartySlot[battler]
  // with MON_DATA_MOVE<n>_PP != MOVE<n>_MAX_PP for some n in 0..3. An empty move slot has PP 0 and
  // max PP 0 in the game; the adapter has no entry there, read as 0 here.
  IfAnyPartyMemberUsedPP(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    const sel = selectedSlot(ctx, battler);
    const party = ctx.ai.party(battler);
    const count = ctx.ai.partyCount(battler);
    for (let partySlot = 0; partySlot < count; partySlot++) {
      if (partySlot === sel) continue;
      const mon = party[partySlot];
      for (let moveSlot = 0; moveSlot < 4; moveSlot++) {
        if ((mon.pp[moveSlot] ?? 0) !== (mon.maxPP[moveSlot] ?? 0)) {
          ctx.jump(ins);
          return;
        }
      }
    }
  },

  // AICmd_LoadBattlerTurnCount, TAI:2096-2104: calcTemp = totalTurns - fakeOutTurnNumber (int - int).
  LoadBattlerTurnCount(ctx, ins) {
    const battler = ctx.battler(ctx.arg(ins, 'battler'));
    ctx.mem.calcTemp = ((ctx.ai.totalTurns() | 0) - (ctx.ai.moveEffectsData(battler).fakeOutTurnNumber | 0)) | 0;
  },

  // AICmd_Dummy3E / AICmd_Dummy3F, TAI:1881-1889: `return;` without AIScript_Iter, so the game
  // would re-run the same opcode forever. Unreachable from the League sections (OPCODES.md trap
  // 11); throw instead of hanging.
  Dummy3E(ctx, ins) {
    throw dummyHang(ins);
  },
  Dummy3F(ctx, ins) {
    throw dummyHang(ins);
  },
};

function dummyHang(ins) {
  const e = new Error(`ai_unimplemented: ${ins.name} (script.s:${ins.line}) never advances the script cursor (trainer_ai.c:1881-1889); the game would hang`);
  e.kind = 'ai_unimplemented';
  e.opcode = ins.name;
  e.line = ins.line;
  return e;
}
