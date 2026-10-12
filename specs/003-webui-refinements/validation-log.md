# Validation log: 003 Web UI refinements

All output below is real and pasted from the runs. Paths are relative to the repo root.

## T001 Baseline (2026-10-11)

- Commit: `3f286652410a3af86c0b27c4df255706f7155b9a` on `002-webui-redesign`.
- `uv run pytest -q tests/integration/test_web*.py`:
```
22 passed, 1 warning in 170.03s (0:02:50)
```
- `uv run pytest -q -m browser tests/browser/`:
```
4 passed in 49.30s
```
- Report hashes: `specs/003-webui-refinements/baseline/t001-sha256.txt` (12 files). Checked again in T042a and T060.
- Snapshot in `specs/003-webui-refinements/baseline/t001-baseline.json`, written by a scratch script (`baseline.py`) that reads the live code:
  - `job_fingerprint` of the `test_optimize_small.py` request (quick, seed t058):
    `{"species": ["SPECIES_INFERNAPE", "SPECIES_STARAPTOR", "SPECIES_LUXRAY", "SPECIES_GARCHOMP", "SPECIES_GYARADOS", "SPECIES_GARDEVOIR"], "min_clear": 0.75, "seed": "t058", "budget": "quick", "legality_options": {"allow_egg_moves": false, "allow_trade_evolutions": false}, "state_version": 3}`
  - `member_floor` for the six `runs/final-defaults` builds (variant own, the recorded moves and item):
    `{'infernape': 41, 'staraptor': 49, 'luxray': 42, 'garchomp': 48, 'gyarados': 35, 'gardevoir': 30}`
  - available pokemon under default options: 186 (493 − 307 unavailable, matching the research count).

## T002 Finished runs (2026-10-11)

A run is finished when `state.json` has `stages.report`.
```
runs/final-defaults/state.json	finished	job.json status=-
runs/job-20261008T115114Z-feb186/state.json	finished	job.json status=done
runs/job-20261008T235244Z-2d8f18/state.json	finished	job.json status=done
runs/job-20261009T193750Z-a1822a/state.json	UNFINISHED	job.json status=cancelled
runs/job-20261009T193751Z-1fdb5e/state.json	finished	job.json status=done
runs/optimize-36cef906f4d5/state.json	finished	job.json status=-
runs/optimize-smoke-quick/state.json	finished	job.json status=-
```
- The only unfinished run is the cancelled 002 throwaway. It can't be resumed, and T002 expects it. RUN-STATE's earlier "all finished" line was wrong about this one run.
- Positive control (a copy of `final-defaults/state.json` with `stages.report` removed): `UNFINISHED`.

## T002a Constitution

`.specify/memory/constitution.md` footer: `**Version**: 1.2.0 | **Ratified**: 2026-10-07 | **Last Amended**: 2026-10-11`. Principle III has the explicit-rule bullet.

## Phase 2 checkpoint (T003–T005, 2026-10-11)

- `web/display_text.clean()` added, with `tests/unit/test_display_text.py`. One recorded phrase is reworded rather than cut: "it does not meet SC-003" becomes "it does not meet the confidence target".
- The catalogue now computes availability per options value (LRU of 16). `SpeciesInfo` keeps its default-options status, so hand-made test catalogues still work.
- The first run failed 8 web tests: the job-options dict also holds min_clear, seed and budget, which `from_dict` rejected. Fixed with `app._legality()`.
- `uv run pytest -q tests/unit/test_display_text.py tests/unit/test_legality_options.py tests/integration/test_web.py`:
```
42 passed, 1 warning in 42.93s
```

## US1 checkpoint (T006–T013, 2026-10-11)

- Fail-first: before the server and page changes, the new and updated tests in `test_web.py` gave `6 failed, 8 passed`.
- Found along the way:
  - **Nidoran**: "Nidoran♂" and "Nidoran♀" normalised to the same name, so a full-name search didn't put the right one first. `_norm` now maps ♂ → m and ♀ → f.
  - **Exact match first**: a search now puts the exact name or key match first, so "Mew" comes before "Mewtwo" (SC-002).
  - **Dragon Scale**: the trade-evolution reason now names the item ("Dragon Scale") instead of `ITEM_DRAGON_SCALE`.
  - **"Unavailable in Platinum"** is used only when no other reason applies. Gengar keeps its trade-evolution reason.
