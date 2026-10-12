# Data Model: Web UI Refinements (003)

Only what changes is listed. Everything else is as in `specs/002-webui-redesign/data-model.md` and
the 001 data model.

## LegalityOptions (changed)

`src/platsim/legality/models.py`

| Field | Type | Default | New | Effect |
|---|---|---|---|---|
| `allow_egg_moves` | bool | False | | unchanged |
| `allow_trade_evolutions` | bool | False | | unchanged |
| `allow_post_game_pokemon` | bool | False | yes | POST acquisition entries count (including National Dex). Unreachable maps never count (research R3). |
| `allow_post_game_items` | bool | False | yes | POST item, TM and tutor entries count. Unreachable maps never count. |
| `allow_unobtainable_pokemon` | bool | False | yes | NEVER(`other_cartridge`) acquisition entries count. Species with no entry get a synthetic level-1 `outside_platinum` source (R4). |

- `to_dict()` returns all five keys. This is written to `provenance.legality_options`.
- `to_dict(compact=True)` leaves out the three new keys while they are False. It is used only by
  `job_fingerprint`, so the default output directories of existing jobs stay the same (R1).
- `from_dict()` accepts any subset of the five keys; missing keys are False. Unknown keys are still
  rejected.

## Ledger entry (changed)

`src/platsim/availability/sources.py` `Entry` and `data/generated/availability.json`

| Field | Change |
|---|---|
| `rate_percent` | NEW, `int | None`. The summed encounter rate of this species for this (map, method) after `_merge_wild`. Wild slots and honey tree only; None for other kinds. Parsed from `wild_encounters.c` and `honey_tree.c` (R8). |
| `level` (honey tree) | Was None. Now 5–15, parsed from `wild_encounters.c` (R5). |
| `detail` (honey rare) | No C identifier. |
| phase reason `unreachable` | NEW. A POST entry on a map that is not reachable even with post-game edges allowed (R3). No rule admits it. |

Project rule: `EXCLUDED_SPECIES` becomes empty. The 42 Munchlax `project_rule` NEVER entries become
PRE (honey trees) or follow their encounter's phase.

## Map story rank (new)

A per-map integer: the number of gym badges needed to reach the map. Lower means earlier. Derived
from the decomp (research R9). It is used only to choose which legal source is named, and is not
part of the legality rules.

| Field | Type | Notes |
|---|---|---|
| `map_header` | str | MAP_HEADER_* |
| `badges_needed` | int 0–8, or None | None means not reachable before the Champion |
| `hops` | int | hops from the maps reached at the previous badge stage; breaks ties |

## SourceOption (changed)

`src/platsim/legality/movesources.py`

| Field | Change |
|---|---|
| `kind` | New value `outside_platinum` (synthetic, R4). It ranks after every real kind. |
| `detail` | Rewritten in plain words (research R7). It never contains an internal constant. |
| `rate_percent` | NEW. The entry's rate, used for the 1% rule. |
| `story_rank` | NEW. `(badges_needed, option min_level, hops, map name)` for the option's map. Non-wild kinds use their map's rank. |

**Selection order** (`option_sort_key`), user decision 2026-10-11: the earliest location wins across
evolution stages. Only feasible options are considered, and they are ordered by:
1. `move_cost` (as today; the option must support the build's moves);
2. Day Care egg last;
3. "1%-only" (False first);
4. `badges_needed` of the option's first map;
5. class rank (own < pre-evolution < NPC trade);
6. number of evolution stages;
7. `min_level`;
8. hops;
9. the id.

Example: Garchomp is named as "Wild - Wayward Cave B1F (Gible, grass) -> Gabite at level 24 ->
Garchomp at level 48" rather than the Victory Road Gabite.
- `min_level` is no longer a tie-break. It stays a feasibility filter: an option is only picked if
  its `min_level` is at or below the build's level (`resources.py:198`).
- Level floors (`_floor_cached`) still use the minimum over all options, so the optimizer's level
  search does not change.

## Species availability (changed)

`src/platsim/web/species_catalog.py`

- `SpeciesInfo` keeps only the static fields: key, const, name, types, dex.
- `Availability(options)` is a table, cached per distinct options value (LRU 16), mapping each species
  to `{available, reason, reason_code, note?}`.

| reason_code | Shown reason |
|---|---|
| `trade_evolution` | "Evolves from <pokemon> by trade (needs a second cartridge)" |
| `trade_evolution_unavailable` | "Evolves from <pokemon> by trade; <what's missing>" |
| `post_game` | "Post-game only (<up to 3 places>)" |
| `national_dex` | "Post-game only (needs the National Dex)" |
| `unavailable` | "Unavailable in Platinum" (was `unobtainable` and `no_source`). Also used when every entry is on a map that can never be entered (`unreachable`). |
| `pre_evolution_unavailable` | "Evolves from <pokemon>, which is not available (<its reason>)" |

The `excluded` code is removed. A reason never contains a requirement id or the word "species".

## Team rule: Leftovers (new)

| Team contains | Leftovers copies |
|---|---|
| Munchlax or Snorlax | unlimited |
| neither, post-game items off | 0 |
| neither, post-game items on | 1 (Victory Road item ball) |

Violation code: `LEFTOVERS_NEEDS_MUNCHLAX`, from the validator's team-level pass.

## Result view (changed)

`src/platsim/web/result_view.py`

- `team[i].moves[j]` gains `type`, e.g. "Fire", from `load_moves()`.
- `summary.legality_options` is passed through. Missing new keys read as False. Old runs have only
  two keys, or null.
- Every shown text field (warnings, obtained_from, move source, ability text, status reason) goes
  through `display_text.clean()`.

## League (new, read-only)

From `decomp/trainers.py` `load_league()`, in the order Aaron, Bertha, Flint, Lucian, Cynthia.

```text
{ "trainer": "cynthia", "name": "Cynthia",
  "sprite": "/api/trainer-sprites/cynthia.png",
  "party": ["spiritomb", "roserade", "togekiss", "lucario", "milotic", "garchomp"] }
```

The party lists pokemon keys only: no levels, moves or items (spec FR-020).

## Theme preference (new, browser only)

`localStorage["platsim-theme"]` is `"light"` or `"dark"`. When it is missing, the page follows
`prefers-color-scheme`. Reading and writing it is wrapped in try/catch. It is never sent to the
server.
