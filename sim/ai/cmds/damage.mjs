// Trainer-AI opcode handlers: damage group (see ../OPCODES.md column "File" and ../INTERFACE.md).
// Each handler: (ctx, ins) => void. Cite the trainer_ai.c handler line in a comment for each.
// TAI = pokeplatinum/src/battle/trainer_ai/trainer_ai.c.
//
// The damage estimator is ../calcdamage.mjs (TrainerAI_CalcDamage / CalcAllDamage / MoveType /
// AI_HasSuperEffectiveMove). Handlers use `ctx.damage` when the caller (T045) provides it, else
// that module. Its functions take `ctx` as `env` (ctx.ai, ctx.rand, ctx.mem).
//
// AIScript_Read returns `int` (TAI:2726); the boolean args are compared `== TRUE` (TRUE = 1).
import * as calcdamage from '../calcdamage.mjs';

const D = (ctx) => ctx.damage ?? calcdamage;
const K = (ctx, n) => ctx.ai.constants.get(n);
const TRUE = 1;

// BattleMon_Get(battler, BATTLEMON_HP_IV + i) for i in STAT_HP..STAT_SPECIAL_DEFENSE.
const attackerIvs = (ctx) => ctx.ai.ivs(ctx.ai.attacker);

// The arguments every "AI attacker's own moves" CalcAllDamage call passes (TAI:1040-1050,
// 2129-2138, 2207-2216): real moves, real heldItem, IVs, Battler_Ability, embargoTurns.
function attackerAllDamage(ctx, varyDamage) {
  const { ai } = ctx;
  const a = ai.attacker;
  return D(ctx).calcAllDamage(ctx, {
    attacker: a,
    moves: ai.moves(a),
    heldItem: ai.heldItem(a),
    ivs: attackerIvs(ctx),
    ability: ai.battlerAbility(a),
    embargoTurns: ai.moveEffectsData(a).embargoTurns,
    varyDamage,
  });
}