- `uv run pytest -q tests/integration/test_web*.py tests/unit/test_display_text.py tests/unit/test_legality_options.py`:
```
56 passed, 1 warning in 172.80s (0:02:52)
```
- `uv run pytest -q -m browser tests/browser/`, which adds the wording scan with its planted-node positive control, the Golem / "zzzz" search and the trade tooltip:
```
4 passed in 49.64s
```
- Screenshot (scratchpad `us1-golem.png`, real catalogue): Golem crossed out with "Evolves from Graveler by trade (needs a second cartridge; allowed with the trade-evolutions rule)"; no show-excluded control; "Allow trade evolutions" has a dotted underline.

## US2 checkpoint (T014–T031, 2026-10-11)

- **T015 fail-before / pass-after** (research R2):
  - Before T019: `AssertionError: SPECIES_AERODACTYL has post-game sources once they are allowed`, `assert []`. The ledger build's `_counts` fills the shared `species_sources` cache with default-option answers, so the post-game view read them.
  - After keying `species_sources` and `breed_mothers` on options: `1 passed`.
- **T022 "can never be entered"**: the plain graph rule didn't work.
  - With uncertain edges opened, the unused Eterna condominium 4F counts as reachable (its collision warp opens).
  - Real post-game areas the graph can't model, such as Turnback Cave's pillar rooms and the Battle Tower rooms, come out unreachable.
  - Rule used instead: a map the decomp names `MAP_HEADER_UNUSED_*` that strict post-game reachability can't reach (`ledger.UNUSED_MAP_PREFIX`). This catches the TM04, Focus Band, Hard Stone and Razor Fang entries and the unused Resort Area mart, and leaves Turnback Cave as ordinary post-game.
- **T025 Battle Frontier exchange**: `ScrCmd_PokeMartFrontier` gives 15 TMs (right counter) and 26 items (left counter). That matches the 41 entries in `itemToBpPrice`.
  - Two parser bugs were fixed on the way: the first search hit the function prototype instead of its body, and `ITEM_END` inside `SHOP_ITEM_END` was being read as an item.
  - **Sweep of other unread shop and prize commands**: the decoration mart and seal mart don't give held items or TMs (out of scope); Mystery Gift is event-only (out of scope); the Amity Square gift man gives berries and accessories (not read, which is unchanged from 001; out of scope for 003).
- **T027 holders** come from the decomp: `item_holders("ITEM_LEFTOVERS")` = {Munchlax, Snorlax} (data.json held_items).
- **T030 regenerated data** (`uv run platsim extract`, then `--check`: up to date):
```
entries_by_phase {'post_game': 2104, 'pre_champion': 2953, 'unobtainable': 1797} -> {'post_game': 2186, 'pre_champion': 2995, 'unobtainable': 1755}
species_pre_champion 180 -> 182
tms_unavailable unchanged (TM04, TM08, TM37, TM42, TM50, TM53, TM61, TM73)
held_items_unavailable_count 56 -> 55; unlimited added ['ITEM_LEFTOVERS']; finite unchanged
unreachable 64, frontier 82
```
  Every change is explained:
  - 42 Munchlax entries moved from unobtainable to pre-Champion (21 honey-tree slots and 21 held Leftovers);
  - 82 frontier entries were added (41 items × the Battle Frontier and the unused Battle Park corner, which is `unreachable`);
  - Munchlax and Snorlax became species sources.
- **Browser fix**: the trade-evolution tooltip, while shown, covered the next rule's checkbox and blocked clicks on it. It now has `pointer-events: none`.
- `uv run pytest -q tests/unit tests/integration/test_availability_controls.py tests/integration/test_web.py tests/integration/test_explain.py` (with story_rank deselected): `1 failed, 349 passed`. The failure was a test assumption: a breed option sorts before Caterpie's dual-slot wild option. After fixing the test, `tests/unit/test_validator.py`: `40 passed`.
- `uv run pytest -q tests/integration/test_extract.py tests/integration/test_web*.py`: `28 passed, 1 warning in 517.83s`.
- `uv run pytest -q -m browser tests/browser/`: `4 passed in 56.71s`. The wording scan now covers 2^5 rule combinations.

