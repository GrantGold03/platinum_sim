# Validation log: 014 damage-boosting held items (H3)

Times are US Eastern. Evidence under `runs/014-evidence/` (git-ignored).

## T001 Setup (2026-10-29)

- Branch `014-damage-boost-items`, base `main` = `3078dad`. `git diff --stat main HEAD -- src tests sim`: empty,
  exit 0.

## T002 Baseline B1-B5 candidates (code = `main` `3078dad`)

- `uv run platsim extract`: exit 0. `candidates_snapshot.py` → `runs/014-evidence/main-candidates.json`: 93 entries.
- **Positive control:** equal to `runs/013-evidence/branch-candidates.json` (same 93 keys, 0 differ).

## T003 Baseline quick B2 (code = `main` `3078dad`)

- `uv run platsim optimize garchomp infernape staraptor rotom floatzel weavile --budget quick --seed 014-b2
  --out runs/014-evidence/b2-main`: 12:42:54 to 1:07:49 PM EDT, **wall 1495.13 s**, exit 0.
- `result.json` sha256 `a9525d31aa6ffdf4...`; clear rate 0.918, expected average final level 54.22; `repo_commit 3078dad`.
- Team (item, start level): Garchomp Sitrus 52, Infernape Sitrus 54, Staraptor Sitrus 53, Rotom Zap Plate 55,
  Floatzel Sitrus 55, Weavile Sitrus 53.

## T004 Switch

- `git switch 014-damage-boost-items`; `uv run platsim extract`: exit 0.

## T005 Current candidate lists (before the change)

```
SPECIES_EMPOLEON ('MOVE_SURF',) ['sitrus_berry', 'splash_plate']
SPECIES_GARCHOMP ('MOVE_EARTHQUAKE',) ['sitrus_berry', 'earth_plate']
SPECIES_SNORLAX ('MOVE_BODY_SLAM',) ['sitrus_berry', 'silk_scarf', 'leftovers']
SPECIES_GARCHOMP ('MOVE_SWORDS_DANCE',) ['sitrus_berry']
```
These match the prefixes in `contracts/held-item-candidates.md`; no contract change needed.

## T006-T007 Tests first

- `-k "booster or expert_belt or muscle_band"` before the change: `4 failed, 4 passed`. The failures are special,
  physical, after-existing and the Muscle Band control (no booster offered yet). The passes are the group-from-data
  test, no booster without an attack, the H2 rule, and the Expert Belt copy test. The copy test passes on the
  existing accounting, as research R3 expected: realizing a second holder is refused at slot 1, and the validator
  flags `ITEM_COPIES` on a hand-built two-holder team.

## T008-T009 Rule

- `held_item_candidates`: after the existing items, for a moveset with an attack, every `HOLD_EFFECT_POWER_UP_SE`
  item with a copy, then the `POWER_UP_PHYS` / `POWER_UP_SPEC` item for the strongest attack's category with a copy.
  No duplicates; then the H2 filter.
- `uv run pytest -q tests/unit/test_optimizer_candidates.py tests/unit/test_item_use.py`: `25 passed in 47.61s`,
  exit 0 (SC-002, SC-003).

## T010-T011 Sources

- `test_damage_booster_sources_in_report`: `1 passed`. `team_sources` names Celestic Town for Wise Glasses and
  Route 221 for Expert Belt, with the script refs.
- `platsim explain item:expert_belt` / `item:wise_glasses` (`runs/014-evidence/explain-branch.txt`, exit 0):
  Route 221 House `npc_item_gift`, daily, day's random level, 1 copy (`scripts_route_221_house.s:39`); Celestic
  Town Northwest House `npc_item_gift`, quantity 1 (`scripts_celestic_town_northwest_house.s:69`).

## T012 Commit

- `681daa9` "feat(014): offer damage-boosting held items by hold effect"; pushed to `origin/014-damage-boost-items`.

## T013 B1-B5 candidates on the branch

- `candidates_snapshot.py` → `runs/014-evidence/branch-candidates.json`: exit 0, 93 entries, same keys and movesets
  as `main-candidates.json`.
- 351 moveset item lists. Each `main` list is an unchanged prefix of the branch list, and all 351 gained items:
  `expert_belt` 351 times, `wise_glasses` 162 times. **0 other differences** (SC-001).

## T014 Quick B2 on the branch

