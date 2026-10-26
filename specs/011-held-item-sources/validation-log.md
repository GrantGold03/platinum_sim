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
