# Feature Specification: No Single-Use Held Items (held items, slice H2)

**Feature Branch**: `013-no-single-use-items`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "H2 (held items, slice 2, revised 2026-10-29): the optimizer never offers single-use held items. Rule: a held item that is consumed when it triggers (Focus Sash, White Herb, Mental Herb, Power Herb, and any other non-berry held item the decomp removes from the holder on use) is never a held-item candidate. Berries stay allowed (today: the best HP-restore berry; later slices may add resist berries / Lum Berry). \"Single-use\" is decided from the decomp (how the battle code consumes the item), not a hand-typed list; the spec should name the decomp evidence and list the items it classifies as single-use. Today held_item_candidates (optimizer/candidates.py) offers only the HP berry, one type-boost item (all pre-Champion picks are unlimited and not consumed) and Leftovers, so no current output changes. H2 makes the rule explicit in held_item_candidates and adds tests that fail if a single-use non-berry item is ever proposed. Superseded plan: offering Focus Sash / Life Orb (Life Orb has 0 pre-Champion copies). Out of scope: the battle player, the ledger, adding any new item group (H3+). Acceptance: B1-B5 candidate sets and same-seed results identical to main; the new tests pass, with a positive control showing the classifier marks Focus Sash single-use and Sitrus Berry as an allowed berry; fast mode and the Node suite pass."

## Context

The held-item work is being redone as small features, each tested by the user before the next starts. H1 (feature 011, merged 2026-10-26) taught the availability ledger three missing item sources, including the Route 221 house, which gives 1 Focus Sash before the Champion.

H2 was first planned as "offer the held items the battle player already models": Focus Sash, and Life Orb if it can be had before the Champion. On 2026-10-29 the user replaced that plan: the optimizer should never pick single-use held items. Berries stay allowed. Life Orb was moot anyway: the ledger gives it 0 pre-Champion copies (its only source is the item on the ground outside Stark Mountain, post-game).

Today's optimizer already offers no single-use non-berry item. It offers the best HP-restoring berry, the one type-boost item for the moveset's strongest attack type, and Leftovers when the team can get it. Checked 2026-10-29: for each of the 17 attack types, the type-boost item it picks has unlimited pre-Champion copies (Silk Scarf, Poison Barb, Hard Stone, Metal Coat, and the Plates, which the Underground can dig up again and again). None of them is used up in battle. So this feature changes no output today. Its value is that the rule becomes explicit, comes from the decomp, and is guarded by tests, so later slices (H3+) cannot bring a single-use item in by accident.

## Clarifications

### Session 2026-10-29

- Q: Should the optimizer offer Focus Sash (the original H2 plan)? → A: No. "I want to completely remove single use items from the options that the optimizer picks. Berries are still okay, but items such as focus sash are not" (user).
- Q: Does "single-use" mean "used up when it triggers in battle" or "only one copy in the game"? → A: Used up when it triggers. The berry exemption only makes sense under that reading, since berries are used up too. The user accepted this reading by running `/speckit-specify` with the description that states it. Under either reading no item offered today changes.

## Decomp evidence: how a held item is used up

