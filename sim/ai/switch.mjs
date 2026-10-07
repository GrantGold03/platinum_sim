// T046: the trainer AI's switch decisions.
//
// Ports (TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c, BL = .../battle_lib.c @ c248fb3f):
//   TAI:3263-3272 AI_PerishSongKO
//   TAI:3286-3350 AI_CannotDamageWonderGuard
//   TAI:3361-3546 AI_OnlyIneffectiveMoves
//   TAI:3560-3624 AI_HasSuperEffectiveMove        (calcdamage.hasSuperEffectiveMove)
//   TAI:3640-3714 AI_HasAbsorbAbilityInParty
//   TAI:3727-3807 AI_HasPartyMemberWithSuperEffectiveMove
//   TAI:3817-3859 AI_IsAsleepWithNaturalCure
//   TAI:3872-3884 AI_IsHeavilyStatBoosted
//   TAI:3894-3987 TrainerAI_ShouldSwitch           -> shouldSwitch()
//   TAI:3989-4040 TrainerAI_PickCommand switch branch -> pickSwitchSlot()
//   BL:7923-8089  BattleAI_PostKOSwitchIn          -> postKOSwitchIn()  (u8 score overflow kept)
//   BL:8091-8095  BattleAI_SwitchedSlot
//   BL:2681-2743  BattleSystem_CalcEffectiveness   -> calcEffectiveness()
//   BL:3009-3029  BattleSystem_TypeMatchupMultiplier -> typeMatchupMultiplier()
//   BL:8097-8199  Move_CalcVariableType            -> moveCalcVariableType()
//   BL:2870-2950  BattleSystem_CountAbility (the modes used here)
//   battle_display.c:4543-4557 party-menu fallback when PostKOSwitchIn returns 6
//
// Singles only (battle type TRAINER): BattleSystem_GetPartner(b) == b (battle_system.c:394-412),
// so aiSlot1 == aiSlot2 == battler and defender1 == defender2 == BATTLER_PLAYER_1.
//
// `st` = { ai, rng, aiSwitchedPartySlot: u8[4], moveHit: u16[4], moveHitBattler: u8[4] }.
// battleCtx->moveHit / moveHitBattler (battle_context.h) are engine state the adapter does not
// expose; opponent.mjs reconstructs them from the Showdown log (UNVERIFIED mapping, see there).
// aiSwitchedPartySlot is reset to 6 by BattleContext_Init after every action (BL:2015;
// battle_controller_player.c:1855, 3998), so it is 6 at the start of every PickCommand and every
// post-KO replacement; the caller passes [6, 6, 6, 6].
import { DECOMP_ROOT } from './constants.mjs';
import * as calcdamage from './calcdamage.mjs';
import { TYPE_CHART, ENUMS, fromShowdown, calcBaseDamage, MOVE_STATUS } from '../damage.mjs';
import { battlerHeldItemEffect } from './choose.mjs';

void DECOMP_ROOT;
const K = (ai, n) => ai.constants.get(n);
const NO_SLOT = 6;
const typeNameOf = (t) => ENUMS.types[t];

// ---------------------------------------------------------------------------------------------
// Type helpers

// BattleSystem_TypeMatchupMultiplier (BL:3009-3029). `int mul = 40`; each matching chart row
// multiplies by its TYPE_MULTI and divides by 10 (int). The 0xFE separator never equals a type, so
// the Foresight immunities ARE applied here. Types are compared as u8 ids.
export function typeMatchupMultiplier(attackingType, defendingType1, defendingType2) {
  const atk = typeNameOf(attackingType & 0xff);
  const d1 = typeNameOf(defendingType1 & 0xff);
  const d2 = typeNameOf(defendingType2 & 0xff);
  let mul = 40;
  for (const e of TYPE_CHART.entries) {
    if (e.atk === '0xFF') break;
    if (e.atk === atk) {
      if (e.def === d1) mul = Math.trunc((mul * e.mul) / 10);
      if (e.def === d2 && d1 !== d2) mul = Math.trunc((mul * e.mul) / 10);
    }
  }
  return mul;
}

