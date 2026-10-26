# Research: Held-Item Sources (H1)

Derived from scratch on 2026-10-26, on branch `011-held-item-sources` (code = `main` `73af068`), from the decomp
(`pokeplatinum/` at `c248fb3f`) and `main`'s code. 008's archive is not used (spec FR-009); it may be compared
only after the build.

## R1. Why `main`'s ledger misses these sources

NPC gifts are read by `npc_gift_entries` (`src/platsim/availability/sources.py:945-995`). It finds each give
(`Common_GiveItemQuantity*` with the item in `VAR_0x8004` and the count in `VAR_0x8005`, or `AddItem` with a
literal item) and takes the item from `_const_dataflow` (`:914-942`). That reader knows only `SetVar VAR, <literal>`;
any other write makes the value unknown (`?`), and an unknown item is dropped. Four gaps, each confirmed in the
decomp:

| Gap | Where it bites | Decomp evidence |
|---|---|---|
| G1. A value set inside a called routine is lost after `Return` | Route 221 house | The item is set in `Route221House_SetReward*` (`scripts_route_221_house.s:50-60`), reached by `CallIfEq` (`:28-30`). `successors()` (`src/platsim/decomp/scripts.py:513-549`) sends the caller's state both into the routine and straight to the next command; `Return` has no successors, so the routine's `SetVar` never reaches the give at `:39`. |
| G2. A random offset added to an item constant | Pastoria City SW house | `GetRandom VAR_0x8004, 17` then `AddVar VAR_0x8004, ITEM_OCCA_BERRY` (`scripts_pastoria_city_southwest_house.s:15-16`): the 17 item ids from Occa upward. `AddVar` makes the value unknown today. |
| G3. An item copied from a saved variable set elsewhere in the file | Amity Square partner pickup | `SetVar VAR_FOLLOWER_MON_PICKUP_ITEM_ID, ITEM_<berry>` in one run (`scripts_amity_square.s:299-344`), then `SetVar LOCAL_VAR_ITEM_OR_ACCESSORY_ID, VAR_FOLLOWER_MON_PICKUP_ITEM_ID` (`:356`, `LOCAL_VAR_ITEM_OR_ACCESSORY_ID` = `VAR_0x8004`, `:8`) and the give at `:375`. |
| G4. An item chosen by a script command from a table in C, given by `AddItem` with variable operands | Amity Square Gift Man | `GetAmitySquareBerryOrAccessoryIDFromMan` (`:923`) reads `sBerryAndAccessoryManOptions` (`src/scrcmd_amity_square.c:147-181`), whose first 9 entries are berries and the rest accessories (`CheckAmitySquareManGiftIsAccessory`: id < 9 is an item). Given by `AddItem LOCAL_VAR_ITEM_OR_ACCESSORY_ID, LOCAL_VAR_ITEM_OR_ACCESSORY_COUNT` (`:940`); `main` reads `AddItem` only with a literal item. |

- Decision: fix all four in the general reader (spec FR-010), never keyed to a map or script name:
  - G1: carry a call stack through the reader, so `Return` continues at the command after the call that entered
    the routine, with the routine's values.
  - G2: `GetRandom VAR, n` gives the offsets `0..n-1`; `AddVar VAR, ITEM_X` on such a set gives the items at
    those ids, taken from the decomp item list (`generated/items.txt`). Any other arithmetic stays unknown.
  - G3: a saved variable (not a `VAR_0x8000`-range temp) copied into a tracked variable takes every literal value
    written to it anywhere in the scripts; if any write is non-literal, it stays unknown.
  - G4: a script command that returns an entry of a C table is read by parsing that table from the C source of the
    command's handler; `AddItem` with a variable item uses the reader's values. Only table entries that are items
    count (`ITEM_*`), so accessories are skipped.
- Alternatives: rules for the three scripts only (rejected by the user, spec Clarifications, Q1).

## R2. What each source gives, and its copy count