## Story rank (T033, T038, T039; built by a background agent, 2026-10-11)

- **Code**: new `availability/story_rank.py` and `tests/unit/test_story_rank.py`. `extract.py` writes `data/generated/story_rank.json`, which the manifest and `--check` cover.
- `uv run pytest tests/unit/test_story_rank.py tests/unit/test_mapgraph.py -q -rx`: `31 passed, 4 xfailed`.
- **Build time**: graph 33.2 s (shared with the ledger), step 2 4.8 s, step 1 1.7 s; about 38.7 s cold, under the 60 s target. At runtime `rank()` only reads the file.
- **Expected values that hold**: Route 201 = 0, Route 209 = 3, Canalave City = 5, Route 220 = 5, Victory Road 1F = 8. Each gym map ranks below its badge, and the gym order from leader levels is Coal, Forest, Relic, Cobble, Fen, Mine, Icicle, Beacon.
- **Four research expectations the decomp contradicts**, kept as `xfail(strict=True)` with the evidence, not edited to pass:
  - **Ravaged Path = 0**: 36 cave tiles inside its south entrance come before the first Rock Smash rock.
  - **Route 218 = 0**: its Jubilife side is 124 land and bridge tiles before the sea. Its grass is on the Canalave side, which is rank 5.
  - **Step-1 Route 209 = 1, not 2**: the Bicycle counts as soon as the Cycle Shop is reached. In the game its giver appears only through a story-variable chain this model doesn't cover.
  - **Gym first-reachable order [0,1,1,3,3,5,6,3]**: Sunyshore is rank 3 because the Valor Lakefront blackout is a story-variable gate (a gap listed in R9).
- **Added beyond R9** (each from the decomp): blockers standing on warp tiles; the Bicycle (slopes, ramps and the Cycling Road gate events); ledges as one-way jumps; the Wayward Cave hidden entrance (an `object_blocks_warp` edge opened); item balls counted as key sources.
- **Open design point**: ranks are per map. A map with an early walkable edge (Route 218, Ravaged Path) ranks early even when its encounter area is later. Ranking per encounter area is the user's call.

## US3 (T032, T034–T037, T040–T043a, 2026-10-11)

- **Rates (T037)** are parsed from the decomp roll chains:
  - grass `[20,20,10,10,10,10,5,5,4,4,1,1]`, surf and Old Rod `[60,30,5,4,1]`, Good and Super Rod `[40,40,15,4,1]`;
  - honey slots `[40,20,20,10,5,5]`;
  - honey groups, best over tree types: common 70, uncommon 70, rare 1. A Munchlax tree rolls A 20 and B 70; a normal tree rolls A 70 and B 20. My first test expectation (uncommon 20) was a misreading, corrected against `GetTreeEncounterGroup`.
  - Gabite on Victory Road 1F sums to 5% (4 + 1). Munchlax is 1%.
- **Text (T036)**: `tests/unit/test_source_text.py` gives `8 passed`. The leak scan covers every option of every base-form pokemon under all 16 rule combinations; its positive control is that the 002 text is caught.
- **Selection order (T040)**: `tests/unit/test_source_preference.py` gives `15 passed`:
  - Garchomp is named from Gible in Wayward Cave B1F;
  - 1%-only locations come last;
  - `member_floor` for the six final-defaults builds equals T001 (41/49/42/48/35/30);
  - Combee is named from the honey tree and its floor stays 1.
  - **Intended change**: the two 001 tests that expected the species itself first (Staravia from Route 209) now expect the earliest catch, which is Starly from Route 201. That follows the user decision on 2026-10-11.
