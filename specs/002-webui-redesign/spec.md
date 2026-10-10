# Feature Specification: Web UI Redesign

**Feature Branch**: `002-webui-redesign`

**Created**: 2026-10-09

**Status**: Implemented on branch `002-webui-redesign` (2026-10-10); awaiting user testing before merge

**Input**: User description: the user's change list (an uncommitted note, folded in here in full), covering
layout, runs and progress, team results, the result summary, and options for the local web UI
started by `platsim serve`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a result at a glance (Priority: P1)

A player opens the page after a run has finished. On the right side they see the most recent
run: a short summary (verdict, clear rate, final level with its level gap, and the run's
settings), one entry per team member with its sprite, and a chart of the clear rate against
each Elite Four member and Cynthia. Values that never change between runs (nature, IVs, EVs)
and bookkeeping details (ability choice code, held-item source, move-source columns, policies,
objective, Cynthia win rate) are not shown. The source of a move appears when the player
hovers over that move.

**Why this priority**: reading the result is the reason for running the tool. Today the result
is a 20-column text table and a long summary list, and the most useful signal (which trainer is
the bottleneck) is missing.

**Independent Test**: start the server against a runs directory that contains one finished
job, open the page, and check the right panel against that job's `result.json`, with no new
job started.

**Acceptance Scenarios**:

1. **Given** a finished run, **When** the page loads, **Then** the result panel shows that run's
   verdict, its clear rate as a single percentage (no interval or run count shown inline), and the final
   level as one line in the form "58.23 (level gap of 4)".
   **When** the player hovers over or focuses the clear rate, **Then** its 95% interval and
   run count appear (for the fixture run: "95% interval 84.9–87.9% · 2,000 runs").
2. **Given** a finished run, **When** the page loads, **Then** no Cynthia win rate, policies,
   objective, nature, IVs, EVs, ability-choice code, held-item source or move-source column is
   visible.
3. **Given** a team member whose ability was a statistical tie between its two abilities,
   **When** its entry is shown, **Then** the ability reads "<Ability1>/<Ability2> (no
   significant difference)", for example "Keen Eye/Tangled Feet (no significant difference)".
4. **Given** a team member with a single ability, or with an ability that was chosen because it
   performed better, **When** its entry is shown, **Then** only that ability's name is shown.
5. **Given** any team member's move, **When** the player hovers over it or focuses it with the
   keyboard, **Then** the move's source is shown (for example "TM38 - Shop - Veilstone Store 3F
   (unlimited)").
6. **Given** a finished run, **When** the page loads, **Then** a bar chart shows the clear rate
   for Aaron, Bertha, Flint, Lucian and Cynthia, in that order, each with its 95% interval.
7. **Given** a finished run, **When** the page loads, **Then** each team member is shown with
   its sprite, species name, start level, expected final level, ability, held item, the way it
   is obtained, and its four moves.
8. **Given** a finished run, **When** the page loads, **Then** the four downloads (spreadsheet,
   CSV, JSON report, Showdown team) remain available.

---

### User Story 2 - Set up and start a run from one side of the screen (Priority: P1)

The left side of the screen holds everything needed to start a run: legality options, species
search, the team, the minimum clear rate, the budget, and the seed. The species list stays
hidden until the player types in the search box. When a species is added to the team, its
sprite is shown next to its name. The budget can be chosen (quick, standard or thorough), and
the seed
explanation appears when the player hovers over the word "Seed".

**Why this priority**: it is the other half of the core loop. The two-column split lets the
player change the team while the previous result is still visible.

**Independent Test**: load the page with no runs, build a six-member team using the search,
choose a budget, and start a run. Check the submitted request carries the chosen budget.

**Acceptance Scenarios**:

1. **Given** a wide screen, **When** the page loads, **Then** run setup is in the left column
   and results are in the right column.
2. **Given** an empty search box, **When** the page loads, **Then** no species list is shown.
3. **Given** the player types one or more characters, **When** the search answers, **Then**
   matching species are listed. **When** the box is cleared again, **Then** the list hides.
4. **Given** the player adds a species, **When** the team updates, **Then** that slot shows the
   species' sprite next to its name.
5. **Given** the budget control, **When** the player picks "thorough" and starts a run, **Then**
   the run uses the thorough budget, and the result shows "thorough" as its budget.
