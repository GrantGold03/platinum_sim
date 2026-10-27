# Trainer-AI opcodes reachable from the League sections

The work order used for T040–T044 (done). Generated from `node sim/ai/parse.mjs`, then annotated by reading every
handler in `pokeplatinum/src/battle/trainer_ai/trainer_ai.c` (TAI below).

- **League flags**: BASIC, EVAL_ATTACK, EXPERT for Aaron, Bertha, Flint and Cynthia
  (`res/trainers/data/elite_four_aaron.json:8-12`, `champion_cynthia.json:10-14`, and the same in
  bertha/flint). Lucian adds SETUP_FIRST_TURN (`elite_four_lucian.json:8-13`).
- **Entry points**: FlagTable bit 0–3 → `Basic_Main` (script.s:52), `EvalAttack_Main` (:6353),
  `Expert_Main` (:1623), `SetupFirstTurn_Main` (:6417). The four sections span script.s:52–6498.
- **Reachability**: static control flow from those four labels (`reachableFrom` in `parse.mjs`).
  This is a superset of what runs in singles: it includes branches that need doubles state.
  Result: **2,888 reachable instructions, 77 of the 109 opcodes**. No reachable instruction names
  a partner battler (`AI_BATTLER_*_PARTNER`); the test asserts this.
- **Count** = static occurrences in the reachable code. **First** = first reachable script.s line.
- **Adapter** = query names in `sim/ai/adapter.mjs` (`ai.` prefix omitted). "AI mem" = AI_CONTEXT
  memory that the interpreter (T045) must own: `battlerMoves`, `battlerAbilities`,
  `battlerHeldItems` (ai_context.h:27-29), `move`, `moveSlot`, `calcTemp`, `moveScore`,
  `moveDamageRolls`.
- **Common handler shape**: every handler first skips the opcode word (`AIScript_Iter(1)`), reads
  its arguments in order, and jumps with `AIScript_Iter(jump)` (`parse.mjs` gives `targetInstr`).
  Battler arguments go through `AIScript_Battler` (TAI:2765): ATTACKER → `attacker` (1),
  DEFENDER and any other value → `defender` (0).

## Table