// UpateMoveStatusForTypeMul (BL:2781-2806)
function updateMoveStatusForTypeMul(mul, mask) {
  if (mul === 0) { // TYPE_MULTI_IMMUNE
    mask |= MOVE_STATUS.INEFFECTIVE;
    mask &= ~MOVE_STATUS.NOT_VERY_EFFECTIVE;
    mask &= ~MOVE_STATUS.SUPER_EFFECTIVE;
  } else if (mul === 5) { // TYPE_MULTI_NOT_VERY_EFF
    if (mask & MOVE_STATUS.SUPER_EFFECTIVE) mask &= ~MOVE_STATUS.SUPER_EFFECTIVE;
    else mask |= MOVE_STATUS.NOT_VERY_EFFECTIVE;
  } else if (mul === 20) { // TYPE_MULTI_SUPER_EFF
    if (mask & MOVE_STATUS.NOT_VERY_EFFECTIVE) mask &= ~MOVE_STATUS.NOT_VERY_EFFECTIVE;
    else mask |= MOVE_STATUS.SUPER_EFFECTIVE;
  }
  return mask;
}

// MoveIsOnDamagingTurn (BL:7588-7606): for two-turn effects it returns
// battleStatusMask & SYSCTL_LAST_OF_MULTI_TURN. During command selection that flag is taken as
// clear (UNVERIFIED: BattleContext_Init keeps `battleStatusMask &= SYSCTL_INIT`).
const TWO_TURN_EFFECTS = ['BATTLE_EFFECT_BIDE', 'BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT', 'BATTLE_EFFECT_CHARGE_TURN_HIGH_CRIT_FLINCH',
  'BATTLE_EFFECT_CHARGE_TURN_DEF_UP', 'BATTLE_EFFECT_SKIP_CHARGE_TURN_IN_SUN', 'BATTLE_EFFECT_FLY', 'BATTLE_EFFECT_DIVE',
  'BATTLE_EFFECT_DIG', 'BATTLE_EFFECT_BOUNCE', 'BATTLE_EFFECT_FLINCH_BURN_HIT'];
function moveIsOnDamagingTurn(ai, move) {
  const eff = ai.moveData(move).effect;
  return !TWO_TURN_EFFECTS.some((n) => K(ai, n) === eff);
}

/**
 * BattleSystem_CalcEffectiveness(move, inType, attackerAbility, defenderAbility,
 * defenderItemEffect, defenderType1, defenderType2, &mask) (BL:2681-2743). Returns the mask.
 */
export function calcEffectiveness(ai, { move, inType, attackerAbility, defenderAbility, defenderItemEffect, defenderType1, defenderType2 }) {
  let mask = 0;
  if (move === K(ai, 'MOVE_STRUGGLE')) return mask;
  let moveType;
  if (attackerAbility === K(ai, 'ABILITY_NORMALIZE')) moveType = K(ai, 'TYPE_NORMAL');
  else if (inType) moveType = inType;
  else moveType = ai.moveData(move).type;
  moveType &= 0xff; // u8 moveType (BL:2684)
  const gravity = (ai.fieldConditionsMask() & K(ai, 'FIELD_CONDITION_GRAVITY')) !== 0;
  const ironBall = defenderItemEffect === K(ai, 'HOLD_EFFECT_SPEED_DOWN_GROUNDED');
  if (attackerAbility !== K(ai, 'ABILITY_MOLD_BREAKER') && defenderAbility === K(ai, 'ABILITY_LEVITATE')
      && moveType === K(ai, 'TYPE_GROUND') && !gravity && !ironBall) {
    mask |= MOVE_STATUS.INEFFECTIVE;
  } else {
    const mt = typeNameOf(moveType);
    const d1 = typeNameOf(defenderType1);
    const d2 = typeNameOf(defenderType2);
    for (const e of TYPE_CHART.entries) {
      if (e.atk === '0xFF') break;
      if (e.atk === '0xFE') {
        if (attackerAbility === K(ai, 'ABILITY_SCRAPPY')) break;
        continue;
      }
      if (e.atk === mt) {
        // NoImmunityOverrides (BL:2756-2773): Iron Ball / Gravity cancel the Flying immunity row.
        const overridden = (ironBall || gravity) && e.def === 'TYPE_FLYING' && e.mul === 0;
        if (e.def === d1 && !overridden) mask = updateMoveStatusForTypeMul(e.mul, mask);
        if (e.def === d2 && defenderType1 !== defenderType2 && !overridden) mask = updateMoveStatusForTypeMul(e.mul, mask);
      }
    }
  }
  if (attackerAbility !== K(ai, 'ABILITY_MOLD_BREAKER') && defenderAbility === K(ai, 'ABILITY_WONDER_GUARD')
      && moveIsOnDamagingTurn(ai, move)
      && (!(mask & MOVE_STATUS.SUPER_EFFECTIVE)
        || (mask & MOVE_STATUS.BASIC_EFFECTIVENESS) === MOVE_STATUS.BASIC_EFFECTIVENESS)) {
    mask |= MOVE_STATUS.INEFFECTIVE;
  }
  return mask >>> 0;
}

