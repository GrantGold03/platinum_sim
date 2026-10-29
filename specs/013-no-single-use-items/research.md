# Research: No Single-Use Held Items (H2)

Decomp read at the pinned commit (`src/platsim/pins.py`), 2026-10-29. All `file:line` references are under
`pokeplatinum/`.

## R1. What removes a held item in battle

**Decision**: An item is single-use when the holder's own hold effect, on triggering, runs a battle script that reaches
`RemoveItem` on the holder. `RemoveItem` (`src/battle/battle_script.c:8972`, `BtlCmd_RemoveItem`) saves the item
for Recycle and sets `heldItem = ITEM_NONE`.

**Evidence, every `RemoveItem` site** (`grep -rn RemoveItem res/battle/scripts` = 11 sites in 11 files):

| Site | Who triggers it | Counts? |
|---|---|---|
| `subscripts/subscript_pluck_check.s:6` | called by 15 `subscript_held_item_*` scripts; removes unless the berry was plucked | yes |
| `subscripts/subscript_held_item_recoil_when_hit.s:17` | `HOLD_EFFECT_RECOIL_PHYSICAL/SPECIAL` (Jaboca, Rowap) | yes |
| `subscripts/subscript_type_resist_berry.s:116` | resist berries, chosen by `GetItemHoldEffect` + compares inside the script | yes |
| `subscripts/subscript_move_followup_message.s:18` | guarded by `CheckItemHoldEffect CHECK_NOT_HAVE ... HOLD_EFFECT_ENDURE` | yes, Focus Sash only |
| `subscripts/subscript_future_sight_damage.s:48` | same `HOLD_EFFECT_ENDURE` guard | yes, Focus Sash only |
| `subscripts/subscript_item_skip_charge_turn.s:20` | called after `CheckItemHoldEffect CHECK_HAVE ... HOLD_EFFECT_CHARGE_SKIP` (`effects/effect_script_0039.s:7,13`, and the other charge-move effect scripts) | yes, Power Herb |
| `subscripts/subscript_power_herb_skull_bash.s:24` | same `HOLD_EFFECT_CHARGE_SKIP` check (`effect_script_0145.s`) | yes, Power Herb |
| `subscripts/subscript_check_quick_claw.s:28` | guarded by mon data `BATTLEMON_CUSTAP_BERRY`, which C sets only for `HOLD_EFFECT_PINCH_PRIORITY` (`src/battle/battle_lib.c:1288-1297`) | yes, Custap Berry only (Quick Claw not removed) |
| `subscripts/subscript_pluck.s:10` | the move Pluck / Bug Bite eating the **target's** berry | no (move-driven) |
| `effects/effect_script_0222.s:8`, `effects/effect_script_0233.s:18` | move effect scripts (Natural Gift, Fling): the user's move spends its item | no (move-driven) |

Other places that clear `heldItem`: Knock Off (`battle_script.c:6627`) and battle setup (`battle_lib.c:122,162`).
Neither is a use by the holder.