- **New report warnings (T041)** carry no ids. `test_display_text` now uses the recorded pre-003 wording as its positive control.
- **Re-render of the fixture (T042)**: `platsim report --rerender tests/fixtures/web_final_defaults --out $SCRATCH/rr` exited 0, with battle numbers and moves unchanged. The `obtained_from` text, old → new:
```
Gift - Route 201 (Chimchar, starter choice (one of three)) -> Monferno (EVO_LEVEL) -> Infernape (EVO_LEVEL)
  -> Gift - Route 201 (Chimchar, starter) -> Monferno at level 14 -> Infernape at level 36
Wild - Route 209 (Staravia, grass) -> Staraptor (EVO_LEVEL)
  -> Wild - Route 201 (Starly, grass) -> Staravia at level 14 -> Staraptor at level 34
Wild - Route 222 (Luxio, grass) -> Luxray (EVO_LEVEL)
  -> Wild - Route 202 (Shinx, grass) -> Luxio at level 15 -> Luxray at level 30
Wild - Victory Road 1F (Gabite, grass) -> Garchomp (EVO_LEVEL)
  -> Wild - Wayward Cave B1F (Gible, grass) -> Gabite at level 24 -> Garchomp at level 48
Wild - Canalave City (Magikarp, old_rod) -> Gyarados (EVO_LEVEL)
  -> Wild - Twinleaf Town (Magikarp, Old Rod) -> Gyarados at level 20
Wild - Route 212 North (Kirlia, grass) -> Gardevoir (EVO_LEVEL)
  -> Wild - Route 208 (Ralts, grass) -> Kirlia at level 20 -> Gardevoir at level 30
```
- **Stored web runs (T042a)**:
  - Each new run keeps its original's timestamp with the id suffix sha256(orig + ":r003")[:6]. **Deviation from the task wording**: these are normal job ids, not `<id>-r003` folders, so the picker and routes need no change. The label ends in "(re-rendered)".
  - Runs: `job-20261008T115114Z-feb186 -> job-20261008T115114Z-75665e`, `job-20261008T235244Z-2d8f18 -> job-20261008T235244Z-c86e64`, `job-20261009T193751Z-1fdb5e -> job-20261009T193751Z-0c1874`. The cancelled `a1822a` was skipped.
  - None of the new `obtained_from` texts contains an internal code.
  - `sha256sum -c baseline/t001-sha256.txt`: all 12 OK, so the originals are untouched.
  - A test in `test_web.py` (`test_rerendered_run_is_listed_and_labelled`) covers this and passes.
- **US3 checkpoint**: `uv run pytest -q tests/unit tests/integration/test_availability_controls.py tests/integration/test_web*.py tests/integration/test_explain.py tests/integration/test_extract.py`:
```
400 passed, 4 xfailed, 1 warning in 599.85s (0:09:59)
```
  `uv run pytest -q -m browser tests/browser/`: `4 passed in 58.34s`.

## US4 checkpoint (T044–T048, 2026-10-11)

- `uv run pytest -q tests/integration/test_web_sprites.py`: `2 passed`.
  - `/api/league` parties are checked against `load_league()`.
  - Every trainer sprite is a 160×80 PNG with tRNS.
  - The roark, `..%2F` and upper-case requests all give 404.
- `PLATSIM_SCREENSHOT_DIR=$SCRATCH/shots uv run pytest -q -m browser tests/browser/`: `4 passed in 60.03s`.
  - For all five bars, hover opens `#trainer-pop` with 1 + party-size loaded images and 6 − party-size empty cells. The header carries the rate, the interval and the battle count. Escape closes it, and its box stays inside 1920×1080.
  - Tab focus opens it as well.
  - A tap in a 360 px touch context opens it, inside the viewport, with 7 images for Cynthia.
- The pop-up screenshots for all five trainers were checked by eye: the trainer sprite is on the left, the team is in a 3×2 grid in party order, and the Elite Four's sixth cell is an empty dashed box. This closes R10's "only Cynthia's frame checked".

## US5 checkpoint (T049–T056, 2026-10-11)