6. **Given** the budget control, **When** the player has not changed it, **Then** it shows the
   default budget (standard).
7. **Given** the seed field, **When** the player hovers over (or focuses) the word "Seed",
   **Then** a short explanation appears. It says that the seed fixes the random battles, that the
   same team, options and seed give the same result, and that a different seed gives an
   independent sample. **When** the pointer or focus leaves, **Then** it hides again. The
   explanation is not shown otherwise.

---

### User Story 3 - Follow a running job and cancel it (Priority: P2)

While a job is running or queued, a progress section shows the elapsed time, an estimated time
remaining, the current stage, and a Cancel button. When nothing is running, the progress
section is not shown.

**Why this priority**: runs take minutes to hours. The player needs to know how long is left
and to be able to stop a run started with the wrong team without restarting the server.

**Independent Test**: start a run with the quick budget, watch elapsed time and ETA update,
press Cancel, and check the job ends as cancelled and the next queued job (if any) starts.

**Acceptance Scenarios**:

1. **Given** no job is queued or running, **When** the page loads, **Then** no progress section
   is shown.
2. **Given** a job is running, **When** the page is open, **Then** the progress section shows
   elapsed time, which increases at least once per second, and the current stage.
3. **Given** a running job whose remaining work can be estimated, **When** progress updates,
   **Then** an ETA is shown. **Given** the estimate is not yet possible, **Then** the ETA reads
   "estimating…" rather than a guessed number.
4. **Given** a running or queued job, **When** the player presses Cancel and confirms, **Then**
   the job stops, its status becomes "cancelled", no result is shown for it, and the next
   queued job starts.
5. **Given** a job finishes or is cancelled, **When** the page next updates, **Then** the
   progress section disappears, and a finished job's result appears in the result panel.

---

### User Story 4 - Look at earlier runs (Priority: P2)

The result panel shows the most recent run by default. A dropdown lists earlier runs, and
picking one shows its result in the same panel.

**Why this priority**: comparing teams means going back to earlier results. The server already
keeps them, but the page cannot show them.

**Independent Test**: with two or more finished jobs in the runs directory, load the page,
check the newest is shown, pick an older one from the dropdown, and check the panel matches
that job.

**Acceptance Scenarios**:

1. **Given** several finished runs, **When** the page loads, **Then** the most recent finished
   run is shown, and the dropdown lists the runs newest first, each labelled with the date and
   time, its six species, and its verdict or status.
2. **Given** the dropdown, **When** the player picks an earlier run, **Then** the result panel
   shows that run, including its chart and team.
3. **Given** the dropdown lists a failed or cancelled run, **When** the player picks it,
   **Then** the panel shows its status and error message instead of a result.
4. **Given** no runs exist, **When** the page loads, **Then** the result panel says no runs
   have finished yet.

---

### Edge Cases

- **A species has no sprite file.** For example, the species exists only as a female sprite, or
  the file is missing. The name is shown with a neutral placeholder of the same size, and the
  layout does not shift.
- **A narrow screen (phone width).** The two columns stack, with setup first and results below,
  and there is no horizontal page scroll.
- **The species data is still loading** (about 35 s after the server starts). The search box
  shows that species are loading, as it does today.
- **The page is reloaded while a job is running.** The progress section reappears with the
  correct elapsed time, which is measured from when the job started, not when the page loaded.
- **Cancel is pressed just as the job finishes.** The job ends as either done or cancelled,
  never both. A done job keeps its result.
- **The server restarts while a job is running.** The job is shown as failed (current
  behaviour), with no progress section.
- **The ETA estimate jumps,** for example because a later stage adds runs. The ETA is only
  ever an estimate, and it is labelled as one.
- **A run predates this feature.** Older runs (for example, with missing per-trainer data) are
  shown with whatever data they have. A missing chart says the data is not available for that
  run.
- **An ability tie has more than two abilities, or the species' second ability cannot be
  found.** The chosen ability is shown, with "(no significant difference)" after it.

## Requirements *(mandatory)*

### Functional Requirements

**Layout**

- **FR-001**: On screens wide enough for two columns, the page MUST show run setup (legality
  options, species search, team, minimum clear rate, budget, seed, start button) on the left and
  results (progress, run picker, result) on the right.