Pinned decomp commit as recorded in `src/platsim/pins.py`. In battle, a held item is removed from its holder by the battle-script command `RemoveItem` (`src/battle/battle_script.c:8972` `BtlCmd_RemoveItem`: it saves the item for Recycle and sets the battler's held item to none). Two other places clear a held item. Knock Off (`battle_script.c:6627`) does it to an opponent's item and is not the item's own effect. Battle setup (`battle_lib.c:122,162`) is not a use. Neither counts here.

A held item is **single-use** when its own hold effect, on triggering, runs a battle script that reaches `RemoveItem` for the holder. Found 2026-10-29 by reading the trigger functions in `src/battle/battle_lib.c` and the subscripts in `res/battle/scripts/subscripts/`:

| Trigger path | Removal evidence | Hold effects / items reached |
|---|---|---|
| `BattleSystem_TriggerHeldItem` / `..._TriggerHeldItemOnStatus` (`battle_lib.c:4576`, `:4967`) → `subscript_held_item_*` | each of those subscripts calls `BATTLE_SUBSCRIPT_PLUCK_CHECK`, which runs `RemoveItem` unless the berry was plucked (`subscript_pluck_check.s:5`) | HP / status / PP / confusion restore berries and pinch berries; **Berry Juice** (`HOLD_EFFECT_HP_RESTORE`, `berry_juice.json`); **White Herb** (`HOLD_EFFECT_STATDOWN_RESTORE`); **Mental Herb** (`HOLD_EFFECT_HEAL_INFATUATION`) |
| Endure on a KO (`subscript_move_followup_message.s:17-18`, `subscript_future_sight_damage.s:47-48`) | `RemoveItem` only when the holder has `HOLD_EFFECT_ENDURE` | **Focus Sash**. Focus Band (`HOLD_EFFECT_MAYBE_ENDURE`) takes the same message path but is not removed |
| Charge-turn skip (`subscript_item_skip_charge_turn.s:20`, `subscript_power_herb_skull_bash.s:24`) | `RemoveItem` | **Power Herb** (`HOLD_EFFECT_CHARGE_SKIP`) |
| Hit-trigger (`BattleSystem_TriggerHeldItemOnHit`, `battle_lib.c:5370`) → `subscript_held_item_recoil_when_hit.s:17`, `subscript_held_item_hp_restore` | `RemoveItem` / pluck check | Jaboca, Rowap, Enigma berries |
| Type-resist (`subscript_type_resist_berry.s:116`) | `RemoveItem` | resist berries (Occa ... Chilan) |
| Speed order (`subscript_check_quick_claw.s:26-28`) | `RemoveItem` only on the Custap Berry branch | Custap Berry. Quick Claw takes the same subscript and is not removed |

Not single-use, though their effects run scripts: Leftovers and Black Sludge (`BattleSystem_TriggerLeftovers`, `battle_lib.c:4922`, `subscript_restore_a_little_hp`), Sticky Barb (it moves to the attacker, `subscript_transfer_sticky_barb`; it is not removed), Toxic Orb and Flame Orb, Focus Band, Quick Claw, and every type-boost item.

**Expected single-use, non-berry items** (the excluded set): Focus Sash, White Herb, Mental Herb, Power Herb, Berry Juice. The classifier built in this feature derives the set from the decomp, and the plan's research confirms it, including any item the table above missed. Pre-Champion copies (ledger, 2026-10-29): Focus Sash 1, Mental Herb 1, White Herb 0, Power Herb 0, Berry Juice 0.

**Berry**: an item whose decomp item data has `"fieldPocket": "POCKET_BERRIES"` (64 items in `res/items/data/`). Berry Juice is in the medicine pocket, so it is not a berry, even though it is used up like one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The optimizer never gives a team a single-use non-berry item (Priority: P1)

A player optimizes a team. No member of the result holds Focus Sash, White Herb, Mental Herb, Power Herb, Berry Juice, or any other item the decomp uses up on trigger, unless that item is a berry. Berries such as Sitrus Berry are still offered as before.

**Why this priority**: The user does not want teams that depend on an item that is gone after one use. The rule protects every later held-item slice.

**Independent Test**: Ask the held-item candidate rule for candidates for a range of members, movesets and teams, including a team where Focus Sash and Mental Herb have pre-Champion copies. No candidate list contains a single-use non-berry item. Then show a positive control: the classifier marks Focus Sash single-use and Sitrus Berry as an allowed berry.

**Acceptance Scenarios**:

1. **Given** any member, moveset and team, **When** held-item candidates are produced, **Then** none is a single-use non-berry item.
2. **Given** the item classifier, **When** it classifies Focus Sash, White Herb, Mental Herb, Power Herb and Berry Juice, **Then** each is single-use and not a berry.
3. **Given** the item classifier, **When** it classifies Sitrus Berry, **Then** it is single-use and a berry, so it stays allowed.
4. **Given** the item classifier, **When** it classifies Leftovers, Focus Band, Quick Claw, Sticky Barb and a type-boost item (Silk Scarf), **Then** none is single-use.
5. **Given** a later change that adds a single-use non-berry item to the candidate rule (simulated in a test), **When** the tests run, **Then** they fail.

---

### User Story 2 - Nothing else changes (Priority: P1)

A player who runs the same request on this branch and on `main` gets the same candidates and the same team.

**Why this priority**: The rule is meant to change no output today. A difference would mean a mistake in the rule or in the claim that today's candidates hold no single-use item.

**Independent Test**: Compare the held-item candidates of benchmark teams B1-B5 with `main`, and run the same-seed optimization of B1-B5 on both.

**Acceptance Scenarios**:

1. **Given** benchmark teams B1-B5, **When** held-item candidates are produced on this branch and on `main`, **Then** they are identical.
2. **Given** B1-B5 and the same seeds, **When** optimized on this branch and on `main`, **Then** results are identical apart from provenance hashes (code hash, repo commit).

---

### Edge Cases

- A berry that is used up (Sitrus, resist berries, Custap) stays allowed. Being a berry wins over being single-use.
- A non-berry item that is used up like a berry (Berry Juice) is excluded.
- An item that leaves its holder by moving to another Pokémon (Sticky Barb) is not single-use.
- An item that shares a script path with a single-use item but is not removed (Focus Band beside Focus Sash, Quick Claw beside Custap Berry) is not single-use. The classifier must follow the item check in the script, not only the script name.
- Items removed only by a move (Knock Off, Thief, Fling, Natural Gift, Pluck, Bug Bite) are not single-use by that alone. Only the holder's own hold effect counts.
- If the classifier finds no single-use item at all, or does not mark Focus Sash, it must fail loudly. An empty result looks the same as a broken reader.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST classify every holdable item as single-use or not, using the decomp: an item is single-use when its own hold effect, on triggering, reaches the battle-script command that removes the holder's item. No hand-typed item list.
- **FR-002**: The system MUST classify an item as a berry exactly when its decomp item data puts it in the berries pocket.
- **FR-003**: The optimizer's held-item candidate rule MUST never propose an item that is single-use and not a berry. The rule applies to every candidate source in that rule, including ones added by later features.
- **FR-004**: Berries MUST stay eligible whether or not they are single-use.
- **FR-005**: Each single-use classification MUST be traceable to decomp file and line (the trigger and the removal), in line with Principle I.
- **FR-006**: The classifier MUST have positive controls. Focus Sash is single-use and not a berry. Sitrus Berry is single-use and a berry. Leftovers is not single-use. A run that finds no single-use item fails.
- **FR-007**: For benchmark teams B1-B5, the held-item candidates and the same-seed optimization results MUST be identical to `main`'s, apart from provenance hashes.
- **FR-008**: The battle player, the availability ledger, the validator and `platsim explain` output MUST NOT change.

### Key Entities

- **Item classification**: for each holdable item, single-use (yes/no) with its decomp evidence, and berry (yes/no). Derived from the pinned decomp, never hand-edited.
- **Held-item candidate rule**: the optimizer's existing rule for which held items to try on a member. It gains one filter: no single-use non-berry item.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across all candidate lists produced by the tests (B1-B5 members and the extra test teams), 0 contain a single-use non-berry item.
- **SC-002**: The classifier's single-use non-berry set includes Focus Sash, White Herb, Mental Herb, Power Herb and Berry Juice. Any further item it reports is checked against the decomp and listed in the validation log.
- **SC-003**: The positive controls pass: Focus Sash single-use, not a berry; Sitrus Berry single-use, a berry; Leftovers, Focus Band, Quick Claw and Silk Scarf not single-use.
- **SC-004**: A test that injects a single-use non-berry item into the candidate rule fails, which shows the guard works.
- **SC-005**: B1-B5 held-item candidates and same-seed optimization results are identical to `main`'s apart from provenance hashes.
- **SC-006**: The fast test mode and the Node test suite pass, with their output recorded.

## Assumptions

- The pinned decomp commit is unchanged. The evidence table above was read on 2026-10-29 and is confirmed by the classifier in the plan's research.
- Removal by the holder's own effect is the only removal that makes an item single-use. Knock Off and similar moves do not count.
- The optimizer's objective is unchanged: it is the one stated in the report files and in earlier feature specs. This feature only narrows which held items it may try, and today that narrowing removes nothing.
- `platsim explain` does not gain a "never offered" note in this feature. That can be a follow-up if the user wants it.
- Same-seed B1-B5 optimizer runs use local compute only. They are the longest step. Feature 011 compared one benchmark team rather than five, and the user may narrow this at plan time.
- Out of scope: the battle player, the ledger, the validator, adding any new item group (H3+).