| Op | Name | Handler (TAI line) | Count | First | Semantics | Adapter | File |
|---:|---|---|---:|---:|---|---|---|
| 0 | IfRandomLessThan | AICmd_IfRandomLessThan :528 | 240 | 1821 | jump if `RandNext() % 256 < i`. Draws one value every time it runs. | (run PRNG) | misc |
| 4 | AddToMoveScore | AICmd_AddToMoveScore :576 | 378 | 514 | `moveScore[moveSlot] += i`; if result < 0 set 0. **moveScore is `s8`** (ai_context.h:14): see trap 1. | AI mem | flow |
| 5 | IfHPPercentLessThan | AICmd_IfHPPercentLessThan :588 | 56 | 337 | `curHP*100/maxHP` (u32, truncating) `< i` → jump | curHP, maxHP | battler |
| 6 | IfHPPercentGreaterThan | :603 | 84 | 1869 | same, `>` | curHP, maxHP | battler |
| 7 | IfHPPercentEqualTo | :618 | 3 | 2649 | same, `==` (only used with 100) | curHP, maxHP | battler |
| 8 | IfHPPercentNotEqualTo | :633 | 7 | 513 | same, `!=` (only with 100) | curHP, maxHP | battler |
| 9 | IfStatus | AICmd_IfStatus :648 | 36 | 290 | jump if `status & mask` (MON_CONDITION_*) | status | battler |
| 10 | IfNotStatus | :662 | 11 | 324 | jump if `(status & mask) == 0` | status | battler |
| 11 | IfVolatileStatus | :676 | 30 | 323 | jump if `statusVolatile & mask` | statusVolatile | battler |
| 12 | IfNotVolatileStatus | :690 | 4 | 2239 | negation | statusVolatile | battler |
| 13 | IfMoveEffect | :704 | 34 | 641 | jump if `moveEffectsMask & mask` (MOVE_EFFECT_*) | moveEffectsMask | battler |
| 14 | IfNotMoveEffect | :718 | 6 | 2222 | negation | moveEffectsMask | battler |
| 15 | IfSideCondition | :732 | 42 | 291 | jump if `sideConditionsMask[side(battler)] & mask` | side, sideConditionsMask | misc |
| 17 | IfLoadedLessThan | :762 | 7 | 1205 | `calcTemp < v` → jump | AI mem | flow |
| 18 | IfLoadedGreaterThan | :774 | 36 | 2590 | `calcTemp > v` | AI mem | flow |
| 19 | IfLoadedEqualTo | :786 | 282 | 63 | `calcTemp == v` | AI mem | flow |
| 20 | IfLoadedNotEqualTo | :798 | 42 | 118 | `calcTemp != v` | AI mem | flow |
| 21 | IfLoadedMask | :810 | 3 | 1194 | `calcTemp & mask` | AI mem | flow |
| 22 | IfLoadedNotMask | :822 | 1 | 895 | `(calcTemp & mask) == 0` | AI mem | flow |
| 23 | IfMoveEqualTo | :834 | 17 | 57 | `AI_CONTEXT.move == v` | AI mem | moves |
| 25 | IfLoadedinTable | AICmd_IfLoadedInTable :858 | 25 | 1213 | scan words at table until `0xFFFFFFFF` (int −1); jump on `calcTemp == entry`. Table word = table − word − 2, read with cursor at opcode+3 (use `image`). | AI mem | flow |
| 26 | IfLoadedNotinTable | :876 | 8 | 1057 | jump if no entry matches | AI mem | flow |
| 28 | IfAttackerHasNoDamagingMoves | :913 | 1 | 2688 | jump if no attacker move has `MOVE_DATA.power != 0` | moves, moveData | moves |
| 29 | LoadTurnCount | :931 | 4 | 1385 | `calcTemp = totalTurns` (0 on the first turn) | totalTurns | misc |
| 30 | LoadTypeFrom | :937 | 65 | 82 | `calcTemp` = attacker/defender type1/type2, or `MOVE_DATA(move).type` (LOAD_MOVE_TYPE: table type, not Hidden Power etc.). League args: ATTACKER/DEFENDER TYPE_1/2, MOVE_TYPE only. | types, moveData | battler |
| 32 | FlagMoveDamageScore | :1012 | 3 | 62 | If move is alt-power (sAltPowerMoveEffects, TAI:48-60) or (power > 1 and not in sNoDamageCalcMoveEffects, TAI:31): compute all 4 attacker moves with `TrainerAI_CalcAllDamage` (TAI:2799) and set `calcTemp` = AI_MOVE_IS_HIGHEST_DAMAGE if no move does strictly more than this slot, else AI_NOT_HIGHEST_DAMAGE; otherwise AI_NO_COMPARISON_MADE. League arg is always USE_MAX_DAMAGE (roll 100). | moves, heldItem, ivs, battlerAbility, moveEffectsData.embargoTurns + all damage inputs | damage |
| 33 | LoadBattlerPreviousMove | :1068 | 13 | 1913 | `calcTemp = movePrevByBattler[battler]` (real state, not AI mem). League: DEFENDER only. | movePrevByBattler | moves |
| 34 | IfTempEqualTo | :1078 | 5 | 83 | `v == calcTemp` | AI mem | flow |
| 36 | IfSpeedCompareEqualTo | :1102 | 40 | 1179 | jump if `BattleSystem_CompareBattlerSpeed(attacker, defender, TRUE) == v` (battle_lib.c:1188-1449). See trap 3. | stat(SPEED), statBoost, battlerAbility, heldItem/itemHoldEffect/itemData, status, fieldConditionsMask, sideConditionsMask, curHP/maxHP, species, moveEffectsData.{slowStartTurnNumber,canUnburden}, totalTurns, speedRand | battler |
| 38 | CountAlivePartyBattlers | :1126 | 15 | 310 | `calcTemp` = party members other than the active slot with HP ≠ 0 and species not NONE/EGG | party, partyCount, selectedPartySlot | misc |
| 40 | LoadCurrentMoveEffect | :1164 | 1 | 6425 | `calcTemp = MOVE_DATA(move).effect` | moveData | moves |
| 41 | LoadBattlerAbility | :1170 | 94 | 69 | ABILITY_NONE if MOVE_EFFECT_ABILITY_SUPPRESSED. For a non-attacker: known ability (AI mem `battlerAbilities`), else the real ability if Shadow Tag / Magnet Pull / Arena Trap, else guess from species abilities — **coin flip `RandNext() & 1` when the species has two**. For the attacker: real `ability` (not `Battler_Ability`). | moveEffectsMask, ability, species, speciesAbilities, AI mem | battler |
| 43 | IfMoveEffectivenessEquals | :1311 | 103 | 68 | `BattleSystem_ApplyTypeChart(move, TrainerAI_MoveType(attacker, move), attacker, defender, TYPE_MULTI_BASE_DAMAGE = 40)` (constants/battle.h:150; battle_lib.c:2560; TAI:3127); map the damage multiplier to TYPE_MULTI_* (STAB×2→DOUBLE etc.), IMMUNE if MOVE_STATUS_IMMUNE; jump on equality. | types, battlerAbility, heldItem/itemHoldEffect, statusVolatile (FORESIGHT), moveEffectsMask (INGRAIN), moveEffectsData.magnetRiseTurns, fieldConditionsMask (gravity via Battler_IgnorableAbility), moveData | damage |
| 44 | IfPartyMemberStatus | :1348 | 3 | 1046 | jump if any non-active, alive, non-egg party member has `status & mask` | party, selectedPartySlot | misc |
| 46 | LoadCurrentWeather | :1414 | 15 | 535 | `calcTemp` = AI_WEATHER_* from fieldConditionsMask; later checks win (rain < sand < sun < hail < fog) | fieldConditionsMask | misc |
| 47 | IfCurrentMoveEffectEqualTo | :1441 | 340 | 134 | `MOVE_DATA(move).effect == v` | moveData | moves |
| 49 | IfStatStageLessThan | :1465 | 41 | 480 | `statBoosts[stat] < v` (0..12, 6 neutral) | statBoost | battler |
| 50 | IfStatStageGreaterThan | :1480 | 84 | 346 | `>` | statBoost | battler |
| 51 | IfStatStageEqualTo | :1495 | 40 | 350 | `==` | statBoost | battler |
| 52 | IfStatStageNotEqualTo | :1510 | 1 | 1479 | `!=` | statBoost | battler |
| 53 | IfCurrentMoveKills | :1525 | 1 | 6358 | same eligibility test as op 32; `TrainerAI_CalcDamage(move, roll)` (TAI:2868) with roll = moveDamageRolls[slot] only if the arg `== TRUE`, else 100; jump if `defender.curHP <= damage`. League arg USE_MAX_DAMAGE. | curHP + damage inputs | damage |
| 55 | IfMoveKnown | :1627 | 18 | 1438 | ATTACKER: real moves; DEFENDER: AI mem `battlerMoves[defender]`; other battler values: never jump | moves, AI mem | moves |
| 56 | IfMoveNotKnown | :1683 | 4 | 2994 | negation, same split | moves, AI mem | moves |
| 57 | IfMoveEffectKnown | :1739 | 29 | 1816 | any (nonzero) known move whose `MOVE_DATA.effect == e`; ATTACKER real, DEFENDER AI mem | moves, moveData, AI mem | moves |
| 58 | IfMoveEffectNotKnown | :1781 | 3 | 2670 | negation (League: DEFENDER only) | moveData, AI mem | moves |
| 59 | IfBattlerUnderEffect | :1823 | 3 | 652 | CHECK_DISABLE: `disabledTurns != 0`; CHECK_ENCORE: `encoredTurns != 0` | moveEffectsData | battler |
| 64 | LoadHeldItem | :1891 | 2 | 902 | `calcTemp = battleMons[b].heldItem` — the **real** item even for the player | heldItem | battler |
| 65 | LoadHeldItemEffect | :1901 | 11 | 1212 | hold effect of the real item for the attacker; for any other battler, of **AI mem `battlerHeldItems`** (ITEM_NONE → HOLD_EFFECT_NONE until revealed) | heldItem, itemHoldEffect, AI mem | battler |
| 66 | LoadGender | :2470 | 6 | 736 | `calcTemp = gender` (GENDER_MALE/FEMALE/NONE) | gender | battler |
| 67 | LoadIsFirstTurnInBattle | :2480 | 8 | 831 | `calcTemp = !(fakeOutTurnNumber < totalTurns)` | moveEffectsData.fakeOutTurnNumber, totalTurns | misc |
| 68 | LoadStockpileCount | :2494 | 3 | 837 | `calcTemp = stockpileCount` | moveEffectsData | battler |
| 69 | LoadBattleType | :2504 | 4 | 894 | `calcTemp = battleType` (tested for DOUBLES, FRONTIER) | battleType | misc |
| 70 | LoadRecycleItem | :2510 | 3 | 913 | `calcTemp = recycleItem[b]` | recycleItem | battler |
| 72 | LoadPowerOfLoadedMove | :2526 | 6 | 2039 | `calcTemp = MOVE_DATA(calcTemp).power` | moveData | moves |
| 73 | LoadEffectOfLoadedMove | :2532 | 3 | 3016 | `calcTemp = MOVE_DATA(calcTemp).effect` | moveData | moves |
| 74 | LoadProtectChain | :2538 | 3 | 3545 | `protectSuccessTurns` if `moveProtect[b]` ∈ {Protect, Detect, Endure}, else 0 | moveProtect, moveEffectsData.protectSuccessTurns | battler |
| 76 | GoTo | :2561 | 228 | 79 | unconditional jump | — | flow |
| 77 | PopOrEnd | :2568 | 268 | 286 | pop cursor stack; if empty set AI_STATUS_FLAG_DONE (this move's evaluation ends) | AI mem (stack) | flow |
| 78 | IfLevel | :2579 | 1 | 563 | compare attacker vs defender `level`: HIGHER(0) `>`, LOWER(1) `<`, EQUAL(2) `==` | level | battler |
| 80 | IfTargetIsNotTaunted | :2620 | 6 | 3129 | jump if defender `tauntedTurns == 0` | moveEffectsData | battler |
| 81 | IfTargetIsPartner | :2630 | 4 | 54 | jump if `(attacker & 1) == (defender & 1)`; never in singles | attacker, defender | misc |
| 83 | CheckBattlerAbility | :1212 | 1 | 441 | like op 41 for DEFENDER but no coin flip: if two possible abilities and neither is `expected` → ability1, else ABILITY_NONE; then calcTemp = AI_UNKNOWN / AI_HAVE / AI_NOT_HAVE. League: DEFENDER, Speed Boost. | moveEffectsMask, ability, species, speciesAbilities, AI mem | battler |
| 85 | IfHeldItemEqualTo | :1915 | 5 | 1169 | same side as attacker → real item; other side → AI mem `battlerHeldItems` | heldItem, side, AI mem | battler |
| 86 | IfFieldConditionsMask | :1936 | 5 | 364 | `fieldConditionsMask & mask` (League: TRICK_ROOM, GRAVITY) | fieldConditionsMask | misc |
| 87 | LoadSpikesLayers | :1948 | 2 | 709 | `calcTemp` = spikes or toxic-spikes layers on side(battler); **other arg values leave calcTemp unchanged** | spikesLayers, toxicSpikesLayers | misc |
| 88 | IfAnyPartyMemberIsWounded | :1968 | 2 | 1047 | any non-active party slot with `hp != maxHP` (includes fainted mons: hp 0 ≠ max) | party, selectedPartySlot | misc |
| 89 | IfAnyPartyMemberUsedPP | :1987 | 1 | 1561 | any non-active party slot with some `pp != maxPP` | party, selectedPartySlot | misc |
| 90 | LoadFlingPower | :2014 | 2 | 1204 | `Battler_ItemFlingPower(b)` (battle_lib.c) | heldItem, itemData.flingPower (+ the function's own checks) | battler |
| 91 | LoadCurrentMovePP | :2024 | 1 | 5327 | `ppCur[moveSlot]` of the attacker | ppCur | moves |
| 92 | IfCanUseLastResort | :2030 | 2 | 1422 | `lastResortCount >= Battler_CountMoves(b) - 1 && count > 1` | moveEffectsData.lastResortCount, moves | moves |
| 94 | LoadDefenderLastUsedMoveClass | :2050 | 10 | 2041 | `MOVE_DATA(movePrevByBattler[defender]).class` (MOVE_NONE's row if none) | movePrevByBattler, moveData | moves |
| 96 | LoadBattlerTurnCount | :2096 | 1 | 2589 | `totalTurns - fakeOutTurnNumber` | totalTurns, moveEffectsData | misc |
| 97 | IfPartyMemberDealsMoreDamage | :2106 | 2 | 5118 | max of active attacker's 4 moves vs each alive non-active party member's max (their moves, item, ability, IVs; embargo FALSE), all against the defender with `attacker` = the active battler id; jump if any party member is strictly higher | party, moves, heldItem, ivs, battlerAbility + damage inputs | damage |
| 98 | IfHasSuperEffectiveMove | :2176 | 2 | 5106 | `AI_HasSuperEffectiveMove(attacker, TRUE)` (TAI:3560): any attacker move with MOVE_STATUS_SUPER_EFFECTIVE vs the opposite battler; skipped if that battler is in battlersSwitchingMask | moves, type-chart inputs, battlersSwitchingMask | damage |
| 99 | IfBattlerDealsMoreDamage | :2187 | 3 | 5528 | AI max damage (CalcAllDamage) vs `TrainerAI_CalcDamage(movePrevByBattler[b], b's item and ability, **the AI's IVs**, attacker=b)`; jump if b's is higher. See trap 4. | movePrevByBattler, heldItem, battlerAbility, ivs + damage inputs | damage |
| 100 | SumPositiveStatStages | :2243 | 1 | 5926 | Σ over BATTLE_STAT_HP..EVASION of `max(0, statBoosts − 6)` | statBoost | battler |
| 101 | DiffStatStages | :2259 | 14 | 1395 | `statBoosts[b][stat] − statBoosts[attacker][stat]` | statBoost | battler |

Unreachable from League sections (32 opcodes; each throws `ai_unimplemented`, T044): 1, 2, 3,
16, 24, 27, 31, 35, 37, 39, 42, 45, 48, 54, 60, 61 Escape, 62 Dummy3E, 63 Dummy3F, 71,
75 PushAndGoTo, 79, 82, 84, 93, 95, 102–108.

## Traps for T040–T047

1. **`moveScore` is `s8`** (ai_context.h:14). `AddToMoveScore` does `moveScore += val` in C, so a
   score that passes 127 wraps negative and the `< 0` check then sets it to 0. Starting at 100, a
   move that collects +28 or more becomes 0. TrainerAI_MainSingles copies scores into `u8`
   arrays (TAI:316-338). Emulate with `((s + v) << 24) >> 24`. Golden tests should include a
   score that crosses 127. This follows from the C types; it is not observed on hardware.
2. **AI randomness consumes the battle PRNG in script order**: IfRandomLessThan (each run),
   LoadBattlerAbility's coin flip, speed-compare ties, `TrainerAI_Init`'s four damage rolls
   (TAI:240), the final tie break (TAI:338), Psywave/Magnitude inside TrainerAI_CalcDamage
   (TAI:3015, 3030). Use the run's seeded stream and keep the same call order.
3. **Speed compare** (op 36) is `BattleSystem_CompareBattlerSpeed(..., ignoreQuickClaw=TRUE)`.
   COMPARE_SPEED_FASTER = 0, SLOWER = 1, TIE = 2 (constants/battle.h:163-165). On equal speed it
   draws `RandNext() & 1` and returns TIE only on 1, else FASTER. Quick Claw still counts through
   `speedRand[battler]` (battle_lib.c:1279), which Showdown lacks (adapter `speedRand` is
   caller-supplied). With ignoreQuickClaw = TRUE priorities stay 0 (battle_lib.c:1374-1398).
   Paralysis is ÷4, Choice Scarf ×1.5, Swift Swim/Chlorophyll ×2 unless Cloud Nine/Air Lock.
4. **IfBattlerDealsMoreDamage** (op 99) passes the AI attacker's IVs and uses AI_CONTEXT.defender
   as the defender, so with b = the defender it computes the player's last move against the
   player's own mon (TAI:2187-2241; the defender argument at TAI:3090 and 3101). Port it as written.
5. **Ability and item knowledge**: ops 41, 83, 55-58, 65, 85 read AI memory, not the truth. T045
   must record what the game records: last move via TrainerAI_RecordLastMove (TAI:2705-2717, called
   at the top of MainSingles), abilities and items when announced (battle_script.c:3074, 3403,
   11732-11742, 11806), cleared on switch (battle_lib.c:2151-2153, 2223-2225). Mapping Showdown
   log events (`-ability`, `-item`, `-enditem`, `[from] ability:`) to those calls is UNVERIFIED.
6. **`movePrevByBattler`** is MOVE_NONE after a failed move (battle_controller_player.c:3944-3948).
   The adapter uses Showdown's `moveLastTurnResult === false`. Whether that matches
   SYSCTL_MOVE_SUCCEEDED for misses, Protect blocks and immunities is UNVERIFIED.
7. **Damage eligibility** (ops 32, 53, 97, 99): moves in sNoDamageCalcMoveEffects (TAI:31-45,
   e.g. Explosion's HALVE_DEFENSE, recharge, charge-turn, recoil-half) or with power ≤ 1 get no
   comparison; alt-power effects (TAI:48-60) always do. TrainerAI_CalcDamage special-cases
   Natural Gift, Judgment, Hidden Power (from IVs), Gyro Ball (`monSpeedValues`, set as a side
   effect of the last speed compare), fixed-damage moves (sets SYSCTL_IGNORE_TYPE_CHECKS, cleared
   at TAI:3104), Return/Frustration (`friendship`), Magnitude/Psywave (draw RNG), Low Kick/Grass
   Knot (`weight` in hectograms, weight_to_power.h). It calls `BattleSystem_CalcMoveDamage`
   (`sim/damage.mjs`, T037) with critical multiplier 1, then the type chart, then
   `damage * roll / 100`.
8. **Stat stages are 0..12** with 6 neutral; HP index 0 is always 6 (SumPositiveStatStages
   iterates from BATTLE_STAT_HP). BATTLE_STAT order is HP, ATK, DEF, **SPEED**, SP_ATK, SP_DEF,
   ACC, EVA (generated/battle_stats.txt). This differs from Showdown's key order.
9. **Turn counters**: `totalTurns` is 0 on the first decision. fakeOutTurnNumber is 0 for leads and
   totalTurns+1 for a switch-in. The adapter derives it as `battle.turn - activeTurns`. This is
   verified for the leads and for one mid-battle switch in `ai_adapter.test.mjs`; post-KO
   replacements are not covered.
10. **Protect chain**: Showdown's stall counter cannot tell 2 from 3 consecutive successes; the
    adapter returns 2 for both. The League script compares it only with `> 1` and `== 0`.
11. **Dummy3E/Dummy3F** never advance the cursor (TAI:1881-1889), so the game would hang. They are
    unreachable, but the interpreter should throw if it ever reaches one.
12. **IfLoadedInTable** compares `int` words, so `TABLE_END` (0xFFFFFFFF) is −1 and ends the scan.
    Use `prog.image`, not re-evaluated arguments.
