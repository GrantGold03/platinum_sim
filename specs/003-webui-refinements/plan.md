# Implementation Plan: Web UI Refinements

**Branch**: `002-webui-redesign` (003 is built on the 002 branch at the user's request, 2026-10-11) |
**Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-webui-refinements/spec.md` (source:
`webui_changes.md`).

## Summary

The user tested the 002 page and asked for twelve changes. They fall into three groups.

**Page-only**
- Wording: no requirement ids, and "pokemon" instead of "species".
- Roster before the chart.
- A trainer pop-up with sprites.
- Move names coloured by type.
- A theme toggle.
- The trade-evolution note becomes a tooltip.
- The show-excluded control is removed.

**Rules, which change legality**
- Munchlax and Snorlax are allowed. Leftovers is allowed only with them on the team (or one post-game
  copy).
- Three new optional rules: post-game pokemon, post-game items and moves, unobtainable pokemon.

**Report text**
- "Obtained from" names levels, items and conditions in plain words.
- It names the earliest legal location by badge gates, skipping 1% encounters.

**Approach**
- The rules go through `LegalityOptions` and the ledger's single phase filter `Ledger.pre()`. The
  validator enforces them independently of the optimizer (Constitution III).
- The source text is reformatted at `SourceOption.detail`, so the reports and the page agree (spec
  FR-018).
- Encounter rates and honey-tree levels are parsed from the decomp encounter code.
- Story order is a new badge-staged tile reachability module. It only chooses which legal source is
  named.
- Old reports are not rewritten; the page cleans their text when showing it.

## Technical Context

**Language/Version**: Python 3.14.7 (server, extraction, optimizer). Browser JavaScript (ES2020, no
build step).

**Primary Dependencies**:
- Existing: FastAPI and uvicorn. Standard library `struct` and `zlib` for PNG.
- Dev: pytest, plus `playwright` (system Chrome) for the browser tests.
- No new dependency.

**Storage**:
- `data/generated/availability.json` is regenerated: rates, honey levels, the `unreachable` reason, and
  the Munchlax change.
- New: `data/generated/story_rank.json`, written by `platsim extract` and checked by `extract --check`. It is
  loaded at runtime, so a web job pays no extra build cost.
- `runs/<job>/` files gain three keys in `provenance.legality_options`, and new source text.
- In the browser, `localStorage["platsim-theme"]`.

**Testing**:
- pytest unit and integration tests: legality options, availability controls, validator, source
  preference, web, result view, sprites.
- Playwright browser tests (`-m browser`).
- The full suite (about 2.5 h) runs before merge.

**Target Platform**: Linux, local. The server binds to 127.0.0.1. Desktop and phone-width browsers.

**Project Type**: a local web UI on top of the existing Python CLI package.

**Performance Goals**:
- A species search under a new rule combination answers within 2 s on first use and instantly after
  that (cached per options value).
- Story ranks build once per process, sharing the about 35 s ledger build. The target is under 60 s
  extra; the result is cached per process.

**Constraints**:
- Offline.
- Decomp is ground truth: rates, honey levels, the field-move to badge table, gym order and obstacles
  are all parsed, not typed.
- `sim/` is unchanged (`sim_code_hash` stays the same).
- Old report files are not modified.
- Default-option job fingerprints are unchanged (research R1).

**Scale/Scope**:
- About 12 source files changed.
- 3 new modules: `availability/story_rank.py`, `web/display_text.py`, and a league/trainer-sprite part
  of `web/sprites.py`.
- 3 static files.
- About 10 test files changed or added.
- One regeneration of the generated data.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I. Decomp is ground truth | PASS | All of these are parsed from the decomp: slot rates (`wild_encounters.c`, `honey_tree.c`), honey levels, the field-move to badge table (`field_move_tasks.c`), obstacles (`res/field/events`), tile behaviours (`map_tile_behavior.c`), badge sites (gym scripts) and gym order (leader party levels). Parties and trainer sprites are read from `res/trainers`. Type colours are page styling, not game data. The synthetic level-1 source for "unobtainable" pokemon is a project rule and is labelled as such, not presented as game data (R4). |
| II. Showdown is the battle engine | PASS | `sim/` is not changed. Leftovers is already modelled in the sim and the Showdown engine. |
| III. In-game legality (v1.2.0) | PASS | Constitution amended to 1.2.0 on 2026-10-11 (analysis C1): an explicit, off-by-default rule may widen the output if the validator enforces it, the report files label each affected source with the rule, and the legality options record it. All three new rules meet this: they are off by default; they are enforced by the validator, independently of the optimizer (R2, R5); "Unavailable in Platinum (allowed by rule)" or the post-game location labels each affected source; and the five options are recorded. The Leftovers team rule is enforced the same way. |
| IV. Reproducible, statistically honest | PASS | Seeds and ordering are unchanged. New reports record all five options and version 0.2.0. Old reports are untouched; the page cleans their text only when showing it, and never changes provenance. Every win rate on the page keeps its interval and battle count one hover away: the trainer pop-up header carries the 002 tooltip text. Web vs CLI byte-identical check (V7). |
| V. Verified claims, positive controls | PASS | Each negative has a control: entries on unreachable maps stay locked while reachable post-game sources unlock, including the Frontier exchange that the first research pass missed (R3); cache-keying fails before the fix (R2); 1%-rule sums (R8); the badge ranks of Route 201, Ravaged Path, Route 209 and Victory Road distinguish the two story-rank steps (R9); the contrast test fails on a seeded bad value (R11); the wording scan hits on the 002 page (V1). |
| Technical constraints | PASS | Offline. The ROM is unused. The generated data is regenerated by `platsim extract` and checked by `extract --check`. |
| Workflow gates | PASS | Spec Kit flow. The local suite must be green, and the full suite is recorded before merge. RUN-STATE is updated as work lands. |

**Post-design re-check (after Phase 1)**: still PASS. Two pieces of added complexity are justified
below. One amendment to an earlier spec is needed: 001 FR-006a (the Munchlax exclusion) is superseded
by 003 FR-008/FR-009. That is a spec change, not a constitution change.

## Project Structure

### Documentation (this feature)

```text
specs/003-webui-refinements/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R14
├── data-model.md
├── quickstart.md        # V1–V8
├── contracts/
│   ├── http-api.md
│   └── ui.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/platsim/
├── legality/
│   ├── models.py            # + 3 options; to_dict(compact=) (R1)
│   ├── movesources.py       # detail text rewrite (R7); `outside_platinum` kind (R4); rate/story_rank
│   │                        #   on SourceOption; option_sort_key change; breed_mothers cache key (R2)
│   └── validator.py         # LEFTOVERS_NEEDS_MUNCHLAX team rule (R5)
├── availability/
│   ├── ledger.py            # option-aware pre(); species_sources cache key; EXCLUDED_SPECIES emptied;
│   │                        #   `unreachable` reason (R2, R3, R5); rate kept through _merge_wild (R8)
│   ├── sources.py           # honey levels + rates parsed from the decomp (R5, R8); Battle Frontier
│   │                        #   exchange as a post-game item source (R3)
│   ├── mapgraph.py          # post-game-edges reachability pass (R3); ability-aware wall test hook (R9)
│   └── story_rank.py        # NEW: badge-staged tile reachability → per-map rank (R9)
├── decomp/                  # small parsers if needed: field-move badges, tile behaviour flags
├── optimizer/
│   ├── candidates.py        # Leftovers candidate gated on team; remove Munchlax rule; reason text
│   └── resources.py         # Leftovers team copies in realize
├── cli.py                   # 3 new flags
├── report/json_report.py    # QUICK_WARNING without internal ids (new runs only)
├── optimizer/run.py         # the indistinguishable warning without "(FR-019)" (new runs only)
├── explain.py               # Munchlax lines
└── web/
    ├── app.py               # options loop from LegalityOptions; /api/league; trainer sprite route; texts
    ├── display_text.py      # NEW: clean() for passed-through text (R6)
    ├── result_view.py       # move type; clean(); five options
    ├── species_catalog.py   # per-options availability tables (R13); new reasons
    ├── sprites.py           # trainer sprites (front_scan.png) with allow-list (R10)
    └── static/{index.html, app.js, style.css}   # contracts/ui.md

data/generated/availability.json     # regenerated
pyproject.toml                       # 0.1.0 → 0.2.0
specs/001-champion-team-optimizer/spec.md   # FR-006a superseded note
specs/002-webui-redesign/contracts/ui.md    # theme/localStorage note superseded

tests/
├── unit/test_legality_options.py         # new options, compact fingerprint, catalogue per options
├── unit/test_validator.py                # Leftovers team rule, post-game tutor control
├── unit/test_source_text.py              # NEW: leak scan, evolution wording, starter/static/trade text
├── unit/test_story_rank.py               # NEW: positive-control ranks (R9)
├── unit/test_type_colours.py             # NEW: contrast both themes (R11)
├── unit/test_source_preference.py        # updated selection order
├── integration/test_availability_controls.py  # Munchlax, Leftovers, honey levels, rates, unreachable
├── integration/test_explain.py           # Munchlax lines
├── integration/test_web.py               # options, reasons, no show-excluded, league route
├── integration/test_web_result_view.py   # move type, cleaned text, five options
├── integration/test_web_sprites.py       # trainer sprites
└── browser/test_page.py                  # order, pop-up, colours, theme, wording scan
```

**Structure Decision**: keep the single-package layout. Story rank is its own module beside the
map graph, so the legality reachability (and the ledger phases) stay exactly as they are. Display
cleaning is one small web module, so no report writer has to know about the page.

## Delivery order (each slice can be tested on its own)

1. **Wording and setup** (US1, P1):
   - `display_text.clean()`, the static wording, the new reasons and "Unavailable in Platinum".
   - The show-excluded control removed, and the trade-evolution tooltip.
   - Page only, plus the reason texts. No legality change.
2. **Rules** (US2, P1):
   - Option plumbing (R1) and the cache-key fixes (R2).
   - The unreachable pass (R3).
   - The three rules, Munchlax and honey levels, and the Leftovers team rule (R5).
   - The per-options catalogue (R13).
   - Regenerate the data.
3. **Source text** (US3, P2):
   - The text rewrite (R7), the rates and the 1% rule (R8).
   - Story rank, step 1 (field moves), then step 2 (story blockers) (R9).
   - The selection-order change, and the re-render check on the fixture.
4. **Trainer pop-up** (US4, P2): `/api/league`, the trainer sprites, and the pop-up on the chart.
5. **Layout, colours, theme** (US5, P3): the order swap, move types and colours with the contrast
   test, and the theme toggle.
6. **Close-out**:
   - The version bump and the amendment notes on the 001 and 002 specs.
   - The web and browser suites, then the full suite, recorded in `validation-log.md`.
   - A real quick job, web vs CLI, byte-identical.

## Risks (raised once, not blocking)

- **Story rank is the largest item** (about 400–600 lines, R9) and has known gaps (ledges, Strength
  puzzles, some story gates). It only affects which legal place is named, so a gap gives a later
  place, never an illegal one.
- **Selection order changes `Build.source` on re-render** for some members. This is allowed by the
  re-render contract (sets, validity and battle numbers are unchanged). The optimizer's level floors
  are untouched, so optimization results should not change; V7 checks this.
- **Regenerating `availability.json` changes `decomp_data_hash`, and any `src/platsim` edit changes
  `platsim_code_hash`.** Either blocks resuming an unfinished `state.json`. All are finished today
  (RUN-STATE, 2026-10-10); this is re-checked before the first edit.
- **"Unobtainable" teams are not cartridge-legal by design.** The labels say so in every report.
- **The trainer `front_scan.png` frames were checked by eye only for Cynthia** (R10). The browser
  screenshots cover the other four.
- **Leftovers changes optimizer behaviour** for teams with Munchlax or Snorlax, through a new item
  candidate. No existing run uses Munchlax, so earlier results are not affected.
- **Honey-tree levels change source text and options** for Aipom, Burmy, Cherubi, Combee and
  Heracross (and their evolutions). Today they resolve only as a level-1 Day Care egg. After the fix
  they also have a wild source at levels 5–15, and the text names the honey tree. Their level floor
  stays 1, because breeding is still legal (analysis H3, checked live on 2026-10-11).
- **Old runs are re-rendered into new run folders** (T042a, analysis H1). The originals are never
  written, and their sha256 is checked against T001.

## Complexity Tracking

| Added complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Badge-staged tile reachability (`story_rank.py`) | The user chose badge gates for "earliest location" (spec FR-017, Clarifications 2026-10-11) | Map level band: offered, not chosen. Graph distance: wrong, because the current graph walks on water and through obstacles (R9). Map-to-map badge edges: miss in-map cut trees and rocks, and the Route 209 blockade. |
| Availability tables per options value (LRU) | Four options now change which pokemon are usable (R13) | Paired fields per option (today's design) would need 16 field sets; precomputing all 16 at startup costs time for combinations nobody uses. |
| A second reachability pass with post-game edges | "Post-game" must not unlock maps that can never be entered (R3) | A hand list of unused maps is hand-typed game data (Constitution I). |