**C trigger functions** (holder's own hold effect → subscript), `src/battle/battle_lib.c`:
`BattleSystem_TriggerHeldItem` `:4576`, `BattleSystem_TriggerLeftovers` `:4922`,
`BattleSystem_TriggerHeldItemOnStatus` `:4967`, `BattleSystem_TriggerDetrimentalHeldItem` `:5307`,
`BattleSystem_TriggerHeldItemOnHit` `:5370`. `BattleSystem_PluckBerry` `:5539` and `BattleSystem_FlingItem`
`:5854` assign the same subscripts but are move-driven and are excluded.

**Alternatives considered**: (a) A hand-typed list of hold effects. Rejected by Principle I and the spec (FR-001).
(b) Showdown's `consumable`/`isBerry` item flags. Rejected as a source of truth (Principle I). They may be used as
a cross-check in the validation log only.

## R2. How the classifier reads it

**Decision**: A decomp reader, `platsim.decomp.item_use`, with four attribution rules. Each `RemoveItem` site is
tied to the hold effects that reach it:

1. **C switch**: inside the five trigger functions in R1, `case HOLD_EFFECT_X:` up to the next `case`/end assigns
   `subscript = subscript_<name>` / `*subscript = subscript_<name>`. X reaches `subscript_<name>.s`, followed
   transitively through `Call BATTLE_SUBSCRIPT_<NAME>`. If that reaches `RemoveItem`, X is single-use. The subscript
   names are the file stems (`subscript_held_item_hp_restore` ↔ `subscript_held_item_hp_restore.s` ↔
   `BATTLE_SUBSCRIPT_HELD_ITEM_HP_RESTORE`). The implementation checks this mapping against the decomp's
   subscript list and fails on any name it cannot resolve.
2. **Script guard, not-have**: `CheckItemHoldEffect CHECK_NOT_HAVE, <b>, HOLD_EFFECT_X, <label>` directly guarding
   a `RemoveItem` → X only (Focus Sash; Focus Band passes through the same script but is not removed).
3. **Script guard, have**: `CheckItemHoldEffect CHECK_HAVE, <b>, HOLD_EFFECT_X, <label>` whose label calls a
   subscript that reaches `RemoveItem` → X (Power Herb).
4. **Script compare on the held effect**: `GetItemHoldEffect <b>, <var>` and later compares of `<var>` with
   `HOLD_EFFECT_*` values on the path to `RemoveItem` → those effects (resist berries). For the Custap branch
   (mon-data flag), the flag `BATTLEMON_CUSTAP_BERRY` is traced to the `HOLD_EFFECT_*` that sets it in C
   (`battle_lib.c:1288`).

**Completeness gate**: every `RemoveItem` site in `res/battle/scripts/` must be attributed to at least one hold
effect, or be one of the move-driven sites in R1 (identified by being reachable only from `effect_script_*` files of
moves, or from `BattleSystem_PluckBerry`/`BattleSystem_FlingItem`). An unattributed site, an unresolved subscript
name, or an empty result raises an error. This is the positive control for the reader: a broken parser cannot return
"nothing is single-use".

**Fallback, if a rule turns out too irregular to parse**: the rule may be replaced by a pinned assertion that names
the exact decomp lines (for example "line N is `CheckItemHoldEffect CHECK_NOT_HAVE ... HOLD_EFFECT_ENDURE`") and
fails if the text changes. That is still read from the decomp, not typed in, and is recorded in Complexity Tracking
if used.

**Alternatives considered**: running the decomp's battle engine (not available offline in this project); reading
only the C switch (misses Focus Sash and Power Herb, which are script-guarded).

## R3. Berry definition

**Decision**: A berry is an item whose `res/items/data/<key>.json` has `"fieldPocket": "POCKET_BERRIES"` (64 items).
`platsim.decomp.item_use` reads the field itself. `Item` and `load_items()` are not changed, because `Item` is written
to `data/generated/items.json` (`src/platsim/extract.py:6`). Adding a field there would change the generated data and
its hash for no behaviour gain.

**Evidence**: `berry_juice.json` has `"fieldPocket": "POCKET_MEDICINE"` and `HOLD_EFFECT_HP_RESTORE`, the same
effect as `oran_berry.json`. So Berry Juice is single-use and not a berry.

**Alternatives considered**: the name ending in "Berry" (rejected: it uses a name, not data); `naturalGiftPower > 0`
(it agrees today but describes a move, not the pocket).

## R4. Expected classification (check values for the tests)

Single-use, not a berry (the excluded set): `ITEM_FOCUS_SASH` (`HOLD_EFFECT_ENDURE`), `ITEM_WHITE_HERB`
(`HOLD_EFFECT_STATDOWN_RESTORE`), `ITEM_MENTAL_HERB` (`HOLD_EFFECT_HEAL_INFATUATION`), `ITEM_POWER_HERB`
(`HOLD_EFFECT_CHARGE_SKIP`), `ITEM_BERRY_JUICE` (`HOLD_EFFECT_HP_RESTORE`). If the reader finds more, each one is
checked against the decomp by hand and listed in the validation log (SC-002). It is excluded only if that check
holds; otherwise the reader is fixed.

Single-use berries (allowed): Sitrus (`HOLD_EFFECT_HP_PCT_RESTORE`), the status, pinch, resist, Jaboca/Rowap,
Enigma and Custap berries.

Not single-use: Leftovers and Black Sludge (`TriggerLeftovers` → `subscript_restore_a_little_hp`, no removal), Focus
Band (`HOLD_EFFECT_MAYBE_ENDURE`: 10% chance per KO, `battle_controller_player.c:3387`, never removed), Quick Claw,
Sticky Barb (it moves to the attacker), Toxic/Flame Orb, every type-boost item. Plain berries with no battle
effect (Poffin-only) are not single-use. They are berries and stay allowed, though no candidate rule offers them.

Pre-Champion copies (ledger, 2026-10-29): Focus Sash 1, Mental Herb 1, White Herb 0, Power Herb 0, Berry Juice 0.
So only Focus Sash and Mental Herb could ever reach a candidate list without this rule.

## R5. Where the rule sits in the optimizer

**Decision**: `held_item_candidates` (`src/platsim/optimizer/candidates.py:422`) filters its final list through
`is_excluded_single_use(item)` (single-use and not a berry), applied once to the output. A new source added by a
later slice is covered without touching the filter (FR-003). It is a final filter, not a per-branch check.

The guard test (SC-004) monkeypatches the candidate sources so that one of them proposes `focus_sash`, and asserts
that it is filtered out. A second test with the filter disabled shows that the injection does reach the output, so
the first test is not passing by accident.

**Today's output (2026-10-29, `main` = `cbb0580`)**: the candidates are the HP berry, one type-boost item and
Leftovers. For all 17 attack types the chosen type boost has unlimited copies and is not single-use. So the filter
removes nothing, and B1-B5 candidates must be identical to `main` (FR-007).

**Alternatives considered**: filtering in `resources.realize` (it runs too late: candidates would still be scored), or
in the ledger (out of scope, and it would wrongly change availability and the validator).

## R6. Comparison with `main` (user: one team is enough)

**Decision**:
- B1-B5 held-item candidates (all variants, Lv 45/55/65, the same 93-entry set as feature 011 T004). These are
  captured on `main` (`cbb0580`) and on the branch, and must have identical keys, movesets and items.
- One same-seed optimization, B2 (`garchomp infernape staraptor rotom floatzel weavile --budget quick --seed
  013-sc005`), on `main` and on the branch. `result.json` may differ only at `/platsim_code_hash`,
  and `/repo_commit`. Generated data is not changed (R3), so `/provenance/worker/decomp_data_hash` must match. In 011 this took about
  25 minutes per run (1474-1494 s). It uses local compute only.

`main` has changed since 011's baseline (012, comment-only pass), so 011's `main-candidates.json` is not reused. Both
sides are captured fresh in this feature.

**Trap (from 011)**: no commits while the full suite or a benchmark runs. `repo_commit` is cached per process.