- **Colours**: `tests/unit/test_type_colours.py` (17 types; the type names are checked against the decomp move data) and `tests/integration/test_web_result_view.py` pass: `8 passed`, then `4 passed` once the move `type` was added (T049 failed first with `KeyError: 'type'`).
  - The type colours were generated from the usual type hues by darkening (light theme) or lightening (dark theme) until each reaches at least 4.6:1 against `--surface`. Lowest: normal 4.64 on light, ghost 4.61 on dark.
- **Browser**: `PLATSIM_SCREENSHOT_DIR=$SCRATCH/shots uv run pytest -q -m browser tests/browser/`: `4 passed in 60.92s`.
  - Results order (DOM and position): summary, team cards, chart, downloads.
  - All 24 move chips have `data-type`, a computed colour equal to their `--type-*`, and a tooltip starting with "<Type> · ".
  - The theme toggle is in the top-right quadrant of the header. A click flips `data-theme` and `aria-pressed`, the choice survives a reload, and with no stored choice the page follows the system setting under both `emulate_media` schemes.
- **Fixed along the way**: with the chart now below the cards, hovering a bar scrolls the page, and the pop-up's scroll-to-close handler hid it at once. The pop-up is now positioned inside the chart (`position: absolute`), and the scroll handler is gone.
- **Screenshots** (light, dark, 360 px, scratchpad) checked by eye: the toggle is top right, the roster comes before the chart, the type colours are readable in both themes, and nothing scrolls sideways at 360 px. The fixture card still shows its recorded "EVO_LEVEL" text, as FR-018 intends: old runs are not rewritten, and the re-rendered copies carry the new text.

## T058 / T059: full suite (2026-10-11)

Started 2026-10-11T19:56:50Z and ended 22:20:13Z. Local CPU only, nothing paid.

`uv run pytest -q -m "not browser"`:
```
FAILED tests/integration/test_evaluate.py::test_determinism_fast - AssertionE...
1 failed, 448 passed, 4 deselected, 4 xfailed, 1 warning in 8540.63s (2:22:20)
exit=1
```
The failure was an outdated assertion, not a defect. The test expected
`provenance.legality_options` to have the two pre-003 keys. The report now records all five,
as FR-012 requires:
```
E         Left contains 3 more items:
E         {'allow_post_game_items': False,
E          'allow_post_game_pokemon': False,
E          'allow_unobtainable_pokemon': False}
```
The assertion now builds the expected dict from the `LegalityOptions` fields (all False) and checks
that it has 5 keys. Rerun with `uv run pytest -q tests/integration/test_evaluate.py::test_determinism_fast`:
`1 passed in 189.82s (0:03:09)`, so with this fix the "not browser" set is 449 passed, 4 xfailed.

`grep -rn '"allow_trade_evolutions": False}' tests/` found three other two-key dicts, all in
`tests/unit/test_legality_options.py`. Each is intentional: two check the compact fingerprint form,
and one is a report written before 003. All three passed in this run.

`uv run pytest -q -m browser tests/browser/`: `4 passed in 57.60s`, exit 0.

The 4 xfails are the strict story-rank controls from US3 (Ravaged Path 0, Route 218 0, step-1
Route 209 = 1, gym order), each with decomp evidence in `tests/unit/test_story_rank.py`.

T058 (web and browser suites) is covered by this run: every `tests/integration/test_web*.py` test
and all 4 browser tests passed.

### Coverage table (FR/SC → check)

