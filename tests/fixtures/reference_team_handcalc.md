# Hand-worked final levels: reference team, one gauntlet (T072, SC-006)

The arithmetic of every exp award in one seeded gauntlet of `tests/fixtures/reference_team.json`
(sha256 `e564b123…f577`, the legal level-60 team: Infernape, Staraptor, Luxray, Garchomp,
Gyarados, Gardevoir, no held items, no trades). The figures were checked line by line against the
worker's `exp_events` and `final_state` and against the Python recomputation in
`tests/integration/test_final_levels.py`. All three agree on every award.

Regenerated after the T072 payout-ordering fix (exp is paid at `MOVE_END`, after the attacker's
recoil; see "Award 4" below). The five battles are unchanged (same seeds, same winners, same turn
counts 11/6/9/10/13); only Staraptor's exp changes, from award 4 on.

## The run

- Request: the one `tests/integration/test_final_levels.py` sends as run `i = 3`:
  `seed = derive_seed("t072-final-levels", 3, 0) = "sodium,614a2dbf2cd85120061fc160f5d3a066"`,
  `player_policy greedy-v1`, `opponent_policy decomp-ai`, `stop_on_loss false`, `log "full"`.
- Battle seeds (`deriveSeed(seed, 0, i)`, echoed by the worker):
  - Aaron `sodium,0580bd24532346736e0bd2d55f198400`;
  - Bertha `sodium,c4e7b411190b614dd32006116b3cddc5`;
  - Flint `sodium,7862b15505a752c702ef57220fa59f81`;
  - Lucian `sodium,d01d43194f3bd2afa24c17a114acb381`;
  - Cynthia `sodium,f60d44e22b411493700aa7830895ab4c`.
- Result: all five battles won (11, 6, 9, 10 and 13 turns). The gauntlet was cleared.

## Rules used (pokeplatinum @ pinned commit)