// Move_CalcVariableType(mon, move) (BL:8097-8199). `entry` is an adapter party entry.
export function moveCalcVariableType(ai, entry, move) {
  const item = ai.itemData(entry.heldItem);
  switch (move) {
    case K(ai, 'MOVE_NATURAL_GIFT'):
      // ITEM_PARAM_NATURAL_GIFT_TYPE; `null` in the item JSON is stored as 31 (see calcdamage itemParam)
      return item ? (item.naturalGiftType === undefined ? 31 : item.naturalGiftType) : 31;
    case K(ai, 'MOVE_JUDGMENT'): {
      const he = item ? item.holdEffect : 0;
      for (const [h, ty] of calcdamage.JUDGMENT_TYPES) if (K(ai, h) === he) return K(ai, ty);
      return K(ai, 'TYPE_NORMAL');
    }
    case K(ai, 'MOVE_HIDDEN_POWER'): {
      const iv = entry.ivs; // [hp, atk, def, spe, spa, spd]
      let type = (iv[0] & 1) | ((iv[1] & 1) << 1) | ((iv[2] & 1) << 2) | ((iv[3] & 1) << 3) | ((iv[4] & 1) << 4) | ((iv[5] & 1) << 5);
      type = Math.trunc((type * 15) / 63) + 1;
      if (type >= K(ai, 'TYPE_MYSTERY')) type++;
      return type;
    }
    case K(ai, 'MOVE_WEATHER_BALL'): {
      // `type` is only assigned under weather (BL:8175-8193); otherwise it is uninitialised.
      const fc = ai.fieldConditionsMask();
      const noCloud = ![0, 1].some((b) => ai.curHP(b) && [K(ai, 'ABILITY_CLOUD_NINE'), K(ai, 'ABILITY_AIR_LOCK')].includes(ai.battlerAbility(b)));
      let type;
      if (noCloud && (fc & K(ai, 'FIELD_CONDITION_WEATHER'))) {
        if (fc & K(ai, 'FIELD_CONDITION_RAINING')) type = K(ai, 'TYPE_WATER');
        if (fc & K(ai, 'FIELD_CONDITION_SANDSTORM')) type = K(ai, 'TYPE_ROCK');
        if (fc & K(ai, 'FIELD_CONDITION_SUNNY')) type = K(ai, 'TYPE_FIRE');
        if (fc & K(ai, 'FIELD_CONDITION_HAILING')) type = K(ai, 'TYPE_ICE');
      }
      if (type === undefined) throw new Error('switch: Move_CalcVariableType(Weather Ball) reads an uninitialised type (BL:8174-8195)');
      return type;
    }
    default:
      return K(ai, 'TYPE_NORMAL');
  }
}