- **FR-002**: On narrow screens, the columns MUST stack with setup first, with no horizontal
  page scroll.
- **FR-003**: The species list MUST be hidden while the search box is empty, and MUST be shown
  once at least one character is typed.
- **FR-004**: Each filled team slot MUST show the species' sprite next to its name.

**Options**

- **FR-005**: Setup MUST let the player choose the budget from the available presets (quick,
  standard, thorough), defaulting to standard, and MUST send the chosen budget with the run.
- **FR-006**: The explanation of the seed (see User Story 2, scenario 7) MUST be hidden by
  default. It MUST appear when the player hovers over the word "Seed" in its label, and also when
  that word gets keyboard focus, so keyboard users can read it.
- **FR-007**: Existing setup behaviour MUST be kept. This covers the two legality checkboxes,
  the trade-evolution availability refresh, the "show excluded species" option, the minimum
  clear rate, duplicate species, and the six-member limit.

**Progress**

- **FR-008**: The progress section MUST be shown only while a job is queued or running.
- **FR-009**: Progress MUST show the elapsed time since the job started, which updates at least
  once a second, and the current stage. A queued job MUST show its queue position. While a job
  runs, every queued job MUST be listed below it (position and species).
- **FR-010**: Progress MUST show an estimated time remaining when one can be estimated, and
  "estimating…" otherwise.
- **FR-011**: Progress MUST offer a Cancel button for the running job and for each queued job.
  Cancelling MUST ask for confirmation.
- **FR-012**: A cancelled job MUST stop running and MUST have status "cancelled". It MUST NOT
  show a result, and the next queued job MUST start.
- **FR-013**: The raw "best so far" text dump MUST NOT be shown.

**Run selection**

- **FR-014**: The result panel MUST show the most recent finished run on every page load, and
  again whenever a new run finishes. A run picked from the dropdown is not remembered.
- **FR-015**: A dropdown MUST list earlier runs newest first, each with its date and time, its
  six species, and its verdict or status. Choosing one MUST show that run.
- **FR-016**: A failed or cancelled run MUST show its status and reason instead of a result.

**Result summary**

- **FR-017**: The summary MUST show the verdict (qualified, borderline or not qualified) and
  the clear rate as a single percentage, without its interval or run count inline. The
  interval and run count MUST appear on hover and on keyboard focus over the clear rate
  (Constitution IV).
- **FR-018**: The summary MUST NOT show the Cynthia win rate, policies, or objective.
- **FR-019**: The summary MUST show the expected average final level and the level gap on one
  line: "XX.XX (level gap of Y)".
- **FR-020**: The summary MUST show the threshold, the budget, the legality options and any
  warnings, as it does today.
- **FR-021**: The summary MUST show the platsim version (for example "platsim 0.1.0") instead of
  commit hashes. The decomp and Showdown commits stay in the downloadable reports only.
- **FR-022**: The download links for the spreadsheet, CSV, JSON report and Showdown team MUST
  remain.

**Team results**

- **FR-023**: Each team member MUST be shown with its sprite, species name, start level,
  expected final level, ability, held item, how it is obtained, and its four moves.
- **FR-024**: Nature, IVs, EVs, the ability-choice code and the held-item source MUST NOT be
  shown.
- **FR-025**: When a member's ability was chosen as a statistical tie, the ability MUST read
  "<Ability1>/<Ability2> (no significant difference)". Otherwise it MUST show the single ability
  name.
- **FR-026**: Move sources MUST NOT appear as columns. Each move's source MUST be shown on hover
  and on keyboard focus.
- **FR-027**: A bar chart MUST show the clear rate per trainer (Aaron, Bertha, Flint, Lucian,
  Cynthia, in battle order), with each bar's 95% interval and the number of battles available
  on hover or focus.

**Quality**

- **FR-028**: The page MUST keep working in light and dark mode, and MUST keep the current
  accessibility: labelled controls, announced status changes, and keyboard access to every
  control including move sources and chart values.
- **FR-029**: The page MUST work offline. Sprites MUST be served by the local server and MUST
  NOT be fetched from the internet.
- **FR-030**: The downloadable reports MUST NOT change. This redesign changes only what the
  page shows.

### Key Entities

- **Run (job)**: one optimizer request from the web UI. It has an id, six species, options
  (minimum clear rate, seed, budget, legality flags), a status (queued, running, done, failed,
  cancelled), and created, started and finished times, progress (stage, runs done and planned),
  and, when done, its result files.
