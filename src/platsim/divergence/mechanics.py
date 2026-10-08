"""Hand-written mechanics divergences for the ledger (T053; research R5, R6; validation-log.md).

Data divergences are computed by compare.py; the damage-formula divergences come from
sim/test/damage_divergences.json (T037). Everything here is a behaviour difference between the
cartridge and Showdown that a data diff cannot see. Each entry cites the decomp and Showdown
source by path:line at the pinned commits (src/platsim/pins.py); the lines were opened and checked
when the entry was written.

Resolutions:
  corrected - the game layer (sim/*.mjs) makes the battle follow the decomp; `test_id` proves it.
  accepted  - the difference remains; `impact` says what it changes. Entries that are waiting for
              a task say so in `impact` (flip them to corrected when that task lands).
"""

from __future__ import annotations

_ENTRIES: list[dict] = [
    {
        "id": "mech-resist-berry-order",
        "area": "mechanics",
        "description": (
            "Resist berries (Occa ... Chilan). Game: a battle subscript halves the final HP change "
            "(DivideVarByValue, rounded toward zero, min 1) when HP is updated, after the Focus Sash/"
            "Endure clamp; Counter, Mirror Coat and Shell Bell use the full damage; no trigger on "
            "substitute hits. Showdown: halves inside the damage calculation (onSourceModifyDamage, "
            "chainModify(0.5)), so Counter/Mirror Coat see the halved damage and the order relative "
            "to Focus Sash differs."),
        "decomp_ref": (
            "pokeplatinum/res/battle/scripts/subscripts/subscript_type_resist_berry.s:21-22 "
            "(Chilan id 35 / super-effective gate), :111 (DivideVarByValue BTLVAR_HP_CALC_TEMP, 2); "
            "called from pokeplatinum/res/battle/scripts/subscripts/subscript_update_hp.s:10"),
        "showdown_ref": "pokemon-showdown/data/items.ts:4347-4366 (occaberry onSourceModifyDamage; the other resist berries follow the same pattern)",
        "resolution": "accepted",
        "impact": (
            "Rare: differs only when a resist-berry holder is hit by a super-effective move and "
            "then uses Counter/Mirror Coat, holds a Focus Sash-like clamp, or rounding of the halved "
            "value differs by 1 HP. Resist berries stay allowed (validation-log 2026-10-07)."),
        "test_id": "UNTESTED: no battle test exercises the ordering yet",
    },
    {
        "id": "mech-full-restore-pseudo-move",
        "area": "ai",
        "description": (
            "Opponent Full Restore uses the project pseudo-move `trainerfullrestore`, because Showdown "
            "has no bag items. sim/ai/patches.mjs heals in Showdown's beforeTurnCallback and removes its "
            "own move action, so it never runs as a move: Taunt, Encore, sleep/freeze/paralysis, "
            "confusion, attraction, Truant and Pressure cannot affect it, lastMove is untouched, Sucker "
            "Punch fails against it and Heal Block does not stop it, as in the game. Remaining "
            "differences: Choice lock (no League mon holds a Choice item), an encored item user facing "
            "Sucker Punch, a player Transform on the same turn copying the extra slot, and message order."),
        "decomp_ref": (
            "pokeplatinum/src/battle/trainer_ai/trainer_ai.c:4056 (TrainerAI_ShouldUseItem); "
            "pokeplatinum/src/battle/battle_script.c:7385-7400 (Sucker Punch vs non-attack)"),
        "showdown_ref": "pokemon-showdown/data/mods/gen4/moves.ts:1411-1418 (taunt onDisableMove: every Status move)",
        "resolution": "corrected",
        "impact": (
            "Corrected by sim/ai/patches.mjs + sim/ai/items.mjs (T047). The remaining edge cases listed "
            "above do not arise with League parties, apart from the encored-Sucker-Punch case, which is "
            "a single-turn ordering difference."),
        "test_id": "sim/test/ai_items.test.mjs; sim/test/ai_golden.test.mjs (Taunt + Full Restore)",
    },
    {
        "id": "exp-gain-and-participation",
        "area": "exp",
        "description": (
            "Showdown has no experience. The game layer tracks participation the game's way and "
            "computes exp per BtlCmd_CalcExpGain / BattleScript_GetExpTask (trainer x1.5, Lucky Egg "
            "x1.5, Exp. Share split, traded x1.5/x1.7; a Build whose source is an NPC trade is traded, "
            "language from the trade's FixedMon vs GAME_LANGUAGE). Ordering: the game only flags the "
            "payout when the enemy faints and pays at MOVE_END, after the attacker's recoil, the faint "
            "loop and Life Orb (and, at end of turn, before each field/mon-condition step), so an "
            "attacker KO'd by its own recoil/Life Orb gets nothing. Showdown fires the enemy's Faint "
            "before the recoil; sim/exp.mjs therefore queues the award and pays it when the Showdown "
            "action returns, or after each residual handler (T072 fix; before it, such an attacker was "
            "paid). Remaining approximation: side-condition residuals (Future Sight, Perish Song) are "
            "paid per Showdown handler instead of at TurnEnd."),
        "decomp_ref": (
            "pokeplatinum/src/battle/battle_script.c:2187 (BtlCmd_CalcExpGain), :9685 "
            "(BattleScript_GetExpTask), :9757-9765 (not-OT boost), :1800 (faint sets SYSCTL_PAYOUT_EXP); "
            "pokeplatinum/src/battle/battle_controller_player.c:3486-3494 (recoil in AFTER_MOVE_MESSAGE), "
            ":3820-3826 (LOOP_FAINTED), :3968 (MOVE_END AnyExpPayout), :940-941/:1295-1296/:1846 (end-of-turn "
            "payouts), :4715-4775 (Life Orb); pokeplatinum/src/battle/battle_lib.c:1456-1479 (exp mask), "
            ":6286 (BattleSystem_PokemonIsOT); pokeplatinum/src/overlay006/npc_trade.c:117-149 "
            "(NPCTrade_CreateMon: OT and language from res/npc_trades/*.json)"),
        "showdown_ref": (
            "pokemon-showdown/sim/battle.ts:2539 (faintMessages: no exp is awarded on faint); "
            "pokemon-showdown/sim/battle-actions.ts:969-975 (faintMessages before applyRecoilDamage)"),
        "resolution": "corrected",
        "impact": (
            "Corrected by sim/exp.mjs (T036; payout ordering T072 follow-up) and sim/team.mjs (traded from "
            "source). Ordering fix on the reference team, 200 T072 runs: mean final average level 60.2925; "
            "worker and the independent Python check (tests/integration/test_final_levels.py) agree 200/200. "
            "Game ordering read from the decomp, not checked on cartridge (UNVERIFIED)."),
        "test_id": (
            "sim/test/exp.test.mjs (cases 1-21; 16 NPC-trade source, 17-20 recoil/Life Orb KO, 21 residual "
            "payout); tests/integration/test_final_levels.py"),
    },
    {
        "id": "exp-level-up-mid-battle",
        "area": "exp",
        "description": (
            "Level-ups happen mid-battle at the KO in the game (stats recomputed with "
            "Pokemon_CalcStats, current HP raised by the max-HP gain). Showdown has no level-up; the "
            "game layer sets the level and stats on the live Showdown Pokemon."),
        "decomp_ref": "pokeplatinum/src/pokemon.c:564 (Pokemon_CalcStats); pokeplatinum/src/battle/battle_script.c:9685 (BattleScript_GetExpTask)",
        "showdown_ref": "pokemon-showdown/sim/pokemon.ts:1398 (setSpecies: stats from the set's level; nothing in Showdown raises a level)",
        "resolution": "corrected",
        "impact": (
            "Corrected by sim/exp.mjs (T009 spike, T036). Exp timing follows the game's payout points "
            "(MOVE_END / end-of-turn steps), not Showdown's Faint event: see exp-gain-and-participation. "
            "UNVERIFIED on cartridge."),
        "test_id": "sim/test/exp.test.mjs (case 13: KO -> mid-battle level-up, HP raised)",
    },
    {
        "id": "exp-auto-learn-spec-conflict",
        "area": "exp",
        "description": (
            "On level-up the game learns a level-up move automatically, with no prompt, when the "
            "Pokemon has fewer than 4 moves (Pokemon_LevelUpMove default branch; BoxPokemon_AddMove "
            "fills the first empty slot with base PP). Showdown never changes move slots after "
            "construction. The game layer follows the game (user decision 2026-10-07): sim/exp.mjs adds "
            "the move to the live Pokemon and party state; with 4 moves the prompt is declined."),
        "decomp_ref": "pokeplatinum/src/battle/battle_script.c:10021-10035; pokeplatinum/src/pokemon.c:3852-3871",
        "showdown_ref": "pokemon-showdown/sim/pokemon.ts:354 (move slots built once from set.moves)",
        "resolution": "corrected",
        "impact": "Corrected by sim/exp.mjs (learned_moves / declined_moves in exp events); moves carry across battles.",
        "test_id": "sim/test/exp.test.mjs (case 13, case 13b)",
    },
    {
        "id": "mech-pp-ups",
        "area": "mechanics",
        "description": (
            "Showdown gives every move 3 PP Ups at construction. The game sets trainer mons' max PP "
            "with ppUps 0 (Pokemon_Init zeroes the data); the spec (FR-008) gives the player no PP "
            "Ups either."),
        "decomp_ref": "pokeplatinum/src/pokemon.c:3925 (BoxPokemon_SetMoveSlot), :292-294 (Pokemon_Init zeroes the mon)",
        "showdown_ref": "pokemon-showdown/sim/pokemon.ts:361 (ppUps = 3)",
        "resolution": "corrected",
        "impact": "Corrected by sim/team.mjs: every slot of both sides is reset to decomp base PP.",
        "test_id": "sim/test/team.test.mjs (Dark Pulse has base PP 15 ... (no PP Ups))",
    },
    {
        "id": "mech-stats-overwrite",
        "area": "mechanics",
        "description": (
            "Battle stats: Showdown computes them with its own formula (spreadModify/statModify). "
            "The game layer overwrites both sides' stats with the decomp formula after construction "
            "so no formula or base-stat difference can leak in."),
        "decomp_ref": "pokeplatinum/src/pokemon.c:564 (Pokemon_CalcStats)",
        "showdown_ref": "pokemon-showdown/sim/battle.ts:2350-2358 (spreadModify, statModify)",
        "resolution": "corrected",
        "impact": "Corrected by sim/team.mjs; the test also shows Showdown's own numbers already agree for every League mon.",
        "test_id": "sim/test/team.test.mjs (player builds / every League opponent: Showdown stats == Python calc_stats)",
    },
    {
        "id": "ai-trainer-ai",
        "area": "ai",
        "description": (
            "Showdown has no in-game trainer AI. The project runs the decomp's AI scripts in an "
            "interpreter (research R6): move choice (TrainerAI_Init/EvalMoves/MainSingles), switch "
            "and item choice in TrainerAI_PickCommand order."),
        "decomp_ref": (
            "pokeplatinum/src/battle/trainer_ai/trainer_ai.c:211 (TrainerAI_Init), :286 "
            "(TrainerAI_MainSingles), :3894 (ShouldSwitch), :3989 (PickCommand), :4056 (ShouldUseItem)"),
        "showdown_ref": "pokemon-showdown/sim/side.ts:1291-1292,1360 ('default' choice -> autoChoose)",
        "resolution": "corrected",
        "impact": (
            "Corrected by the `decomp-ai` opponent policy (T045-T048), now the default. Remaining "
            "UNVERIFIED reconstructions from Showdown's log: the AI's knowledge of the player's "
            "ability and item, the move that last hit it, and last-move success; Gyro Ball speed values "
            "are recomputed per decision. No cartridge comparison has been made. Showdown-mismatch "
            "counters (invalidChoice, trappedSwitch, lockMismatch) are reported per run."),
        "test_id": "sim/test/ai_choose/ai_switch/ai_items/ai_golden/ai_gauntlet.test.mjs",
    },
    {
        "id": "mech-pickup-honey-gather-after-battle",
        "area": "mechanics",
        "description": (
            "Pickup and Honey Gather can give the holder an item after a won battle, trainer battles "
            "included (BtlCmd_GenerateEndOfBattleItem). The gauntlet does not model end-of-battle item "
            "generation, so these abilities have no effect in simulation."),
        "decomp_ref": (
            "pokeplatinum/src/battle/battle_script.c:7797, :7825 (BtlCmd_GenerateEndOfBattleItem); "
            "pokeplatinum/res/battle/scripts/subscripts/subscript_battle_won.s:72"),
        "showdown_ref": "pokemon-showdown/data/abilities.ts (pickup/honeygather: no end-of-battle item in a single battle)",
        "resolution": "accepted",
        "impact": (
            "Only an item gained between League rooms; it never changes a battle in progress. The "
            "ability screen will see a tie for these and keep slot 1 (FR-008c)."),
        "test_id": "tests/unit/test_abilities.py (Pickup/Honey Gather classified has-effect)",
    },
    {
        "id": "mech-rng",
        "area": "mechanics",
        "description": (
            "The cartridge's battle RNG is a 32-bit LCG (BattleSystem_RandNext); Showdown uses a "
            "seeded ChaCha20 (sodium) PRNG, and draws random numbers in a different order and "
            "count. Individual battles cannot be reproduced from a cartridge seed."),
        "decomp_ref": "pokeplatinum/src/battle/battle_system.c:1308-1311 (BattleSystem_RandNext, LCRNG)",
        "showdown_ref": "pokemon-showdown/sim/prng.ts:176 (SodiumRNG); :59 (sodium seeds)",
        "resolution": "accepted",
        "impact": (
            "None on the estimates: results are win-rate distributions over seeded runs "
            "(Constitution IV), reproducible from the project seed, not from the cartridge."),
        "test_id": "sim/test/seeds.test.mjs (seed derivation is deterministic)",
    },
]


def entries() -> list[dict]:
    return [dict(e) for e in _ENTRIES]