// MON_DATA_TYPE_1 / _2 of a party Pokemon: the species' types (decomp species data).
function partyTypes(ai, entry) {
  const t = ai.tables.species[entry.species].types;
  return [t[0], t[1] ?? t[0]];
}

// Pokemon_GetValue(HP) != 0 && SPECIES_OR_EGG not NONE/EGG
function aliveReal(ai, entry) {
  return entry.hp !== 0 && entry.species !== K(ai, 'SPECIES_NONE') && entry.species !== K(ai, 'SPECIES_EGG');
}

const selSlot = (ai, b) => ai.selectedPartySlot(b) & 0xff; // u8 selectedPartySlot (battle_context.h:252)

// The bench filter repeated in every helper: not either active slot, not either aiSwitchedPartySlot.
function benchEligible(st, battler, i, entry) {
  const { ai } = st;
  return aliveReal(ai, entry) && i !== selSlot(ai, battler) && i !== st.aiSwitchedPartySlot[battler];
}

// BattleSystem_CountAbility (BL:2870-2950), singles (maxBattlers 2).
function countAbility(ai, mode, battler, ability) {
  let result = 0;
  for (let i = 0; i < ai.maxBattlers; i++) {
    if (mode === 'THEIR_SIDE' && ai.side(i) !== ai.side(battler) && ai.battlerAbility(i) === ability) result++;
    if (mode === 'EXCEPT_ME' && i !== battler && ai.battlerAbility(i) === ability) result++;
  }
  return result;
}

const env = (st) => ({ ai: st.ai, rand: () => st.rng.next(), mem: st.mem ?? {} });

// ---------------------------------------------------------------------------------------------
// ShouldSwitch helpers

// AI_PerishSongKO (TAI:3263-3272). perishSongTurns == 0 with the effect set: Showdown keeps the
// 'perishsong' volatile with duration 1 on its last turn; the game's counter is decremented at the
// end of turn so it is never 0 at decision time (the routine "functionally does nothing",
// TAI:3256-3259). The adapter exposes no perishSongTurns; this port returns FALSE when the
// effect is absent and throws if it is present (never reached by League parties: no Perish Song).
function perishSongKO(st, battler) {
  const { ai } = st;
  if (ai.moveEffectsMask(battler) & K(ai, 'MOVE_EFFECT_PERISH_SONG')) {
    throw new Error('switch: AI_PerishSongKO needs moveEffectsData.perishSongTurns, which the adapter does not expose');
  }
  return false;
}

function cannotDamageWonderGuard(st, battler) {
  const { ai } = st;
  if (ai.battleType() & K(ai, 'BATTLE_TYPE_DOUBLES')) return false;
  const opp = battler ^ 1;
  if (ai.ability(opp) !== K(ai, 'ABILITY_WONDER_GUARD')) return false; // battleMons[].ability (raw)
  const e = env(st);
  const moves = ai.moves(battler);
  for (let i = 0; i < 4; i++) {
    const move = moves[i];
    const moveType = calcdamage.moveType(e, battler, move);
    if (move) {
      const { moveStatusMask } = calcdamage.applyTypeChart(e, { move, type: moveType, attacker: battler, defender: opp, damage: 0 });
      if (moveStatusMask & MOVE_STATUS.SUPER_EFFECTIVE) return false;
    }
  }
  const party = ai.party(battler);
  for (let i = 0; i < ai.partyCount(battler); i++) {
    const p = party[i];
    if (aliveReal(ai, p) && i !== selSlot(ai, battler)) {
      for (let j = 0; j < 4; j++) {
        const move = p.moves[j] ?? 0;
        const moveType = moveCalcVariableType(ai, p, move);
        if (move) {
          const [t1, t2] = ai.types(opp);
          const mask = calcEffectiveness(ai, { move, inType: moveType, attackerAbility: p.ability, defenderAbility: ai.battlerAbility(opp),
            defenderItemEffect: battlerHeldItemEffect(ai, opp), defenderType1: t1, defenderType2: t2 });
          if ((mask & MOVE_STATUS.SUPER_EFFECTIVE) && st.rng.next() % 3 < 2) {
            st.aiSwitchedPartySlot[battler] = i;
            return true;
          }
        }
      }
    }
  }
  return false;
}

