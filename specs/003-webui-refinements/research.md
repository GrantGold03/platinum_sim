# Research: Web UI Refinements (003)

Facts come from read-only code research on 2026-10-11 (file:line as of commit `3f28665` on
`002-webui-redesign`). Nothing below has been run as a test yet. Each decision names the check that
will confirm it.

## R1. Option plumbing for the three new rules

**Decision**:
- Add three booleans to `LegalityOptions` (`src/platsim/legality/models.py:56-88`):
  `allow_post_game_pokemon`, `allow_post_game_items`, `allow_unobtainable_pokemon`.
- They follow the existing `allow_trade_evolutions` path at every hop:
  - CLI `_add_legality_flags` / `_legality` (`cli.py:13-26`): `--allow-post-game-pokemon`,
    `--allow-post-game-items` and `--allow-unobtainable-pokemon`.
  - The web `_options()` key loop (`web/app.py:516-523`) and `run_one` (`app.py:305-306`). Both
    become driven by `LegalityOptions` fields, not hard-coded names.
  - `/api/species` query params.
  - `provenance.legality_options` in the report, which records all five keys explicitly.
  - The `result_view` summary and the page summary text (`app.js:377`).
- **Fingerprint stability**: `job_fingerprint()` (`optimizer/run.py:85-87`) hashes `to_dict()`, so
  adding keys would move the default output directory of every job (`run.py:90-92`). The
  fingerprint therefore uses `to_dict(compact=True)`, which leaves out the new keys while they are
  False. Reports always write all five.
- `from_dict` already defaults missing keys to False (`models.py:78`), so old reports still load
  and re-render.

**Rationale**: one dataclass drives everything, as for trade evolutions. Constitution III wants
optional constraints to be explicit inputs.

**Alternatives considered**: a separate "rules" object (rejected: it duplicates `LegalityOptions`);
always including all keys in the fingerprint (rejected: it silently re-homes default CLI runs).

## R2. Where availability is filtered: one seam, two cache bugs

**Decision**:
- `Ledger.pre(subject, kind)` (`availability/ledger.py:132-136`) is the single place where phases
  are filtered, and every reader goes through it (species sources, item and TM copies, tutors, once
  flags, movesources, validator error sources). Make it option-aware by entry kind:
  - acquisition kinds (`ACQUIRE_KINDS`): PRE, plus POST if `allow_post_game_pokemon`, plus
    NEVER(`other_cartridge`) if `allow_unobtainable_pokemon`;
  - item and tutor kinds: PRE, plus POST if `allow_post_game_items`.
- National Dex entries are already POST with a `national_dex:` reason (`ledger.py:243-246`), so
  they unlock with the matching post-game rule, as the spec intends.
- **Fix first** (they would return stale answers across option views):
  - `Ledger.species_sources` caches in the shared `derived` dict, keyed by species only
    (`ledger.py:138-145`). Key it on options.
  - `movesources.breed_mothers` uses a fixed cache key (`movesources.py:474`). Key it on options.
- The optimizer caches `_COPIES` (`resources.py:105-113`) and `_ITEM_COPIES`
  (`candidates.py:411-418`) by `id(led)`, which is safe because there is one view per options value.

**Rationale**: the phase filter is already the choke point. Changing it there keeps the validator
and the optimizer in step (Constitution III) without touching each reader.

**Positive control**: a test asserts that the fixed caches give different answers for two option
views of one ledger (it fails today).

## R3. "Post-game" also covers maps that can never be entered

**Finding**: POST means "not reachable before the Champion" (`ledger.py:82-107`). The map graph
never computes post-game reachability: `_usable` returns False for post-game edges
(`mapgraph.py:1193`). So POST also covers UNUSED_* maps and the collision-warp condominium. Turning
on post-game items as-is would count sources on maps that can't be entered: a TM04 gift (unused Eterna
condominium 4F), a Focus Band (unused Jubilife condominium 4F), a Razor Fang (unused Battle Park), a
Hard Stone and the unused Resort Area mart.

**Decision**:
- Add a second reachability pass to the map graph that also allows post-game edges.
- POST entries on maps that pass still can't reach get a new reason, `unreachable`, and are never
  admitted by any rule.
