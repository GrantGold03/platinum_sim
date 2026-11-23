# Validation log: feature 029 H4, resist berries

Branch `029-h4-resist-berries` from `main` 58f1570, main checkout. Times US Eastern.

## T001 Setup (11:18 AM EST, 2026-11-23)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:6c038ef7601b38e3b400c96159a24968a7c0998d915f0586a50dcd1f0fa472d1 sha256:4e8673d95a2ff503a0b7325977601ac4cc128f962f868d6426f236e799de842b
divergence_ledger_version: sha256:821f33356f6a61bb
```

Scripts adapted from 028 under `scripts/`: `acceptance.py` (`runs/029-evidence`, identity seed `029-ident`, holders of any of the 17
resist berries reported per winner), `attribution.py` (an appended-items list may gain at most two resist berries at its end;
anything else a defect), `equal_levels.py` (master `029-equal|B2`), `hand_check.py` (plus the berry ranking per B2 member),
`make_check_team.py` (the unmodified B2 winner for the conditions control and the same team with the top-ranked berry on the member
whose top berry blocks the most). Ordering note: the check-team script needs the ranking function, which T008 defines; the function is
written before the player check (T007) and wired into the item lists only after it (T008), so the optimizer change still follows the
player check.

## T002 Pre-feature side (11:18:33 to 11:29:50 AM EST, alone, exit 0; code identical to `main` 58f1570)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961], wall 507.3 s, no resist-berry holder: the same winner as
027 and 028. Generation at the job's reference level 47: 1.6 s for six members, 7.0 s with the allocation. Identity evaluations
(seed 029-ident). Snapshot `evidence/candidates-main.json`: 36 records.

## T003 Engine against the game (11:35 AM EST)

`sim/test/resist_berries.test.mjs` part 1 on level-100 Bronzong (Steel/Psychic, 2x to Fire), Flint's Houndoom, same seed with and
without Occa: HP lost 19 with the berry, 38 without; 19 = floor(38/2), the game's integer halving (`subscript_type_resist_berry.s`,
`DivideVarByValue BTLVAR_HP_CALC_TEMP, 2`); the log shows `-enditem ... Occa Berry|[weaken]` and the item is gone. A neutral (Fire into
Passho) hit leaves the berry. Read against the sources (no constructed battle needed, both sides agree):

| Case | Game | Engine (vendored `data/items.ts`) | Same |
|---|---|---|---|
| Substitute hit | `BattleControllerPlayer_UpdateHP` loads `subscript_hit_substitute`, never `subscript_update_hp` (the berry's caller) | `if (hitSub) return;` (type berries); Chilan's condition excludes a substitute | yes |
| Chilan on a resisted Normal hit | hold effect 35 skips the super-effective test | `move.type === 'Normal'` only | yes |
| Multi-hit | `subscript_update_hp` per hit; `RemoveItem` after the first | `eatItem()` on the first hit | yes |
| Normalize | move type read as Normal | Gen 4 Normalize sets the type to Normal | yes |
| One-hit KO, type-ignoring moves | skipped | not super-effective; fixed damage | no League case |

No difference found: no ledger entry; ledger version unchanged.

## T004 to T006 The player models resist berries (11:30 to 11:36 AM EST)

`sim/policy/expectimax2.mjs`: `damageTable` keeps the hit's super-effectiveness (`moveStatusMask`) and its type (`rec.type`, Hidden
Power's type, Normal under Normalize); `resistBerryApplies` matches the defender's hold effect; `damageOutcomes` halves the first hit's
roll (integer) before the knockout split, so a halved hit can turn a knockout into a survival, and flags each outcome; `applyHit`
removes the berry when such an outcome lands. Only where the hit lands: switch-in and threat judgements read unhalved damage
(FR-012). First implementation flaw, found by the tests: the damage input's move record has no `type`; fixed by taking it from the
move record. `sim/gauntlet.mjs`: v4 knob `resistBerries=0|1`. Part 2 of the test file: halved and consumed; another type unchanged;
after use not halved; Chilan on a resisted Normal hit; knob off. Node suite: **402 pass, 0 fail**, exit 0 (`evidence/player-check/
node.log`); replay byte-identical. No replay or identity team holds a resist berry (checked at analyze: reference team, benchmark
team, the B2 winner, the replay fixtures). greedy-v1 unchanged: it only estimates its own damage into the foe, and no League trainer
holds a berry.

## T007 Player check (11:37:59 to 11:45:33 AM EST, alone, Shift, 029's copy of 028's paired script)

Check team (`make_check_team.py`, research R6; the ranking function was added to `candidates.py` before the check but not wired into
the item lists until after it): the pre-feature B2 winner with Weavile's Icicle Plate replaced by Chople Berry (Weavile's top berry,
blocking 2736; the largest of the six members). A first launch failed at once on the team argument (`file:` prefix missing); no
battle ran.

| Control or check | n | Model | Reference | only model / only reference | p |
|---|---|---|---|---|---|
| B2 winner unchanged (conditions control) | 200 | 0.9700 | 0.9700 | 0 / 0 | 1 |
| pairing control (`--self`, berry team) | 200 | 0.8150 | 0.8150 | 0 / 0 | 1 |
| **Berry team** | 2,000 | **0.8570** | **0.8560** | 3 / 1 | **0.625** |

The unchanged team's 0.970 [0.936, 0.986] covers the optimizer's 0.944, so the conditions are right. **Verdict: not worse (no supported
loss).** Only four battles of 2,000 differ: the berry fires at most once per battle. Speed: 14.30 vs 15.55 gauntlets/s in the main
comparison; the controls show the first run of each pool is slower whatever the policy (11.32 vs 14.85 with identical play on the
unchanged team), so the berry model's own cost is not separable here; stated in the README as at most about 8%. The berry team clears
less than the unchanged team (0.857 vs 0.970) because the plate was Weavile's damage item; the optimizer decides that trade, not the player.

## T008 to T010 The optimizer offers two resist berries (11:46 AM to 12:10 PM EST)

`candidates.py`: `resist_berry_ranking(const_member, level, led)` (research R5; each threat divided by the member's base Defense for a
physical move or Special Defense for a special one; a type skipped when every ability of the species is immune to it: Levitate,
Flash Fire, Volt Absorb, Motor Drive, Water Absorb, Dry Skin, from `battle_lib.c`); `extra_item_candidates` appends the top two
(`RESIST_BERRY_COUNT = 2`) after Shell Bell for every set with an attack. Found at the first look at the ranking: Rotom (Levitate) was
offered Shuca first; fixed by the ability rule above, now Colbur, Kasib.

B2 ranking (hand check): Garchomp Yache, Haban; Infernape Shuca, Payapa; Staraptor Charti, Wacan; Rotom Colbur, Kasib; Floatzel Rindo,
Wacan; Weavile Chople, Occa. Defensive controls: Skarmory (Def 140, SpD 70) Occa first (special Fire); Blissey (Def 10, SpD 135)
Chople first (physical Fighting).

`tests/unit/test_resist_berries.py` (7 tests): every berry offerable by hold effect; known members; the defences rule on a synthetic
Grass member against equal-strength Ice Punch (physical) and Signal Beam (special): Def 150 / SpD 50 ranks Tanga (Bug) first at three
times Yache's value, swapped stats rank Yache first; the top two last after Shell Bell on B2; the 36 snapshot members change only by
appended berries (029 attribution). 028 and 025 pins updated (berries after the bell). The attribution script's berry set was missing
at first (an insertion anchor did not match); fixed. Item tests 22 passed; fast suite **643 passed, 32 deselected, 4 xfailed**, exit 0.

## T011 and T012 Branch acceptance (12:00:40 to 12:19:18 PM EST, alone, exit 0) and the merge gate

| Measure | main | branch |
|---|---|---|
| B2 quick winner | levels [52, 50, 50, 50, 51, 53], clear 0.9440 | identical, clear 0.9440; resist-berry holders: none |
| Teams screened | 205 | 269 (item deviations 78 → 142: the berries) |
| Identity (ref, b2main) | | identical after the volatile fields |
| Equal levels, 2,000 pairs | 0.9450 | 0.9450 (0 / 0, p 1); level diff +0.00 |
| Attribution, 36 members | | every difference `appended` (35 members) or identical (Spiritomb: no threat to block); 0 defects |
| Dead moves in extras | 56 | 56 (all with a filler reason) |
| Generation, B2 at Lv 47 | 1.6 s members, 7.0 s team | 1.7 s, 7.4 s (SC-006: at most 10 s) |

**Gate (FR-010): pass.** Docs: README (items bullet names the berries; 029 block with the Principle VII statement and the partial
model of FR-012), FUTURE-FEATURES section 0, RUN-STATE.