function onlyIneffectiveMoves(st, battler) {
  const { ai } = st;
  const defender1 = 0; // BATTLER_PLAYER_1 (singles: defender2 == defender1, TAI:3374-3380)
  const defender2 = 0;
  const e = env(st);
  const moves = ai.moves(battler);
  let numMoves = 0;
  for (let i = 0; i < 4; i++) {
    const move = moves[i];
    const type = calcdamage.moveType(e, battler, move);
    if (move && ai.moveData(move).power) {
      numMoves++;
      let eff = 0;
      if (ai.curHP(defender1)) eff = calcdamage.applyTypeChart(e, { move, type, attacker: battler, defender: defender1, damage: 0 }).moveStatusMask;
      if ((eff & MOVE_STATUS.INEFFECTIVE) === 0) return false;
      eff = 0;
      if (ai.curHP(defender2)) eff = calcdamage.applyTypeChart(e, { move, type, attacker: battler, defender: defender2, damage: 0 }).moveStatusMask;
      if ((eff & MOVE_STATUS.INEFFECTIVE) === 0) return false;
    }
  }
  if (numMoves < 2) return false; // TAI:3413-3415
  const party = ai.party(battler);
  const sweep = (accept) => {
    for (let i = 0; i < ai.partyCount(battler); i++) {
      const p = party[i];
      if (!benchEligible(st, battler, i, p)) continue;
      for (let j = 0; j < 4; j++) {
        const move = p.moves[j] ?? 0;
        const type = moveCalcVariableType(ai, p, move);
        if (move && ai.moveData(move).power) {
          for (const d of [defender1, defender2]) {
            let eff = 0;
            if (ai.curHP(d)) {
              const [t1, t2] = ai.types(d);
              eff = calcEffectiveness(ai, { move, inType: type, attackerAbility: p.ability, defenderAbility: ai.battlerAbility(d),
                defenderItemEffect: battlerHeldItemEffect(ai, d), defenderType1: t1, defenderType2: t2 });
            }
            if (accept(eff)) {
              st.aiSwitchedPartySlot[battler] = i;
              return true;
            }
          }
        }
      }
    }
    return false;
  };
  // TAI:3431-3484: super-effective member, 2/3 of the time (one draw per SE check)
  if (sweep((eff) => (eff & MOVE_STATUS.SUPER_EFFECTIVE) && st.rng.next() % 3 < 2)) return true;
  // TAI:3490-3543: neutral member (mask exactly 0), 1/2 of the time
  if (sweep((eff) => eff === 0 && st.rng.next() % 2 === 0)) return true;
  return false;
}

function hasAbsorbAbilityInParty(st, battler) {
  const { ai } = st;
  const e = env(st);
  // TAI:3651: short-circuit: the % 3 draw only happens when the SE check is TRUE
  if (calcdamage.hasSuperEffectiveMove(e, battler, true) && st.rng.next() % 3 !== 0) return false;
  const hit = st.moveHit[battler];
  if (hit === 0) return false;
  if (ai.moveData(hit).power === 0) return false;
  const moveType = ai.moveData(hit).type;
  let checkAbility;
  if (moveType === K(ai, 'TYPE_FIRE')) checkAbility = K(ai, 'ABILITY_FLASH_FIRE');
  else if (moveType === K(ai, 'TYPE_WATER')) checkAbility = K(ai, 'ABILITY_WATER_ABSORB');
  else if (moveType === K(ai, 'TYPE_ELECTRIC')) checkAbility = K(ai, 'ABILITY_VOLT_ABSORB');
  else return false; // `return ABILITY_NONE` (0) (TAI:3673)
  if (ai.battlerAbility(battler) === checkAbility) return false;
  const party = ai.party(battler);
  for (let i = 0; i < ai.partyCount(battler); i++) {
    const p = party[i];
    if (benchEligible(st, battler, i, p)) {
      const ability = p.ability & 0xff; // u8 ability (TAI:3645)
      if (checkAbility === ability && (st.rng.next() & 1)) {
        st.aiSwitchedPartySlot[battler] = i;
        return true;
      }
    }
  }
  return false;
}

