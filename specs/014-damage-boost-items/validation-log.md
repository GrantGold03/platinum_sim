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
