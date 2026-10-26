# Validation log: 011 held-item sources (H1)

Times are US Eastern.

## T001 Setup (2026-10-26)

- Branch `011-held-item-sources`, base `main` `73af068`; spec docs up to `c610d67`.
- `git diff --stat f88cdd0 HEAD -- src tests sim`: empty (code identical to the code 008 was verified on).
- `git diff a8b529b^ a8b529b -- src tests | git apply --check -v`: "Checking patch" for
  `src/platsim/availability/sources.py`, `tests/integration/test_availability_controls.py`,
  `tests/unit/test_validator.py`; exit 0.

## T002 Baseline availability (2026-10-26, code = `main`)

- `uv run platsim extract`: exit 0, wall 44.57 s (log `runs/011-evidence/extract-main.log`).
- `data/generated/availability.json` copied to `runs/011-evidence/availability-main.json`. Held-item counts:
  **66 unlimited, 37 finite, 55 unavailable**.
- Per-item copies for all 446 items from `load_items()` (via `Ledger.item_copies`):
  `runs/011-evidence/main-availability-items.json` (scratchpad script `snapshot.py`).

## T004 Baseline held-item candidates (2026-10-26, code = `main`)

- B1-B5 (`bench_007.json` from branch `007-status-moves-items`), every variant, Lv 45/55/65: **93 entries**,
  `runs/011-evidence/main-candidates.json`. Items offered: dread/earth/fist/flame/icicle/meadow/mind/sky/splash/
  spooky/zap plates, silk scarf, Sitrus Berry.
- Script check: the same code produced `runs/008-evidence/candidates-main.json` on 2026-10-19; keys, movesets and
  items are equal, so the new script reads the candidates the same way.

## T003 Baseline explain (2026-10-26, code = `main`)

- `uv run platsim explain item:<key>` for black_belt, expert_belt, focus_sash, the 8 Pastoria berries, belue_berry,
  liechi_berry, choice_band: 14/14 exit 0. Output `runs/011-evidence/explain-main.txt`.

## T005 Baseline quick optimization of B2 (2026-10-26, code = `main`)

- `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 011-sc006
  --out runs/011-evidence/sc006-main`: 11:31:25 to 11:56:19 AM EDT, wall 1493.9 s, exit 0.
- `result.json` sha256 `0dbeab6aa580482e...`; `qualified=False` (quick never qualifies), clear rate 0.886,
  expected average final level 53.52. `repo_commit c610d67`, `repo_dirty=True` (the user's uncommitted lock-file
  deletion, untracked Spec Kit files, and this feature's uncommitted tasks/log edits; no `src/` change).

## Stop after the baseline (user, 2026-10-26)

- The user said not to rely on 008's documentation or implementation and to build from scratch when in doubt.
  T006 onward (cherry-pick `a8b529b`) is not started. Spec FR-009, research R1-R5, plan and tasks need revising
  through Spec Kit before implementation resumes. T001-T005 are on `main`'s code and stay valid.

## Implementation (after the from-scratch re-plan; tasks rewritten `f975456`)

### T006 Gap tests first (2026-10-26)

- `tests/integration/test_gift_reader.py`: G1-G4 positive controls (expected sets read from the decomp text by a
  regex or by item id, not by the reader), and negative controls: the literal Byron TM91 gift unchanged, Liechi
  Berry and Choice Band at 0 copies, every baseline `npc_item_gift` entry still produced (skips without the
  git-ignored baseline file).
- On `main`'s reader: `4 failed, 3 passed in 35.80s`. Each failure is `assert set() == {...}` (no item found at the
  give line): G1 Route 221 `:39`, G2 Pastoria `:20` (17 berries Occa..Chilan, incl. Babiri), G3 Amity `:375`,
  G4 Amity `:940`. Negative controls pass.

### T007 G1 call return (2026-10-26)

- `_const_dataflow` follows each Call with a return point (stack depth `CALL_DEPTH = 8`); a Return continues after
  the call with the routine's values; the fall-through still carries the caller's values.
- `test_gift_reader.py`: `3 failed, 4 passed in 36.79s`; G1 passes (Route 221 `:39` gives Black Belt, Expert
  Belt, Focus Sash); G2-G4 still fail as expected; all three negative controls pass (no baseline gift lost or changed).