- The ledger keeps the phase name POST for the rest, so existing counts stay the same until
  regenerated.

**Missing source: the Battle Frontier exchange** (found 2026-10-11 after the user asked about TM04).
- `ScrCmd_PokeMartFrontier` (`pokeplatinum/src/scrcmd.c:6635-6660`) has two counters:
  - right: TM06, TM73, TM61, TM45, TM40, TM31, TM08, TM04, TM81, TM30, TM53, TM36, TM59, TM71, TM26;
  - left: vitamins, Power items, Toxic and Flame Orb, White and Power Herb, BrightPowder, Choice Band and
    Scarf, Focus Band, Scope Lens, Muscle Band, Focus Sash, Razor Claw, Razor Fang, Rare Candy.
- Prices are in BP (`src/overlay007/shop_menu.c:1340-1382`).
- The ledger doesn't extract it, so today TM04, TM08, TM61 and TM73 look as if they have no
  obtainable source at all.
- **Decision**: add a `frontier_exchange` item source. Its phase is POST (the Battle Frontier is
  post-game) and its quantity is unlimited (BP can be earned again). The items are parsed from the
  `ScrCmd_PokeMartFrontier` arrays, and the map comes from the scripts that call `PokeMartFrontier`.
  - It only matters with "Allow post-game items and moves" on. The default rules are unchanged:
    it's post-game, so the pre-Champion counts don't move.

**Positive controls**:
- With post-game items on, these become available:
  - TM50 (Stark Mountain), TM37 (Route 228), TM42 (Survival Area), TM53 (Route 226);
  - TM04, TM08, TM61, TM73 and Focus Band (Battle Frontier exchange);
  - the Victory Road Leftovers.
- With post-game items on, these stay unreachable, and are never the source named for anything:
  - the unused-map entries (the Eterna condominium 4F TM04 gift, the Jubilife condominium Focus Band,
    the Battle Park Razor Fang).
  - The items themselves may still be available from another source, such as the Frontier.
- The `illegal_postgame_tutor.json` validator fixture stays illegal with the rule off.

**Alternatives considered**: a hand list of unused maps (rejected by Constitution I: it is hand-typed
game data, and the graph can derive it).

## R4. Unobtainable pokemon

**Finding** (from `build_catalog()`, 2026-10-11):
- 24 species have only `other_cartridge` entries (dual-slot GBA), e.g. Caterpie, Ekans, Shuckle,
  Sableye, Lunatone.
- 40 have no entry at all (`no_source`), e.g. the Kanto, Johto and Hoenn starters, the legendaries,
  Glameow, Stunky, Clamperl.
- 94 more are blocked only through a pre-evolution (`pre_evolution_unavailable`), e.g. Ivysaur.

**Decision**:
- "Unavailable in Platinum" (spec FR-005) is the reason for `unobtainable` and `no_source`.
- With `allow_unobtainable_pokemon`:
  - `other_cartridge` entries count, at their real levels;
  - a species with no entry gets one synthetic source of kind `outside_platinum` at level 1 (the Gen 4
    egg hatch level), labelled "Unavailable in Platinum (allowed by rule)".
- Evolved forms are then reached through the normal evolution rules, e.g. Charizard from a synthetic
  Charmander at level 36.
- Moves still come from the decomp learnsets (`movesources._choices`), so spec FR-011 holds without
  further work.
- The synthetic kind needs entries in `ACQUIRE_LABELS` (`movesources.py:107`), `OPTION_RANK` and
  `option_class` (`movesources.py:753-762`). It ranks last, so a real source always wins.

**Rationale**: this rule is explicitly outside the cartridge. A synthetic level-1 source is the
smallest honest model, and it is labelled as such in every report. Constitution v1.2.0, Principle III,
allows it as an explicit, off-by-default rule (amended 2026-10-11, analysis C1).