| Item | Checked by | Result |
|------|-----------|--------|
| FR-001 no requirement ids | `test_page.py::test_page_walkthrough` wording scan (32 rule combinations, every page state); `test_display_text.py`; `test_web.py::test_loading_and_error_texts_say_pokemon` | pass |
| FR-002 no "species" | same wording scan; `test_web.py::test_reasons_are_plain_and_excluded_pokemon_always_listed`, `test_loading_and_error_texts_say_pokemon` | pass |
| FR-003 excluded always listed | `test_web.py::test_reasons_are_plain_and_excluded_pokemon_always_listed`; walkthrough Golem search | pass |
| FR-004 "no match" only when no name matches | walkthrough "zzzz" and Golem searches | pass |
| FR-005 "Unavailable in Platinum" | `test_web.py::test_reasons_are_plain_and_excluded_pokemon_always_listed` | pass |
| FR-006 other reasons plain | same test; `test_validator.py::test_trade_evo_reason_names_trade` | pass |
| FR-007 trade tooltip | walkthrough (hover and focus show `#trade-help`) | pass |
| FR-008 Munchlax and Snorlax usable | `test_availability_controls.py::test_munchlax_and_snorlax_allowed_leftovers_from_munchlax`, `test_default_rules_usable_set_is_t001_plus_munchlax_and_snorlax` | pass |
| FR-009 Leftovers team rule | `test_validator.py::test_leftovers_needs_munchlax_or_snorlax`, `test_leftovers_with_post_game_items_is_one_copy`; `test_optimizer_candidates.py::test_member_candidates_and_full_team_validate` | pass |
| FR-010 post-game pokemon rule | `test_validator.py::test_post_game_pokemon_rule`; `test_web.py::test_legality_options_page_search_and_jobs` | pass |
| FR-010a post-game items and moves rule | `test_availability_controls.py::test_post_game_items_and_unreachable_maps`, `test_frontier_exchange_items`; `test_validator.py::test_postgame_tutor_is_legal_with_post_game_items` | pass |
| FR-011 unobtainable rule | `test_validator.py::test_unobtainable_pokemon_rule`; synthetic outside-Platinum source tests | pass |
| FR-012 rules recorded and shown | `test_evaluate.py::test_determinism_fast` (five keys, after the fix); `test_web.py::test_legality_options_page_search_and_jobs`; T060 real job (below) | pass (T060 confirmed) |
| FR-013 list updates on rule change | walkthrough (toggle each rule, crossed-out state changes without reload) | pass |
| FR-014 evolution level and item named | `test_source_text.py::test_starter_and_level_evolutions`, `test_held_item_evolution_names_item_and_time`, `test_other_evolution_methods` | pass |
| FR-015 "(name, starter)" | `test_source_text.py::test_starter_and_level_evolutions` | pass |
| FR-016 static with no parenthetical | `test_source_text.py::test_static_encounter_has_no_parenthetical` | pass |
| FR-017 earliest location, 1% rule | `test_source_preference.py::test_garchomp_is_named_from_gible_in_wayward_cave`, `test_one_percent_only_location_is_skipped_unless_it_is_the_only_one`, `test_earliest_catch_beats_breeding_across_stages`; `test_story_rank.py` | pass (4 strict xfails documented) |
| FR-018 text at the source, reports too | `test_source_text.py::test_no_internal_code_in_any_source_text` (all 16 rule combinations); re-rendered runs (T042a) | pass |
| FR-019 results order | walkthrough (DOM order and position: summary, cards, chart, downloads) | pass |
| FR-020 trainer pop-up | walkthrough (hover, focus, touch tap, Escape, all five trainers) | pass |
| FR-021 local sprites | `test_web_sprites.py::test_trainer_sprites_and_league`, `test_sprites` | pass |
| FR-022 move type colours | `test_type_colours.py` (contrast ≥ 4.6:1); `test_web_result_view.py::test_moves_carry_their_type`; walkthrough chip colours | pass |
| FR-023 theme toggle | walkthrough (top right, click flips, survives reload, follows system with nothing stored) | pass |
| FR-024 002 behaviour kept | the whole 002 suite in this run (449 passed with the fix); browser `test_older_run_without_per_trainer`, `test_finish_is_announced_and_shown`, `test_no_runs_yet` | pass |
| SC-001 wording scan | walkthrough scan | pass |
| SC-002 full-name search | `test_web.py::test_full_name_search_returns_that_pokemon_first` | pass |
| SC-003 each pokemon rule unblocks its pokemon | `test_web.py::test_legality_options_page_search_and_jobs`; `test_validator.py` rule tests | pass |
| SC-003a post-game item or move becomes legal | `test_validator.py::test_postgame_tutor_is_legal_with_post_game_items`; `test_availability_controls.py::test_frontier_exchange_items` | pass |
| SC-004 Leftovers test set | `test_validator.py::test_leftovers_needs_munchlax_or_snorlax`, `test_leftovers_with_post_game_items_is_one_copy` | pass |
| SC-005 no internal codes in "obtained from" | `test_source_text.py::test_no_internal_code_in_any_source_text`; re-rendered runs; T060 new run | pass |
| SC-006 pop-up sprites for all five trainers | walkthrough plus screenshots checked by eye (US4) | pass |
| SC-007 theme kept after reload | walkthrough | pass |