### T008 G2 random offset (2026-10-26)

- `GetRandom`/`GetRandom2 VAR, n` give offsets 0..n-1 (`src/scrcmd.c:4947, :4958`); `AddVar VAR, ITEM_X` on offsets
  gives the items at `id(ITEM_X) + k` from `load_items()`; anything else is '?'.
- `test_gift_reader.py`: `2 failed, 5 passed in 35.76s`; G2 passes (Pastoria `:20` gives the 17 berries); G3, G4
  fail as expected; negative controls pass.

### T009 G3 saved variables (2026-10-26)

- `_saved_var_values()`: each saved variable (not `VAR_0x*` temps, not `VAR_MAP_LOCAL*`, not `VAR_RESULT`) maps
  to every literal `SetVar` value in all scripts, or '?' if any other script command writes it (first operand,
  comparisons excluded) or any `src/**/*.c` names it. 192 variables seen, 122 all-literal.
  `VAR_FOLLOWER_MON_PICKUP_ITEM_ID` -> the 9 Amity berries (no C source names it; checked by grep).
- `test_gift_reader.py`: `1 failed, 6 passed in 36.92s`; G3 passes (Amity `:375`); G4 fails as expected;
  negative controls pass.

### T010 G4 C-table command and variable AddItem (2026-10-26)

- `_table_commands()` reads every command in `include/data/scripts/scrcmd.h` and its handler in `src/scrcmd*.c`;
  a handler with exactly one variable pointer assigned `*dest = <static const array>[...]` yields the array's
  values. Matched: **1 command** of the table, `SCRCMD_GETAMITYSQUAREBERRYORACCESSORYIDFROMMAN` (destination
  operand 1; 9 `ITEM_*` berries + 7 `ACCESSORY_*`). Only `ITEM_*` values become entries.
- `npc_gift_entries` reads `AddItem VAR_0x8004/5, VAR_...` from the reader's values.
- `test_gift_reader.py`: `7 passed in 38.96s` (G1-G4 and all negative controls).

### T011 Daily-random-level rule (2026-10-26)

- A daily give whose path runs `GetDailyRandomLevel` counts each item as 1 copy (once flag `<daily flag>:<item>`,
  source = the `GetDailyRandomLevel` line). Tests added: Route 221 items quantity 1, one acquisition per item,
  source `:15`; Pastoria's plain daily gift stays unlimited (negative control). `9 passed in 38.96s`.
- The 1-copy test was written after the code; checked that it bites: with `_daily_random_level` replaced by a stub
  returning None, the three Route 221 entries come out `unlimited` (so the test would fail).

### T012 Rebuild (2026-10-26)

- `uv run platsim extract`: exit 0, wall 46.06 s (baseline 44.57 s, ×1.03). `--check`: up to date (11 files).
- `pytest tests/integration/test_gift_reader.py tests/integration/test_availability_controls.py`: `1 failed, 64
  passed in 40.11s`. The failure is the expected count pin: `test_wild_held_item_counts` `assert 74 == 66`
  (held items unlimited); pins are updated in T017.

### T013 Everything the reader change touched (FR-010) (2026-10-26)

Full output: `runs/011-evidence/t013-diff.txt` (scratchpad script `diff_entries.py`; per-item copies recomputed
to `runs/011-evidence/branch-availability-items.json`).

- Ledger entries: `main` 6812 → 6893: **81 added, 0 removed, 0 changed**. All 81 added entries are `pre_champion`.

  | Site | Entries | Items | Copies changed |
  |---|---|---|---|
  | Route 221 house | 3 | Black Belt, Expert Belt, Focus Sash | all 3: 0 → 1 |
  | Pastoria City SW house | 17 | Occa..Chilan (17 resist berries) | 8: Charti, Chilan, Coba, Kebia, Occa, Passho, Payapa, Tanga 0 → unlimited (the other 9 were already unlimited) |
  | Amity Square (pickup `:375` + Gift Man `:940`) | 18 | Belue, Cornn, Durin, Magost, Nomel, Pamtre, Rabuta, Spelon, Watmel | all 9: 0 → unlimited (`HOLD_EFFECT_NONE`) |
  | Route 208 house | 26 | 26 berries | none (all already unlimited) |
  | Flower Shop | 5 | Aspear, Cheri, Chesto, Pecha, Rawst Berry | none |
  | Solaceon News Press | 12 | 12 Poké Ball kinds | Dive Ball 1 → unlimited (`HOLD_EFFECT_NONE`) |