- **Result summary**: the per-run figures shown on screen: verdict, clear rate, average final
  level, level gap, threshold, budget, legality options, warnings, versions, and per-trainer
  clear rates with intervals and battle counts.
- **Team member result**: species, sprite, start level, expected final level, ability (with
  the tie flag and the alternative ability), held item, how it is obtained, and four moves, each
  with its source.
- **Sprite**: a small image of a species, taken from the vendored decomp's graphics and served
  locally.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a run, the player can name the weakest trainer and the run's clear rate
  within 10 seconds of looking at the result panel, without scrolling on a 1080p screen.
- **SC-002**: A finished run's team section shows at most 8 visible fields per team member,
  down from 20 columns today. The four moves count as one field, and so do the start and final
  levels. The 8 are: sprite, species, levels, ability, held item, obtained from, moves, and
  the slot number.
- **SC-003**: A player can build a team, choose a budget and start a run without the result
  panel leaving the screen on a 1080p display.
- **SC-004**: Cancelling a running job ends it within 10 seconds of confirmation, and the next
  queued job starts.
- **SC-005**: Any of the last 50 runs can be opened in two actions (open the dropdown, pick the
  run).
- **SC-006**: Every one of the 30 functional requirements above is covered by an automated check
  or a recorded browser walkthrough before the feature is called done. The browser walkthrough
  closes the "real-browser UI check" gap listed in `RUN-STATE.md`.
- **SC-007**: The reports downloaded for a given run are byte-identical before and after this
  change.

## Assumptions

- **Users**: one person runs the tool locally. There are no accounts or permissions. The server
  stays bound to 127.0.0.1.
- **Run history**: the dropdown lists the jobs the web server knows about, which is up to the
  last 50 runs it has stored. Runs made with the command line (for example
  `runs/final-defaults/`) are not listed. Listing them is out of scope for this feature.
- **Sprites**: the vendored decomp has per-species sprites
  (`pokeplatinum/res/pokemon/<species>/`): 160×80 two-frame front images, 32×64 icons, and
  palette files. These are used, so no network or new asset source is needed. Which image is
  used and how it is converted is a planning decision. The ROM is not used.
- **Ability ties**: the report already records why each ability was chosen; a tie is recorded
  as `tie_default`. The alternative ability name comes from the species' data in the decomp.
- **ETA**: the estimate comes from the progress the optimizer already reports (runs done and
  runs planned, and the stage), together with the elapsed time. It is labelled as an estimate,
  and it is not required to be accurate across stages.
- **Cancel**: a cancelled run keeps any files already written in its run folder, but it is not
  resumed and not shown as a result. Partial results are out of scope.
- **Statistical honesty (constitution, Principle IV)**: the clear rate's interval and run
  count are not shown inline, but they appear on hover or focus over the clear rate (FR-017). The
  per-trainer chart still shows intervals and battle counts, and the JSON, spreadsheet and CSV reports keep all of the provenance unchanged.
- **Stack**: the redesign keeps the current local, build-free web page and the existing server.
  Changing the stack is out of scope unless planning shows a need.
- **Out of scope**: drag-to-reorder slots, team import, saved teams, a copy button for the
  Showdown team, loss-cause and resource views, and the divergence ledger view. These came up in
  review but are not in the requested change list.

## Clarifications

### Session 2026-10-09

- Q: What replaces the commit hashes in the summary? → A: The platsim version only (option A).
- Q (added by the user): How is the seed explanation shown? → A: Only when the player hovers over
  the word "Seed". Keyboard focus also shows it, to keep FR-028.
- Q (from analysis C1, constitution IV): How is the clear rate's uncertainty shown? → A: The
  interval and run count appear on hover or focus over the clear rate (option 3). They are not
  shown inline.
- Q (from analysis U4): Which jobs does the progress section show when several are waiting? →
  A: The running job, and below it every queued job, each with its own Cancel.
- Q (from analysis A1): Which time does a run's label show? → A: The time the job was created,
  in the browser's local time.
- Q (from analysis I4): What counts as "narrow"? → A: Every check uses 360 px.
- Q (from analysis N6): Should the page remember the last run picked? → A: No. It always opens
  on the newest finished run.
