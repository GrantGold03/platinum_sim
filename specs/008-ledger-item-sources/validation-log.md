# Validation log: 008 ledger item sources

Real output per checkpoint. Machine: 16 threads. Evidence files: `runs/008-evidence/` (git-ignored).

## T001 Setup (2026-10-19)

- Branch `008-ledger-item-sources` from `main` at `f88cdd0`. Before T002, `git diff --stat main -- src sim tests` prints nothing (code equals `main`); `uv run platsim extract --check`: "up to date (11 files)".
- **R1 patch check:** `git diff main a8b529b -- src/platsim/availability/sources.py tests/integration/test_availability_controls.py tests/unit/test_validator.py | git apply --check -v`:
  ```
  Checking patch src/platsim/availability/sources.py...
  Checking patch tests/integration/test_availability_controls.py...
  Checking patch tests/unit/test_validator.py...
  ```
  Only `a8b529b` touches these files between `main` and `007-status-moves-items`; the one new import (`platsim.decomp.scripts.walk`, `scripts.py:562`) exists on `main`; `src/platsim/decomp` is identical on both branches.
- **R2 `main` counts** (`uv run platsim extract`, 41.8 s): 66 unlimited, 37 finite, 55 unavailable (158). Snapshot `runs/008-evidence/availability-main-f88cdd0.json`. `main`'s tests pin 66 and 55 (`test_availability_controls.py:522, 526`).
- Constitution v1.4.0 brought from the 007 branch as its own docs commit (`7deb5d9`).

## T001b SC-005 "before" (2026-10-19, code = `main`)

- Quick optimization of B2 (garchomp, infernape, staraptor, rotom, floatzel, weavile), seed `008-sc005`, out `runs/008-evidence/sc005-main`: `wall_s 1365`, exit 0, `qualified=False` (quick never qualifies). `result.json` sha256 `899d1df9c8d4d0cf...`.
- Held-item candidates for every B1-B5 member (all variants; Lv 45, 55, 65; 93 entries) on `main`'s ledger: `runs/008-evidence/candidates-main.json`.

## T002 Apply (2026-10-19)

- `git cherry-pick -n a8b529b`: the three code/test files applied; the commit's two 007 spec files conflicted (modify/delete; they do not exist on `main`) and were removed. `git diff --cached a8b529b -- <the 3 files> | wc -l` → `0`: **byte-identical to the 007 commit, no adaptation** (FR-008).

## T003-T007 Ledger and validator (2026-10-19)

- `uv run platsim extract`: 42.8 s; `--check`: "up to date (11 files)". Counts **74 unlimited, 40 finite, 44 unavailable** (SC-002).
- `uv run pytest -q tests/integration/test_availability_controls.py tests/integration/test_extract.py tests/unit/test_validator.py`: `114 passed in 425.03s` (includes the 66/55 → 74/44 pins and `test_route_221_focus_sash_accepted_once`: one holder passes, two give ITEM_COPIES, Choice Band gives ITEM_UNAVAILABLE; SC-003).
- **Held-item availability diff vs `main`** (11 items, all unavailable before):

  | Item | Now | Source |
  |---|---|---|
  | Black Belt, Expert Belt, Focus Sash | 1 copy | Route 221 house (`scripts_route_221_house.s:39`, daily random level condition, `:15`) |
  | Charti, Chilan, Coba, Kebia, Occa, Passho, Payapa, Tanga Berry | unlimited | Pastoria City SW house (`scripts_pastoria_city_southwest_house.s:20`, daily) |

  Other counts (TMs, species, maps, flag groups) unchanged; `entries_by_phase.pre_champion` 2,995 → 3,076 (+81), no entry removed. `platsim explain` output for all 11 plus Wacan in `runs/008-evidence/explain.txt`; each shows the source, script line, copies and the pre-Champion verdict (SC-001).
- **The 81 new entries by site** (same dataflow improvement; the spec named three sites):

  | Site | Items | Newly pre-Champion |
  |---|---|---|
  | Route 221 house | 3 | 3 (above) |
  | Pastoria SW house | 17 resist berries | 8 (above) |
  | Amity Square (`scripts_amity_square.s:375`) | 9 berries (Belue, Cornn, Durin, Magost, Nomel, Pamtre, Rabuta, Spelon, Watmel) | 9, none a counted held item |
  | Route 208 house | 26 berries | 0 |
  | Solaceon News Press | 12 balls | 0 |
  | Flower Shop | 5 berries | 0 |

  The last three are extra sources for items already pre-Champion: no availability change (FR-006 holds). Recorded in the spec's Assumptions.

## T008 Optimizer inputs (2026-10-19)

- Held-item candidates for all 93 B1-B5 member/variant/level entries on this branch's ledger: `cmp runs/008-evidence/candidates-main.json runs/008-evidence/candidates-branch.json` → **IDENTICAL**. Items offered: dread/earth/fist/flame/icicle/meadow/mind/sky/splash/spooky/zap plates, silk scarf, Sitrus. Fist Plate still wins over the new 1-copy Black Belt (unlimited sorts first, research R3), so the Fighting path was exercised.

## T009 SC-005 "after" (2026-10-19)

- Same request with the code applied, out `runs/008-evidence/sc005-branch`: `wall_s 1386`, exit 0. `cmp` of the two `result.json`: differ. Field-level diff (every key, recursively):
  ```
  /platsim_code_hash 'sha256:0b958e84...' -> 'sha256:e32d0b47...'
  /provenance/worker/decomp_data_hash 'sha256:9d3a901f...' -> 'sha256:2e462157...'
  ```
  Only the two provenance fingerprints differ, as they must (code and generated data changed). Team, levels, rates and every stage record are identical (SC-005, FR-007).

## T010 Full suite (2026-10-19)

- `uv run pytest -q`: `509 passed, 4 xfailed, 1 warning in 9192.47s (2:33:12)`, exit 0. `node --test sim/test/*.test.mjs`: `# tests 314`, `# pass 314`, `# fail 0`, exit 0. Logs: `runs/008-evidence/t010-*.log`.
- Against `main`'s last full run (007 T002, 2026-10-15, `f88cdd0` snapshot: `1 failed, 503 passed, 4 xfailed`, 508 collected): 513 collected = **+5**, exactly the tests `a8b529b` adds (4 in `test_availability_controls.py`, 1 in `test_validator.py`; same as the 007 collect diff). The T002 failure (`test_determinism_fast`, None commit in the git-less snapshot) passes in the real checkout. Node unchanged at 314 (no `sim/` change).