| Source | Items | Repeat | Copies under `main`'s rules | Decision |
|---|---|---|---|---|
| Route 221 house | Black Belt, Expert Belt, Focus Sash, in that order, one per successful day (`:42-44` advance `VAR_ROUTE_221_HOUSE_REWARD_INDEX` 0→1→2→0) | daily flag `FLAG_DAILY_RECEIVED_ROUTE_221_HOUSE_REWARD` (`:41`), and only if a party Pokémon is at the day's random level (`GetDailyRandomLevel`, `:15-24`) | daily → unlimited | **1 copy of each** (user, 2026-10-14). Detected from the script: a daily give whose path runs `GetDailyRandomLevel`. |
| Pastoria City SW house | the 17 berries from Occa Berry (`ITEM_OCCA_BERRY` + 0..16) | daily flag (`:19`) | daily → unlimited; also berries → unlimited when a berry patch is reachable (`Ledger.item_copies`) | `main`'s rules unchanged. |
| Amity Square partner pickup | Magost, Cornn, Rabuta, Nomel, Spelon, Pamtre, Watmel, Durin, Belue Berry (`:299-344`, 20%-7% each) | none: repeats while walking | berries → unlimited | `main`'s rules unchanged. |
| Amity Square Gift Man | the same 9 berries (`scrcmd_amity_square.c` table, first 9) | daily flag `FLAG_DAILY_RECEIVED_AMITY_SQUARE_MAN_GIFT` (`:973`) | daily → unlimited | `main`'s rules unchanged. |

- Held items affected: the 9 Amity berries all have `HOLD_EFFECT_NONE` (checked in `res/items/data/*_berry.json`),
  so they are not counted in the held-item totals. Expected held-item changes: Black Belt, Expert Belt, Focus Sash
  (0 → 1) and every Pastoria berry that is unavailable on `main` (→ unlimited). The exact list comes from the
  per-item diff against the baseline (T002 evidence), not from this table.
- Amity Square partner condition: entry with a walking partner needs one of 16 species in the party, which include
  every stage of the three starters (`scripts_amity_square.s:646-677`). Every player has a starter, so the condition
  is always met. It is recorded in the reason text, not as a gate.

## R3. Other places the general fix may reach (FR-010)

Scripts that write the item variable in a way G1-G4 may now read (grep of `res/field/scripts`, 2026-10-26; a text
search, so it shows candidates, not results):

- `AddVar`/`SubVar`/`GetRandom` on `VAR_0x8004`: Flower Shop, Great Marsh 6, Global Terminal 1F, Jubilife City,
  Mining Museum, Pastoria SW house, Route 208 house.
- Item set inside a routine that ends in `Return`: Celestic Town cave, Jubilife City, Route 207, Route 221 house,
  Solaceon News Press, Sunyshore City.
- `AddItem` with a variable item: Amity Square, Route 208 house, scratch-off cards, Veilstone prize exchange, an
  unused Battle Park room (plus `scripts_common`, hidden and visible items, which the gift reader skips).
- `SetVar VAR_0x8004` from another variable: 25 files, mostly shared or post-game scripts.

Decision: implementation lists every site whose entries change (before/after ledger diff), with the items. Any held
item whose availability changes and is not from the three sources is reported to the user before acceptance
(spec FR-010). Watch in particular: Veilstone prize exchange (the Game Corner is already modelled by
`game_corner_entries`, so new gift entries there could double count) and scratch-off cards (random prizes).

## R4. User-facing text

- `platsim explain` prints each entry's `detail` verbatim (`src/platsim/explain.py:217-219`); the optimizer's
  source text comes from `src/platsim/report/sources.py` instead, so wording does not reach optimizer results.
- Decision: the reasons this feature adds are written in plain English for a player (contract). Decomp identifiers
  (flag names, file:line) are citations and may appear, as they do on `main`'s existing lines; the project's own
  labels and implementation words may not. `main`'s existing reason phrases are unchanged.

## R5. Optimizer impact

- `held_item_candidates` (`src/platsim/optimizer/candidates.py:422-449`) offers the best HP-restoring berry, one type
  booster for the strongest attack (unlimited copies sort first, so a 1-copy Black Belt cannot displace the unlimited
  Fist Plate), and Leftovers when the team can get it. Expert Belt and Focus Sash are not in this rule; resist berries
  are not HP berries.
- Expected: B1-B5 candidates identical to the baseline (T004) and the same-seed quick B2 run identical apart from
  provenance hashes (T005). Measured in implementation; any difference is explained before acceptance.

## R6. Story ranking is separate

`story_rank.item_source_maps` (`src/platsim/availability/story_rank.py:522-536`) finds item sources by a literal text
search of `SetVar VAR_0x8004, ITEM_Y` / `AddItem ITEM_Y` for story checkpoints that need an item. It does not use the
gift reader and is not changed.