- Held-item counts (unlimited/finite/unavailable): **66/37/55 → 74/40/44**.
- **Gate: passed.** Every held item (hold effect not NONE) whose availability changed is from the Route 221 house
  (3) or the Pastoria SW house (8). Outside the three sources only Dive Ball changed (not a held item): the News
  Press daily reward picks one of 12 balls in called routines (`scripts_solaceon_town_pokemon_news_press.s:49-118`,
  daily flag `:68`), now read by G1; `main`'s daily rule makes it unlimited. Reported to the user.
- Veilstone prize exchange and scratch-off cards (research R3): no entry added at either site.
- No item's copies decreased (spec edge case "already available elsewhere").

### T015 Reason-text check (2026-10-26)

- Added to `test_gift_reader.py`: the label check (contract rule 2 patterns, decomp file:line required) with its
  positive control (a made-up line with `T053` and `dataflow` is rejected), applied to the source lines at the
  three new sites for Focus Sash, Occa Berry and Belue Berry.
- On the T014 code: `1 failed, 4 passed`. Positive control passes; Occa and Belue lines carry no labels; Focus Sash
  fails only because its line does not yet state the level condition and the 1-copy count (T016).

### T016 Reasons (2026-10-26)

- Route 221: `daily (FLAG_DAILY_RECEIVED_ROUTE_221_HOUSE_REWARD set at ...:41); given only if a party Pokemon is at
  that day's random level (GetDailyRandomLevel at res/field/scripts/scripts_route_221_house.s:15); the items rotate
  Black Belt, Expert Belt, Focus Sash; counted as 1 copy of each` (rotation order read from the order the script
  sets the items).
- Pastoria: `daily (...:19); one of 17 possible items`. Gift Man: `daily (...:973); one of 9 possible items or 7
  other prizes` (the 7 accessories of the C table). News Press: `daily (...:68); one of 12 possible items`.
- Amity partner condition: not stated. It is checked when the map loads (gate scripts, `OnTransition` hides the
  partner object), which the ledger's object-visibility reader does not model, so no command-based rule can attach
  it to the gift. **User decision (2026-10-26): leave it out**; recorded in spec Clarifications, FR-003, the edge
  case, the contract and research R2.
- Side effect, measured: the 4 Great Marsh 6 daily-shard entries `main` already had gain "; one of 4 possible items"
  (accurate; wording only, no availability change). Recorded in the contract. No other existing entry changed.
- After rebuild: `test_gift_reader.py` `13 passed in 39.09s` (incl. the reason-text check for Focus Sash, Occa,
  Belue and its positive control).

### T019 Validator (2026-10-26)

- `test_focus_sash_one_copy` in `tests/unit/test_validator.py`: ledger 1 copy; one holder no error; two holders
  `["ITEM_COPIES"]`. The file: `51 passed in 80.20s` (includes the Choice Band `ITEM_UNAVAILABLE` test). On `main`
  the first assertion would fail (Focus Sash 0 copies, baseline T002).

### T017 Count pins (2026-10-26)

- `test_wild_held_item_counts` pins 66/37/55 → **74/40/44**, with a comment naming the 11 changed items.
- `pytest tests/integration/test_availability_controls.py tests/integration/test_extract.py
  tests/integration/test_explain.py tests/integration/test_gift_reader.py`: `97 passed in 404.22s`, exit 0.

### T020 B1-B5 candidates (2026-10-26)

- `runs/011-evidence/branch-candidates.json` vs `main-candidates.json`: same 93 keys, **0 entries differ**
  (movesets and held-item candidates identical). FR-008 / SC-006 (inputs).

### T023 No archived code (2026-10-26)

- `git diff 73af068 -- src tests`: 0 matches each for `_const_dataflow_literal`, `007 dataflow`, `new_site`.
  Positive control: the same search in `git show a8b529b -- src` finds 3, 2 and 6. FR-009.