**Alternatives considered**: refusing `no_source` species even with the rule on (rejected: then the
rule's name would be false for 40 of 64 species).

## R5. Munchlax, Snorlax and Leftovers

**Findings**:
- The exclusion is `EXCLUDED_SPECIES` (`ledger.py:183-218`). It is used in `species_catalog.py`,
  `candidates.py:205-242` and `explain.py:201-202, 391-399`. Its spec origin is 001 FR-006a
  (`specs/001-champion-team-optimizer/spec.md:50-51, 189-190`).
- **Honey-tree entries have no level** (`sources.py:410-421`), so `movesources._options` skips them
  as wild sources (`:377-378`). Checked live on 2026-10-11: Aipom, Burmy, Cherubi, Combee and
  Heracross are still available, but only as `Day Care egg (mother: Combee, …)` at level 1, because
  the breeding path uses them.
  - Without the level fix, un-excluding Munchlax would likely give a breed-only source too
    (corrects the first research pass, which said it would give no source; analysis H3).
  - The fix gives an honest wild source at levels 5–15 (`pokeplatinum/src/overlay006/wild_encounters.c:1208-1210`),
    so the text names the honey tree. The level floor stays 1, because breeding is still legal.
- Leftovers sources:
  - 21 Munchlax wild-held entries (100%: both held-item slots are Leftovers in
    `res/pokemon/munchlax/data.json`);
  - one item ball at Victory Road 1F Room 2, which is POST.
  - No Snorlax encounter exists. Snorlax comes only from Munchlax (`EVO_LEVEL_HAPPINESS`).
- The optimizer never offers Leftovers today: `held_item_candidates` (`candidates.py:421-438`) offers
  only an HP berry and a type-boost item.
- The sim already models Leftovers (`sim/policy/expectimax2.mjs:125, 822`), so `sim/` is unchanged.

**Decision**:
- Empty `EXCLUDED_SPECIES`, and remove the `excluded` reason code and its texts.
- Parse the honey-tree level range from `wild_encounters.c` and set it on honey entries. This also
  gives every other honey-tree-only path a level.
- The Munchlax rare-tree detail drops the C identifier ("honey tree, rare: only some trees, depending
  on Trainer ID").
- **Team rule, enforced in two places:**
  - Validator: a team-level check after the member loop (`validator.py:297-360`) with a new code
    `LEFTOVERS_NEEDS_MUNCHLAX`.
    - With Munchlax or Snorlax on the team, Leftovers is unlimited.
    - Without them, Leftovers counts only non-Munchlax sources: 0 by default, or 1 (Victory Road)
      with post-game items.
    - Munchlax wild-held entries become PRE (unlimited), so this rule must be explicit; the
      per-member check alone would pass.
  - Optimizer: `held_item_candidates` takes the team's species. It adds Leftovers when the team has
    Munchlax or Snorlax, or when the counted copies are above 0. `resources.realize` (`resources.py:187-238`)
    already tracks copies per team.
- 001's FR-006a is amended to point at 003 (that spec is not rewritten).

**Positive controls**:
- `source_options(MUNCHLAX)` is non-empty, with levels 5–15.
- A team of Munchlax plus 5 others with Leftovers on 3 members is legal.
- The same team without Munchlax is illegal with `LEFTOVERS_NEEDS_MUNCHLAX`.
- With post-game items on, one Leftovers is legal and two are not.

## R6. Requirement ids and the word "species" on the page

**Findings**: the shown texts that contain "species" or requirement ids:
- `index.html:13, 21, 35, 39-42`;
- `app.js:109, 125, 197`;
- `species_catalog.py:136-146` reasons and `:187` note;
- the `resolve_team` messages (`:218-232`);
- `app.py:198-200, 399-400`;
- optimizer and validator messages that can reach `job.error` (`candidates.py:213-273`,
  `validator.py:396, 495-505`);
- report warnings: `run.py:670` "(FR-019)", and `json_report.py:48-52` `QUICK_WARNING` "(research.md
  R8)… SC-003".

**Decision**:
- **Web-owned text** (static files, `species_catalog`, `app.py`) is rewritten at its source.
- **Passed-through text** (report warnings, job errors, invalid reasons, recorded job messages) goes
  through one function, `web/display_text.py: clean()`, applied in `result_view` and the job and
  error routes. It:
  - removes parenthesised or bare requirement references (`FR-\d+[a-z]?`, `SC-\d+`,
    `research\.md R\d+`), including surrounding "(…)" and doubled spaces;
  - replaces the word "species" with "pokemon", keeping the case.
- The report files keep their text (spec FR-001), but report-writing code may stop *adding* new ids.
- **A scan test checks the result**: the browser test reads `document.body.innerText`, every
  `title`, `aria-label` and tooltip, for every page state across all stored fixture runs, and asserts
  zero matches (spec SC-001).

**Rationale**: the report files are the record (Constitution IV), so old reports stay as written.
A single cleaning point also catches messages added later.

**Alternatives considered**: rewriting the optimizer and validator messages everywhere (rejected for
this feature: they are CLI output too, and `job.error` text from old runs would still need cleaning).

## R7. "Obtained from" text format (spec FR-014–FR-016, FR-018)

**Findings**:
- The text is `SourceOption.detail` (`movesources.py:381-383, 423-431`). It is built from
  `Entry.detail` (`sources.py:344-574`) after `_merge_wild` strips slot numbers
  (`ledger.py:221-243`).
- Leaks today:
  - `EVO_*` method names (`how = ev.method`, `movesources.py:426`);
  - script command names ("StartWildBattle", "GivePokemon");
  - raw constants ("NPC_TRADE_KAZZA_ABRA (give SPECIES_MACHOP)", "ROAMING_SLOT_MESPRIT",
    "fossil revival of ITEM_ARMOR_FOSSIL");
  - time-of-day codes ("night NIGHT/LATE_NIGHT").
- Name helpers exist: items via `load_items()[c].name`, moves via `load_moves()[c].name`, species via
  `species_name`. The evolution params are in `Evolution.param` (`decomp/species.py:47-49`).

**Decision**: rewrite the `SourceOption.detail` formatting only. `Entry.detail` keeps its
machine-oriented text, because extraction tests match on it.

New text:

| Case | Text |
|---|---|
| Wild | `Wild - <map> (<pokemon>, <method>)`, method one of grass, surf, Old Rod, Good Rod, Super Rod, morning/day, night, swarm, Poké Radar, honey tree, Great Marsh, Feebas tiles |
| Starter | `Gift - Route 201 (<pokemon>, starter)` |
| Other gifts | `Gift - <map> (<pokemon>)` |
| Gift egg | `Gift egg - <map> (<pokemon>)` |
| Static | `Static encounter - <map>` (no parenthetical) |
| Roamer | `Roamer - <pokemon>` |
| NPC trade | `NPC trade - <map> (<nickname>, give <pokemon>)` |
| Fossil | `Fossil - <map> (<fossil item name>)` |
| Unobtainable rule | `Unavailable in Platinum (allowed by rule)` |

Evolution steps are joined with ` -> `:

| Evolution method | Step text |
|---|---|
| `EVO_LEVEL` | `<pokemon> at level N` |
| `EVO_USE_ITEM` (and `_MALE` / `_FEMALE`) | `<pokemon> with <item>` plus "(male)" / "(female)" |
| `EVO_LEVEL_WITH_HELD_ITEM_DAY` / `_NIGHT` | `<pokemon> by leveling up holding <item> during the day` / `at night` |
| `EVO_LEVEL_HAPPINESS` (and `_DAY` / `_NIGHT`) | `<pokemon> by friendship` plus day / night |
| `EVO_LEVEL_KNOW_MOVE` | `<pokemon> by leveling up knowing <move>` |
| `EVO_LEVEL_SPECIES_IN_PARTY` | `<pokemon> by leveling up with <pokemon> in the party` |
| magnetic field / moss rock / ice rock | `<pokemon> by leveling up at <map>` |
| `EVO_LEVEL_BEAUTY` | `<pokemon> by leveling up with high Beauty` |
| ATK/DEF and PID methods | `<pokemon> at level N (<condition>)` |
| `EVO_LEVEL_MALE` / `_FEMALE` | `<pokemon> at level N (male / female)` |
| trade methods | keep today's wording, without requirement ids |

- Breeding keeps "Day Care egg (mother: …)".
- **A test catches leaks**: for every pre-Champion and post-game `SourceOption` of every species under
  every rule combination, the detail matches no `[A-Z]{2,}_[A-Z_]+` constant and contains no "EVO".
- The browser test at `test_page.py:155-160` expects a wrapped line in the fixture text. It is
  re-pointed at a fixture member whose new text is still long, or the wrap check is dropped if none
  is long enough.

## R8. Encounter rates and "1% encounters"

**Finding**: the per-slot rates are lost when `_merge_wild` strips slot numbers. They are defined by
the decomp encounter functions:
- `GetGroundEncounterSlot`: 20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1 (`wild_encounters.c:820-848`);
- surf: 60, 30, 5, 4, 1 (`:851-865`);
- Old Rod: 60, 30, 5, 4, 1 (`:868-887`);
- Good Rod and Super Rod: 40, 40, 15, 4, 1 (`:888-911`);
- honey tree group C (Munchlax) is 1% (`honey_tree.c:197-243`).

**Decision**:
- Parse these thresholds from the C functions (Constitution I: no hand-typed rates).
- Store each wild entry's summed `rate_percent` per (map, species, method) through `_merge_wild`.
  This adds a field to `Entry` and regenerates `data/generated/availability.json`.
- A location is a "1% encounter" when the species' summed rate there, for that method, is ≤ 1.
- Replacement slots keep the base slot's rate: swarm uses slots 0–1, time of day 2–3, Poké Radar
  4/5/10/11, dual-slot 8–9.

**Positive controls**:
- Gabite on Victory Road sums to 5% (4 + 1), so it is not a 1% encounter.
- A species sitting only in slots 10 and 11 of a map sums to 2%.
- Munchlax honey trees are 1%. Munchlax is still named, because it has no other source (spec edge
  case).

## R9. Earliest location by badge gates (spec FR-017; user's choice 2026-10-11)

**Findings**:
- **Nothing computes story order today.** The map graph has no badge or HM model. The tile test is the
  collision bit only (`mapgraph.py:250-253`), so 24,343 sea tiles count as walkable, while rock-climb
  walls and ledges count as walls. Cut trees, rocks and boulders are ignored.
- Hop counts from Twinleaf are therefore meaningless: Route 220 is 4 hops away across water, and Route
  209 is reached from the north at 19 hops.
- No edge carries a badge or HM requirement. The `badge` and `badge_count` gates in `gates.py:331-334`
  are recorded but not used by the map graph.

**What the decomp provides, all parseable:**
- **Badge per field move**: `src/field_move_tasks.c`, where each `FieldMoves_Check<Move>` calls
  `PlayerHasRequiredBadge(…, BADGE_ID_X)`:

  | Move | Badge |
  |---|---|
  | Cut | Forest |
  | Fly | Cobble |
  | Surf | Fen |
  | Strength | Mine |
  | Defog | Relic |
  | Rock Smash | Coal |
  | Waterfall | Beacon |
  | Rock Climb | Icicle |

  `res/field/scripts/scripts_field_moves.s` is an independent cross-check: it pairs
  `FindPartySlotWithMove` with `CheckBadgeAcquired`.
- **Obstacles**: `res/field/events/*.json` objects with `OBJ_EVENT_GFX_CUT_TREE` (49, script 10000),
  `ROCK_SMASH` (590, 10001) and `STRENGTH_BOULDER` (49, 10002). Script id → field-move entry → badge.
- **Tiles**: the behaviour is the low byte of the terrain attribute.
  - Surfable comes from `sTileBehaviorFlags` (`src/map_tile_behavior.c`).
  - Waterfall and rock climb are single behaviours.
- **Gym order**: the `GiveBadge` sites in the gym scripts give badge → map. The order comes from the
  leaders' top party levels (`res/trainers/data/leader_*.json`, strictly rising 14 → 50): Coal, Forest,
  Relic, Cobble, Fen, Mine, Icicle, Beacon.
  - `generated/badges.txt` is the badge *id* order, not the gym order, so it is not used for ordering.
- **Story blockers cleared next to `GiveBadge`**: for example `FLAG_HIDE_HEARTHOME_CITY_ROUTE_209_BLOCKADE`
  (Relic), the Pastoria grunt (Fen) and the Veilstone grunts (Icicle).
  - The Route 210 Psyduck are cleared by `CheckItem ITEM_SECRETPOTION`, and the potion is given at
    Valor Lakefront.

**Decision**:
- Build a new module, `availability/story_rank.py`. It is separate from the legality reachability,
  which stays unchanged, so ledger phases don't move.
- For badge stage k = 0..8 (gym order), a tile is passable if it is:
  - non-collision land;
  - surfable, if Surf is unlocked;
  - a waterfall, if Waterfall is unlocked;
  - rock climb, if Rock Climb is unlocked;
  - and not blocked by a Cut, Rock Smash or Strength object whose move is still locked, or by a
    pre-game blocker object whose opener's rank is above k.
- Nodes are (map, tile region), joined by warps and borders.
- A map's `badges_needed` is the smallest k at which any of its regions is reached.
- It reuses the existing tile flood (`mapgraph._flood`, `_header_tiles`, `_border_tiles`) with an
  ability-aware wall test, cached per ability set.
- **Built in two steps:**
  1. Field-move obstacles and tiles.
  2. Story blockers. An opener in a script that also does `GiveBadge X` takes X's rank, and
     `CheckItem ITEM_Y` takes the rank of the map where Y is obtained, which covers the Psyduck.
- **Tie-break** within a badge rank: the option's own minimum level on that map, then hops from the
  maps already reached at stage k-1, then the map name. So Staravia's Route 209 (min 18) wins over
  Route 210 South (19), and the Sneasel maps that tie at level 33 are ordered by hops.
- **Across evolution stages** (user decision 2026-10-11): the badge rank is compared before the
  number of evolutions. So Garchomp is named from Gible in Wayward Cave B1F (levels 17–20, pre-Champion
  in the ledger) rather than Gabite on Victory Road 1F (level 41). Today's text for that run reads
  "Wild - Victory Road 1F (Gabite, grass) -> Garchomp (EVO_LEVEL)". The full order is in data-model
  "Selection order".
- **Scope**: the rank only chooses which *legal* source is named. It never makes a source legal or
  illegal. A wrong rank names a later place, never an illegal one.

**Positive controls** (tests; the expected values are decomp-derived claims, checked when the test
first runs):
- Route 201 → 0.
- Ravaged Path → 1 (Rock Smash needs Coal).
- Route 209 → 3 (Relic). Step 1 alone gives 2, so this test tells the two steps apart.
- Route 218, Canalave City and Route 220 → 5 (Surf needs Fen).
- Victory Road 1F → 8 (Waterfall on Route 223 needs Beacon).
- Each gym's own map ranks below its badge's index.
- The gym order from leader levels matches the order in which the gym maps first become reachable.

**Known gaps** (documented, not fixed):
- One-way ledges are treated as walls.
- Strength puzzles are approximated as "the boulder can be removed".
- Story gates not tied to a badge or an item (e.g. some Snowpoint access) are not modelled.
- Fog doesn't block movement and is ignored.

**Alternatives considered**:
- (A) Graph distance to the nearest gym town (rejected: water and obstacles make it wrong, e.g. Route
  220 would come out near Jubilife).
- (B) Badge-staged reachability between maps only (rejected: it misses cut trees and the rocks in Mt
  Coronet inside maps, and the story blockers that decide Route 209).
- Map level band (offered, not chosen by the user).

## R10. Trainer pop-up data and sprites

**Findings**:
- `decomp/trainers.py:41-47, 138-199` (`LEAGUE`, `load_league`) gives each first-run party in order:
  Aaron 5, Bertha 5, Flint 5, Lucian 5, Cynthia 6.
- `res/trainers/classes/<class>/front_scan.png` is 160×80, 4-bit indexed, with two 80×80 frames
  side by side. That is the same layout as the pokemon front sprites, so `with_transparent_index0`
  and the existing `.sprite-front` CSS apply.
  - `front.png` is a tall 8-bit strip with opaque separator rows, so it is not used.
  - The Cynthia frame was checked by eye. The other four were checked by header only, so a browser
    screenshot is needed.

**Decision**:
- Add a new read-only `GET /api/league`, which returns the five trainers with their key, display name
  and the party's pokemon keys in order.
- Add `GET /api/trainer-sprites/{trainer}.png`, with an allow-list of the five keys, serving
  `front_scan.png` with tRNS added and cached in memory.
- The page fetches the league once and opens the pop-up from the chart's `g.bar-group` on
  mouseenter, focus and click/tap. Escape, mouseleave and blur close it. The pop-up is clamped
  inside the viewport.

**Alternatives considered**: putting the parties into `result.json` (rejected: that would change the
report for display-only data, and the parties are fixed by the game, not by the run).

## R11. Move type colours (spec FR-022)

**Finding**: `result_view` sends only `{name, source}` per move (`result_view.py:93`). The type is
available from the `result.json` move key through `decomp/moves.py:53` `load_moves()`.

**Decision**:
- Add `type` (e.g. "Fire") to each move in the result view.
- The page sets `data-type` on the move chip and adds the type to its tooltip text, so the type is
  not shown by colour alone.
- Colours are CSS custom properties per type, with a light and a dark value. A unit test parses
  `style.css` and asserts a contrast ratio of at least 4.5:1 against the card background in both
  themes for all 17 types (positive control: the test fails on a deliberately low-contrast value).

## R12. Theme toggle, layout order, setup changes

- **Theme** (spec FR-023):
  - A button in `header.site`, which becomes a flex row, top-right.
  - The button has `aria-pressed` and an accessible name.
  - The choice is stored in `localStorage["platsim-theme"]` inside try/catch and applied as
    `data-theme` on `<html>` by a small inline script in `<head>`, so the page doesn't flash.
  - With no stored choice, the existing `prefers-color-scheme` rules apply, so the
    `test_web.py:34` assertion still holds.
  - 002's `contracts/ui.md:42, 65` ("nothing in localStorage", "dark mode via
    prefers-color-scheme") are superseded for the theme only.
  - The browser screenshot test sets the theme by clicking the toggle, because `emulate_media` no
    longer wins once a choice is stored.
- **Results order** (spec FR-019): swap `#chart` and `#team-cards` in `index.html:102-111`.
  `test_page.py:126-128` (summary and chart within 1080 px) changes to summary plus first card row.
- **Setup**:
  - Remove `#show-excluded`. The page always sends `excluded=1`.
  - The "no match" message appears only when the server returns nothing, which now means no name
    matched.
  - `#trade-help` becomes a tooltip on the trade-evolutions label, using the existing `withTip`
    pattern and `aria-describedby`.
  - Add the three new checkboxes. The fieldset legend changes from "both off by default" to "all off
    by default".
  - Every rule change re-runs the search.

## R13. Species catalogue with five options

**Finding**: the catalogue precomputes two views (trade off and on) as paired fields
(`species_catalog.py:71-80, 144-148`). Availability now depends on four options (egg moves never
changes it): trade, post-game pokemon, unobtainable, and post-game items, because item evolutions and
incense breeding go through `item_copies`.

**Decision**:
- Compute one availability table per distinct options value on first use, cached with an LRU of 16
  entries.
- Each table is built from `ledger.with_options(opts)` by the same `why()` logic.
- `SpeciesInfo` keeps the static fields (key, name, types, dex). Availability moves into a
  per-options map.
- Each new view costs the `source_options` walk over 493 species. This is measured in the plan's
  quickstart. If it is over 2 s, the default view is warmed at startup.

## R14. Code hash, generated data, version

- Any edit under `src/platsim` changes `platsim_code_hash`. Regenerating `availability.json` (needed
  by R3, R5 and R8) changes `decomp_data_hash`. Both block resuming an unfinished `state.json`.
  - All existing `runs/*/state.json` are finished (RUN-STATE, 2026-10-10). Re-check this before
    implementing.
- `tests/integration/test_extract.py:81` (`extract --check`) requires the regenerated
  `availability.json` to be committed.
- `pyproject` version goes 0.1.0 → 0.2.0, because new reports differ in source text and options
  (002 R5: the page shows the recorded version).
- `sim/` is not touched, so `sim_code_hash` is unchanged.