- Code `681daa9` (pushed). Same command as T003, out `runs/014-evidence/b2-branch`: 1:14:16 to 1:34:15 PM EDT,
  **wall 1198.44 s**, exit 0. **Ratio branch/main = 0.80** (1198.44 / 1495.13; SC-005). The branch was faster in
  this single pair, so the extra candidates did not make it slower. One run per side is not enough to call the
  speed-up an effect.
- `result.json` sha256 `4c6d8e41a614a20e...`; clear rate 0.838 at its own start levels, expected average final
  level 53.34; `repo_commit 681daa9`.
- Team (item, start level): Garchomp Earth Plate 51, Infernape Sitrus 53, Staraptor Sitrus 53, **Rotom Expert Belt
  53**, Floatzel Sitrus 53, Weavile Sitrus 54. Start levels sum 317 vs 322 on `main`, so the branch team starts
  lower. This is why the equal-levels comparison (T016) is the acceptance test, not the clear rates at each team's
  own levels.
- Booster options in `state.json` stages: screen `expert_belt` 46 / `wise_glasses` 23 mentions, prune 24 / 8,
  level_search 1 / 0. The new items were tried, and one was chosen.

## T015 Equal-levels script and pairing control

- Scratchpad `equal_levels.py` (written fresh; research R5): both `result.json` teams set to the branch team's
  start levels, validated with `load_and_validate`, played with `run_full_gauntlets` on one pool, master
  `014-equal|B2`, `expectimax2-v2`; `mcnemar_exact(branch, main)`; mean final level via `final_level_stats`.
- **Control** (`--self`: `main`'s team against itself, 200 runs, `runs/014-evidence/equal-levels-control.txt`):
  `n 200: A 0.9200 vs B 0.9200, only 0/0, p 1, verdict indistinguishable`; mean final levels equal (54.224); exit 0,
  149.1 s. Same seeds give the same outcomes, so the pairing works.

## T016 Equal-levels comparison (2,000 paired; FR-009, SC-004)

- 1:37:53 to 2:00:26 PM EDT, exit 0, wall 1313.9 s (`runs/014-evidence/equal-levels.txt`). `main`'s team was legal
  at the branch levels (validation raised nothing).
```
levels [51, 53, 53, 53, 53, 54]; A items ['earth_plate', 'sitrus_berry', 'sitrus_berry', 'expert_belt', 'sitrus_berry', 'sitrus_berry']; B items ['sitrus_berry', 'sitrus_berry', 'sitrus_berry', 'zap_plate', 'sitrus_berry', 'sitrus_berry']
n 2000: A(branch) 0.8195 vs B(main) 0.7650, only 356/247, p 1.037e-05, verdict A
mean final level (cleared runs): A 53.34289200732154 vs B 53.39520697167756
```
- **Pass.** The branch team clears significantly more at equal levels (verdict A, branch better), and its mean final
  level is not higher (53.34 vs 53.40).
- What differs between the two teams: Garchomp Sitrus → Earth Plate (same moves), and Rotom Zap Plate → Expert Belt
  with Ominous Wind / Shock Wave → Dark Pulse / Charge Beam. The other four members are identical. The gain is
  therefore not attributed to Expert Belt alone.

## T017 Untouched paths (FR-007)

- `git diff --stat main -- sim src/platsim/availability src/platsim/legality src/platsim/explain.py src/platsim/decomp`:
  empty, exit 0. Control: `git diff --stat main -- src tests` lists `candidates.py` (+11) and
  `test_optimizer_candidates.py` (+89).

## T018 Gates (code `0938314` = `681daa9` + docs)

- 2:00:59 to 2:15:44 PM EDT; logs `runs/014-evidence/t018-pytest.log`, `t018-node.log`, `t018.time`.
- `uv run pytest -q -m "not battle_sim"`: `525 passed, 26 deselected, 4 xfailed, 1 warning in 608.05s`, exit 0.
  On `main`: 516 passed. +9 = the new tests in `test_optimizer_candidates.py` (8 booster tests + 1 report-source test).
- `(cd sim && node --test test/*.test.mjs)`: `# tests 314`, `# pass 314`, `# fail 0`, exit 0. SC-006.
- No commit was made while the suites ran.

## T019 Docs

- `FUTURE-FEATURES.md` (H3 status; later groups renamed H4+) and `RUN-STATE.md` updated.