function hasPartyMemberWithSuperEffectiveMove(st, battler, checkEffectiveness, rand) {
  const { ai } = st;
  const hit = st.moveHit[battler];
  const hitBy = st.moveHitBattler[battler];
  if (hit === 0 || hitBy === K(ai, 'BATTLER_NONE')) return false;
  if (ai.moveData(hit).power === 0) return false;
  const e = env(st);
  const party = ai.party(battler);
  for (let i = 0; i < ai.partyCount(battler); i++) {
    const p = party[i];
    if (!benchEligible(st, battler, i, p)) continue;
    const [pt1, pt2] = partyTypes(ai, p);
    const hitType = calcdamage.moveType(e, hitBy, hit);
    let eff = calcEffectiveness(ai, { move: hit, inType: hitType, attackerAbility: ai.battlerAbility(hitBy), defenderAbility: p.ability,
      defenderItemEffect: ai.itemHoldEffect(p.heldItem), defenderType1: pt1, defenderType2: pt2 });
    if (eff & checkEffectiveness) {
      for (let j = 0; j < 4; j++) {
        const move = p.moves[j] ?? 0;
        const moveType = moveCalcVariableType(ai, p, move);
        if (move) {
          const [t1, t2] = ai.types(hitBy);
          eff = calcEffectiveness(ai, { move, inType: moveType, attackerAbility: p.ability, defenderAbility: ai.battlerAbility(hitBy),
            defenderItemEffect: battlerHeldItemEffect(ai, hitBy), defenderType1: t1, defenderType2: t2 });
          if ((eff & MOVE_STATUS.SUPER_EFFECTIVE) && st.rng.next() % rand === 0) {
            st.aiSwitchedPartySlot[battler] = i;
            return true;
          }
        }
      }
    }
  }
  return false;
}

function isAsleepWithNaturalCure(st, battler) {
  const { ai } = st;
  if ((ai.status(battler) & K(ai, 'MON_CONDITION_SLEEP')) === 0
      || ai.battlerAbility(battler) !== K(ai, 'ABILITY_NATURAL_CURE')
      || ai.curHP(battler) < Math.trunc(ai.maxHP(battler) / 2)) return false;
  if (st.moveHit[battler] === 0 && (st.rng.next() & 1)) { st.aiSwitchedPartySlot[battler] = NO_SLOT; return true; }
  if (ai.moveData(st.moveHit[battler]).power === 0 && (st.rng.next() & 1)) { st.aiSwitchedPartySlot[battler] = NO_SLOT; return true; }
  if (hasPartyMemberWithSuperEffectiveMove(st, battler, MOVE_STATUS.INEFFECTIVE, 1)) return true;
  if (hasPartyMemberWithSuperEffectiveMove(st, battler, MOVE_STATUS.NOT_VERY_EFFECTIVE, 1)) return true;
  if (st.rng.next() & 1) { st.aiSwitchedPartySlot[battler] = NO_SLOT; return true; }
  return false;
}

// AI_IsHeavilyStatBoosted (TAI:3872-3884): u8 sum of (stage - 6) over HP..EVASION.
function isHeavilyStatBoosted(st, battler) {
  const { ai } = st;
  let numBoosts = 0;
  for (let stat = K(ai, 'BATTLE_STAT_HP'); stat < K(ai, 'BATTLE_STAT_MAX'); stat++) {
    const s = ai.statBoost(battler, stat);
    if (s > 6) numBoosts = (numBoosts + s - 6) & 0xff;
  }
  return numBoosts >= 4;
}

// ---------------------------------------------------------------------------------------------
// TrainerAI_ShouldSwitch (TAI:3894-3987)

