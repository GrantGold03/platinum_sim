---
description: "Task list for 003 Web UI Refinements"
---

# Tasks: Web UI Refinements

**Input**: the design documents in `specs/003-webui-refinements/`: plan.md, spec.md, research.md
(R1–R14), data-model.md, contracts/http-api.md, contracts/ui.md and quickstart.md (V1–V8). The
source list is `webui_changes.md` at the repo root.

**Tests**: included. The constitution requires a green local suite and positive controls (Principle V).
The spec's success criteria SC-001 to SC-007 are automated checks.

**Format**: `[ID] [P?] [Story] Description`. `[P]` means the task can run in parallel, because it
touches different files and has no unfinished dependency.

## Ground rules for every task

- **Branch**: work on `002-webui-redesign` (the user's choice). Don't create a branch. Don't merge
  without the user's go-ahead.
- **Scope**:
  - Don't edit `sim/`, because `sim_code_hash` must not change.
  - Don't modify any existing file under `runs/`.
  - Old report files are read, never rewritten.
- **Decomp is ground truth**: every rate, level, badge, obstacle, party and gym-order fact is parsed
  from `pokeplatinum/` with a cited path. Hand-typed game data is forbidden. Type colours are styling,
  not game data.
- **Generated data**: after any change to `availability/` output, run `uv run platsim extract` and
  then `uv run platsim extract --check`. `data/generated/` and `runs/` are git-ignored, so they are
  rebuilt locally, never committed.
- **Recording results**: paste the real test output for each checkpoint into
  `specs/003-webui-refinements/validation-log.md` (created in T001).
- **Temp files** go in the session scratchpad (`$SCRATCH`), never `/tmp` or the repo.
- **Existing helpers**: reuse the session `ledger` and `catalog` fixtures (`tests/conftest.py`), and
  `StubRunner`, `copy_fixture_run` and `make_app` (`tests/integration/_web_helpers.py`).
- **Wording**: any text a task adds to the page uses "pokemon" and never a requirement id.

## Path conventions

- Server: `src/platsim/web/`. Page: `src/platsim/web/static/`.
- Rules and data: `src/platsim/legality/`, `src/platsim/availability/`, `src/platsim/optimizer/`.
- Tests: `tests/unit/`, `tests/integration/`, `tests/browser/`.

---

## Phase 1: Setup

- [X] T001 Create `specs/003-webui-refinements/validation-log.md` and record the baseline in it:
  - `git rev-parse HEAD`;
  - the output of `uv run pytest -q tests/integration/test_web*.py`;
  - the output of `uv run pytest -q -m browser tests/browser/`;
  - `sha256sum runs/*/result.json tests/fixtures/web_final_defaults/*`, which the "old reports
    untouched" checks (T042a, V7) compare against later;
  - `job_fingerprint` of the default `tests/integration/test_optimize_small.py` request (T014);
  - `_floor_cached` for the six reference species (T035);
  - the sorted list of available pokemon keys under default options (T016).
- [X] T002 Confirm that every `runs/*/state.json` is finished before the first `src/platsim` edit
  (research R14). Every edit changes `platsim_code_hash`, which blocks resuming an unfinished run.
  - A run is finished when its `state.json` has `stages.report` (`src/platsim/optimizer/run.py:277`,
    `:673`, `:704`). Paste the per-run list into `validation-log.md`.
  - **Positive control**: the same check reports "unfinished" on a scratch copy with
    `stages.report` removed.
  - An unfinished run whose `job.json` status is `cancelled` is expected (e.g. the T035 throwaway in
    002) and can't be resumed anyway; list it and continue. Any other unfinished run: stop and ask
    the user.

- [X] T002a Check that `.specify/memory/constitution.md` is at v1.2.0, with the Principle III bullet
  on explicit, off-by-default rules (amended 2026-10-11, analysis C1). T026 depends on it. If the
  file is not at 1.2.0, stop.

---

## Phase 2: Foundational (blocks all stories)

- [X] T003 Create `src/platsim/web/display_text.py` with `clean(text: str | None) -> str | None`
  (research R6). It does three things:
  - removes requirement references: `FR-\d+[a-z]?`, `SC-\d+` and `research\.md R\d+`, together with
    any parentheses around them. Also remove an empty "()" or a trailing "; " left behind, and
    collapse doubled spaces;
  - replaces the whole word "species" with "pokemon", keeping the case ("Species" → "Pokemon",
    "SPECIES" → "POKEMON");
  - leaves None alone.
- [X] T004 [P] Write unit tests for `clean()` in `tests/unit/test_display_text.py`:
  - "statistically indistinguishable on paired runs (FR-019)" loses " (FR-019)";
  - the `QUICK_WARNING` text from `src/platsim/report/json_report.py:48-52` loses "(research.md R8)"
    and "SC-003";
  - "exactly 6 species are required" becomes "exactly 6 pokemon are required";
  - None stays None;
  - text with nothing to clean is returned unchanged;
  - **Positive control**: the input that holds every pattern changes.
- [X] T005 Restructure the catalogue into per-options availability tables in
  `src/platsim/web/species_catalog.py` (research R13; data-model "Species availability"):
  - `SpeciesInfo` keeps the static fields only: key, const, name, types, dex.
  - Add `SpeciesCatalog.availability(options: LegalityOptions)`. It returns a
    `{key: {available, reason, reason_code, note?}}` map, built on first use from
    `ledger.with_options(options)` with the existing `why()` / `why_trade()` logic, and cached in an
    LRU of 16 entries keyed by `options`.
  - `search`, `resolve_team` and `to_json` take `options: LegalityOptions` instead of
    `allow_trade_evolutions`.
  - Update the callers in `src/platsim/web/app.py:437-452`.
  - The behaviour must stay identical for today's two options. The current
    `tests/unit/test_legality_options.py::test_catalog_reflects_trade_option` and
    `tests/integration/test_web.py` must still pass, with only call-signature edits.

**Checkpoint**: `uv run pytest -q tests/unit/test_display_text.py tests/unit/test_legality_options.py tests/integration/test_web.py`
passes. Record the output.

---

## Phase 3: User Story 1 – Understand why a pokemon can or cannot be used (P1) 🎯 MVP

**Goal**: every search shows the matching pokemon, usable or crossed out, with a short plain reason.
The page never shows "species" or a requirement id.

**Independent test**: search Golem with trade evolutions off and on, and run the wording scan (V1, V2).

### Tests for User Story 1

- [X] T006 [P] [US1] Update `tests/integration/test_web.py`:
  - remove the `id="show-excluded"` assertion (`:31`);
  - `/api/species?q=golem` returns Golem with `available: false`, a reason containing "Graveler"
    and "trade", and `available: true` with `trade_evolutions=1`;
  - a pokemon with only dual-slot entries (Caterpie) and one with no entry (Bulbasaur) both have
    `reason == "Unavailable in Platinum"` and `reason_code == "unavailable"`;
  - no reason for any of the 493 pokemon, under trade on and off, matches `\b(FR|SC)-\d+` or contains
    "species" (case-insensitive). **Positive control**: the regex matches "FR-005";
  - the 503 loading text and the 422 texts contain "pokemon" and not "species";
  - **Search sweep** (spec SC-002): for every pokemon in the catalogue and all 16 combinations of the
    four availability-changing rules, `catalog.search(full_name, options)` returns that pokemon
    first. Run it on the catalogue directly, not over HTTP. (It needs T020's options; until T020,
    run it for the trade option only.)
  - **Unreachable-only pokemon**: if any pokemon's entries are all `unreachable` (after T022), its
    reason is "Unavailable in Platinum". The test lists those pokemon, or asserts that none exist.
    This is the positive control for T022.
- [X] T007 [P] [US1] Extend `tests/browser/test_page.py`:
  - **Wording scan** (spec SC-001): in setup, for the query "a" under each of the 16 rule
    combinations (toggle the checkboxes and wait for the search response; until T029 adds the new
    checkboxes, only the existing ones), after a 422 error, and for every fixture run shown, collect `document.body.innerText` plus every `title`, `aria-label`,
    `placeholder` and `.tip` text. Assert there is no match for `\b(FR|SC)-\d+` and none for
    `species` (case-insensitive). **Positive control**: inject a hidden-then-shown node with
    "species FR-001", check that the scan catches it, then remove it.
  - Replace the show-excluded steps (`:214-219`) with: searching "golem" shows a `li.excluded` with a
    disabled add button and a `.reason`; there is no `#show-excluded`; and "No pokemon match" appears
    only for "zzzz".
  - `#trade-help` is hidden until "Allow trade evolutions" is hovered or focused, then visible.

### Implementation for User Story 1

- [X] T008 [US1] Rewrite `REASON_TEXT` in `src/platsim/web/species_catalog.py:136-146` to match the
  data-model table:
  - `unobtainable` and `no_source` become `unavailable`, "Unavailable in Platinum";
  - no requirement ids anywhere;
  - `pre_evolution_unavailable` nests the cleaned reason;
  - the `note` (`:187`) says "Evolves by trade: needs a second cartridge for the trade".
  - Keep `excluded` until T024 removes it, but its text must be id-free now ("Excluded by project
    rule").
- [X] T009 [US1] Rewrite the server texts in `src/platsim/web/species_catalog.py` `resolve_team`
  (`:218-232`) and in `src/platsim/web/app.py:198-200, 399-400` to say "pokemon": "unknown pokemon",
  "exactly 6 pokemon are required…", "Pokemon data is loading…" and so on.
- [X] T010 [US1] Apply `display_text.clean()` to all passed-through text:
  - in `src/platsim/web/result_view.py`: `warnings` (`:68`), `obtained_from`, the move `source` and
    the ability text;
  - in `src/platsim/web/app.py`: `job.error`, the `invalid_reasons` values, and 422
    `detail`/`reasons` that come from the optimizer or validator.
- [X] T011 [US1] Update `src/platsim/web/static/index.html`:
  - change the wording at `:13`, `:21`, `:35` per `contracts/ui.md`;
  - delete the `#show-excluded` label and input (`:39-42`) and the requirement-id comments
    (`:18`, `:44`);
  - turn `#trade-help` (`:32-33`) into a tooltip of the "Allow trade evolutions" label, using the
    existing `.tip-wrap`/`.tip` pattern and keeping `aria-describedby`.
- [X] T012 [US1] Update `src/platsim/web/static/app.js`:
  - remove `#show-excluded` handling (`:12, :98, :129, :472`) and always send `excluded=1`;
  - change the texts at `:109`, `:125` ("No pokemon match “q”.") and `:197`;
  - change the `aria-label` for an unusable result (`:132`) to "<name>: not available, <reason>".
- [X] T013 [P] [US1] In `src/platsim/web/static/style.css`, add the tooltip styling for the
  trade-evolution note (reuse `.tip`), and remove the now-unused `#setup .rules p` rule (`:290`) if
  nothing else uses it.

**Checkpoint**: `uv run pytest -q tests/integration/test_web.py tests/unit/test_display_text.py` and
`uv run pytest -q -m browser tests/browser/` pass. Record the output, and save a screenshot of a Golem
search to `$SCRATCH`.

---

## Phase 4: User Story 2 – Choose which pokemon pools are allowed (P1)

**Goal**: three new opt-in rules; Munchlax and Snorlax are usable; the Leftovers team rule; the
validator enforces all of it.

**Independent test**: quickstart V3 and V4.

### Tests for User Story 2

- [X] T014 [P] [US2] Extend `tests/unit/test_legality_options.py`:
  - `LegalityOptions()` has five False fields;
  - `to_dict()` has all five keys;
  - `to_dict(compact=True)` leaves out the three new keys while they are False;
  - `from_dict` accepts the old two-key dicts and still rejects unknown keys;
  - `job_fingerprint` of a default request is unchanged from its value at T001's commit. Compute it
    in the test from a frozen literal recorded in T001;
  - the CLI flags `--allow-post-game-pokemon`, `--allow-post-game-items` and
    `--allow-unobtainable-pokemon` exist on `validate`, `evaluate` and `optimize`;
  - resuming with different new options is refused.
- [X] T015 [P] [US2] Add a cache test to `tests/unit/test_legality_options.py`: for one ledger,
  `species_sources(X)` and `breed_mothers(...)` under two option views that differ for X give
  different answers (research R2). Pick X from the ledger: a species whose only sources are POST.
  **This test must fail before T019.** Note the failing output in `validation-log.md`.
- [X] T016 [P] [US2] Extend `tests/integration/test_availability_controls.py`:
  - **Munchlax and Snorlax**:
    - `source_options(SPECIES_MUNCHLAX)` has a `wild_slot` option whose detail names the honey tree,
      with levels 5–15, as well as any breed option;
    - Snorlax is reachable through `EVO_LEVEL_HAPPINESS`;
    - `item_copies("ITEM_LEFTOVERS")` comes from the Munchlax wild-held entries;
    - replace `test_munchlax_excluded_and_leftovers_not_from_munchlax` and the
      `test_honey_tree_headers` assertion at `:360`.
  - **Unreachable**:
    - under post-game items, TM50, TM37, TM42, TM53 and the Victory Road 1F Room 2 Leftovers count;
    - entries on UNUSED_* maps have reason `unreachable` and never count under any rule.
  - **Frontier**:
    - `frontier_exchange` entries exist for TM04, TM08, TM61, TM73 and Focus Band, with phase POST
      and quantity unlimited;
    - under post-game items, TM04's copies are unlimited; under default rules, 0.
  - **Usable set**: with all rules off, the available set equals T001's set plus `munchlax` and
    `snorlax`, exactly.
  - **Default rules unchanged**: compared with T001, the pre-Champion item and TM counts change only
    where Munchlax's own entries are involved. List the diffs in the test as expected values.
  - Update `test_wild_held_item_counts` (`:467`) and `test_shared_flag_counts_summary` (`:569`) to the
    new values, each with a comment saying why it changed.
- [X] T017 [P] [US2] Extend `tests/unit/test_validator.py`, covering quickstart V4:
  - **`LEFTOVERS_NEEDS_MUNCHLAX`**:
    - Munchlax plus 5 others with Leftovers on 3 members is legal;
    - the same team without Munchlax and with Leftovers on 1 member gives `LEFTOVERS_NEEDS_MUNCHLAX`;
    - with post-game items on and no Munchlax, 1 Leftovers is legal and 2 are not;
    - Snorlax in place of Munchlax is legal.
  - **New rules**:
    - a `post_game` pokemon is `SPECIES_UNAVAILABLE` by default and legal with post-game pokemon on;
    - Bulbasaur is legal only with unobtainable pokemon on, and its source kind is `outside_platinum`
      at level 1;
    - `illegal_postgame_tutor.json` stays illegal by default and becomes legal with post-game items
      on.
- [X] T018 [P] [US2] Update `tests/integration/test_web.py`:
  - `POST /api/jobs` with Munchlax is accepted;
  - the three new keys are validated as booleans (non-boolean gives 422);
  - `job["options"]` has five keys;
  - `/api/species?post_game_pokemon=1` and `unobtainable_pokemon=1` flip a known pokemon;
  - the setup page has 5 unchecked rule checkboxes.

  Also update `tests/integration/test_explain.py::test_munchlax_excluded` to the new behaviour, and
  `tests/unit/test_optimizer_candidates.py::test_resolve_species_errors` (`:50-58`).

### Implementation for User Story 2

- [X] T019 [US2] Key `Ledger.species_sources` (`src/platsim/availability/ledger.py:138-145`) and
  `movesources.breed_mothers` (`src/platsim/legality/movesources.py:474`) on options. T015 must now
  pass.
- [X] T020 [US2] Add the three fields to `LegalityOptions` in `src/platsim/legality/models.py:56-94`,
  with `to_dict(compact=False)`. Use `to_dict(compact=True)` in `job_fingerprint`
  (`src/platsim/optimizer/run.py:85-87`).
- [X] T021 [US2] Generate the CLI flags from `LegalityOptions` fields in `src/platsim/cli.py:13-26`
  (`--allow-<field-with-dashes>`). Do the same for the web `_options()` key loop
  (`src/platsim/web/app.py:516-523`) and `run_one` (`:305-306`), so the next option needs no hand
  edits. Add the query params to `/api/species` (`app.py:437-443`).
- [X] T022 [US2] Add the post-game reachability pass to `src/platsim/availability/mapgraph.py`. It is
  a `reachable(allow_post_game=True)` mode that treats `post_game` edges as usable (`_usable`,
  `:1190-1199`). Then, in `src/platsim/availability/ledger.py` `_base_phase` (`:82-107`), give POST
  entries on maps unreachable even in that mode the reason `unreachable` (research R3). Add a unit
  test in `tests/unit/test_mapgraph.py`:
  - `MAP_HEADER_UNUSED_ETERNA_CITY_CONDOMINIUMS_4F` is unreachable;
  - Stark Mountain is reachable post-game;
  - Route 201 is reachable in both modes.
- [X] T023 [US2] Make `Ledger.pre(subject, kind)` (`src/platsim/availability/ledger.py:132-136`)
  option-aware, as research R2 specifies:
  - acquisition kinds: PRE, plus POST if `allow_post_game_pokemon`, plus NEVER(`other_cartridge`) if
    `allow_unobtainable_pokemon`;
  - item and tutor kinds: PRE, plus POST if `allow_post_game_items`;
  - `unreachable` is never admitted.

  Then check every reader listed in R2 for a phase test that bypasses `pre()`. For example,
  `movesources.py:534` and `:862`, and `validator.py:323, 332`. Route each through `pre()`.
- [X] T024 [US2] Remove the Munchlax rule and give honey trees their levels:
  - **Remove the rule**: set `EXCLUDED_SPECIES = frozenset()` and remove `EXCLUDED_SPECIES_REASON`
    use in `src/platsim/availability/ledger.py:183-218`. Remove its branches in
    `src/platsim/optimizer/candidates.py:205-242`, `src/platsim/explain.py:201-202, 391-399` and
    `species_catalog.py` (the `excluded` reason code).
  - **Honey levels**: parse the honey-tree level range from
    `pokeplatinum/src/overlay006/wild_encounters.c` near `:1200-1210`. The form is `5 + rand(11)`; use
    a regex on the expression and fail loudly if it doesn't match. Set it on the honey entries in
    `src/platsim/availability/sources.py:410-421`.
  - **Rare-tree text**: drop the C identifier ("honey tree, rare: only some trees, depending on
    Trainer ID").
- [X] T025 [US2] Add Battle Frontier exchange item sources in `src/platsim/availability/sources.py`,
  modelled on `game_corner_entries` (`:986-998`):
  - **Items**: parse both arrays in `ScrCmd_PokeMartFrontier` (`pokeplatinum/src/scrcmd.c:~6635`)
    and the BP prices in `src/overlay007/shop_menu.c:1340-1382`.
  - **Map**: the map(s) whose scripts call `PokeMartFrontier`.
  - **Entry**: kind `frontier_exchange`, quantity `UNLIMITED`, detail "<N> BP". Phase falls out of
    `_base_phase` as POST; check it.
  - Register the kind with the item kinds in `ledger.py`.
  - **Sweep**: grep `pokeplatinum/src` and `res/field/scripts` for other shop or prize commands that
    `sources.py` does not read (e.g. other `PokeMart*` variants, prize exchanges). List each one in
    `validation-log.md` as covered, added, or out of scope with a reason.
- [X] T026 [US2] Add the synthetic `outside_platinum` source for pokemon with no entry, in
  `src/platsim/legality/movesources.py` `_options` (`:356-434`), used only when
  `allow_unobtainable_pokemon` is on (research R4):
  - kind `outside_platinum`, level 1, quantity unlimited;
  - detail "Unavailable in Platinum (allowed by rule)";
  - add the kind to `ACQUIRE_LABELS` (`:107`) and to `OPTION_RANK`/`option_class` (`:753-762`),
    ranked last.
- [X] T027 [US2] Add the Leftovers team rule in `src/platsim/legality/validator.py`, after the member
  loop (`:297-360`). It uses code `LEFTOVERS_NEEDS_MUNCHLAX` (data-model "Team rule"):
  - with Munchlax or Snorlax on the team, Leftovers is unlimited;
  - otherwise the copies are only non-Munchlax-held sources, which means 0 by default and 1 with
    post-game items;
  - the message names the rule in plain words, with no requirement id.
- [X] T028 [US2] Let the optimizer use Leftovers:
  - `held_item_candidates` (`src/platsim/optimizer/candidates.py:421-438`) takes the team's species
    consts and adds `ITEM_LEFTOVERS` when the team has Munchlax or Snorlax, or when the non-Munchlax
    copies are above 0;
  - pass the team through from `member_candidates` (`:477`) and `resources.repair`
    (`src/platsim/optimizer/resources.py:258`);
  - `resources.realize` (`:187-238`) counts Leftovers copies by the same rule as T027, so the
    optimizer and the validator agree.
- [X] T029 [US2] Show the three new rules on the page:
  - **`index.html`**: add the three checkboxes in the order in `contracts/ui.md`, and set the
    legend to "Optional rules (all off by default)".
  - **`app.js`**:
    - send the three keys on POST (`:205-207`);
    - re-run the search on every rule change (`:473`);
    - add the rules to the `/api/species` query;
    - list all five in the summary "Legality options" row (`:377`), with missing keys read as "off".
  - **`result_view.py`**: pass the five options through (`:67`).
- [X] T030 [US2] Regenerate the generated data with `uv run platsim extract`, then run
  `uv run platsim extract --check`. Record the per-phase entry counts before (T001 commit) and after
  in `validation-log.md`, and explain every change. Expected changes: the Munchlax entries, the
  honey levels, the `unreachable` reason and the frontier entries.
- [X] T031 [US2] Add a note to `specs/001-champion-team-optimizer/spec.md` beside FR-006a (`:189-190`)
  and the clarification at `:50-51`: "Superseded by 003 FR-008/FR-009 (2026-10-11): Munchlax and
  Snorlax are allowed; Leftovers only with them on the team." Don't delete the original text.

**Checkpoint**: run
`uv run pytest -q tests/unit tests/integration/test_availability_controls.py tests/integration/test_web*.py tests/integration/test_explain.py tests/integration/test_extract.py`,
then the browser tests. Paste the output. T015 must show fail-before / pass-after.

---

## Phase 5: User Story 3 – Read where each team member comes from (P2)

**Goal**: plain "obtained from" text, naming the earliest legal location by badge gates across
evolution stages, without 1% encounters. The reports of new runs carry it.

**Independent test**: quickstart V5.

### Tests for User Story 3

- [X] T032 [P] [US3] Create `tests/unit/test_source_text.py`:
  - **Leak scan**: no `SourceOption.detail`, for every species × the 16 combinations of the four
    availability-changing rules, matches `[A-Z]{2,}_[A-Z_]{2,}` or contains "EVO", "Start",
    "GivePokemon" or "GiveEgg". **Positive control**: today's starter detail matches before T036.
  - **Specific texts**:
    - the Infernape chain reads "Gift - Route 201 (Chimchar, starter) -> Monferno at level N ->
      Infernape at level M", with N and M read from the decomp `Evolution.param`, not typed;
    - Weavile's step names Razor Claw and night;
    - Rotom's static encounter has no parentheses;
    - Kazza's trade reads "NPC trade - <map> (Kazza, give Machop)";
    - a fossil names its item;
    - Lickitung → Lickilicky names Rollout;
    - Mantyke → Mantine names Remoraid;
    - Magneton → Magnezone names the place.
- [X] T033 [P] [US3] Create `tests/unit/test_story_rank.py` with the positive controls from research
  R9:
  - Route 201 → 0, Ravaged Path → 1, Route 209 → 3, Route 218 / Canalave City / Route 220 → 5, Victory
    Road 1F → 8;
  - every gym's own map ranks below its badge's index;
  - the gym order from leader levels is Coal, Forest, Relic, Cobble, Fen, Mine, Icicle, Beacon, and
    matches the order in which the gym maps first become reachable;
  - **Step-1 control**: with story blockers turned off, Route 209 is 2. This proves the two steps
    differ.
  - If a decomp-derived rank disagrees with an expected value, investigate before changing the test,
    and record the finding.
- [X] T034 [P] [US3] Extend `tests/integration/test_availability_controls.py` for the rates
  (research R8):
  - every wild entry has `rate_percent`, and honey entries have one per group;
  - Gabite on Victory Road 1F sums to 5;
  - Munchlax honey is 1;
  - the slot-rate tables parsed from `wild_encounters.c` equal the decomp's cumulative thresholds;
  - **Positive control**: a deliberately broken regex input raises.
- [X] T035 [P] [US3] Update `tests/unit/test_source_preference.py` for the new selection order
  (data-model "Selection order"):
  - **Garchomp** is named from Gible in Wayward Cave B1F, not from Gabite on Victory Road;
  - **Staravia** is from Route 209 rather than Route 210 South;
  - **Sneasel**: among the Route 216, Route 217 and Acuity Lakefront ties at level 33, the one with
    fewer hops wins;
  - a 1%-only location is skipped when another location exists, and named when it's the only one;
  - a Day Care egg is named only when no catch qualifies;
  - an option whose `min_level` is above the build level is never chosen;
  - `_floor_cached` level floors are unchanged for the six reference species (compare with T001);
  - **Combee**: its text names the honey tree, not a Day Care egg, and its `_floor_cached` is
    unchanged at 1, because breeding stays legal (analysis H3).

  Update `TRADE_TAIL` and the "holding Protector" checks in `tests/unit/test_legality_options.py`
  (`:34`, `:122-142`) to the new trade text.

### Implementation for User Story 3

- [X] T036 [US3] Rewrite the `SourceOption.detail` formatting in
  `src/platsim/legality/movesources.py` (`:381-383`, `:423-431`, breed `:496-506`) to the tables in
  research R7:
  - **Names**: items via `load_items()[c].name`, moves via `load_moves()[c].name`, species via
    `species_name`, and maps via `human_map`.
  - **Steps**: store `ev.param` on `Stage` (`:276-280`) so each step can name its level, item, move
    or species.
  - **Constants in other text**: NPC-trade, roamer and fossil details map their constants through
    the decomp data, e.g. the NPC trade nickname from `res/npc_trades/*.json` "name".
  - **Unchanged**: `Entry.detail`, because extraction tests match on it.
  - The held-item text that embeds `option.detail` (`:853`) picks up the new text automatically.
    Check it reads well.
- [X] T037 [US3] Keep encounter rates through the merge (research R8):
  - in `src/platsim/availability/sources.py`, parse the slot-rate tables from
    `pokeplatinum/src/overlay006/wild_encounters.c` (`GetGroundEncounterSlot`, `:820-848`; surf
    `:851-865`; Old Rod `:868-887`; Good and Super Rod `:888-911`) and the honey group rates from
    `src/overlay005/honey_tree.c:197-243`. Fail loudly on a parse mismatch;
  - give each wild `Entry` its slot's rate, using the replacement-slot mapping in R8;
  - `_merge_wild` (`src/platsim/availability/ledger.py:221-243`) sums `rate_percent` instead of
    dropping it;
  - carry `rate_percent` onto `SourceOption`.
- [X] T038 [US3] Create `src/platsim/availability/story_rank.py`, **step 1, field moves** (research
  R9):
  - **Parsers**:
    - `field_move_badges()` from `pokeplatinum/src/field_move_tasks.c` (the `FieldMoves_Check<Move>` →
      `BADGE_ID_*` regex). Cross-check it against `res/field/scripts/scripts_field_moves.s`, and fail
      if the two disagree;
    - `gym_order()` from the badge sites (`GiveBadge` in the gym scripts) plus the top party level in
      `res/trainers/data/leader_*.json`;
    - obstacle objects (`OBJ_EVENT_GFX_CUT_TREE`, `ROCK_SMASH`, `STRENGTH_BOULDER`, through script ids
      10000–10002) from `res/field/events/*.json`;
    - surfable, waterfall and rock-climb tile behaviours from `src/map_tile_behavior.c` and
      `include/constants/field/map_tile_behaviors.h`.
  - **Reachability**: for k = 0..8, use an ability-aware wall test that reuses `mapgraph._flood`,
    `_header_tiles` and `_border_tiles`, with nodes (map, region) and edges from the existing warps
    and borders. Cache per ability set.
  - **Output**: `rank(map_header) -> (badges_needed, hops)`.
  - **Storage**: `extract.py` writes the ranks to `data/generated/story_rank.json` and `extract --check`
    covers it. Runtime code only reads the file, so a web job pays no build cost.
  - Log the build time to `validation-log.md`; the target is under 60 s.
- [X] T039 [US3] `story_rank.py` **step 2, story blockers**:
  - blocker objects whose hidden flag is set in a script that also does `GiveBadge X` stay walls until
    stage index(X);
  - `CheckItem ITEM_Y` gates (the Route 210 Psyduck / SecretPotion) take the rank of Y's source map;
  - extend `src/platsim/availability/gates.py` only as far as needed to read these.
  - T033's Route 209 → 3 must now pass, and its step-1 control must still give 2.
- [X] T040 [US3] Change `option_sort_key` (`src/platsim/legality/movesources.py:765`) and its users
  (`src/platsim/optimizer/resources.py` `realize`, `src/platsim/legality/validator.py:237-247`) to the
  data-model "Selection order":
  - `story_rank` comes from `story_rank.rank()` of the option's first-stage map;
  - non-map kinds (`outside_platinum`) rank last;
  - `min_level` stays a feasibility filter only;
  - `_floor_cached` (`resources.py:274-298`) is unchanged.
- [X] T041 [US3] Stop *new* reports from adding internal ids:
  - `src/platsim/optimizer/run.py:670` drops "(FR-019)";
  - `src/platsim/report/json_report.py:48-52` `QUICK_WARNING` drops "(research.md R8)" and "SC-003"
    and keeps its meaning.

  The texts of old reports stay as they are.
- [X] T042 [US3] Regenerate the data (`uv run platsim extract` and `--check`) for the rate field, and
  record the diff summary in `validation-log.md`. Then re-render the fixture into scratch:
  `uv run platsim report --rerender tests/fixtures/web_final_defaults --out "$SCRATCH/rr"`.
  - **Expect**: the re-render's checks pass, its output text matches T032 and T035 (Garchomp from
    Gible), and every battle number is unchanged.
  - Paste the old vs new `obtained_from` list into `validation-log.md`. Don't overwrite the fixture.
- [X] T042a [US3] Re-render the stored web runs (spec SC-005, edge cases; analysis H1). For each
  `runs/job-*` that has a `result.json`:
  - run `uv run platsim report --rerender runs/<id> --out runs/<id>-r003`;
  - write `runs/<id>-r003/job.json`, copied from the original with a new id and a
    `"rerendered_from": "<id>"` field, so the run picker lists it. If the picker filters on the
    `job-` prefix (`src/platsim/web/app.py:537-550`), adjust the filter rather than renaming;
  - mark these in the picker label "(re-rendered)";
  - skip a cancelled job with no result;
  - never modify the originals: check their sha256 against T001 after the step.

  Add an integration test in `tests/integration/test_web.py`: a re-rendered fixture copy is listed,
  labelled "(re-rendered)", and its `obtained_from` has no internal code.
- [X] T043 [US3] Update `tests/browser/test_page.py:155-160`. The page text must equal the API's
  `obtained_from`. Point the "wraps onto a second line" check at a card whose text is still long
  enough, or drop it if none is. Explain the choice in a comment.

**Checkpoint**: `uv run pytest -q tests/unit tests/integration/test_availability_controls.py tests/integration/test_extract.py tests/integration/test_web*.py`
plus the browser tests. Paste the output.

---

## Phase 6: User Story 4 – See who the player is up against (P2)

**Goal**: hovering, focusing or tapping a trainer in the chart shows their sprite and a 3×2 grid of
their team.

**Independent test**: quickstart V6 (pop-up part).

### Tests for User Story 4

- [X] T044 [P] [US4] Extend `tests/integration/test_web_sprites.py`:
  - `GET /api/trainer-sprites/{aaron,bertha,flint,lucian,cynthia}.png` returns 200, a PNG of
    160×80 with a `tRNS` chunk;
  - `GET /api/trainer-sprites/roark.png` and `../x.png` return 404;
  - `GET /api/league` returns the five trainers in order, with Cynthia's party exactly
    spiritomb, roserade, togekiss, lucario, milotic, garchomp, read from `load_league()` in the test,
    not typed;
  - each Elite Four member has 5;
  - every party key is accepted by `/api/sprites/{key}/front.png`.
- [X] T045 [P] [US4] Extend `tests/browser/test_page.py`. For each of the 5 `g.bar-group`:
  - hover, Tab focus and tap (`page.tap` with `has_touch`) each open `#trainer-pop`;
  - the pop-up has 1 trainer `img` and 5 or 6 pokemon `img`, all with `naturalWidth > 0`;
  - its header shows the clear rate, the interval and the battle count;
  - Escape closes it;
  - its bounding box is inside the viewport at 1920×1080 and at 360×800;
  - the empty sixth cell is present for Elite Four members.

  Save one pop-up screenshot per trainer to `$PLATSIM_SCREENSHOT_DIR`, and check the four Elite Four
  trainer sprites by eye (research R10: only Cynthia was checked before).

### Implementation for User Story 4

- [X] T046 [P] [US4] In `src/platsim/web/sprites.py`, add `trainer_sprite_png(trainer)`:
  - an allow-list of the five keys, mapped to `res/trainers/classes/<class>` through the
    `decomp/trainers.py` `LEAGUE` classes;
  - read `front_scan.png`, apply `with_transparent_index0`, and cache it.
- [X] T047 [US4] In `src/platsim/web/app.py`, add `GET /api/league` (data-model "League"; from
  `load_league()`, with `Cache-Control: max-age=86400`) and `GET /api/trainer-sprites/{trainer}.png`
  (404 with a JSON `detail` otherwise).
- [X] T048 [US4] Add the pop-up per `contracts/ui.md` "Trainer pop-up":
  - **`app.js`**:
    - fetch `/api/league` once;
    - build `div#trainer-pop[role=dialog]` with the trainer sprite on the left and a 3×2 grid of
      front sprites;
    - open it from `renderChart`'s bar groups (`:396-451`) on mouseenter, focus and click;
    - close it on Escape, mouseleave, blur and an outside click;
    - clamp its position to the viewport;
    - move the clear-rate text from `#chart-tip` into the pop-up header and remove `#chart-tip`;
    - if the league fetch fails, keep the old tooltip.
  - **`style.css`**: the grid and sprite sizing (reuse `.sprite-front`).

**Checkpoint**: `uv run pytest -q tests/integration/test_web_sprites.py` and the browser tests pass.
Record the output and the screenshots you checked.

---

## Phase 7: User Story 5 – Results layout, move colours and theme (P3)

**Goal**: the roster comes before the chart; move names are coloured by type; a light/dark toggle.

**Independent test**: quickstart V6 (order, colours, theme).

### Tests for User Story 5

- [X] T049 [P] [US5] Extend `tests/integration/test_web_result_view.py`: every move has `type`, a
  display type name read from `load_moves()`, such as "Fire".
- [X] T050 [P] [US5] Create `tests/unit/test_type_colours.py`:
  - parse `src/platsim/web/static/style.css`;
  - for all 17 types, the `--type-<type>` light and dark values each reach a contrast ratio of at least
    4.5:1 against the card background of that theme;
  - **Positive control**: a stub CSS string with `#ffff00` on white fails.
- [X] T051 [P] [US5] Extend `tests/browser/test_page.py`:
  - **Order**: summary, then cards, then chart, then downloads, by DOM order and by box `y`. Replace
    the `:126-128` "chart within 1080 px" check with "summary and the first card row within 1080 px".
  - **Moves**: each move chip has `data-type`, its computed colour equals the matching `--type-*`
    value, and its tooltip starts with "<Type> ·".
  - **Theme**:
    - `#theme-toggle` is inside the top-right quadrant of the header;
    - clicking it flips `data-theme` and `aria-pressed`;
    - reloading keeps it;
    - clearing `localStorage` and reloading under each `emulate_media` scheme follows the system.
  - **Screenshots**: switch the existing light and dark screenshots (`:283-286`) to set the theme
    through the toggle.

### Implementation for User Story 5

- [X] T052 [US5] Swap `#chart` and `#team-cards` in `src/platsim/web/static/index.html:102-111`.
- [X] T053 [US5] Add the move `type` in `src/platsim/web/result_view.py:93`, from `result.json`
  `team.builds[i].moves[j].move` through `load_moves()["MOVE_" + key.upper()].type`, formatted like
  `species_catalog._type_name`. Use `null` if the key is unknown.
- [X] T054 [US5] Colour moves by type:
  - **`app.js`**: set `data-type` on the move chip and prefix the tooltip with the type (`:457`,
    `withTip`).
  - **`style.css`**: one `--type-<type>` custom property per type in `:root`, in the dark media query
    and in `[data-theme=dark]`, and a `.move[data-type=…]` colour rule. Choose values that pass T050.
- [X] T055 [US5] Theme toggle per `contracts/ui.md`:
  - **`index.html`**: an inline `<head>` script that applies a stored theme before paint, inside
    try/catch, and `button#theme-toggle` in `header.site`.
  - **`app.js`**: the click handler, `aria-pressed`, the label, and storage in try/catch.
  - **`style.css`**:
    - `header.site` becomes a flex row;
    - `[data-theme=light]` and `[data-theme=dark]` blocks repeat the existing variables;
    - the `prefers-color-scheme` block applies only when there is no `data-theme`;
    - keep the literal `prefers-color-scheme: dark` so `tests/integration/test_web.py:34` still holds.
- [X] T056 [P] [US5] Add a superseded note to `specs/002-webui-redesign/contracts/ui.md:42, 65`: the
  theme now uses `localStorage` and a toggle (003); the run picker still stores nothing.

**Checkpoint**: `uv run pytest -q tests/unit/test_type_colours.py tests/integration/test_web_result_view.py`
and the browser tests pass. Check the light, dark and 360 px screenshots by eye.

---

## Phase 8: Polish & cross-cutting

- [X] T057 Bump `pyproject.toml` from 0.1.0 to 0.2.0 (research R14). Update
  `tests/unit/test_version.py` if it pins the version. Check that the page shows "platsim 0.2.0" for
  a new run and "platsim 0.1.0" for old runs.
- [X] T058 Run the web and browser suites: `uv run pytest -q tests/integration/test_web*.py`, then
  `uv run pytest -q -m browser tests/browser/`. Paste the output.
- [X] T059 Run the full suite. This is **about 2.5 h of local CPU, with no paid resources**:
  `uv run pytest -q -m "not browser"`, then `uv run pytest -q -m browser tests/browser/`.
  - Paste the real output into `validation-log.md`.
  - Add a table mapping FR-001 to FR-024 (with FR-010a) and SC-001 to SC-007 (with SC-003a) to the
    test or walkthrough step that checks each, with pass or fail.
- [X] T060 Quickstart V7. Run a real `quick` job through `uv run platsim serve` and the same request
  through the command line: the `tests/integration/test_optimize_small.py` request, seed `t058`, all
  rules off. Then `cmp` the two `result.json` files and paste the exit code. This is about 2 × 25 min
  of local CPU, with no paid resources.
  - Check that `provenance.legality_options` has five keys and `platsim_version` is 0.2.0.
  - Check that `sha256sum` of every pre-existing `runs/*/result.json` equals T001's.
- [X] T061 [P] Update `README.md`:
  - the three new CLI flags and rules;
  - Munchlax and Snorlax, and the Leftovers rule;
  - the new endpoints (`/api/league`, trainer sprites);
  - the theme toggle;
  - that "obtained from" names the earliest location by badge gates;
  - the 0.2.0 version.
- [X] T062 [P] Update `RUN-STATE.md`: 003 is done, then the remaining traps and the user-testing
  handoff (merge only on the user's go-ahead: `git switch main && git merge --ff-only 002-webui-redesign`).

---

## Dependencies & execution order

```text
Setup (T001–T002) ─▶ Foundational (T003–T005) ─┬─▶ US1 (T006–T013) 🎯 MVP
                                                ├─▶ US2 (T014–T031)   [static files shared with US1 → page part (T029) after T012]
                                                ├─▶ US3 (T032–T043)   [needs US2's T023/T030 (rules + regenerated data) before T040/T042]
                                                ├─▶ US4 (T044–T048)   [independent; app.js after T029]
                                                └─▶ US5 (T049–T056)   [independent; static files after T048]
All stories ─▶ Polish (T057–T062)
```

- **Shared files**:
  - `app.js`, `index.html` and `style.css` are edited by T011–T013, T029, T048 and T052–T055, in
    that order.
  - `tests/integration/test_web.py` is edited by T006 then T018.
  - `tests/browser/test_page.py` is edited by T007, T043, T045 and T051, in that order.
  - `movesources.py` is edited by T019, T026, T036 and T040, in that order.
  - `ledger.py` is edited by T019, T022, T023, T024 and T037, in that order.
- **US2 internal order**: T019 → T020 → T021; T022 → T023; T024 → T025 → T026 → T027 → T028; then
  T030 regenerates the data.
- **US3 internal order**: T036 and T037 → T038 → T039 → T040 → T041 → T042 → T042a → T043.
- **T002a** (constitution check) comes before T026.

## Parallel examples

```text
After Phase 2, in parallel:
  T006 test_web.py (US1)          T014 test_legality_options.py   T016 test_availability_controls.py
  T017 test_validator.py          T032 test_source_text.py        T033 test_story_rank.py
  T044 test_web_sprites.py        T046 sprites.py                 T049 test_web_result_view.py
  T050 test_type_colours.py
```

## Implementation strategy

1. **MVP**: Phases 1–3 (US1). The wording and the always-visible reasons fix the most visible
   confusion. Validate with the wording scan.
2. **US2**: the rules. This changes legality, so the validator tests (T017) and the
   fail-before/pass-after cache test (T015) gate it.
3. **US3**: the source text. This is the largest slice (story rank). Step 1 and step 2 are separate
   tasks, so a partial result is still useful: step 1 alone names a legal, possibly later, place.
4. **US4, US5**: page-only, low risk.
5. **Polish**: the full suite, the web-vs-CLI byte-identical check, docs, and handoff to the user for
   hands-on testing before any merge.

Each checkpoint records real test output in `validation-log.md`. Nothing is marked done without
running its check.
