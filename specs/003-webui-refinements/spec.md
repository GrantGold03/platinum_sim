# Feature Specification: Web UI Refinements

**Feature Branch**: `003-webui-refinements` (no branch created yet; work currently sits on `002-webui-redesign`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: the change list in `webui_changes.md` (repo root until removed after the merge; `git show 24df0df:webui_changes.md`), written after hands-on
testing of the 002 redesign. It covers: wording (no requirement numbers, "pokemon" not "species"),
an Elite Four / Champion hover preview, swapping the roster and the per-trainer chart, clearer
"obtained from" text, always showing excluded pokemon, allowing Munchlax/Snorlax (and Leftovers only
with them), a short "Unavailable in Platinum" reason, a hover tooltip for the trade-evolution note,
two new optional rules, type-coloured move names, and a light/dark toggle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand why a pokemon can or cannot be used (Priority: P1)

The player searches for a pokemon while building a team. Every match is shown, whether or not it
can be used. One that can't be used is crossed out, with a short reason in plain words. The player
never sees requirement numbers or the word "species".

**Why this priority**: today a search for an unavailable pokemon such as Golem says "No species
match Golem" unless a hidden checkbox is ticked. The player can't tell "doesn't exist" from "not
allowed". This is the most common confusion in testing.

**Independent Test**: start the server, type names into the search box with each rule on and off,
and read the list and its reasons.

**Acceptance Scenarios**:

1. **Given** trade evolutions are not allowed, **When** the player searches "Golem", **Then** Golem
   is listed, crossed out, with a reason naming the trade evolution from Graveler, and no "no match"
   message appears.
2. **Given** trade evolutions are allowed, **When** the player searches "Golem", **Then** Golem is
   listed as usable.
3. **Given** any search, **When** the list is shown, **Then** there is no control to show or hide
   excluded pokemon.
4. **Given** a pokemon that cannot be obtained in Platinum at all (event-only, needs another
   cartridge, or has no source in the game data), **When** it is listed, **Then** its reason reads
   exactly "Unavailable in Platinum".
5. **Given** any page state (setup, progress, results, errors, tooltips), **When** the player reads
   it, **Then** no requirement number such as "FR-005" or "FR-019" appears and the word "species"
   never appears.
6. **Given** the setup area, **When** the player hovers over or focuses "Allow trade evolutions",
   **Then** the existing explanation ("Trade evolutions need a second cartridge … before the
   Champion.") appears as a tooltip, and it is not shown as text otherwise.

---

### User Story 2 - Choose which pokemon pools are allowed (Priority: P1)

The player can widen what a run may use with three new optional rules: "Allow post-game exclusive
pokemon", "Allow post-game items and moves" and "Allow pokemon unobtainable in Platinum". All are off
by default. Munchlax
and Snorlax are now usable by default. Leftovers can be held only when one of them is on the team.

**Why this priority**: these rules change which teams are legal and what the optimizer may return,
so they matter more than layout.

**Independent Test**: tick each rule, search a pokemon it unlocks, start a quick run, and check the
run's recorded options and the team's held items.

**Acceptance Scenarios**:

1. **Given** default rules, **When** the player searches "Munchlax" or "Snorlax", **Then** each is
   listed as usable.
2. **Given** a team that includes Munchlax or Snorlax, **When** the run finishes, **Then** any team
   member may hold Leftovers.
3. **Given** a team with neither Munchlax nor Snorlax and post-game items not allowed, **When** the
   run finishes, **Then** no team member holds Leftovers. With post-game items allowed, at most one
   member holds it.
4. **Given** "Allow post-game exclusive pokemon" is off, **When** the player searches a pokemon
   obtainable only after the Champion, **Then** it is crossed out with a post-game reason. **When**
   the rule is on, **Then** it is usable.
5. **Given** "Allow pokemon unobtainable in Platinum" is off, **When** the player searches a pokemon
   with reason "Unavailable in Platinum", **Then** it is crossed out. **When** the rule is on,
   **Then** it is usable.
6. **Given** "Allow post-game items and moves" is on and "Allow post-game exclusive pokemon" is off,
   **When** the player searches a post-game-only pokemon, **Then** it is still crossed out, and a
   finished run may use post-game held items and moves on its usable pokemon.
7. **Given** a run started with any new rule on, **When** its result is shown or its report is
   opened, **Then** the rule is recorded and shown with the run's other legality options.
8. **Given** the page loads, **When** the player looks at setup, **Then** all three new rules are off.

---

### User Story 3 - Read where each team member comes from (Priority: P2)

Each team card's "obtained from" text is short and concrete. It names the evolution level or item.
It gives the earliest place the pokemon can be found and drops redundant notes.

**Why this priority**: the player needs this text to actually build the team in the game. The
current text has internal codes ("EVO_LEVEL") and noise.

**Independent Test**: open a finished run whose team has a level evolution, an item evolution, the
starter and a static encounter, and read each card.

**Acceptance Scenarios**:

1. **Given** a member that evolves by level, **When** its card is shown, **Then** the text gives
   the level (for example "Garchomp at level 48", after Gabite) and never shows "EVO_LEVEL" or any
   other internal code.
2. **Given** a member that evolves by an item (for example Weavile), **When** its card is shown,
   **Then** the item is named (for example Razor Claw, together with any other condition such as
   time of day).
3. **Given** the starter, **When** its card is shown, **Then** the text reads
   "(<pokemon name>, starter)", without "starter choice (one of three)".
4. **Given** a static encounter, **When** its card is shown, **Then** the location is shown with no
   parenthetical note.
5. **Given** a wild pokemon found in several places, **When** its card is shown, **Then** the
   earliest location in story order is used, skipping 1% encounters unless every location for that
   pokemon is a 1% encounter.

---

### User Story 4 - See who the player is up against (Priority: P2)

Hovering over an Elite Four member or Cynthia (in the per-trainer chart) shows a small pop-up. The
trainer sprite is on the left and their team's pokemon sprites are in a 3-wide by 2-tall grid on
the right. Moves are not shown.

**Why this priority**: it explains a low clear rate at a glance without leaving the page.

**Independent Test**: open a finished run, hover over and focus each of the five trainers, and
compare the pop-up with the trainer's first-run party in the game data.

**Acceptance Scenarios**:

1. **Given** a finished run, **When** the player hovers over or focuses Cynthia, **Then** a pop-up
   shows her sprite on the left and Spiritomb, Roserade, Togekiss, Lucario, Milotic and Garchomp in
   a 3×2 grid.
2. **Given** an Elite Four member with five pokemon, **When** the pop-up is shown, **Then** the
   five sprites fill the grid in party order and the sixth cell is empty.
3. **Given** the pop-up, **When** the player moves away or presses Escape, **Then** it closes.

---

### User Story 5 - Results layout, move colours and theme (Priority: P3)

In the results panel the team roster comes first and the per-trainer clear-rate chart follows it.
The export links stay at the bottom. Each move name is coloured by its type. A light/dark toggle
sits in the top-right corner.

**Why this priority**: presentation only; the other stories don't depend on it.

**Independent Test**: open a finished run in both themes and check the order of the panel, the move
colours and the toggle.

**Acceptance Scenarios**:

1. **Given** a finished run, **When** the results panel is shown, **Then** the order is: summary,
   team roster, per-trainer chart, export links.
2. **Given** a team card, **When** the moves are shown, **Then** each move name has its type's
   colour (for example Fire moves in the Fire colour), and the colour stays readable in both themes.
3. **Given** the page in any theme, **When** the player uses the toggle in the top-right corner,
   **Then** the page switches between light and dark.
4. **Given** the player chose a theme, **When** the page is reloaded, **Then** that theme is kept.
   **Given** the player never chose one, **Then** the page follows the system setting.

---

### Edge Cases

- A pokemon blocked by several reasons (for example post-game and a trade evolution): the list shows
  every reason that still applies under the current rules. Turning on one rule must not make a
  pokemon usable while another reason still blocks it.
- Snorlax with no own encounter: it is usable through Munchlax (friendship evolution). Its
  "obtained from" text names Munchlax and how it evolves.
- Leftovers on a team with Munchlax/Snorlax: several members may hold Leftovers. Each Munchlax caught
  holds one, so there's no fixed count. (Assumption; see Assumptions.)
- Munchlax honey trees depend on the player's Trainer ID, so not every save can find Munchlax on
  every tree. The text must not promise a specific tree. It names honey trees as the source.
- A 1%-only pokemon: the 1% location is used, since nothing else exists.
- Runs finished before this feature, viewed in the picker: their recorded text and options are shown
  as recorded. Each web run that has a result is also re-rendered once into a new run that the picker
  lists, marked "(re-rendered)", so the new text is available. The original run is never modified. Text that came from the report itself (for example a warning that contains "(FR-019)")
  must still have the requirement number removed on the page.
- The trainer pop-up on a touch screen or keyboard: it opens on focus or tap, not only on mouse hover.
- A tooltip or pop-up near the screen edge stays fully on screen.
- A run whose result has no per-trainer data: there is no chart, so there is no pop-up, and the page
  does not error.

## Requirements *(mandatory)*

### Functional Requirements

**Wording**

- **FR-001**: No text the page shows (labels, help, tooltips, reasons, status and error messages,
  and text taken from a run's report) may contain a requirement id (a pattern such as `FR-` or
  `SC-` followed by digits). Report-sourced text is cleaned when it is shown; the report files keep
  it.
- **FR-002**: The word "species" (any case, singular or plural) MUST NOT appear in any text the page
  shows. "Pokémon" (with the accent) is used instead, and the unaccented spelling "pokemon" MUST
  NOT appear in page text either (user follow-up, 2026-10-11). Data keys, URLs and file contents are
  not page text and are out of scope.

**Pokemon list and reasons**

- **FR-003**: The "Show excluded species (with the reason)" control MUST be removed. Search results
  MUST always include pokemon that can't be used, crossed out with their reason.
- **FR-004**: The "no match" message MUST appear only when no pokemon's name matches the search.
- **FR-005**: A pokemon that cannot be obtained in Platinum at all (event-only, needs another
  cartridge, or no source in the game data) MUST have the reason "Unavailable in Platinum" and
  nothing more.
- **FR-006**: The other reasons (trade evolution, post-game only, pre-evolution unavailable) MUST
  stay short plain sentences without requirement ids.
- **FR-007**: The existing trade-evolution explanation MUST be shown as a tooltip when the "Allow
  trade evolutions" option is hovered over or focused, and MUST NOT be shown as text otherwise.

**Rules**

- **FR-008**: Munchlax and Snorlax MUST be usable team members under the default rules. Munchlax's
  honey-tree encounters MUST count as a source.
- **FR-009**: Leftovers MUST be an allowed held item for every team member when Munchlax or Snorlax
  is on the team. Without them, Leftovers MUST NOT be allowed, except that when "Allow post-game
  items and moves" is on, the single post-game Leftovers (the Victory Road item ball) counts as one
  copy that one member may hold. The legality validator MUST
  enforce this rule independently of the optimizer.
- **FR-010**: Setup MUST offer "Allow post-game exclusive pokemon", off by default. When it is on,
  pokemon whose only sources are after the Champion (including sources that need the National Dex)
  MUST be usable. This rule unlocks pokemon only; it does not unlock post-game items, TMs or move
  tutors.
- **FR-010a**: Setup MUST offer a separate rule, "Allow post-game items and moves", off by default.
  When it is on, items, TMs and move tutors that can only be obtained after the Champion MUST count
  as sources for held items and moves. It is independent of FR-010: either rule can be on without
  the other.
- **FR-011**: Setup MUST offer "Allow pokemon unobtainable in Platinum", off by default (allowed by
  constitution v1.2.0, Principle III). When it is
  on, pokemon with the reason "Unavailable in Platinum" MUST be usable. Their moves are still
  limited to what they can learn in the game data.
- **FR-012**: All three new rules MUST be recorded in each run's report and shown in the results summary
  with the existing legality options, the same way the trade-evolution and egg-move options are.
  Like the existing options, they MUST be available on the command line as well as on the page.
- **FR-013**: The pokemon list MUST update its usable/crossed-out state as soon as any rule changes,
  as it already does for trade evolutions.

**"Obtained from" text**

- **FR-014**: Level evolutions MUST name the level. Item evolutions MUST name the item. Other
  evolutions MUST name their condition in plain words (for example friendship, time of day, a
  place). No internal code (such as `EVO_LEVEL` or `ITEM_`) may appear.
- **FR-015**: The starter MUST read "(<pokemon name>, starter)".
- **FR-016**: A static encounter MUST show its location with no parenthetical note.
- **FR-017**: When a pokemon has several wild locations, the text MUST use the earliest one in story
  order, leaving out 1% encounters unless all of its locations are 1% encounters. This applies across
  evolution stages. If an earlier evolution can be caught earlier in the story, that catch is named
  (e.g. Garchomp from Gible in Wayward Cave B1F, not from Gabite on Victory Road), provided the source
  is legal at the member's level. A Day Care egg is named only when no catch qualifies.
- **FR-018**: The new "obtained from" text MUST be produced where the source text is generated, so
  the report files (JSON report, spreadsheet, CSV) of new runs and the page show the same text.
  Earlier runs keep their recorded text unless they are re-rendered with the existing source-text
  re-render command. For a given request, the chosen team's sets and every battle number MUST stay
  the same, unless the team includes Munchlax or Snorlax, or a new rule is on. Fields that may
  change: the source text, the named source (`Build.source`), the recorded version, and the five
  recorded rule keys.

**Results panel**

- **FR-019**: The results panel order MUST be: summary, team roster, per-trainer clear-rate chart,
  export links.
- **FR-020**: Hovering over, focusing or tapping a trainer in the per-trainer chart MUST open a
  pop-up. It shows the trainer's sprite on the left and their first-run party's pokemon sprites in a
  3-wide by 2-tall grid, in party order. The pop-up MUST NOT show moves, levels or items. Escape or
  moving away closes it.
- **FR-021**: The trainer and pokemon sprites MUST come from the local game data, so they work
  offline.
- **FR-022**: Each move name MUST be shown in its type's colour, with enough contrast to read in
  both themes. Type is still conveyed by text (for example in the move's tooltip), not by colour
  alone.

**Theme**

- **FR-023**: A light/dark toggle MUST sit in the top-right corner. It defaults to the system
  setting. The player's choice MUST be kept across reloads in the same browser.

**Unchanged**

- **FR-024**: Everything the 002 redesign specified and this list doesn't change MUST keep working,
  with the 002 tests still passing (updated only where this spec changes the expected text or
  order).

### Key Entities

- **Legality rules**: the run's options. These are the existing trade-evolution and egg-move options
  plus the three new ones (post-game exclusive pokemon, post-game items and moves, pokemon
  unobtainable in Platinum). They are
  recorded in the run's report.
- **Pokemon availability**: for each pokemon, whether it is usable under the current rules, and the
  short reason when it isn't.
- **Source description**: the plain-language "obtained from" text for a team member. It covers the
  earliest location, the evolution level/item/condition, the starter, or a static encounter.
- **Trainer preview**: an Elite Four member or Cynthia, their sprite, and their first-run party in
  order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An automated scan of every page state (setup, search results with all rule
  combinations, progress, each stored run's result, error messages) finds zero requirement ids and
  zero occurrences of "species".
- **SC-002**: Searching for any pokemon by its full name returns that pokemon, usable or crossed out,
  for every pokemon in the game data and every rule combination. The "no match" message appears 0
  times.
- **SC-003**: For each pokemon rule, every pokemon blocked only by that rule becomes usable when the rule
  is turned on. With all rules off, the set of usable pokemon is the same as today's, except Munchlax
  and Snorlax are added.
- **SC-003a**: With "Allow post-game items and moves" on, at least one held item or move that is
  rejected with the rule off is accepted (a positive control). With it off, the set of accepted
  held items and moves is the same as today's, except for the Leftovers rule.
- **SC-004**: Across a team-legality test set, Leftovers is accepted on every team containing
  Munchlax or Snorlax, rejected on every team without them under the default rules, and accepted on
  at most one member when only post-game items allow it.
- **SC-005**: Across all teams in new runs and in re-rendered runs, no "obtained from" text
  contains an internal code, and each one follows FR-014–FR-017.
- **SC-006**: The trainer pop-up shows the right sprites for all five trainers (checked against the
  game data) and opens by mouse, keyboard and touch.
- **SC-007**: The theme toggle switches the theme in one click and is kept after a reload.

## Assumptions

- This is a follow-up to 002 and builds on its page. It goes in before 002 is merged into `main`,
  either on the 002 branch or on a branch made from it (the user decides).
- The 24 dual-slot pokemon can be caught with a GBA cartridge in a DS or DS Lite, but are labelled
  "Unavailable in Platinum" at the user's request (2026-10-11).
- "Unavailable in Platinum" covers the current reasons "event-only or needs another cartridge" and
  "no source in the game data". A pokemon blocked only because its pre-evolution is blocked keeps a
  "evolves from X" reason.
- Post-game reasons include the current "needs the National Dex" reason. National Dex sources become
  usable when "Allow post-game exclusive pokemon" is on.
- Leftovers: wild Munchlax and Snorlax always hold Leftovers in the game data (both held-item slots).
  Several Munchlax can be caught, so any number of members may hold it once Munchlax or Snorlax is on
  the team. No other source is recognised; the rule is "on the team", not "caught at some point".
- Reversing the earlier Munchlax exclusion (feature 001's project rule) is intended. The 001 spec and
  the availability rules are updated to match.
- "Earliest location" is story order by badge gates: a map ranks by how many gym badges the player
  needs before they can reach it, derived from the game data (field-move badges, obstacles, water and
  story blockers). Ties are broken as in the data model's selection order. It changes which legal source is named, never which sources are legal.
- Type colours are a design choice for the page, not game data, so they don't come from the decomp.
  They are standard-looking type colours adjusted for contrast in each theme.
- The theme choice is a per-browser convenience; it is not saved on the server.
- The "Unchanged" requirement covers the 002 report-file rule only to the extent FR-018 allows.
- "Post-game items and moves" uses the availability data's existing post-game phase for items, TMs
  and tutors. National Dex sources count as post-game.

## Clarifications

### Session 2026-10-11

- Q: What should "Allow post-game exclusive pokemon" unlock? → A: Make pokemon and resources two
  separate options. The pokemon rule unlocks pokemon only (FR-010); a separate "Allow post-game
  items and moves" rule unlocks post-game items, TMs and tutors (FR-010a). Both are off by default.
- Q: With post-game items allowed, does the post-game Victory Road Leftovers count without Munchlax
  or Snorlax? → A: Yes, as one copy (FR-009).
- Q: When a pokemon can be caught directly or as an earlier evolution, which source is named? → A:
  The earliest location, across evolution stages (FR-017). Day Care eggs still come last.
- Q: How is "earliest location" ordered, given the code has no story order? → A: By badge gates, the
  number of badges needed to reach the map (Assumptions).
- Q: Should the new "obtained from" text also go into the report files of new runs? → A: Yes. The
  text is fixed where it is generated, so reports and the page agree; old runs keep their text
  unless re-rendered (FR-018).