export function shouldSwitch(st, battler = 1) {
  const { ai } = st;
  const vol = ai.statusVolatile(battler);
  const [t1, t2] = ai.types(battler);
  const steel = K(ai, 'TYPE_STEEL');
  if ((vol & K(ai, 'VOLATILE_CONDITION_TRAPPED'))
      || (ai.moveEffectsMask(battler) & K(ai, 'MOVE_EFFECT_INGRAIN'))
      || countAbility(ai, 'THEIR_SIDE', battler, K(ai, 'ABILITY_SHADOW_TAG'))
      || countAbility(ai, 'THEIR_SIDE', battler, K(ai, 'ABILITY_ARENA_TRAP'))
      || (countAbility(ai, 'EXCEPT_ME', battler, K(ai, 'ABILITY_MAGNET_PULL')) && (t1 === steel || t2 === steel))) {
    return false;
  }
  let alivePartyMons = 0;
  const party = ai.party(battler);
  for (let i = 0; i < ai.partyCount(battler); i++) {
    if (benchEligible(st, battler, i, party[i])) alivePartyMons++;
  }
  if (alivePartyMons) {
    if (perishSongKO(st, battler)) return true;
    if (cannotDamageWonderGuard(st, battler)) return true;
    if (onlyIneffectiveMoves(st, battler)) return true;
    if (hasAbsorbAbilityInParty(st, battler)) return true;
    if (isAsleepWithNaturalCure(st, battler)) return true;
    if (calcdamage.hasSuperEffectiveMove(env(st), battler, false)) return false;
    if (isHeavilyStatBoosted(st, battler)) return false;
    if (hasPartyMemberWithSuperEffectiveMove(st, battler, 0x8, 2)) return true; // MOVE_STATUS_INEFFECTIVE
    if (hasPartyMemberWithSuperEffectiveMove(st, battler, 0x4, 3)) return true; // MOVE_STATUS_NOT_VERY_EFFECTIVE
  }
  return false;
}

// ---------------------------------------------------------------------------------------------
// BattleAI_PostKOSwitchIn (BL:7923-8089)

