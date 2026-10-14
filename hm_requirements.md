# Mandatory HM Use Before the Champion

This file lists, for Pokémon Platinum, when each HM is first needed to move the story forward and
when it is needed for the last time. Only mandatory uses count. Defog (fog) and Fly
(travel shortcut) are convenience HMs and are left out.

Generated on 2026-10-13 from the project's map model (`src/platsim/availability/story_rank.py`,
decomp commit pinned in `data/generated/manifest.json`). It has **not** been checked by playing
the game.

## Summary

| HM | Usable from badge | First mandatory | Needed for | Last mandatory use |
|---|---|---|---|---|
| **Rock Smash** (HM06) | Coal (1) | Right after badge 1 | The way north to Eterna (gym 2), and so everything after it | Before Eterna; never again |
| **Cut** (HM01) | Forest (2) | After badge 2 | Galactic Eterna Building | That building; never again |
| **Surf** (HM03) | Fen (5) | After badge 5 | Canalave (gym 6), Iron Island, Route 223 and Victory Road | **The League**, needed to the end |
| **Strength** (HM04) | Mine (6) | After badge 6 | The Mt. Coronet route to Routes 216/217 and Snowpoint (gym 7); Spear Pillar; Distortion World | Distortion World |
| **Rock Climb** (HM08) | Icicle (7) | After badge 7 | Lake Acuity, Spear Pillar, Distortion World | Distortion World |
| **Waterfall** (HM07) | Beacon (8) | After badge 8 | Route 223 and Victory Road to the League | **The League**, needed to the end |
| **Fly** (HM02) | Cobble (4) | Never | — | — |
| **Defog** (HM05) | Relic (3) | Never (left out as a convenience HM) | — | — |

**For a team built to beat Cynthia:**
- Only **Surf and Waterfall** are needed to reach the League.
- **Strength and Rock Climb** are needed through Spear Pillar and the Distortion World, which
  come before the 8th badge.
- **Rock Smash and Cut** are needed only early in the game.

**Other findings:**
- **Victory Road:** the main path needs only Surf and Waterfall. Its 25 Strength boulders and 7
  Rock Smash rocks are off the main path, according to the model.
- **Canalave Library:** the "you need Strength" check passes if you just carry the HM04 item
  (`res/field/scripts/scripts_canalave_city.s:681-689`). No team member has to know Strength
  there.

## Where each HM is obtained

| HM | Where | Kind |
|---|---|---|
| HM01 Cut | Eterna City | NPC gift |
| HM02 Fly | Veilstone City Galactic Warehouse | Item ball |
| HM03 Surf | Celestic Town (cave) | NPC gift |
| HM04 Strength | Iron Island (Riley) | NPC gift |
| HM05 Defog | Solaceon Ruins, Room 7 | Item ball |
| HM06 Rock Smash | Oreburgh Gate 1F | NPC gift |
| HM07 Waterfall | Sunyshore City | NPC gift |
| HM08 Rock Climb | Route 217 | Item ball |

These come from `data/generated/availability.json`. All of them are available before the
Champion.

## Badge needed to use each move outside battle

Parsed from `src/field_move_tasks.c` and cross-checked against
`res/field/scripts/scripts_field_moves.s`:

| Badge | Moves it unlocks |
|---|---|
| Coal (1) | Rock Smash |
| Forest (2) | Cut |
| Relic (3) | Defog |
| Cobble (4) | Fly |
| Fen (5) | Surf |
| Mine (6) | Strength |
| Icicle (7) | Rock Climb |
| Beacon (8) | Waterfall |

## Method

1. **Milestones.** These are places the main story must reach:
   - the eight gyms;
   - the Champion's room;
   - the Galactic Eterna Building, Galactic HQ, Lake Valor, Iron Island (Riley, HM04), Lake
     Acuity, Spear Pillar and the Distortion World;
   - Victory Road;
   - where HM03, HM07 and HM08 are given.
2. **Baseline.** For each number of badges held (0–8), the model floods the map with every field
   move unlocked by those badges. Each milestone gets the first badge count at which it can be
   reached.
3. **Per-HM test.** For each badge count and each HM, the flood is rerun with that HM never
   usable at that stage. It starts from Twinleaf Town plus the Pokémon Center of every town
   reached at the previous stage, which is where Fly drops you. An HM is **mandatory at a stage**
   if a milestone first reached at that stage can no longer be reached. "First" and "last" in the
   summary are the earliest and latest stages where an HM is mandatory.
4. **Control.** With nothing removed, every milestone is reachable at its baseline stage.
5. **Victory Road on its own.** The flood was started inside the League's south Pokémon Center
   (after Route 223), with each HM removed in turn. Only removing Surf or Waterfall cuts off the
   north side and the Champion's room. The League's outdoor area does not connect south to north
   without Victory Road.

Two earlier versions of this test gave wrong results and were corrected:

- **Starting every stage from Twinleaf** made Rock Smash look mandatory for badges 2–3, because
  the route crossed the Route 204 rock again.
- **Starting from every door of a visited town** placed the player behind obstacles. For
  example, the Galactic building door in Eterna hid the need for Cut.

## Limits of the model

These come from `story_rank.py`'s own list of known gaps:

- **Story order isn't fully modelled.** The Valor Lakefront roadblock is missing, so the model
  reaches Sunyshore at badge 3 and the League entrance at badge 5. In the game you get there
  after Spear Pillar. This changes when Surf and Waterfall are first needed for the League, not
  whether they are.
- **Some story gates aren't modelled.** Gates that depend on story progress rather than a badge
  or an item are missing. The Bicycle is treated as available from badge 1.
- **Strength boulder puzzles** count as solved once Strength can be used. A boulder that has to
  be pushed in a set order could add a Strength need that the model doesn't see.
- **Fog is ignored**, which matches leaving out Defog.
