# Research: H4, Shell Bell

## R1. The game's rule

- **Finding**: `battle_controller_player.c` AFTER_MOVE_HIT_STATE_SHELL_BELL (:4738): holder's item effect
  `HOLD_EFFECT_HP_RESTORE_ON_DMG`, not during U-turn's pivot (`SYSCTL_UTURN_ACTIVE`), the move hit, `shellBellDamageDealt` > 0,
  attacker ≠ defender, holder below max HP and above 0 → heal `BattleSystem_Divide(shellBellDamageDealt, itemPower)` (itemPower 8
  from the item data; the divide keeps the sign and returns at least 1 for a nonzero dividend, `battle_lib.c:3599`). U-turn heals on
  the pivot path `BattleSystem_TriggerHeldItemOnPivotMove` (`battle_lib.c:7345`) under the same conditions, before the switch.
  `shellBellDamageDealt` accumulates the HP the target lost, substitute HP included (:3361-3430).
- **Decision**: the player's rule is max(1, floor(dmg / 8)) on the HP the target lost, holder below max and above 0.

## R2. The engine's rule and the expected differences (FR-003)

- **Finding**: Showdown `items.ts` shellbell: `onAfterMoveSecondarySelf`, `if (move.totalDamage && !pokemon.forceSwitchFlag)
  heal(move.totalDamage / 8)`; `battle.ts` heal truncates and raises a value in (0, 1] to 1. U-turn uses `selfSwitch`, which sets
  `switchFlag`, not `forceSwitchFlag` (`forceSwitchFlag` is set by moves like Roar and Dragon Tail on the target,
  `battle-actions.ts:1349`), so **the engine also heals on U-turn**: the spec's "skipped on U-turn" was an assumption; corrected
  here (spec Overview table amended at implementation).
- **To check at implementation (Node test against the vendored engine)**: (a) substitute: whether `move.totalDamage` counts damage
  dealt to a substitute; (b) multi-hit: total over hits in both; (c) the holder's own recoil fainting it before the heal; (d) the
  heal's order relative to Life Orb style self-damage (one held item, so only recoil and drain). Each difference confirmed becomes
  a ledger entry with its impact; agreement is recorded in the validation log.

## R3. The player model and the reference arm (FR-001, FR-008)

- **Finding**: `applyHit(X, S, side, rec, e, dmgIn)` applies the damage (`dmg = min(dmgIn, t.hp)`), recoil, the drain heal and Life
  Orb, then `afterHpLoss(X, u)`; `holdEffect(X, item)` reads an item's hold effect. Multi-hit moves reach `applyHit` with their total.
  The 018 v4 candidate syntax (`sim/gauntlet.mjs:53-72`) builds a v4 variant from `expectimax2-v4?key=value` knobs.
- **Decision**: after the Life Orb line and before `afterHpLoss`, `if (opts.shellBell && dmg > 0 && u.item && holdEffect(X, u.item)
  === 'HOLD_EFFECT_HP_RESTORE_ON_DMG' && u.hp > 0 && u.hp < u.maxhp) u.hp = Math.min(u.maxhp, u.hp + Math.max(1, Math.floor(dmg /
  8)))`; option default on; knob `shellBell=0` builds the reference arm. The player check uses `paired_policies.py --teams
  file:<team> ` with policies `expectimax2-v4` and `expectimax2-v4?shellBell=0`, 2,000 pairs.

## R4. The policy name

- **Decision**: keep `expectimax2-v4`. Its decisions change only for a team holding Shell Bell, which the optimizer never offered
  and no benchmark or replay team holds; the README and the provenance note record the change. A new name would break every
  stored result's comparability for a case none of them contains. **Alternative**: `expectimax2-v5` (rejected: no stored team is
  affected).

## R5. The player-check team

- **Decision**: the B2 quick winner of feature 027 (`runs/027-evidence/b2-branch/team.json`, the identical team on main), with Shell
  Bell given to Garchomp in place of its current item (the member that attacks most; legality and the one copy re-checked by
  `load_and_validate`). The check reports the clear rates, discordant pairs and exact McNemar p.

## R6. The optimizer change (FR-005 to FR-007)

- **Finding**: 025's `extra_item_candidates` appends the lens and claw by hold effect; the screen's `item_deviation` kind screens
  every `items_extra` item beyond the cap; `_item_for_effect` picks the item of an effect with copies.
- **Decision**: append `_item_for_effect("HOLD_EFFECT_HP_RESTORE_ON_DMG", led)` for sets with an attack, after the claw; no
  item-conditioned extras; the screen and the 026/027 rules unchanged; the one copy enforced by `resources.realize` as for the claw.