/** Returns the party slot (0..5) or 6 if none. `trace` (optional array) gets stage scores. */
export function postKOSwitchIn(st, battler = 1, trace = null) {
  const { ai } = st;
  const defender = battler ^ 1; // BattleSystem_RandomOpponent, singles (BL:4193-4195)
  const partySize = ai.partyCount(battler);
  const party = ai.party(battler);
  let battlersDisregarded = 0; // u8
  let score; // u8, deliberately carried between stages and loop iterations as in the C
  let maxScore; // u8 (BUG: overflow, docs/bugs_and_glitches.md "Post-KO Switch-In AI Scoring Overflow")
  let picked = NO_SLOT;
  const eligible = (i, p) => p.species !== K(ai, 'SPECIES_NONE') && p.species !== K(ai, 'SPECIES_EGG') && p.hp
    && selSlot(ai, battler) !== i && i !== st.aiSwitchedPartySlot[battler];
  const [defType1, defType2] = ai.types(defender).map((t) => t & 0xff);

  // Stage 1 (BL:7958-8025)
  while (battlersDisregarded !== 0x3f) {
    maxScore = 0;
    picked = NO_SLOT;
    for (let i = 0; i < partySize; i++) {
      const p = party[i];
      if (eligible(i, p) && (battlersDisregarded & (1 << i)) === 0) {
        const [monType1, monType2] = partyTypes(ai, p).map((t) => t & 0xff);
        score = typeMatchupMultiplier(monType1, defType1, defType2) & 0xff;
        score = (score + typeMatchupMultiplier(monType2, defType1, defType2)) & 0xff;
        if (trace) trace.push({ stage: 1, slot: i, score });
        if (maxScore < score) {
          maxScore = score;
          picked = i;
        }
      } else {
        battlersDisregarded = (battlersDisregarded | (1 << i)) & 0xff;
      }
    }
    if (picked !== NO_SLOT) {
      const p = party[picked];
      let i;
      for (i = 0; i < 4; i++) {
        const move = p.moves[i] ?? 0;
        const moveType = moveCalcVariableType(ai, p, move);
        if (move) {
          const mask = calcEffectiveness(ai, { move, inType: moveType, attackerAbility: p.ability, defenderAbility: ai.battlerAbility(defender),
            defenderItemEffect: battlerHeldItemEffect(ai, defender), defenderType1: defType1, defenderType2: defType2 });
          if (mask & MOVE_STATUS.SUPER_EFFECTIVE) break;
        }
      }
      if (i === 4) battlersDisregarded = (battlersDisregarded | (1 << picked)) & 0xff;
      else return picked;
    } else {
      battlersDisregarded = 0x3f;
    }
  }

  // Stage 2 (BL:8032-8086)
  maxScore = 0;
  picked = NO_SLOT;
  const att = ai.pokemon(battler); // battleMons[battler]: the fainted (or U-turning) battler
  const def = ai.pokemon(defender);
  for (let i = 0; i < partySize; i++) {
    const p = party[i];
    if (!eligible(i, p)) continue;
    for (let j = 0; j < 4; j++) {
      const move = p.moves[j] ?? 0;
      const moveType = moveCalcVariableType(ai, p, move);
      if (move && ai.moveData(move).power !== 1) {
        // BattleSystem_CalcMoveDamage(move, sideConditions[defender side], fieldConditions,
        // power 0, type 0, battler, defender, critMul 1); powerMul taken as 10 (its reset value).
        const input = fromShowdown(ai.battle, att, def, move, { power: 0, type: undefined, powerMul: 10 });
        score = calcBaseDamage({ ...input, critMul: 1 }) & 0xff;
        const r = calcdamage.applyTypeChart(env(st), { move, type: moveType, attacker: battler, defender, damage: score });
        score = r.damage & 0xff;
        if (r.moveStatusMask & MOVE_STATUS.IMMUNE) score = 0;
      }
      if (score === undefined) throw new Error('switch: PostKOSwitchIn read an uninitialised score');
      if (trace) trace.push({ stage: 2, slot: i, move, score });
      if (maxScore < score) {
        maxScore = score;
        picked = i;
      }
    }
  }
  return picked;
}

// battle_display.c:4549-4556: first party slot with HP that is not an active slot.
export function firstAliveFallback(ai, battler) {
  const party = ai.party(battler);
  let slot;
  for (slot = 0; slot < ai.partyCount(battler); slot++) {
    if (party[slot].hp && selSlot(ai, battler) !== slot) break;
  }
  return slot;
}

// TrainerAI_PickCommand switch branch (TAI:4001-4030): post-KO logic when the chosen slot is 6,
// then a first-alive fallback (which also skips aiSwitchedPartySlot, TAI:4018-4022).
export function pickSwitchSlot(st, battler = 1) {
  const { ai } = st;
  if (st.aiSwitchedPartySlot[battler] === NO_SLOT) {
    let i = postKOSwitchIn(st, battler);
    if (i === NO_SLOT) {
      const party = ai.party(battler);
      for (i = 0; i < ai.partyCount(battler); i++) {
        if (party[i].hp !== 0 && i !== selSlot(ai, battler) && i !== st.aiSwitchedPartySlot[battler]) break;
      }
    }
    st.aiSwitchedPartySlot[battler] = i;
  }
  return st.aiSwitchedPartySlot[battler];
}

// Post-KO / forced replacement (battle_display.c:4543-4557): BattleAI_SwitchedSlot (6 after
// BattleContext_Init), then PostKOSwitchIn, then the party-menu fallback.
export function replacementSlot(st, battler = 1, trace = null) {
  let slot = st.aiSwitchedPartySlot[battler];
  if (slot === NO_SLOT) {
    slot = postKOSwitchIn(st, battler, trace);
    if (slot === NO_SLOT) slot = firstAliveFallback(st.ai, battler);
  }
  return slot;
}