| Step | Rule | Source |
|---|---|---|
| Base yield | `u16 exp = baseExpReward; exp = (exp * faintedLevel) / 7;` | `src/battle/battle_script.c:2216-2217` |
| Split | `gainedExp = exp / nGaining`, minimum 1. nGaining counts the party mons that have HP != 0 and are in `sideGetExpMask`. | `battle_script.c:2201-2207, 2232-2236` |
| Recipient | gets exp only if in the mask (or holding Exp. Share), HP != 0 and level != 100 | `battle_script.c:9709, 9740-9743` |
| When paid | The faint only sets `SYSCTL_PAYOUT_EXP`. The award runs from `AnyExpPayout` at `MOVE_END`, after the move's recoil, the faint loop and Life Orb; at the end of turn, before each field/mon-condition step. "HP != 0" is read at that moment. | `battle_script.c:1800`; `src/battle/battle_controller_player.c:3486-3494, 3820-3826, 3968, 4449, 940-941, 1295-1296` |
| Trainer battle | `totalExp = totalExp * 150 / 100` | `battle_script.c:9753-9755` |
| Lucky Egg / traded | not applicable: no held items, no NPC-trade members | `battle_script.c:9749-9751, 9757-9765` |
| Mask | An enemy entering clears the mask and sets it to {player's active slot}. A player mon entering while the enemy has HP is added to the mask. | `src/battle/battle_lib.c:1456-1479`, `battle_script.c:455-626` |
| Level-up | Exp is capped at the level-100 value. The mon levels up while exp >= table[level+1]. | `src/pokemon.c:3501-3526` |

Exp tables come from `res/pokemon/.shared/exp_tables.csv` (the row for level n is on line n+2):

| Level | Medium slow | Slow | Line |
|---|---|---|---|
| 60 | 211060 | 270000 | `exp_tables.csv:62` |
| 61 | 222522 | 283726 | `exp_tables.csv:63` |
| 62 | 234393 | 297910 | `exp_tables.csv:64` |
| 63 | 246681 | 312558 | `exp_tables.csv:65` |

Growth rates come from `res/pokemon/<species>/data.json:28`:
- medium slow: Infernape, Staraptor, Luxray;
- slow: Garchomp, Gyarados, Gardevoir.

Every member starts at level 60, so the medium-slow members start with 211060 exp and the slow
members with 270000.

## The awards

Base exp is `res/pokemon/<species>/data.json:12` (`base_exp_reward`). The enemy level is
`res/trainers/data/<trainer>.json` at the line given. "Mask" lists the slots flagged when the enemy
fainted. A slot in brackets had 0 HP when the award was paid, so it is not counted and gets
nothing. In this run at most one live mon was in the mask at every payout, so `gained = exp // 1`.
The exp each recipient receives is `gained * 150 // 100`.

| # | Battle, turn | Fainted (base exp; level, source line) | base × level, then // 7 | Mask | Gained → ×1.5 | Recipient: exp before + award = after | Level |
|---|---|---|---|---|---|---|---|
| 1 | Aaron T4 | Yanmega (198; L49, `elite_four_aaron.json:18`) | 198×49 = 9702 → 1386 | [Infernape], Staraptor | 1386 → 2079 | Staraptor 211060 + 2079 = 213139 | 60 |
| 2 | Aaron T6 | Drapion (204; L53, `:74`) | 204×53 = 10812 → 1544 | Staraptor | 1544 → 2316 | Staraptor 213139 + 2316 = 215455 | 60 |
| 3 | Aaron T7 | Vespiquen (188; L50, `:46`) | 188×50 = 9400 → 1342 | Staraptor | 1342 → 2013 | Staraptor 215455 + 2013 = 217468 | 60 |
| 4 | Aaron T8 | Heracross (200; L51, `:60`) | 200×51 = 10200 → 1457 | [Staraptor] (see note) | nGaining = 0 → nobody | none: Staraptor stays at 217468 | 60 |
| 5 | Aaron T11 | Scizor (200; L49, `:32`) | 200×49 = 9800 → 1400 | [Gardevoir], Garchomp | 1400 → 2100 | Garchomp 270000 + 2100 = 272100 | 60 |
| 6 | Bertha T1 | Whiscash (158; L50, `elite_four_bertha.json:18`) | 158×50 = 7900 → 1128 | Infernape | 1128 → 1692 | Infernape 211060 + 1692 = 212752 | 60 |
| 7 | Bertha T3 | Gliscor (192; L53, `:32`) | 192×53 = 10176 → 1453 | [Infernape], Gyarados | 1453 → 2179 | Gyarados 270000 + 2179 = 272179 | 60 |
| 8 | Bertha T4 | Golem (177; L52, `:60`) | 177×52 = 9204 → 1314 | Gyarados | 1314 → 1971 | Gyarados 272179 + 1971 = 274150 | 60 |
| 9 | Bertha T5 | Rhyperior (217; L55, `:74`) | 217×55 = 11935 → 1705 | Gyarados | 1705 → 2557 | Gyarados 274150 + 2557 = 276707 | 60 |
| 10 | Bertha T6 | Hippowdon (198; L52, `:46`) | 198×52 = 10296 → 1470 | Gyarados | 1470 → 2205 | Gyarados 276707 + 2205 = 278912 | 60 |
| 11 | Flint T1 | Houndoom (204; L52, `elite_four_flint.json:18`) | 204×52 = 10608 → 1515 | Infernape | 1515 → 2272 | Infernape 212752 + 2272 = 215024 | 60 |
| 12 | Flint T3 | Infernape (209; L55, `:60`) | 209×55 = 11495 → 1642 | [Infernape], Staraptor | 1642 → 2463 | Staraptor 217468 + 2463 = 219931 | 60 (219931 < 222522) |
| 13 | Flint T4 | Magmortar (199; L57, `:74`) | 199×57 = 11343 → 1620 | Staraptor | 1620 → 2430 | Staraptor 219931 + 2430 = 222361 | 60 (222361 < 222522) |
| 14 | Flint T7 | Flareon (198; L55, `:32`) | 198×55 = 10890 → 1555 | [Staraptor], Garchomp | 1555 → 2332 | Garchomp 272100 + 2332 = 274432 | 60 |
| 15 | Flint T9 | Rapidash (192; L53, `:46`) | 192×53 = 10176 → 1453 | Garchomp | 1453 → 2179 | Garchomp 274432 + 2179 = 276611 | 60 |
| 16 | Lucian T2 | Mr. Mime (136; L53, `elite_four_lucian.json:19`) | 136×53 = 7208 → 1029 | Infernape | 1029 → 1543 | Infernape 215024 + 1543 = 216567 | 60 |
| 17 | Lucian T4 | Espeon (197; L55, `:33`) | 197×55 = 10835 → 1547 | [Infernape], Staraptor | 1547 → 2320 | Staraptor 222361 + 2320 = 224681 | **61** (≥ 222522) |
| 18 | Lucian T5 | Gallade (208; L59, `:75`) | 208×59 = 12272 → 1753 | Staraptor | 1753 → 2629 | Staraptor 224681 + 2629 = 227310 | 61 |
| 19 | Lucian T7 | Alakazam (186; L56, `:61`) | 186×56 = 10416 → 1488 | [Staraptor], Garchomp | 1488 → 2232 | Garchomp 276611 + 2232 = 278843 | 60 |
| 20 | Lucian T10 | Bronzong (188; L54, `:47`) | 188×54 = 10152 → 1450 | Garchomp | 1450 → 2175 | Garchomp 278843 + 2175 = 281018 | 60 |
| 21 | Cynthia T3 | Spiritomb (168; L58, `champion_cynthia.json:20`) | 168×58 = 9744 → 1392 | [Infernape], Staraptor | 1392 → 2088 | Staraptor 227310 + 2088 = 229398 | 61 |
| 22 | Cynthia T5 | Togekiss (220; L60, `:48`) | 220×60 = 13200 → 1885 | Staraptor | 1885 → 2827 | Staraptor 229398 + 2827 = 232225 | 61 (232225 < 234393) |
| 23 | Cynthia T8 | Lucario (204; L60, `:62`) | 204×60 = 12240 → 1748 | [Staraptor], Garchomp | 1748 → 2622 | Garchomp 281018 + 2622 = 283640 | 60 (283640 < 283726) |
| 24 | Cynthia T10 | Garchomp (218; L62, `:90`) | 218×62 = 13516 → 1930 | Garchomp | 1930 → 2895 | Garchomp 283640 + 2895 = 286535 | **61** (≥ 283726) |
| 25 | Cynthia T11 | Milotic (213; L58, `:76`) | 213×58 = 12354 → 1764 | Garchomp | 1764 → 2646 | Garchomp 286535 + 2646 = 289181 | 61 |
| 26 | Cynthia T13 | Roserade (204; L58, `:34`) | 204×58 = 11832 → 1690 | [Garchomp], Gardevoir | 1690 → 2535 | Gardevoir 270000 + 2535 = 272535 | 60 |

Luxray never entered battle, so it gained nothing.

## Final state

| Member | Final exp | Final level |
|---|---|---|
| Infernape | 216567 | 60 |
| Staraptor | 232225 | 61 |
| Luxray | 211060 | 60 |
| Garchomp | 289181 | 61 |
| Gyarados | 278912 | 60 |
| Gardevoir | 272535 | 60 |

Staraptor's exp, step by step: 211060 + 2079 (Yanmega) + 2316 (Drapion) + 2013 (Vespiquen) +
0 (Heracross) + 2463 (Infernape) + 2430 (Magmortar) + 2320 (Espeon) + 2629 (Gallade) + 2088
(Spiritomb) + 2827 (Togekiss) = 232225. Check: 211060 + 21165 = 232225; 21165 = the old total
23350 (234410 − 211060) − 2185 (the Heracross award it no longer gets).

The final average level is (60 + 61 + 60 + 61 + 60 + 60) / 6 = 362 / 6 = **60.33**.

The worker reported `final_levels [60, 61, 60, 61, 60, 60]` and `final_state.exp
[216567, 232225, 211060, 289181, 278912, 272535]`. Both are identical to the values above, and so
is the Python recomputation (`recompute()` in `tests/integration/test_final_levels.py`).
(The worker's event for Heracross reports `gained: 1`: with nGaining = 0 the C would divide by
zero; `sim/exp.mjs` floors the unused value to 1 and the Python check uses 0. Nobody receives it,
so the per-slot totals agree.)

## Award 4: a recoil KO of the attacker (decomp payout order)

On Aaron T8, Staraptor's Brave Bird knocks out Heracross, and the 1/3 recoil knocks out Staraptor
too. Showdown's log (battle 0 of this run):

```
|move|p1a: STARAPTOR|Brave Bird|p2a: HERACROSS
|-supereffective|p2a: HERACROSS
|-damage|p2a: HERACROSS|0 fnt
|faint|p2a: HERACROSS
|-damage|p1a: STARAPTOR|0 fnt|[from] Recoil
|faint|p1a: STARAPTOR
```

Showdown fires the enemy's faint before the recoil. The decomp pays exp later:
1. The recoil is an indirect secondary effect (`res/battle/scripts/effects/effect_script_0198.s`,
   `MOVE_SUBSCRIPT_PTR_RECOIL_1_3`). It runs during `BATTLE_CONTROL_AFTER_MOVE_MESSAGE`
   (`ONE_HIT_TRIGGER_SECONDARY`, `src/battle/battle_controller_player.c:3486-3494`). Its
   subscript calls `UPDATE_HP` (`res/battle/scripts/subscripts/subscript_recoil_1_3.s`).
2. Fainted mons are handled after that, in `BATTLE_CONTROL_LOOP_FAINTED` (`:3820-3826`). The faint
   animation command only sets the payout flag (`BtlCmd_PlayFaintAnimation`,
   `src/battle/battle_script.c:1800`).
3. Exp is paid only at `BATTLE_CONTROL_MOVE_END` (`BattleControllerPlayer_AnyExpPayout`, `:3968`,
   `:4449`; `subscript_grant_exp.s` = `CalcExpGain` + `StartGetExpTask`).

So when `BtlCmd_CalcExpGain` runs, Staraptor has 0 HP. It is not counted (`battle_script.c:2204`),
nGaining is 0, and it gains nothing (`:9740`). Life Orb self-damage is applied in the same window
(`BattleControllerPlayer_TriggerAfterMoveHitEffects`, `battle_controller_player.c:4715-4775`, run
before `UPDATE_MOVE_BUFFERS` → `MOVE_END`).

Before the fix, both the worker and the Python check gave Staraptor 2185 here and the run ended at
`final_levels [60, 62, 60, 61, 60, 60]` (average 60.5). The worker (`sim/exp.mjs`) now queues an
enemy faint and pays when the Showdown action returns (and after each residual handler); the Python
check pays a pending award at the next action-start line of the log. Both follow the decomp
reading above, which has not been checked against the running game (**UNVERIFIED** on cartridge).

Over the 200 T072 runs after the fix: worker and Python agree on every run (final levels 200/200,
final exp 200/200, every award 200/200); the mean final average level is 60.2925. Recomputing the
same new logs with the old rule (pay at the enemy's faint) changes 262 awards and matches the
worker's final exp in only 40/200 runs (`test_positive_control_payout_ordering`).
