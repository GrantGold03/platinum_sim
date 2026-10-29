# Validation log: 013 no single-use held items (H2)

Times are US Eastern. Evidence under `runs/013-evidence/` (git-ignored).

## T001 Setup (2026-10-29)

- Branch `013-no-single-use-items`, base `main` = `cbb0580`. `git diff --stat main HEAD -- src tests sim`: empty, exit 0
  (only spec documents differ).

## T002 Baseline B1-B5 held-item candidates (code = `main` `cbb0580`)

- `uv run platsim extract`: exit 0, 47.4 s (`extract-main.log`).
- Scratchpad script `candidates_snapshot.py`: `tests/fixtures/bench_007.json` from `007-status-moves-items`, every member,
  variant, Lv 45/55/65, `member_candidates(..., team=...)`. Output `runs/013-evidence/main-candidates.json`: 93 entries.
- **Positive control:** equal to `runs/011-evidence/main-candidates.json` (same 93 keys, 0 entries differ), so the
  rebuilt script reads candidates the same way as 011's.
- Items offered: dread/earth/fist/flame/icicle/meadow/mind/sky/splash/spooky/zap plates, silk scarf, Sitrus Berry.

## T003 Baseline same-seed quick B2 (code = `main` `cbb0580`)

- `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 013-sc005
  --out runs/013-evidence/sc005-main`: 10:33:57 to 10:54:56 AM EDT, wall 1259.38 s, exit 0.
- `result.json` sha256 `1febaabe255163b6...`; clear rate 0.81, expected average final level 53.22, `qualified=False`
  (quick never qualifies). `repo_commit cbb0580`, `repo_dirty=True` (the user's uncommitted lock-file deletion and
  untracked Spec Kit files; no `src/` change).

## T004 Switch (2026-10-29)

- `git switch 013-no-single-use-items`; `uv run platsim extract`: exit 0, 44.9 s (`extract-branch.log`).

## T005 Tests first

- `tests/unit/test_item_use.py` written before the module. `uv run pytest -q tests/unit/test_item_use.py`: collection
  error, `ImportError: cannot import name 'item_use' from 'platsim.decomp'`, exit 1 (expected).

## T006-T010 Reader `src/platsim/decomp/item_use.py`

- Script parser, subscript call graph (`BATTLE_SUBSCRIPT_X` / `subscript_x` → file stem; checked against
  `generated/battle_subscripts.txt` and `subscripts/sub_seq.order`, 297 = 297 in the same order), the five C trigger
  switches (rule 1), and a path-by-path walk with per-battler hold-effect constraints for the script guards (rules 2-4).
  The `custapBerry` flag is traced to `HOLD_EFFECT_PINCH_PRIORITY` (`battle_lib.c:1288`).
- Move-driven sites are found through `include/data/move_side_effect_subscripts.h` (Pluck has no `Call` from any
  script; it is reached via `MOVE_SUBSCRIPT_PTR_PLUCK`, `:142`).
- Berry flag read from item data `fieldPocket` in the module; `platsim/decomp/items.py` unchanged (research R3).
- No research R2 fallback (pinned line assertion) was needed; Complexity Tracking stays empty.
- Fix during T011: script refs were built with `rel()`, which fails on the test's copied tree. They are now built
  relative to the scripts root and read the same `res/battle/scripts/...:line` for the real decomp.

## T011 Classifier results

- `uv run pytest -q tests/unit/test_item_use.py`: `9 passed in 0.74s`, exit 0. (The completeness-gate test first
  failed because it parsed the copied tree before editing it, so the cache held the unedited parse. The test was
  reordered; the reader was not changed. A direct run on an edited copy raised
  `ItemUseReadError: res/battle/scripts/subscripts/subscript_battle_won.s:6: RemoveItem not tied to any hold effect
  and not reachable from a move`.)
- Reader cold run time: 0.62 s (one process, scratchpad probe).
- All 11 `RemoveItem` sites accounted for: 8 attributed, 3 move-driven (`effect_script_0222.s:8` Natural Gift,
  `effect_script_0233.s:18` Fling, `subscript_pluck.s:10` Pluck).
  - `subscript_pluck_check.s:6`: 26 hold effects (HP/status/PP/confusion berries, pinch berries, Berry Juice's
    `HOLD_EFFECT_HP_RESTORE`, White Herb, Mental Herb, ...).
  - `subscript_type_resist_berry.s:116`: 17 (`HOLD_EFFECT_WEAKEN_*`).
  - `subscript_move_followup_message.s:18` and `subscript_future_sight_damage.s:48`: `HOLD_EFFECT_ENDURE`.
  - `subscript_item_skip_charge_turn.s:20`, `subscript_power_herb_skull_bash.s:24`: `HOLD_EFFECT_CHARGE_SKIP`.
  - `subscript_held_item_recoil_when_hit.s:17`: `HOLD_EFFECT_RECOIL_PHYSICAL/SPECIAL`.
  - `subscript_check_quick_claw.s:28`: `HOLD_EFFECT_PINCH_PRIORITY` (Custap only; Quick Claw not single-use).
- **Excluded set (single-use, not a berry): exactly `ITEM_BERRY_JUICE`, `ITEM_FOCUS_SASH`, `ITEM_MENTAL_HERB`,
  `ITEM_POWER_HERB`, `ITEM_WHITE_HERB`.** Same as research R4; no extra item to check (SC-002).
- 64 berries: 44 single-use, 20 with no battle effect (Poffin-only: Razz, Bluk, Nanab, Wepear, Pinap, Pomeg, Kelpsy,
  Qualot, Hondew, Grepa, Tamato, Cornn, Magost, Rabuta, Nomel, Spelon, Pamtre, Watmel, Durin, Belue).
- Evidence: Focus Sash cites `subscript_move_followup_message.s:17-18` and `subscript_future_sight_damage.s:47-48`;
  Sitrus cites `battle_lib.c:4593` and `subscript_pluck_check.s:6`; Power Herb cites `effect_script_0039.s:7`,
  `effect_script_0145.s:6` and the two removal lines.
- Negative controls: Leftovers, Focus Band, Quick Claw, Sticky Barb, Silk Scarf, none: not single-use, no evidence.

## T012-T014 Candidate rule

- Before the filter, `-k single_use`: `2 failed, 1 passed`. The guard test failed with
  `assert 'focus_sash' not in ['sitrus_berry', 'focus_sash']` (today's code does offer an injected Sash). The control
  failed with `AttributeError: ... has no attribute 'is_excluded_single_use'` (the filter did not exist yet).
- Filter added as the last step of `held_item_candidates` (`src/platsim/optimizer/candidates.py`).
- `uv run pytest -q tests/unit/test_optimizer_candidates.py tests/unit/test_item_use.py`: `17 passed in 44.14s`,
  exit 0 (SC-001, SC-003, SC-004).