### T024 After-build comparison with 008 (2026-10-26; read only after T013-T020)

Source: `specs/008-ledger-item-sources/validation-log.md` (T003-T007 section). Nothing was changed to match it.

- **Same:** held-item counts 74/40/44; the same 11 held items change (3 Route 221 items to 1 copy, 8 Pastoria berries
  to unlimited); 81 entries added, none removed; same six sites.
- **Difference 1, Amity entry count:** 008's site table lists Amity Square with 9 entries (`:375` only), but its
  table sums to 72 while it reports 81 added. This build has 18 Amity entries (pickup `:375` and Gift Man `:940`,
  9 berries each) and its table sums to 81. Checked against the decomp: the Gift Man give is
  `AddItem LOCAL_VAR_ITEM_OR_ACCESSORY_ID, ...` at `scripts_amity_square.s:940`, so 18 is right; 008's table left out
  the Gift Man row.
- **Difference 2, Dive Ball:** 008 reports the News Press as "0 newly pre-Champion", which is true (Dive Ball was
  already pre-Champion, 1 copy). This build also records that its copies change 1 → unlimited: the News Press
  reward is daily (`scripts_solaceon_town_pokemon_news_press.s:68`) and `main`'s daily rule counts daily gifts as
  unlimited. Not a held item; no optimizer effect.
- **Difference 3, Great Marsh 6 wording:** 008 is not comparable here (its wording differed); this build's
  "one of 4 possible items" on those 4 existing lines is recorded under T016.

### T018 Explain before/after (2026-10-26)

- `runs/011-evidence/explain-branch.txt`: 14/14 exit 0. Liechi Berry and Choice Band **unchanged** from
  `explain-main.txt` (FR-006); the other 12 items each gain their new source line(s).
- New lines (refs in brackets):
  - Focus Sash: `[pre_champion] npc_item_gift at Route 221 House (MAP_HEADER_ROUTE_221_HOUSE), quantity 1: daily
    (FLAG_DAILY_RECEIVED_ROUTE_221_HOUSE_REWARD set at ...:41); given only if a party Pokemon is at that day's
    random level (GetDailyRandomLevel at ...:15); the items rotate Black Belt, Expert Belt, Focus Sash; counted as
    1 copy of each [res/field/scripts/scripts_route_221_house.s:39]`; phase pre_champion, copies 1.
  - Occa Berry: `... Pastoria City Southwest House ..., quantity unlimited: daily (...:19); one of 17 possible items
    [...scripts_pastoria_city_southwest_house.s:20]`.
  - Belue Berry: `... Amity Square ..., quantity 1: several possible items at this site; each counted once
    [...scripts_amity_square.s:375]` (pickup) and Gift Man `... quantity unlimited: daily (...:973); one of 9
    possible items or 7 other prizes [...scripts_amity_square.s:940]`.
- **Fix found here:** the Focus Sash line also showed `one-time flag: FLAG_DAILY_RECEIVED_ROUTE_221_HOUSE_REWARD:
  ITEM_FOCUS_SASH`, a flag name made up by T011 to count each item once; it reads as a decomp citation but does not
  exist in the game. Removed: the house has one map (`_owners` = `MAP_HEADER_ROUTE_221_HOUSE`), so quantity 1 alone
  gives 1 copy. The test now asserts no once flag and `item_copies == 1` for each item. `test_gift_reader.py`:
  `13 passed`. Rebuild and re-capture after the B2 run (T021) finishes.

### T021 Same-seed quick B2 (2026-10-26)

- Code `6d56b01` committed and pushed. Same command as T005, out `runs/011-evidence/sc006-branch`: 1:51:25 to
  2:16:00 PM EDT, wall 1474.30 s, exit 0.
- Field-by-field diff of `result.json` against `sc006-main`: only `/platsim_code_hash`,
  `/provenance/worker/decomp_data_hash` and `/repo_commit` differ. Team, clear rate, levels, held items and
  their sources are identical (SC-006).
- After the T018 fix (`c81bb5b`, pushed): rebuilt; Focus Sash `explain` has no "one-time flag" line, copies 1;
  counts still 74/40/44 with Black Belt, Expert Belt, Focus Sash at 1 each.