export const handlers = {
  // AICmd_FlagMoveDamageScore, TAI:1012-1066. Eligibility of AI_CONTEXT.move (TAI:1023-1036), then
  // CalcAllDamage over the attacker's moves; calcTemp = IS_HIGHEST if no slot does strictly more
  // than moveSlot's value (TAI:1052-1062), else NOT_HIGHEST; ineligible -> NO_COMPARISON_MADE.
  FlagMoveDamageScore(ctx, ins) {
    const varyDamage = ctx.arg(ins, 'bool') | 0;
    const m = ctx.mem;
    if (D(ctx).damageCheckApplies(ctx.ai, m.move)) {
      const { damageVals } = attackerAllDamage(ctx, varyDamage);
      let i;
      for (i = 0; i < 4; i++) {
        if (damageVals[i] > damageVals[m.moveSlot]) break;
      }
      m.calcTemp = i === 4 ? K(ctx, 'AI_MOVE_IS_HIGHEST_DAMAGE') : K(ctx, 'AI_NOT_HIGHEST_DAMAGE');
    } else {
      m.calcTemp = K(ctx, 'AI_NO_COMPARISON_MADE');
    }
  },

  // AICmd_IfMoveEffectivenessEquals, TAI:1311-1346. ApplyTypeChart on TYPE_MULTI_BASE_DAMAGE (40)
  // with TrainerAI_MoveType's type; the u32 result is mapped STAB*2 -> DOUBLE, STAB*4 -> QUADRUPLE,
  // STAB/2 -> HALF, STAB/4 -> QUARTER (other values, e.g. 60 for neutral STAB, stay as they are);
  // MOVE_STATUS_IMMUNE -> TYPE_MULTI_IMMUNE; jump if equal to `modifier`.
  IfMoveEffectivenessEquals(ctx, ins) {
    const expected = ctx.arg(ins, 'modifier') | 0;
    const { ai, mem } = ctx;
    const type = D(ctx).moveType(ctx, ai.attacker, mem.move);
    const r = D(ctx).applyTypeChart(ctx, {
      move: mem.move, type, attacker: ai.attacker, defender: ai.defender, damage: K(ctx, 'TYPE_MULTI_BASE_DAMAGE'),
    });
    let damage = r.damage >>> 0;
    const stab = K(ctx, 'TYPE_MULTI_STAB_DAMAGE');
    if (damage === stab * 2) damage = K(ctx, 'TYPE_MULTI_DOUBLE_DAMAGE');
    else if (damage === stab * 4) damage = K(ctx, 'TYPE_MULTI_QUADRUPLE_DAMAGE');
    else if (damage === Math.trunc(stab / 2)) damage = K(ctx, 'TYPE_MULTI_HALF_DAMAGE');
    else if (damage === Math.trunc(stab / 4)) damage = K(ctx, 'TYPE_MULTI_QUARTER_DAMAGE');
    if (r.moveStatusMask & K(ctx, 'MOVE_STATUS_IMMUNE')) damage = K(ctx, 'TYPE_MULTI_IMMUNE');
    // `damage == expected`: u32 vs int -> compared as unsigned.
    if (damage === (expected >>> 0)) ctx.jump(ins);
  },

  // AICmd_IfCurrentMoveKills, TAI:1525-1567. roll = moveDamageRolls[moveSlot] if the arg == TRUE,
  // else 100; same eligibility as FlagMoveDamageScore; TrainerAI_CalcDamage of AI_CONTEXT.move
  // (u32 result); jump if defender curHP <= damage. Ineligible moves never jump.
  IfCurrentMoveKills(ctx, ins) {
    const useDamageRoll = ctx.arg(ins, 'roll_damage') | 0;
    const { ai, mem } = ctx;
    const roll = useDamageRoll === TRUE ? mem.moveDamageRolls[mem.moveSlot] : 100;
    if (D(ctx).damageCheckApplies(ai, mem.move)) {
      const a = ai.attacker;
      const damage = D(ctx).calcDamage(ctx, {
        move: mem.move,
        heldItem: ai.heldItem(a),
        ivs: attackerIvs(ctx),
        attacker: a,
        ability: ai.battlerAbility(a),
        embargoTurns: ai.moveEffectsData(a).embargoTurns,
        variance: roll,
      }) >>> 0;
      if (ai.curHP(ai.defender) <= damage) ctx.jump(ins);
    }
  },

  // AICmd_IfPartyMemberDealsMoreDamage, TAI:2106-2174. Max of the active attacker's moves, then for
  // each other party slot with HP != 0 and species not NONE/EGG: CalcAllDamage with that mon's
  // moves, held item, IVs and (raw) ability, embargo FALSE, but attacker = AI_CONTEXT.attacker, so
  // the stats/types/level are still the active battler's (BattleSystem_CalcMoveDamage reads
  // battleMons[attacker]). Jump (and stop) at the first strictly higher party member.
  IfPartyMemberDealsMoreDamage(ctx, ins) {
    const varyDamage = ctx.arg(ins, 'roll_damage') | 0;
    const { ai } = ctx;
    const battler = ai.attacker;
    const activeMonDamage = attackerAllDamage(ctx, varyDamage).max;
    const party = ai.party(battler);
    const count = ai.partyCount(battler);
    const selected = ai.selectedPartySlot(battler);
    for (let i = 0; i < count; i++) {
      if (i === selected) continue;
      const p = party[i];
      if (p.hp !== 0 && p.species !== K(ctx, 'SPECIES_NONE') && p.species !== K(ctx, 'SPECIES_EGG')) {
        const moves = [0, 1, 2, 3].map((j) => p.moves[j] ?? 0);
        const partyMonDamage = D(ctx).calcAllDamage(ctx, {
          attacker: ai.attacker, moves, heldItem: p.heldItem, ivs: p.ivs, ability: p.ability, embargoTurns: 0, varyDamage,
        }).max;
        if (partyMonDamage > activeMonDamage) {
          ctx.jump(ins);
          break;
        }
      }
    }
  },

  // AICmd_IfHasSuperEffectiveMove, TAI:2176-2185: AI_HasSuperEffectiveMove(attacker, TRUE).
  IfHasSuperEffectiveMove(ctx, ins) {
    if (D(ctx).hasSuperEffectiveMove(ctx, ctx.ai.attacker, true) === true) ctx.jump(ins);
  },

  // AICmd_IfBattlerDealsMoreDamage, TAI:2187-2241 (OPCODES.md trap 4). aiDamage = CalcAllDamage
  // max over the AI's moves; battlerDamage = TrainerAI_CalcDamage(movePrevByBattler[b], b's real
  // item, the AI attacker's IVs, attacker = b, Battler_Ability(b), b's embargoTurns, roll), where
  // roll = moveDamageRolls[moveSlot] if varyDamage == TRUE else 100, and the defender is still
  // AI_CONTEXT.defender. No eligibility check: MOVE_NONE and status moves are computed too.
  IfBattlerDealsMoreDamage(ctx, ins) {
    const inBattler = ctx.arg(ins, 'battler');
    const varyDamage = ctx.arg(ins, 'roll_damage') | 0;
    const { ai, mem } = ctx;
    const ivs = attackerIvs(ctx);
    const aiDamage = attackerAllDamage(ctx, varyDamage).max;
    const battler = ctx.battler(inBattler);
    const roll = varyDamage === TRUE ? mem.moveDamageRolls[mem.moveSlot] : 100;
    const battlerDamage = D(ctx).calcDamage(ctx, {
      move: ai.movePrevByBattler(battler),
      heldItem: ai.heldItem(battler),
      ivs,
      attacker: battler,
      ability: ai.battlerAbility(battler),
      embargoTurns: ai.moveEffectsData(battler).embargoTurns,
      variance: roll,
    });
    if (battlerDamage > aiDamage) ctx.jump(ins);
  },
};
