# Validation log: 009 move and item classification

Real output per checkpoint. Evidence: `runs/009-evidence/` (git-ignored).

## T001 Setup (2026-10-19)

- Branch `009-move-item-classes` from `main` at `de102fa` (slice 1 merged). `git diff --stat main -- src sim tests`: empty. `extract --check`: "up to date (11 files)".
- R1: `git diff main 9e1f065 -- <8 src/test files> | git apply --check -v` → 8 "Checking patch" lines, no error.
- R2: `main`'s player has no `export const MODELLED = {` table; `9e1f065`'s reader returns `{}` then; nothing calls it.
- R3: `expectimax_self_boosts()` has 16 effects; 0 damaging moves use them, so the old "boosting attack" HM tier never occurs.

## T002-T004 Before (code = `main`)

- T002: `runs/009-evidence/candidates-main.json`, 93 member/variant/level entries.
- T003: `runs/009-evidence/hm-main.json`: `7440 cases, 2301 with a move replaced` (every B1-B5 member/variant at Lv 55, top 30 ranked movesets, each of the 8 HMs, one-member team).
- T004: quick B2, seed `009-sc004`, `runs/009-evidence/sc004-main`: `wall_s 1273`, exit 0, `qualified=False` (quick never qualifies).

## T005 Apply

- `git cherry-pick -n 9e1f065`: 8 src/test files applied; the 007 `tasks.md` conflicted (modify/delete) and was removed. `git diff --cached 9e1f065 -- src/platsim/optimizer <3 new tests> | wc -l` → `0`: byte-identical, no adaptation (FR-008). The only other src/test differences from `9e1f065` are slice 1's merged files.

## T006-T008 Classification and nothing-changes checks

- `pytest tests/unit/test_move_classes.py tests/unit/test_item_classes.py`: `114 passed in 38.52s` (SC-001, SC-002: every effect classifies; Screech foe drop; exactly 6 fixed-damage effects; Magnitude variable, not fixed; 17 resist berries found through the numeric reference; Amulet Coin, Flee and Friendship items no outcome in their named functions; exp/EV effects derived).
- `pytest tests/unit/test_required_hms_adopted.py tests/unit/test_required_hms.py`: `13 passed in 42.43s` (FR-006, FR-007).
- Re-run on the branch: `cmp candidates-main.json candidates-branch.json` → **IDENTICAL** (93 entries; FR-004, FR-005, SC-003). `cmp hm-main.json hm-branch.json` → **IDENTICAL** (7,440 cases, 2,301 replacing a move; FR-006, research R3).

## T009 Same-seed quick run after

- `runs/009-evidence/sc004-branch`: `wall_s 1267`, exit 0. Field-level diff of the two `result.json` (every key, recursively):
  ```
  /platsim_code_hash 'sha256:e32d0b47...' -> 'sha256:ad9c2068...'
  ```
  Only the code fingerprint differs; `decomp_data_hash` is unchanged (no ledger change in this slice). The "before" hash equals slice 1's branch hash (`e32d0b47...`), as `main` = slice 1. SC-004 met.

## T010 Full suite (2026-10-19)

- `uv run pytest -q`: `627 passed, 4 xfailed, 1 warning in 9650.47s (2:40:50)`, exit 0. `node --test sim/test/*.test.mjs`: `# tests 314`, `# pass 314`, `# fail 0`, exit 0 (no `sim/` change). Logs `runs/009-evidence/t010-*.log`.
- Against slice 1's full run (509 passed, 4 xfailed): **+118** = exactly the three new test files (`test_move_classes.py` 70, `test_item_classes.py` 44, `test_required_hms_adopted.py` 4). No test removed or newly failing. SC-005 met.