## T060: web vs command line (quickstart V7, 2026-10-11)

Request: infernape staraptor luxray garchomp gyarados gardevoir, `quick`, seed `t058`, min clear 75%,
all rules off. Local CPU only, nothing paid.

- Web: `uv run platsim serve --port 8765`, POST `/api/jobs`. Job `job-20261011T222457Z-c4aa1b` ran
  from 22:24:57Z to 22:57:23Z and finished `done`. The server exited 0 on SIGINT.
- CLI: `uv run platsim optimize ... --budget quick --seed t058 --out <scratchpad>/cli-t058-003` ran
  from 22:57:24Z to 23:29:20Z and exited 0.

```
cmp runs/job-20261011T222457Z-c4aa1b/result.json <scratchpad>/cli-t058-003/result.json   -> exit 0
b665cfa91b5bca1ce0ad1fd6b937582f041bd1f1b103d54617627dd66ba3d617  runs/job-20261011T222457Z-c4aa1b/result.json
b665cfa91b5bca1ce0ad1fd6b937582f041bd1f1b103d54617627dd66ba3d617  <scratchpad>/cli-t058-003/result.json
legality_options: {'allow_egg_moves': False, 'allow_trade_evolutions': False, 'allow_post_game_pokemon': False, 'allow_post_game_items': False, 'allow_unobtainable_pokemon': False} n_keys: 5
platsim_version (job.json): 0.2.0
sha256sum -c baseline/t001-sha256.txt -> all 12 OK, exit 0
```

- The web report is byte-identical to the CLI report. The hash is not the empty-file hash (`e3b0c442…`).
- The report records all five rule keys, and the job is recorded as platsim 0.2.0.
- The pre-existing runs and the fixture are unchanged since T001.
- This closes the FR-012 and SC-005 "new run" checks.

## User follow-up after testing (2026-10-11)

Two changes requested after hands-on testing.

1. **"Pokémon" spelling** (FR-002 amended).
   - Page text in `index.html` and `app.js`, plus the server messages in `species_catalog.py` and
     `app.py`, now say "Pokémon".
   - `display_text.clean()` turns "species" or an unaccented "pokemon" in passed-through text into
     "Pokémon". Identifiers (`allow_post_game_pokemon`, `pokemon-showdown/`, `res/pokemon/`) are left
     alone, and `test_display_text.py` tests each of these.
   - The browser wording scan now also rejects an unaccented "pokemon". It has a positive control
     that plants "Choose pokemon" and expects the scan to fail, and it checks that the accented word
     is actually read.
2. **Trainer hover showed two boxes**. Each bar's SVG `<title>` made the browser draw its own native
   tooltip next to the pop-up. The `<title>` is removed; the bar's `aria-label` still gives
   screen readers the same text.
   - The walkthrough now asserts, for each of the five trainers, that `#chart-tip` is hidden while
     the pop-up is open and that the chart has no `<title>`.
   - Positive control: with the `<title>` line put back, `test_page_walkthrough` failed at
     `assert page.locator("#chart-body svg title").count() == 0` (`1 failed in 36.50s`). It was then
     restored.

Results:
- `uv run pytest -q tests/unit/test_display_text.py tests/integration/test_web.py tests/integration/test_web_result_view.py tests/integration/test_web_sprites.py`:
  `35 passed`.
- `uv run pytest -q -m browser tests/browser/`: `4 passed in 58.91s`.
- The light-theme screenshot was checked by eye: "Pokémon" renders correctly.
- After restarting `platsim serve`, the live server answers with "some Pokémon cannot be used: …
  unknown Pokémon".
- The full non-browser suite was not rerun for these changes. They touch only `web/` text, and its
  tests are the ones listed above.
